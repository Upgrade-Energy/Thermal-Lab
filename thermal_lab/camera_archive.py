"""Camera-only archival of vendor numerical exports, without a bench controller."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .thermal import Recorder
from .topview_import import read_topview_csv


def archive_topview(paths, destination, *, unit, camera_id):
    """Create an indexed recording of imported frames, preserving missing times.

    Index time is host import receipt, NOT the original exposure time. File
    order is caller supplied. This function never opens USB or power equipment.
    A failed recording remains on disk with status FAILED for investigation.
    """
    paths = list(paths)
    if not paths:
        raise ValueError('At least one TopView CSV is required')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = dict(format='powerlab-camera-import-v1', status='RECORDING',
                    camera_id=camera_id, unit='C', input_unit=unit,
                    source='HARDWARE_FILE_IMPORT',
                    recording_timestamp_basis='host_import_monotonic',
                    capture_timestamp_available=False, frames_written=0,
                    started_utc=datetime.now(timezone.utc).isoformat())
    manifest_path = destination / 'camera-session.json'

    def save():
        temporary = manifest_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
        temporary.replace(manifest_path)

    recorder = Recorder([], 0)
    origin = time.monotonic()
    save()
    try:
        recorder.start(destination / 'thermal.jsonl.gz')
        for sequence, path in enumerate(paths):
            frame = read_topview_csv(path, unit=unit, camera_id=camera_id)
            frame.update(elapsed_s=time.monotonic() - origin,
                         recording_timestamp_basis='host_import_monotonic',
                         imported_utc=datetime.now(timezone.utc).isoformat(),
                         import_sequence=sequence)
            recorder.ingest([frame])
        recorder.close()
        if recorder.error:
            raise OSError(recorder.error)
        manifest['status'] = 'COMPLETE'
    except Exception as exc:
        recorder.close()
        manifest.update(status='FAILED', error=str(exc))
        raise
    finally:
        manifest['frames_written'] = recorder.count
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return manifest
