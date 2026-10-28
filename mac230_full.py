"""Invoke the SHIPPED full applicable verifier on exact isolated Mac inputs.

No selected/full relabel, synthetic review, pipeline override or approval. The
local control tests are not execution of the Mac product or its full recipe.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from mac230_prepare import check_program, digest, dump, manifest

# The actual incoming interpreter imports these modules from its own app/tree.
# This is the same public API sequence as the Linux full-manifest adapter.
FULL_SCRIPT = r'''
import json,sys,traceback
from pathlib import Path
program,plan,output,executor=map(Path,sys.argv[1:5])
sys.path[:0]=[str(program/'app'),str(program/'tree')]
from localharness import source_admission,source_merge as merge,source_update_battery as battery,source_verification_bundle as bundle,update_composition
from localharness.package_notice import read,write
before=bundle.digest(program/'python-package-files.json')
activated=source_admission.activate(program)
after=bundle.digest(program/'python-package-files.json')
write(output.parent/'source-admission-observation.json',{
 'consumer':'packaged source_admission.activate','activated':activated,
 'package_manifest_before':before,'package_manifest_after':after,
 'state':read(program/'source-admission-state.json')})
meta=read(program/'python-app.json');manifest_sha=meta['verification_bundle_sha256']
full=bundle.load(program/'verification',manifest_sha,meta['version'])
if plan.exists():raise ValueError('Preserve previous full attempt; select a new work directory')
core=program/'tree'
record=merge.create(core,core,core,plan,exe=merge.executable(program))
operation={'id':'acceptance-pristine-'+plan.parent.name,'version':meta['version'],'state':'verifying',
 'tree':str(plan.parent/'synthetic-verification-data'),
 'input_sha256':merge.input_signature(record),'candidate_sha256':merge.candidate_signature(plan),
 'coordinator':{'kind':'incoming-update-runtime.v1','program':str(program),'verification_bundle_sha256':manifest_sha},
 'verification_bundle':{'root':str(program/'verification'),'sha256':manifest_sha},
 'verification_executor':read(executor),
 'scope':'pristine packaged composition qualification; no authored merge/apply/review approval'}
write(plan/'pipeline.json',operation)
result={'format':'helene-mac230-full-result.v2','scope':operation['scope'],
 'manifest_sha256':manifest_sha,'recipe':full['lanes'],'full_pass':False}
try:
 update_composition.prepare(plan,operation)
 result['composition_sha256']=update_composition.signature(plan,operation)
 result['sources']=battery.prepare(operation,plan,None,lambda:False)
 result['battery']=operation.get('battery')
 write(plan/'pipeline.json',operation)
 result['validation']=battery.validate(operation,plan)
 result['full_pass']=True
except BaseException as exc:
 result['error']=type(exc).__name__+': '+str(exc)
 result['traceback']=traceback.format_exc();result['battery']=operation.get('battery')
 raise
finally:
 write(output,result)
'''


def executor_for(program, work):
    """Per-run path capability; never rewrite the version-bound executor lock."""
    program, work = Path(program).resolve(), Path(work).resolve()
    cache = work/'npm-cache/cache'
    if not cache.is_dir() or cache.is_symlink():
        raise ValueError('Pinned owned npm cache must be prepared before full execution')
    tools = {'python':str(program/'runtime/bin/python3')}
    for name in ('node','npm','cargo'):
        found = shutil.which(name)
        if not found:
            raise ValueError('Native executor tool unavailable: '+name)
        tools[name] = found
    native = {str(program/name):digest(program/name) for name in ('helene-body','helene-bridge')}
    return {**tools,'npm_config_cache':str(cache),
            'native_env':{'HELENE_BODY_DIR':str(program),'HELENE_BODY_BIN':str(program/'helene-body')},
            'native_files':native}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('capture-executor','run'))
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--packages',type=Path)
    args=p.parse_args()
    if sys.platform!='darwin' or platform.machine()!='arm64':
        raise RuntimeError('Requires real Darwin ARM64 executor')
    inputs=manifest(args.manifest)
    program=(args.work/'candidate/Helene').resolve()
    check_program(program,inputs)
    python=program/'runtime/bin/python3'
    if not python.is_file():raise ValueError('Incoming native runtime interpreter missing')
    args.evidence.mkdir(parents=True,exist_ok=True)
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL')}
    home=args.work/('full home '+args.action);home.mkdir(exist_ok=False)
    env.update(HOME=str(home),USERPROFILE=str(home),PYTHONNOUSERSITE='1',
        PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONUNBUFFERED='1',
        TMPDIR=str(home),PYTHONPATH=os.pathsep.join((str(program/'app'),str(program/'tree'))))
    if args.action=='capture-executor':
        command=[str(python),'-B','-s','-m','localharness.source_verification_bundle',
            'capture-executor','--output',str(args.evidence/'executor-darwin.json')]
        if args.packages:command+=['--packages',str(args.packages.resolve())]
        with (args.evidence/'executor-capture.log').open('wb') as output:
            subprocess.run(command,cwd=program,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
        return 0
    if not inputs.get('verification_bundle_sha256'):
        raise ValueError('Frozen applicable bundle/lock required; capture is not full PASS')
    executor=args.work/'verification-executor.json'
    dump(executor,executor_for(program,args.work))
    dump(args.evidence/'executor-selection.json',json.loads(executor.read_text('utf8')))
    plan=args.work/'full-plan';output=args.evidence/'full-verification.json'
    script_path=args.work/'run-shipped-full.py';script_path.write_text(FULL_SCRIPT,encoding='utf8')
    with (args.evidence/'full-verification.log').open('wb') as log:
        completed=subprocess.run([str(python),'-B','-s',str(script_path),str(program),
            str(plan),str(output),str(executor)],cwd=args.work,env=env,stdout=log,stderr=subprocess.STDOUT)
    if (plan/'test-battery').is_dir():
        shutil.copytree(plan/'test-battery',args.evidence/'test-battery',dirs_exist_ok=False)
    for name in ('plan.json','pipeline.json','composition.json'):
        if (plan/name).is_file():shutil.copyfile(plan/name,args.evidence/name)
    result=json.loads(output.read_text(encoding='utf8')) if output.is_file() else {}
    summary={'exit_code':completed.returncode,'full_pass':result.get('full_pass') is True,
        'input_manifest_sha256':digest(args.manifest),'output_sha256':digest(output) if output.exists() else None,
        'interpretation':'No native/review/product acceptance follows from source battery alone'}
    dump(args.evidence/'full-summary.json',summary)
    if completed.returncode or result.get('full_pass') is not True:
        raise RuntimeError('Full applicable native source battery is not green; inspect exact retained reports')
    print('MAC230_FULL_APPLICABLE_BATTERY_PASS',flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
