"""Small native rebuild over an immutable qualified main ZIP; no runtime rebuild.

The caller extracts the prior final ZIP preserving Unix modes, then supplies
its NEW disposable Helene folder here. Never point at a live installation.
Existing delivery archives are not replaced. No downloads/publication.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from localharness import app_components
from macos_python_app import create
DESK=Path(__file__).resolve().parents[1]
FILES={'python_app.py':'app/python_app.py','mac_migrate.py':'app/mac_migrate.py',
       'localharness/mac_migration.py':'app/localharness/mac_migration.py',
       'localharness/app_migration.py':'app/localharness/app_migration.py',
       'localharness/profile_paths.py':'app/localharness/profile_paths.py',
       'resources/mac-migration.html':'app/resources/mac-migration.html',
       'resources/HELENE-MAP.md':'app/resources/HELENE-MAP.md'}


def overlay(program,archive):
    if sys.platform!='darwin':raise RuntimeError('Compile/sign Cocoa entries on native macOS')
    program,archive=Path(program).resolve(),Path(archive).resolve()
    if archive.exists():raise FileExistsError(archive)
    cfg=json.loads((program/'helene.json').read_text())
    if cfg.get('setup_complete') is not False or (program/'data').exists() or (program/'python-migration.json').exists():
        raise ValueError('Overlay requires a fresh disposable unpacking, never an existing profile')
    if archive.is_relative_to(program):raise ValueError('Write archive outside its program input')
    for source,target in FILES.items():
        path=program/target;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DESK/source,path)
    meta=json.loads((program/'python-app.json').read_text());create(program,meta['version'])
    inventory=program/'python-package-files.json';value=json.loads(inventory.read_text())
    for relative in list(value['files']):
        path=program/relative
        if path.is_file():value['files'][relative]=app_components.digest(path)
    for path in (program/'Migrate Helene.app').rglob('*'):
        if path.is_file():value['files'][path.relative_to(program).as_posix()]=app_components.digest(path)
    for relative in FILES.values():value['files'][relative]=app_components.digest(program/relative)
    (program/'python-package-files.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(program.rglob('*')):
            if path.is_symlink():raise ValueError('Unexpected distribution symlink: '+str(path))
            if path.is_file():output.write(path,'Helene/'+path.relative_to(program).as_posix())
    digest=app_components.digest(archive)
    archive.with_suffix(archive.suffix+'.sha256').write_text(digest+' *'+archive.name+'\n',encoding='ascii')
    return {'archive':str(archive),'sha256':digest,'bytes':archive.stat().st_size,'overlay':FILES,
            'qualification':'Build only; run macos_migration_pilot.py separately'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();print(json.dumps(overlay(a.program,a.archive),indent=2))
