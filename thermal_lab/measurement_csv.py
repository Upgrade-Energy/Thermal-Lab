"""Excel-compatible measurement rows written alongside accepted recording frames."""
import csv
import json
from pathlib import Path


FIELDS = ('frame_index', 'elapsed_s', 'camera_name', 'camera_id', 'measurement_name',
          'measurement_id', 'kind', 'value_c', 'min_c', 'mean_c', 'max_c',
          'x', 'y', 'x2', 'y2', 'workspace_revision', 'source', 'run_id', 'run_elapsed_s',
          'shape', 'vertices', 'tracking', 'region_id', 'pixel_x', 'pixel_y')


def safe_text(value):
    value = str(value)
    return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


class MeasurementCSV:
    """One row per named point/region per frame; publish only a completed session.

    Written by the thermal recorder thread, not the preview or camera read loop.
    Names and geometry are those actually used for that frame's measurements.
    """
    def __init__(self, directory):
        self.path = Path(directory) / 'measurements.partial.csv'
        self.frames = 0
        self.rows = 0
        self.stream = self.path.open('x', newline='', encoding='utf-8-sig')
        try:
            self.writer = csv.DictWriter(self.stream, fieldnames=FIELDS)
            self.writer.writeheader()
            self.stream.flush()
        except Exception:
            self.stream.close()
            raise

    def write(self, frame, index):
        settings = frame['workspace']
        for group in ('points', 'areas'):
            for item in settings[group]:
                values = frame['measurements'][item['id']]
                row = dict(frame_index=index, elapsed_s=frame['elapsed_s'],
                           camera_name=safe_text(settings.get('camera_name', '')),
                           camera_id=safe_text(frame['camera_id']),
                           measurement_name=safe_text(item['name']), measurement_id=safe_text(item['id']),
                           kind=values['kind'], workspace_revision=frame.get('workspace_revision', ''),
                           source=safe_text(frame['source']), run_id=safe_text(frame.get('run_id', '')),
                           run_elapsed_s=frame.get('run_elapsed_s', ''))
                row.update({key: item[key] for key in ('x', 'y', 'x2', 'y2') if key in item})
                if item.get('tracking'):
                    row.update({key:values[key] for key in ('x','y','pixel_x','pixel_y','tracking')})
                    row['region_id']=safe_text(item.get('region_id',''))
                row['shape']=item.get('shape','point' if group=='points' else 'rectangle')
                row['vertices']=json.dumps(item['vertices'],separators=(',',':')) if 'vertices' in item else ''
                row.update({key + '_c': values[key] for key in ('value', 'min', 'mean', 'max') if key in values})
                self.writer.writerow(row)
                self.rows += 1
        self.stream.flush()
        self.frames += 1

    def close(self):
        self.stream.close()

    def publish(self):
        if not self.stream.closed:
            raise RuntimeError('Measurement CSV must be closed before publication')
        destination = self.path.with_name('measurements.csv')
        if destination.exists():
            raise FileExistsError(destination)
        self.path.rename(destination)
        self.path = destination
