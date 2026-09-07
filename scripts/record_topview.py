"""Archive TopView numerical CSVs into a camera-only indexed recording."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thermal_lab.camera_archive import archive_topview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='+', type=Path)
    parser.add_argument('--unit', choices=['C', 'F', 'K'], required=True)
    parser.add_argument('--camera-id', required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New session directory; existing directories are refused')
    args = parser.parse_args()
    try:
        result = archive_topview(args.csv, args.output, unit=args.unit, camera_id=args.camera_id)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Camera recording failed: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
