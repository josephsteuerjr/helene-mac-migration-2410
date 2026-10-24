"""One native small-overlay qualification; unchanged heavy components stay out."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
TMP=Path(os.environ['RUNNER_TEMP'])
base=TMP/'base/Helene-2.0.0-macos-arm64.zip'
with base.open('rb') as f:
    assert hashlib.file_digest(f,'sha256').hexdigest()=='75646ae7309bd7e2a383441a0e4b3c589714b1804bbdb17950edeb1acc50dc73'
extract=TMP/'migration-stage';extract.mkdir()
with zipfile.ZipFile(base) as z:
    for item in z.infolist():
        rel=PurePosixPath(item.filename)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Invalid archive path')
        target=extract.joinpath(*rel.parts)
        if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with z.open(item) as src,target.open('wb') as dst:
            import shutil
            shutil.copyfileobj(src,dst)
        mode=(item.external_attr>>16)&0o777
        if mode:target.chmod(mode)
program=extract/'Helene'
archive=TMP/'Helene-2.0.0-macos-arm64-migration.zip'
subprocess.run([sys.executable,str(ROOT/'desk/installer/overlay_mac_migration.py'),'--program',str(program),'--archive',str(archive)],check=True)
# Portable test reads real packaged dependencies and tests real killed-process recovery.
env=dict(os.environ,PYTHONPATH=str(program/'app'))
logs=TMP/'qualification-logs';logs.mkdir()
with (logs/'focused.log').open('wb') as log:
    focused=subprocess.run([sys.executable,str(ROOT/'desk/tests/t_mac_migration_2410.py'),'-v'],env=env,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
print((logs/'focused.log').read_text(),flush=True)
with (logs/'native.log').open('wb') as log:
    native=subprocess.run([sys.executable,str(ROOT/'desk/tests/macos_migration_pilot.py'),'--program',str(program),'--evidence',str(TMP/'migration-evidence')],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
print((logs/'native.log').read_text(),flush=True)
focused.check_returncode();native.check_returncode()
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(TMP/'qualification.json').write_text(json.dumps({'archive':archive.name,'sha256':digest,'bytes':archive.stat().st_size,'native_macos':True,'scope':'Synthetic legacy migration, UI, admission, failed-start/retry and preservation; not physical permissions or authenticated agent proof.'},indent=2))
print('MAC_MIGRATION_QUALIFIED',flush=True)
