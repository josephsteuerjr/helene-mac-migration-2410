"""Native dependency/executor preparation only, never candidate acceptance.

Uses the same resolved-package/removal generator as the Linux proof. The earlier
crypto-only prototype is preserved in root task artifacts, not used for closure.
"""
from pathlib import Path
import argparse
import email
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from mac230_prepare import fetch, extract

BASE={'name':'Helene-2.2.17-macos-arm64.zip','url':'https://github.com/josephsteuerjr/praxis/releases/download/v2.2.17/Helene-2.2.17-macos-arm64.zip',
      'sha256':'49a8912a44efdba2c3a4e409de9b672b605c7665093147bf2a6e4e474c593e38','bytes':127880161}
PINS=['cryptography==48.0.1','pytest==8.4.2','aiogram==3.31.0']

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def run(py,*args,**kwargs):
    subprocess.run([str(py),*map(str,args)],check=True,**kwargs)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.work.exists() or a.out.exists():raise ValueError('Probe directories must be new')
    a.work.mkdir(parents=True);a.out.mkdir(parents=True)
    archive=fetch(BASE,a.work/BASE['name'])
    program=extract(archive,a.work/'probe-program');py=program/'runtime/bin/python3'
    pure=Path(subprocess.check_output([str(py),'-c','import sysconfig;print(sysconfig.get_paths()["purelib"])'],text=True).strip())
    prefix=pure.resolve().relative_to(program.resolve()).as_posix()+'/'
    target=a.work/'resolved-site';report=a.out/'pip-report.json'
    run(py,'-m','pip','install','--only-binary=:all:','--upgrade','--target',target,'--report',report,*PINS)
    overlay=a.out/'runtime-overlay'
    env={**os.environ,'HELENE_OVERLAY_SITE_PREFIX':prefix}
    run(sys.executable,Path(__file__).with_name('runtime_overlay.py'),'--donor',archive,'--donor-sha',BASE['sha256'],
        '--site',target,'--output',overlay,'--platform','macos','--pip-report',report,env=env)
    manifest=json.loads((overlay/'manifest.json').read_text('utf8'))
    for name,prior in manifest.get('remove',{}).items():
        q=program/name
        if sha(q)!=prior:raise ValueError('Probe donor file changed: '+name)
        q.unlink()
    for name,row in manifest['files'].items():
        q=program/name;q.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(overlay/name,q);q.chmod(0o755 if row['mode']=='100755' else 0o644)
    # Module import and effective metadata must agree before an executor is frozen.
    capture='''import sys,json,importlib.util,importlib.metadata as md
import cryptography,pytest,aiogram,pydantic
assert cryptography.__version__=="48.0.1" and pytest.__version__=="8.4.2" and aiogram.__version__=="3.31.0"
assert [d.version for d in md.distributions() if (d.metadata.get("Name") or "").lower()=="cryptography"]==["48.0.1"]
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
k=Ed25519PrivateKey.generate();sig=k.sign(b"synthetic-capture");k.public_key().verify(sig,b"synthetic-capture")
spec=importlib.util.spec_from_file_location("capture",sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps(m.executor_lock(),sort_keys=True),encoding="utf8")
'''
    run(py,'-c',capture,Path(__file__).with_name('capture_executor_source.py').resolve(),(a.out/'executor-darwin.json').resolve())
    # Resolve once above; download those exact versions, never a second resolution.
    resolved=json.loads(report.read_text('utf8'))['install'];wheels=a.out/'wheelhouse';wheels.mkdir()
    requirements=[r['metadata']['name']+'=='+r['metadata']['version'] for r in resolved]
    run(py,'-m','pip','download','--only-binary=:all:','--no-deps','--dest',wheels,*requirements)
    packages={}
    for wheel in wheels.glob('*.whl'):
        with zipfile.ZipFile(wheel) as z:
            name,=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
            meta=email.message_from_bytes(z.read(name))
        packages[meta['Name'].lower().replace('_','-')]={'filename':wheel.name,'version':meta['Version'],'sha256':sha(wheel)}
    (wheels/'wheels.json').write_text(json.dumps({'packages':packages},sort_keys=True),encoding='utf8')
    (a.out/'probe.json').write_text(json.dumps({'scope':'runtime/dependency/executor preparation only; no test or GUI PASS',
        'donor':BASE,'requested_pins':PINS,'overlay_manifest_sha256':sha(overlay/'manifest.json'),
        'executor_sha256':sha(a.out/'executor-darwin.json'),'capture_source_sha256':sha(Path(__file__).with_name('capture_executor_source.py'))},sort_keys=True),encoding='utf8')
    print('Native executor/dependency preparation retained; no candidate acceptance claimed',flush=True)

if __name__=='__main__':main()
