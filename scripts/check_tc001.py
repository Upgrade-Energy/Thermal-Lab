"""Run with Python 3.12+; writes camera-only evidence and returns USB check status."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thermal_lab.camera_diagnostics import diagnose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = diagnose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve previous evidence instead of silently overwriting it.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'USB_ACCESS_VERIFIED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
