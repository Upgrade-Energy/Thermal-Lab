"""Record real TC001 Max numerical frames without starting a bench controller."""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thermal_lab.tc001_max import TC001Max, DLL_SHA256, PLANE_BYTES
from thermal_lab.thermal import Recorder, measurements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topview-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--camera-id', help='Windows PnP instance ID; required with multiple cameras')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error('--seconds must be between 1 and 600')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='RECORDING', source='HARDWARE', adapter='experimental_tc001_max',
                    dll_sha256=DLL_SHA256, timestamp_basis='host_monotonic_arrival',
                    device_dropped_frames=None, started_utc=datetime.now(timezone.utc).isoformat(),
                    temperature_basis='apparent_raw_kelvin_64',
                    host_environment_correction_applied=False, frames_written=0)
    def save():
        temporary = args.output / 'session.tmp'
        temporary.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        temporary.replace(args.output / 'camera-session.json')
    save()
    recorder = Recorder([], 0, compression_level=1)
    camera = TC001Max(args.topview_directory, camera_id=args.camera_id)
    count = 0
    times = []
    distinct = set()
    previous_hash = None
    last_change = time.monotonic()
    last_data = None
    try:
        recorder.start(args.output / 'thermal.jsonl.gz')
        with camera:
            manifest['camera_id'] = camera.camera_id
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                frame, data = camera.read()
                digest = hashlib.sha256(data[PLANE_BYTES:2 * PLANE_BYTES]).hexdigest()
                if digest != previous_hash:
                    last_change = time.monotonic()
                elif time.monotonic() - last_change > 2:
                    raise OSError('Thermal plane unchanged for over two seconds')
                previous_hash = digest
                distinct.add(digest)
                frame['measurements'] = measurements(frame, dict(
                    points=[dict(name='Center', x=.5, y=.5)],
                    areas=[dict(name='Full frame', x=0, y=0, x2=1, y2=1)]))
                recorder.ingest([frame])
                if count == 0:
                    (args.output / 'first.frame').write_bytes(data)
                last_data = data
                times.append(frame['elapsed_s'])
                count += 1
        recorder.close()
        if recorder.error:
            raise OSError(recorder.error)
        if count < 2 or recorder.count != count or len(distinct) < 2:
            raise OSError('Insufficient distinct recorded camera frames')
        (args.output / 'last.frame').write_bytes(last_data)
        manifest.update(status='COMPLETE', frames_written=recorder.count,
                        accepted_frames=count, received_buffers=camera.received,
                        rejected_buffers=camera.rejected, distinct_thermal_planes=len(distinct),
                        first_arrival_s=times[0], last_arrival_s=times[-1],
                        observed_fps=(count-1)/(times[-1]-times[0]),
                        last_measurements=frame['measurements'])
    except BaseException as exc:
        recorder.close()
        manifest.update(status='FAILED', error=str(exc), frames_written=recorder.count,
                        accepted_frames=count, received_buffers=camera.received,
                        rejected_buffers=camera.rejected)
        raise
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
