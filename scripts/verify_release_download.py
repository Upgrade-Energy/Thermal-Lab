"""Verify the production updater against the release just published by CI."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab_update import check, config, download


def main():
    settings = config()
    # Represent an older installation without changing installed metadata.
    older = dict(settings, version='0.0.0')
    release = check(older, preview=True)
    assert release and release['version'] == settings['version'], 'Published update is missing'
    received = download(older, release)
    tested = ROOT / 'dist' / release['name']
    assert hashlib.sha256(received.read_bytes()).digest() == hashlib.sha256(tested.read_bytes()).digest(), 'Release differs from the Windows-tested installer'
    assert check(settings, preview=True) is None, 'Current version should be up to date'
    evidence = ROOT / 'release-evidence'
    evidence.mkdir(exist_ok=True)
    (evidence / 'verification.json').write_text(json.dumps(dict(
        repository=settings['repository'], version=release['version'],
        asset=release['name'], sha256=release['sha256'], size=release['size'],
        github_check=True, authenticated_download=True, checksum_verified=True,
        matches_windows_tested_installer=True, current_version_up_to_date=True,
    ), indent=2))
    print('PASS: GitHub update discovery, authenticated download, checksum and current-version check')


if __name__ == '__main__':
    main()
