"""Small preparation primitives. Never publishes, dispatches, or imports product code."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import zipfile

OLD_NAME = 'Helene-2.2.0-macos-arm64.zip'
OLD_SHA = 'e1d64b404b2aff5cce594c2cada261a233813091acfa3178d8aa665a1e047333'
OLD_BYTES = 122745701

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def check_archive(path, expected):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Expected exact lowercase SHA256')
    if digest(path) != expected:
        raise ValueError('Archive SHA256 mismatch: ' + Path(path).name)

def extract(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Refuse to reuse an earlier extraction')
    with zipfile.ZipFile(archive) as source:
        names = set()
        for info in source.infolist():
            name = info.filename.rstrip('/')
            parts = PurePosixPath(name)
            if (not name or parts.is_absolute() or '..' in parts.parts or '\\' in name
                    or ':' in name or parts.parts[0] != 'Helene' or name in names
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe or duplicate ZIP member: ' + name)
            names.add(name)
        destination.mkdir(parents=True)
        for info in source.infolist():
            target = destination / info.filename
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            target.chmod((info.external_attr >> 16) & 0o777 or 0o644)
    return destination / 'Helene'

def broken_archive(source, output):
    """A synthetic failed-next input, not a distributed release."""
    with zipfile.ZipFile(source) as reader:
        meta = json.loads(reader.read('Helene/python-app.json'))
        meta.update(version='2.2.2', synthetic_broken_fixture=True)
        changes = {'Helene/python-app.json': json.dumps(meta).encode(),
                   'Helene/app/python_app.py': b'import os;os._exit(73)\n'}
        inv = json.loads(reader.read('Helene/python-package-files.json'))
        inv['version'] = '2.2.2'
        for name, raw in changes.items():
            rel = name.removeprefix('Helene/')
            if rel in inv['files']:
                inv['files'][rel] = hashlib.sha256(raw).hexdigest()
        changes['Helene/python-package-files.json'] = json.dumps(inv).encode()
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as writer:
            for info in reader.infolist():
                # This small fixture reuses qualified runtime bytes; no rebuild/model IO.
                writer.writestr(info, changes.get(info.filename, reader.read(info)))
    return Path(output)

def validate_inputs():
    if not re.fullmatch(r'qualification-221[\w.-]*', os.environ['CANDIDATE_TAG']):
        raise ValueError('Use a dedicated qualification-221 candidate release')
    if not re.fullmatch(r'Helene-2\.2\.1[\w.-]*\.zip', os.environ['CANDIDATE_NAME']):
        raise ValueError('Expected an exact 2.2.0 candidate ZIP basename')
    if not re.fullmatch('[0-9a-f]{64}', os.environ['CANDIDATE_SHA']):
        raise ValueError('Expected exact SHA256')

if __name__ == '__main__':
    if sys.argv[1:] == ['validate-inputs']:
        validate_inputs()
    elif sys.argv[1:] == ['extract']:
        base = Path(os.environ['RUNNER_TEMP'])
        old = base / 'mac221-input/old' / OLD_NAME
        candidate = base / 'mac221-input/new' / os.environ['CANDIDATE_NAME']
        check_archive(old, OLD_SHA)
        if old.stat().st_size != OLD_BYTES:raise ValueError('Old archive size differs')
        check_archive(candidate, os.environ['CANDIDATE_SHA'])
        with zipfile.ZipFile(candidate) as z:
            meta = json.loads(z.read('Helene/python-app.json'))
            if (meta['version'], meta['target']) != ('2.2.1', 'macos-arm64'):
                raise ValueError('Not the expected Mac 2.2.0 package')
        extract(old, base / 'mac221-fixture/program')
    else:
        raise SystemExit('Use validate-inputs or extract')
