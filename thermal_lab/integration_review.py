"""Read-only camera views for local integration clients. No caller-supplied paths."""
import base64
import io
import math
import time

from PIL import Image
from .imaging import thermal_image, optical_image, optical_plane_image, aligned_optical
from .playback import Recording
from .workspace import measurement_values


def camera_view(service, body):
    from .integration import identifier
    camera_id = body.get('camera_id')
    mode = body.get('mode', 'Thermal')
    if not isinstance(camera_id, str) or mode not in ('Thermal', 'Optical', 'Blend'):
        raise ValueError('Camera identity and valid view mode required')
    run_id = body.get('run_id')
    if run_id is not None:
        identifier(run_id)
        elapsed = body.get('elapsed_s', 0)
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed):
            raise ValueError('Finite run time required')
        folder = service.recordings / run_id
        recording = None
        for index in range(3):
            path = folder / f'camera{index}'
            if not path.exists():
                continue
            if not path.resolve().is_relative_to(service.recordings):
                raise ValueError('Archive is outside recording root')
            candidate = Recording(path)
            if candidate.manifest['camera_id'] == camera_id:
                recording = candidate
                break
        if recording is None:
            raise ValueError('Linked camera archive is unavailable in this service recording root')
        first = recording.read(0)
        if recording.manifest.get('run_id') != run_id or first.get('run_id') != run_id:
            raise ValueError('Recording run identity mismatch')
        offset = first['run_elapsed_s'] - first['elapsed_s']
        index = recording.index_at(elapsed - offset)
        frame = recording.read(index)
        if frame.get('run_id') != run_id:
            raise ValueError('Frame run identity mismatch')
        settings = frame['workspace']
        if mode != 'Thermal' and recording.optical is None:
            raise ValueError('Recording does not contain optical video')
        optical = optical_plane_image(recording.optical.read(index, frame)) if mode != 'Thermal' else None
        frame = dict(frame, elapsed_s=frame['run_elapsed_s'], recording_elapsed_s=frame['elapsed_s'])
        extra = dict(frame_index=index, requested_elapsed_s=elapsed,
                     time_difference_s=frame['elapsed_s']-elapsed, fresh=None, archive_status='COMPLETE')
    else:
        # Hold the acquisition lock only to take immutable references, never while rendering.
        with service.lock:
            service.require_owner(body)
            camera = next((c for c in service.cameras if c['camera_id'] == camera_id), None)
            state = next((c for c in service.state()['cameras'] if c['camera_id'] == camera_id), None)
            if camera is None or not state['fresh']:
                raise ValueError('Camera frame is stale or unavailable')
            sample = camera['sample']; settings = camera['settings']
        frame = dict(sample['frame'], measurements=measurement_values(sample['frame'], settings), workspace=settings)
        optical = optical_image(sample['raw']) if mode != 'Thermal' else None
        extra = dict(fresh=True, age_s=state['age_s'], host_monotonic=sample['received_at'])
    picture, limits = thermal_image(frame['temperatures'], 'Iron')
    if optical is not None:
        optical = aligned_optical(optical, settings['alignment'])
        picture = optical if mode == 'Optical' else Image.blend(optical, picture, .55)
    output = io.BytesIO(); picture.save(output, format='PNG', compress_level=1)
    if run_id is None:
        extra['age_s'] = time.monotonic() - sample['received_at']
        if extra['age_s'] > 1:
            raise ValueError('Camera frame became stale during rendering')
    return dict(schema=1, frame=frame, image='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode(),
                mode=mode, limits=limits, temperature_basis='apparent_raw_kelvin_64', **extra)
