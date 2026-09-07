import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import test_analysis as fixtures
from thermal_lab.media_export import export_png,export_mp4,validate_options,render_frame,ExportCancelled,video_indices


class MediaExportTests(unittest.TestCase):
    def recording(self,root):return fixtures.AnalysisTests().fixture(root/'source')

    def test_png_exact_render_and_embedded_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.recording(root);options=dict(rotation=90,labels=False,settings=fixtures.AnalysisTests().settings())
            meta=export_png(r,1,root/'frame.png',options)
            with Image.open(root/'frame.png') as saved:
                self.assertEqual(saved.size,(768,1024))
                self.assertEqual(saved.tobytes(),render_frame(r,1,validate_options(r,options))[0].tobytes())
                self.assertEqual(json.loads(saved.info['ThermalLab'])['source_frame'],1)
            self.assertEqual(meta['measurements']['p']['value'],22)
            self.assertEqual(meta['measurement_basis'],'offline_fixed_geometry_all_frames')
            with self.assertRaises(FileExistsError):export_png(r,0,root/'frame.png',{})
            with self.assertRaisesRegex(ValueError,'outside'):export_png(r,0,r.path/'image.png',{})
            with self.assertRaisesRegex(ValueError,'optical'):export_png(r,0,root/'optical.png',dict(mode='Optical'))

    def test_mp4_can_decode_all_frames_and_has_source_mapping(self):
        import imageio_ffmpeg
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.recording(root);meta=export_mp4(r,root/'video.mp4',dict(labels=True))
            reader=imageio_ffmpeg.read_frames(str(root/'video.mp4'),pix_fmt='rgb24')
            header=next(reader);frames=list(reader)
            self.assertEqual(header['size'],(1024,768));self.assertEqual(len(frames),meta['frame_count'])
            self.assertEqual(meta['source_frame_indices'],[0,1,2])
            self.assertEqual(json.loads((root/'video.mp4.json').read_text())['fps'],25)
            self.assertNotEqual(frames[0],frames[-1])

    def test_cancel_encoder_failure_and_publish_collision_leave_no_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.recording(root);cancel=[False]
            with self.assertRaises(ExportCancelled):
                export_mp4(r,root/'cancel.mp4',{},lambda:cancel[0],lambda *_:cancel.__setitem__(0,True))
            self.assertEqual(list(root.iterdir()),[r.path])
            with patch('imageio_ffmpeg.get_ffmpeg_exe',return_value=str(root/'missing.exe')):
                with self.assertRaises(OSError):export_mp4(r,root/'fail.mp4',{})
            self.assertEqual(list(root.iterdir()),[r.path])
            def collide(n,total):
                if n==total:(root/'existing.mp4').write_bytes(b'user data')
            with self.assertRaises(FileExistsError):export_mp4(r,root/'existing.mp4',{},progress=collide)
            self.assertEqual((root/'existing.mp4').read_bytes(),b'user data')
            self.assertFalse((root/'existing.mp4.json').exists())

    def test_host_timing_resampling_includes_last_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            r=self.recording(Path(temp));r.times=[0,.01,.11]
            self.assertEqual(video_indices(r),[0,1,1,2])

