import gzip, json, struct, sys, math, csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thermal_lab.thermal import FRAME_INDEX,measurements
from thermal_lab.tc001_max import decode_frame,PLANE_BYTES
from thermal_lab.workspace import measurement_values
from thermal_lab.optical_recording import OpticalRecording,OPTICAL_OFFSET
from thermal_lab.measurement_csv import safe_text
if not __debug__: raise SystemExit("Verification requires assertions enabled; do not use python -O")
root=Path(sys.argv[1]);entries=list(FRAME_INDEX.iter_unpack((root/'thermal.idx').read_bytes()));times=[];first=None;last=None
manifest=json.loads((root/'camera-session.json').read_text())
optical=OpticalRecording(root,entries,manifest['optical_codec']) if manifest.get('optical_video_recorded') else None
optical_hashes=set()
csv_stream=None;csv_rows=0
if manifest.get('measurement_csv'):
 assert manifest['measurement_csv_status']=='COMPLETE' and manifest['measurement_csv']=='measurements.csv'
 csv_stream=(root/'measurements.csv').open(encoding='utf-8-sig',newline='')
 csv_reader=csv.DictReader(csv_stream)
with (root/'thermal.jsonl.gz').open('rb') as f:
 for index,(elapsed,offset,size) in enumerate(entries):
  f.seek(offset);frame=json.loads(gzip.decompress(f.read(size)))[0]
  assert frame['elapsed_s']==elapsed
  assert len(frame['temperatures'])==49152 and all(math.isfinite(v) for v in frame['temperatures'])
  assert frame['source']=='HARDWARE' and frame['capture_timestamp'] is None
  assert frame['camera_id']==manifest['camera_id']
  if optical:
   optical.read(index,frame)
   optical_hashes.add(frame['optical_sha256'])
  if 'workspace' in frame:
   assert frame['workspace']['camera_id']==manifest['camera_id']
   assert measurement_values(frame,frame['workspace'])==frame['measurements']
   if csv_stream:
    for kind in ('points','areas'):
     for definition in frame['workspace'][kind]:
      row=next(csv_reader);csv_rows+=1
      assert int(row['frame_index'])==index and float(row['elapsed_s'])==elapsed
      assert row['camera_id']==safe_text(frame['camera_id']) and row['source']==safe_text(frame['source'])
      assert row['camera_name']==safe_text(frame['workspace'].get('camera_name',''))
      assert row['measurement_id']==safe_text(definition['id']) and row['measurement_name']==safe_text(definition['name'])
      value=frame['measurements'][definition['id']]
      assert row['kind']==value['kind']
      for key in ('value','min','mean','max'):
       assert float(row[key+'_c'])==value[key] if key in value else row[key+'_c']==''
      for key in ('x','y','x2','y2'):
       geometry=value if definition.get('tracking') else definition
       assert float(row[key])==geometry[key] if key in geometry else row[key]==''
      if definition.get('tracking'):
       assert row['tracking']==definition['tracking']
       assert row['region_id']==safe_text(definition.get('region_id',''))
       assert int(row['pixel_x'])==value['pixel_x'] and int(row['pixel_y'])==value['pixel_y']
      if 'shape' in row:
       assert row['shape']==definition.get('shape','point' if kind=='points' else 'rectangle')
       assert json.loads(row['vertices'])==definition['vertices'] if 'vertices' in definition else row['vertices']==''
  else:
   assert measurements(frame,dict(points=[dict(name='Center',x=.5,y=.5)],areas=[]))['Center']==frame['measurements']['Center']
  if first is None:first=frame
  last=frame;times.append(elapsed)
assert all(b>a for a,b in zip(times,times[1:]))
for label,frame in [('first',first),('last',last)]:
 raw=(root/(label+'.frame')).read_bytes();decoded=decode_frame(raw,camera_id=frame['camera_id'],elapsed_s=frame['elapsed_s'],sequence=frame['arrival_sequence'])
 assert frame['temperatures']==decoded['temperatures']
 assert frame['raw_sha256']==decoded['raw_sha256']
 codes=struct.unpack('<49152H',raw[PLANE_BYTES:PLANE_BYTES*2])
 assert tuple(round((v+273.15)*64) for v in frame['temperatures'])==codes
 if optical:assert optical.read(0 if label=='first' else len(entries)-1,frame)==raw[OPTICAL_OFFSET:]
assert manifest['status']=='COMPLETE' and manifest['frames_written']==len(entries)
if 'duration_s' in manifest:assert manifest['duration_s']==times[-1]
if csv_stream:
 assert next(csv_reader,None) is None
 csv_stream.close()
 assert manifest['measurement_csv_frames']==len(entries) and manifest['measurement_csv_rows']==csv_rows
result=dict(status='PASS',recording=root.name,frames=len(entries),temperature_values_checked=len(entries)*49152,strictly_increasing_arrivals=True,first_last_raw_roundtrip_exact=True,manifest=manifest)
if csv_stream:result.update(measurement_csv_rows_checked=csv_rows,measurement_csv_exact=True)
if optical:
 assert manifest['optical_frames_written']==len(entries)
 result.update(optical_pairs_checked=len(entries),unique_optical_frames=len(optical_hashes),optical_first_last_raw_exact=True)
Path('docs/camera-evidence',root.name+'-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='manifest'},indent=2))
