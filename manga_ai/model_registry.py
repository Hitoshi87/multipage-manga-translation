"""Shared, dependency-free model inventory for setup and runtime checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('auto', '1107', 'preview', 'assist', 'aot', 'tessdata', 'all')


def models(profile='auto'):
    if profile not in PROFILES:
        raise ValueError('Unknown model profile: ' + profile)
    rows = json.loads((ROOT / 'models/manifest.json').read_text(encoding='utf-8'))['models']
    return [row for row in rows if profile == 'all' or profile in row['profiles']]


def status(item, root=None, verify=False):
    path = Path(root or ROOT / 'models') / item['path']
    if not path.is_file():
        return 'missing'
    if path.stat().st_size != item['size_bytes']:
        return 'invalid_size'
    if verify:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != item['sha256']:
            return 'invalid_sha256'
    return 'ok'
