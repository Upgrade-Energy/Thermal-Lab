"""Import TopView numerical CSV exports without inferring temperature from RGB.

Tested with TopView 1.30.003 / TC001 Max. Some exports encode the unit as
`Unit(?)`, so callers must explicitly supply the unit verified in TopView.
File imports have no device capture timestamp and are not live USB frames.
"""
import csv
import hashlib
import io
import math
from pathlib import Path

from .validation import ValidationError
from .thermal import validate_frame


def parse_topview_csv(data, *, unit, camera_id):
    if unit not in ('C', 'F', 'K'):
        raise ValidationError('Explicit TopView temperature unit C, F or K is required')
    if not isinstance(camera_id, str) or not camera_id.strip():
        raise ValidationError('Camera identity is required')
    if len(data) > 32 * 1024 * 1024:
        raise ValidationError('TopView CSV exceeds 32 MiB')
    try:
        rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise ValidationError('Invalid TopView CSV') from exc
    if len(rows) < 4 or len(rows[0]) != 3 or rows[0][0] != 'File':
        raise ValidationError('Missing TopView file header')
    if rows[1] != ['Area Name', 'Max.', 'Mean', 'Min.']:
        raise ValidationError('Unsupported TopView measurement header')
    declared = rows[0][2]
    known_units = {'Unit(℃)': 'C', 'Unit(°C)': 'C', 'Unit(℉)': 'F',
                   'Unit(°F)': 'F', 'Unit(K)': 'K'}
    if declared not in known_units and declared != 'Unit(?)':
        raise ValidationError('Unsupported TopView unit header')
    if declared in known_units and known_units[declared] != unit:
        raise ValidationError('Selected unit conflicts with TopView header')

    def temperature(value):
        try:
            result = float(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError('Invalid numeric temperature') from exc
        if unit == 'F':
            result = (result - 32) * 5 / 9
        elif unit == 'K':
            result -= 273.15
        if not math.isfinite(result) or not -100 <= result <= 1000:
            raise ValidationError('Invalid or out-of-range temperature')
        return result

    index = 2
    regions = {}
    while index < len(rows) and rows[index]:
        row = rows[index]
        if len(row) != 4 or not row[0] or row[0] in regions:
            raise ValidationError('Invalid or duplicate TopView measurement')
        high, mean, low = map(temperature, row[1:])
        if not low <= mean <= high:
            raise ValidationError('Inconsistent TopView measurement limits')
        regions[row[0]] = dict(min=low, mean=mean, max=high)
        index += 1
    index += 1
    if index >= len(rows):
        raise ValidationError('Missing TopView pixel grid')
    header = rows[index]
    # TopView 1.30 appends an empty CSV field to each pixel row.
    if header and header[-1] == '':
        header = header[:-1]
    width = len(header) - 1
    if not 1 <= width <= 1024 or header != [''] + [str(x) for x in range(width)]:
        raise ValidationError('Invalid TopView column coordinates')
    pixels = []
    grid = rows[index + 1:]
    if not 1 <= len(grid) <= 1024:
        raise ValidationError('Invalid TopView grid height')
    for y, row in enumerate(grid):
        if row and row[-1] == '':
            row = row[:-1]
        if len(row) != width + 1 or row[0] != str(y):
            raise ValidationError('Missing, reordered or ragged TopView pixel row')
        pixels.extend(temperature(v) for v in row[1:])
    return validate_frame(dict(
        width=width, height=len(grid), temperatures=pixels, camera_id=camera_id,
        source='HARDWARE_FILE_IMPORT', valid=True, unit='C',
        timestamp_basis='unavailable_in_vendor_csv', capture_timestamp=None,
        vendor='TOPDON', vendor_file=rows[0][1], vendor_unit_header=declared,
        input_unit=unit, unit_basis='explicit_operator_selection',
        vendor_measurements=regions, source_sha256=hashlib.sha256(data).hexdigest(),
    ))


def read_topview_csv(path, *, unit, camera_id):
    with Path(path).open('rb') as stream:
        data = stream.read(32 * 1024 * 1024 + 1)
    return parse_topview_csv(data, unit=unit, camera_id=camera_id)
