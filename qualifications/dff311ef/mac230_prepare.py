"""Pinned public inputs and safe, mode-preserving extraction; no publication.

This harness is not a product update implementation. It only prepares isolated
synthetic native consumers and records the exact package identities they used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import urllib.parse
import urllib.request
import zipfile

FORMAT = 'helene-mac230-acceptance-input.v1'
TARGET = 'macos-arm64'
SHA = re.compile(r'[0-9a-f]{64}')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2), encoding='utf8')


def https_url(value):
    row = urllib.parse.urlsplit(value)
    if (row.scheme != 'https' or not row.hostname or row.username or row.password
            or row.fragment):
        raise ValueError('Only explicit public HTTPS input URLs are accepted')
    return value


def asset(value):
    if not isinstance(value, dict):
        raise ValueError('Asset must be an exact object')
    if not SHA.fullmatch(str(value.get('sha256', ''))):
        raise ValueError('Asset needs an exact lowercase SHA256')
    if not isinstance(value.get('bytes'), int) or not 0 < value['bytes'] <= 8_000_000_000:
        raise ValueError('Asset needs exact nonzero byte length')
    name = value.get('name', '')
    if Path(name).name != name or not name or '\\' in name or '/' in name or ':' in name:
        raise ValueError('Asset name must be a plain basename')
    https_url(value['url'])
    return value


def manifest(path):
    value = json.loads(Path(path).read_text(encoding='utf8'))
    if value.get('format') != FORMAT or value.get('target') != TARGET:
        raise ValueError('Wrong Mac acceptance manifest format/target')
    if not re.fullmatch(r'2\.3\.0(?:-rc\.[1-9][0-9]*)?', value.get('version', '')):
        raise ValueError('Expected parent-frozen 2.3.0 RC/release version')
    if not SHA.fullmatch(str(value.get('source_inputs_sha256', ''))):
        raise ValueError('Frozen source-inputs.json SHA256 missing')
    for key in ('base', 'candidate'):
        asset(value[key])
    if 'broken' in value:
        asset(value['broken'])
        if not isinstance(value.get('broken_version'),str) or not value['broken_version']:
            raise ValueError('Explicit synthetic broken-next version required')
    if not isinstance(value.get('base_version'), str) or not value['base_version']:
        raise ValueError('Explicit base version required')
    https_url(value['feed_url'])
    if value.get('verification_bundle_sha256') is not None and not SHA.fullmatch(value['verification_bundle_sha256']):
        raise ValueError('Invalid verification bundle identity')
    return value


def check_archive(path, expected, size=None):
    path = Path(path)
    if not SHA.fullmatch(expected) or digest(path) != expected:
        raise ValueError('Archive SHA256 differs: ' + path.name)
    if size is not None and path.stat().st_size != size:
        raise ValueError('Archive byte length differs: ' + path.name)


def fetch(value, path):
    value = asset(value)
    path = Path(path)
    if path.exists():
        check_archive(path, value['sha256'], value['bytes'])
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.part')
    if partial.exists():
        raise ValueError('Prior partial download retained; inspect rather than overwrite')
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            https_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    request = urllib.request.Request(value['url'], headers={'User-Agent':'Helene-native-qualification'})
    with urllib.request.build_opener(Redirect()).open(request, timeout=120) as source, partial.open('xb') as output:
        count = 0
        while block := source.read(1024 * 1024):
            count += len(block)
            if count > value['bytes']:
                raise ValueError('Public input exceeds pinned length')
            output.write(block)
    check_archive(partial, value['sha256'], value['bytes'])
    partial.rename(path)
    return path


def extract(archive, destination):
    """Reject links/traversal/duplicate and case-fold-colliding ZIP entries."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Extraction target must be new')
    with zipfile.ZipFile(archive) as source:
        seen = set()
        for entry in source.infolist():
            name = entry.filename.rstrip('/')
            relative = PurePosixPath(name)
            key = name.casefold()
            if (not name or relative.is_absolute() or '..' in relative.parts
                    or '\\' in name or ':' in name or relative.parts[0] != 'Helene'
                    or key in seen or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('Unsafe/duplicate ZIP member: ' + name)
            seen.add(key)
        destination.mkdir(parents=True)
        for entry in source.infolist():
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            target.chmod((entry.external_attr >> 16) & 0o777 or 0o644)
    return destination / 'Helene'


def check_program(root, inputs):
    root = Path(root)
    app = json.loads((root/'python-app.json').read_text(encoding='utf8'))
    if (app.get('version'), app.get('target')) != (inputs['version'], TARGET):
        raise ValueError('Candidate package version/target differs')
    if digest(root/'source-inputs.json') != inputs['source_inputs_sha256']:
        raise ValueError('Candidate frozen source binding differs')
    expected = inputs.get('verification_bundle_sha256')
    if expected and (digest(root/'verification/manifest.json') != expected
                     or app.get('verification_bundle_sha256') != expected):
        raise ValueError('Candidate full verification bundle differs')
    return app


def broken_archive(source, output):
    """Declared synthetic startup-fault input; NOT a fabricated future release.

    Retains the exact version/core/runtime, changes only the application entry and
    its package-inventory hash. No ready receipt, pipeline state or cancellation
    marker is altered. A failed startup MUST cause the real updater's rollback.
    """
    with zipfile.ZipFile(source) as reader:
        code = b'import os; os._exit(73)  # synthetic native acceptance startup fault\n'
        inventory = json.loads(reader.read('Helene/python-package-files.json'))
        if 'app/python_app.py' not in inventory['files']:
            raise ValueError('Application entry is absent from package inventory')
        inventory['files']['app/python_app.py'] = hashlib.sha256(code).hexdigest()
        changes = {'Helene/app/python_app.py':code,
                   'Helene/python-package-files.json':json.dumps(inventory, sort_keys=True).encode()}
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as writer:
            for entry in reader.infolist():
                writer.writestr(entry, changes.get(entry.filename, reader.read(entry)))
    return Path(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--fetch', action='store_true')
    args = p.parse_args()
    value = manifest(args.manifest)
    paths = {}
    for key in ('base','candidate',*(['broken'] if 'broken' in value else [])):
        path = args.work/'inputs'/value[key]['name']
        if args.fetch:
            fetch(value[key], path)
        check_archive(path, value[key]['sha256'], value[key]['bytes'])
        paths[key] = path
    root = extract(paths['candidate'], args.work/'candidate')
    check_program(root, value)
    extract(paths['base'], args.work/'program')
    dump(args.work/'input-receipt.json', {'manifest_sha256':digest(args.manifest),
        'assets':{key:{'sha256':digest(path),'bytes':path.stat().st_size} for key,path in paths.items()},
        'scope':'input/extraction only, no runtime PASS'})


if __name__ == '__main__':
    main()
