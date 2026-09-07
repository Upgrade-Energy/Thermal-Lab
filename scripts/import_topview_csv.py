"""Import a vendor numerical temperature grid as a Power Lab frame JSON."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thermal_lab.topview_import import read_topview_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--unit', required=True, choices=['C', 'F', 'K'])
    parser.add_argument('--camera-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    frame = read_topview_csv(args.input, unit=args.unit, camera_id=args.camera_id)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(frame, stream, allow_nan=False)
        stream.write('\n')
    print(f"Imported {frame['width']}x{frame['height']} temperatures; "
          f"range {min(frame['temperatures']):.2f} to {max(frame['temperatures']):.2f} C")
    print('File import only; no capture timestamp or calibration qualification.')


if __name__ == '__main__':
    main()
