"""Rendered presentation exports; source numerical archives remain read-only."""
import copy
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
from .analysis import recording_fingerprint
from .imaging import thermal_image,optical_plane_image,aligned_optical,rotate_image,sensor_to_view
from .workspace import validate_settings,measurement_values
from .regions import vertices
from .tracking import positioned


class ExportCancelled(Exception):pass


@lru_cache(maxsize=1)
def label_font():
    for name in (str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf'),'DejaVuSans.ttf'):
        try:return ImageFont.truetype(name,18)
        except OSError:pass
    return ImageFont.load_default(size=18)


def validate_options(recording,options):
    options=copy.deepcopy(options)
    result=dict(mode=options.get('mode','Thermal'),palette=options.get('palette','Iron'),
                rotation=options.get('rotation',180),labels=options.get('labels',True),settings=options.get('settings'))
    if result['mode'] not in ('Thermal','Optical','Blend'):raise ValueError('Invalid export view')
    if result['mode']!='Thermal' and recording.optical is None:raise ValueError('Recording has no optical video')
    if result['palette'] not in ('Iron','Rainbow','White hot','Black hot'):raise ValueError('Invalid palette')
    if result['rotation'] not in (0,90,180,270):raise ValueError('Invalid rotation')
    if not isinstance(result['labels'],bool):raise ValueError('Labels must be enabled or disabled')
    if result['settings'] is not None:
        result['settings']=validate_settings(result['settings'])
        if result['settings']['camera_id']!=recording.manifest['camera_id']:raise ValueError('Analysis belongs to another camera')
    return result


def render_frame(recording,index,options):
    frame=recording.read(index);picture,limits=thermal_image(frame['temperatures'],options['palette'])
    if options['mode']!='Thermal':
        optical=optical_plane_image(recording.optical.read(index,frame))
        optical=aligned_optical(optical,frame.get('workspace',{}).get('alignment',{}))
        picture=optical if options['mode']=='Optical' else Image.blend(optical,picture,.55)
    rotation=options['rotation'];picture=rotate_image(picture,rotation)
    settings=options['settings'] if options['settings'] is not None else frame.get('workspace',{})
    values=measurement_values(frame,settings) if options['settings'] is not None else frame.get('measurements',{})
    if options['labels']:
        draw=ImageDraw.Draw(picture);font=label_font()
        def label(x,y,text,color='white',header=False):
            # Keep labels within the image, including geometry near its edges.
            while draw.textlength(text,font=font)>picture.width-16 and len(text)>4:text=text[:-4]+'…'
            box=draw.textbbox((0,0),text,font=font);width=box[2];height=box[3]-box[1]
            x=max(4,min(x,picture.width-width-8));y=max(4 if header else 38,min(y,picture.height-height-10))
            draw.rectangle((x-3,y-3,x+width+3,y+height+5),fill='#111923')
            draw.text((x,y-box[1]),text,font=font,fill=color)
        for kind in ('points','areas'):
            for item in settings.get(kind,[]):
                item=positioned(item,values)
                if item is None:continue
                x,y=sensor_to_view(item['x']*256,item['y']*192,rotation);x*=4;y*=4
                if item.get('shape')=='polygon':
                    polygon=[tuple(v*4 for v in sensor_to_view(px*256,py*192,rotation)) for px,py in vertices(item)]
                    draw.line(polygon+[polygon[0]],fill='#67ffe0',width=2)
                elif 'x2' in item:
                    x2,y2=sensor_to_view(item['x2']*256,item['y2']*192,rotation);x2*=4;y2*=4
                    draw.rectangle((min(x,x2),min(y,y2),max(x,x2),max(y,y2)),outline='#67ffe0',width=2)
                else:draw.ellipse((x-5,y-5,x+5,y+5),outline='#67ffe0',width=2)
                value=values.get(item['id'],{})
                text=f"{value['value']:.3f} °C" if 'value' in value else ' / '.join(f'{value[k]:.2f}' for k in ('min','mean','max') if k in value)+' °C (min/mean/max)'
                color='#ffb389' if item.get('tracking')=='hottest' else '#81d7ff' if item.get('tracking')=='coldest' else '#67ffe0'
                label(x+9,y-24,item['name']+' · '+text,color)
        basis='ANALYSIS' if options['settings'] is not None else 'RECORDED'
        label(8,8,f"{basis} · {options['mode']} · frame {index+1} · {frame['elapsed_s']:.3f} s · {limits[0]:.1f} to {limits[1]:.1f} °C apparent",header=True)
    return picture,dict(source_frame=index,source_elapsed_s=frame['elapsed_s'],measurements=values)


def destination(recording,path,suffix):
    path=Path(path).resolve()
    if path.suffix.lower()!=suffix:raise ValueError('Output must end in '+suffix)
    if path.is_relative_to(recording.path.resolve()):raise ValueError('Export outside the source recording folder')
    if path.exists() or path.with_suffix(path.suffix+'.json').exists():raise FileExistsError('Choose a new export filename')
    return path


def metadata(recording,options):
    return dict(schema='thermal-lab-media-v1',camera_id=recording.manifest['camera_id'],source=recording.manifest['source'],
                recording_sha256=recording_fingerprint(recording),options=options,
                measurement_basis='offline_fixed_geometry_all_frames' if options['settings'] is not None else 'original_recorded',
                temperature_basis='apparent_C',radiometric=False,exposure_sync_qualified=False)


def publish(temp,path):
    # Windows rename refuses an existing target and also works on FAT/exFAT.
    # POSIX rename would overwrite, so use an exclusive hard link there.
    if os.name=='nt':os.rename(temp,path)
    else:os.link(temp,path)


def export_png(recording,index,path,options):
    options=validate_options(recording,options);path=destination(recording,path,'.png')
    picture,frame=render_frame(recording,index,options);meta=metadata(recording,options);meta.update(frame)
    info=PngImagePlugin.PngInfo();info.add_text('ThermalLab',json.dumps(meta,allow_nan=False))
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.png',delete=False) as stream:temp=Path(stream.name)
    try:
        picture.save(temp,format='PNG',pnginfo=info);publish(temp,path)
    finally:temp.unlink(missing_ok=True)
    return meta


def video_indices(recording,fps=25):
    count=math.ceil((recording.times[-1]-recording.times[0])*fps)+1
    if count>250_000:raise ValueError('Video export exceeds 250,000 output frames; split the recording first')
    return [recording.index_at(recording.times[0]+i/fps) for i in range(count)]


def export_mp4(recording,path,options,cancelled=lambda:False,progress=lambda *_:None):
    from imageio_ffmpeg import get_ffmpeg_exe
    options=validate_options(recording,options);path=destination(recording,path,'.mp4');indices=video_indices(recording)
    if cancelled():raise ExportCancelled('Export cancelled')
    meta=metadata(recording,options)
    meta.update(fps=25,frame_count=len(indices),duration_s=len(indices)/25,
                timing='constant_25fps_hold_previous_host_arrival; final frame included',source_frame_indices=indices,
                source_elapsed_s=[recording.times[i] for i in indices])
    width,height=(768,1024) if options['rotation'] in (90,270) else (1024,768)
    meta.update(width=width,height=height)
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.mp4',delete=False) as stream:temp=Path(stream.name)
    side=path.with_suffix('.mp4.json');temp_side=temp.with_suffix('.json');published_side=False;created_side=False
    process=None;done=threading.Event();last_progress=[time.monotonic()];watcher=None
    try:
        with tempfile.TemporaryFile() as errors:
            command=[get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                     '-r','25','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)]
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors,bufsize=0,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            def watch():
                while not done.wait(.1):
                    if cancelled() or time.monotonic()-last_progress[0]>45:
                        if process.poll() is None:
                            try:process.kill()
                            except OSError:pass
                        return
            watcher=threading.Thread(target=watch,daemon=True);watcher.start()
            previous=None;pixels=None
            for n,index in enumerate(indices):
                if cancelled():raise ExportCancelled('Export cancelled')
                if index!=previous:pixels=render_frame(recording,index,options)[0].tobytes();previous=index
                view=memoryview(pixels)
                while view:
                    written=process.stdin.write(view)
                    if not written:raise OSError('Encoder stopped accepting frames')
                    view=view[written:]
                last_progress[0]=time.monotonic();progress(n+1,len(indices))
            process.stdin.close();code=process.wait(timeout=45)
            if cancelled():raise ExportCancelled('Export cancelled')
            if code:
                errors.seek(0);raise OSError('MP4 encoder failed: '+errors.read(8192).decode(errors='replace'))
        if temp.stat().st_size==0:raise OSError('Encoder produced an empty file')
        with temp_side.open('x',encoding='utf-8') as stream:
            created_side=True;json.dump(meta,stream,indent=2,allow_nan=False)
        if cancelled():raise ExportCancelled('Export cancelled')
        publish(temp_side,side);published_side=True
        publish(temp,path)
        return meta
    except Exception:
        if published_side:side.unlink(missing_ok=True)
        if cancelled():raise ExportCancelled('Export cancelled') from None
        raise
    finally:
        done.set()
        if process:
            if process.poll() is None:process.kill()
            process.wait(timeout=5)
            if process.stdin:process.stdin.close()
        if watcher:watcher.join(timeout=1)
        temp.unlink(missing_ok=True)
        if created_side:temp_side.unlink(missing_ok=True)
