"""Native Finder-entry + real served migration form + OS lease/startup pilot.
Run with a driver Python OUTSIDE the disposable --program directory. Requires
psutil and playwright+Chromium in that driver (not product dependencies).
Uses synthetic old-profile memory/Git only. No live accounts, voice replay,
service mutation, privilege or source retirement. Screenshots need inspection.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request


def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def wait(fn,seconds=90):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.2)
    raise TimeoutError('Native migration condition did not settle')


def main(program,evidence):
    if sys.platform!='darwin':raise RuntimeError('Native macOS required')
    root=Path(program).resolve();out=Path(evidence).resolve();out.mkdir(parents=True,exist_ok=False)
    if Path(sys.executable).resolve().is_relative_to(root):raise RuntimeError('Use an external driver Python, not the destination runtime')
    if (root/'data').exists() or (root/'python-migration.json').exists():raise ValueError('Pilot needs a disposable fresh application')
    work=out/'fixture';old=work/'Old Helene';data=work/'New profile';(old/'data/memory').mkdir(parents=True)
    (old/'data/soul').mkdir();shutil.copytree(root/'tree',old/'tree')
    (old/'data/memory/probe.txt').write_text('Synthetic legacy memory')
    (old/'data/soul/identity.md').write_text('Synthetic legacy identity')
    cfg=json.loads((root/'helene.json').read_text());cfg.update(tree='data',code='tree',setup_complete=False,fixture_custom='retain')
    (old/'helene.json').write_text(json.dumps(cfg));(old/'helene-build.json').write_text('{"version":"1.2.7","platform":"macos"}')
    (old/'Helene.app/Contents/MacOS').mkdir(parents=True)
    code=old/'tree';(code/'migration_fixture.py').write_text('base=1\n')
    def git(*args):return subprocess.check_output(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-C',str(code),*args])
    git('init','--quiet');git('add','migration_fixture.py');git('commit','--quiet','-m','synthetic')
    (code/'migration_fixture.py').write_text('staged=2\n');git('add','migration_fixture.py')
    (code/'migration_fixture.py').write_text('unstaged=3\n');(code/'untracked_fixture.py').write_text('unique=4\n')
    expected={'head':git('rev-parse','HEAD').decode().strip(),'index':sha(code/'.git/index'),'edit':sha(code/'migration_fixture.py'),'untracked':sha(code/'untracked_fixture.py'),'memory':sha(old/'data/memory/probe.txt'),'identity':sha(old/'data/soul/identity.md'),'config':sha(old/'helene.json')}
    def control(pid):
        path=root/f'.python-window-{pid}.json'
        if path.is_file():return json.loads(path.read_text())
    def invoke(c,command,args=None):
        req=urllib.request.Request(c['origin']+'/__python__/invoke',data=json.dumps({'command':command,'args':args or {}}).encode(),headers={'Content-Type':'application/json','X-Helene-Window':c['token']})
        with urllib.request.urlopen(req,timeout=240) as response:return json.load(response)['result']
    def receipt():
        path=root/'python-migration.json'
        return json.loads(path.read_text()) if path.is_file() else {}
    processes=[];migration=None
    try:
        with (out/'migration-window.log').open('wb') as log:
            migration=subprocess.Popen([str(root/'Migrate Helene.app/Contents/MacOS/Helene')],cwd=out,stdout=log,stderr=log)
        processes.append(migration);c=wait(lambda:control(migration.pid))
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':780,'height':760})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(c['origin']);page.locator('#old').fill(str(old));page.locator('#data').fill(str(data))
            page.locator('#prepare').click();page.wait_for_function("document.querySelector('#error').textContent.includes('Explicitly')")
            assert not receipt();page.locator('#closed').check()
            # OS census rejects a real same-user process whose cwd is the donor.
            live=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],cwd=old);processes.append(live)
            page.locator('#prepare').click();page.wait_for_function("document.querySelector('#error').textContent.includes('process')")
            assert not receipt();live.terminate();live.wait(10)
            # Independent process holds flock without naming donor in argv/cwd.
            hold_script="import fcntl,os,time;f=open(os.environ['FIXTURE_LOCK'],'a+');fcntl.flock(f,fcntl.LOCK_EX);print('LOCKED',flush=True);time.sleep(60)"
            holder=subprocess.Popen([sys.executable,'-c',hold_script],cwd=out,env=dict(os.environ,FIXTURE_LOCK=str(old/'data/.desktop-owner.lock')),stdout=subprocess.PIPE,text=True);processes.append(holder)
            assert holder.stdout.readline().strip()=='LOCKED'
            page.locator('#prepare').click();page.wait_for_function("document.querySelector('#error').textContent.includes('Data is still owned')")
            assert not receipt();holder.terminate();holder.wait(10)
            page.locator('#prepare').click();page.wait_for_function("!document.querySelector('#start').disabled",timeout=240000)
            note=receipt();assert note['state']=='prepared' and not note.get('startup_proof')
            page.screenshot(path=str(out/'prepared-web.png'),full_page=True)
            time.sleep(2);subprocess.run(['screencapture','-x',str(out/'prepared-cocoa.png')],check=True)
            # Definite failed startup leaves profile prepared and donor intact.
            entry=root/'app/python_app.py';original=entry.read_bytes();entry.write_bytes(b'raise SystemExit(73)\n')
            page.locator('#start').click()
            # Preparation already created the file. Its existence is not an
            # acknowledgement of this asynchronous Start request.
            def failed_start():
                path=root/'mac-migration-status.json'
                value=json.loads(path.read_text()) if path.is_file() else {}
                return value if value.get('state')=='start_failed' else None
            failure=wait(failed_start)
            assert '73' in failure.get('error',''),failure
            page.wait_for_function("!document.querySelector('#start').disabled && document.querySelector('#error').textContent.includes('73')")
            assert receipt()['state']=='prepared';entry.write_bytes(original)
            page.locator('#start').click()
            note=wait(lambda:receipt() if receipt().get('state')=='new_app_started' else None,150)
            assert note.get('startup_proof') and note['startup_proof'].get('channel_pid')
            selected=Path(note['source_paths'][0]['selected']);home=Path(note['data_paths'][0])
            got={'head':subprocess.check_output(['git','-C',str(selected),'rev-parse','HEAD']).decode().strip(),'index':sha(selected/'.git/index'),'edit':sha(selected/'migration_fixture.py'),'untracked':sha(selected/'untracked_fixture.py'),'memory':sha(home/'memory/probe.txt'),'identity':sha(home/'soul/identity.md'),'config':sha(old/'helene.json')}
            assert got==expected,(got,expected)
            assert json.loads((root/'helene.json').read_text())['fixture_custom']=='retain'
            assert sha(old/'tree/.git/index')==expected['index'] and sha(old/'data/memory/probe.txt')==expected['memory']
            assert not (home/'memory/probe.txt').samefile(old/'data/memory/probe.txt')
            page.wait_for_function("document.querySelector('#status').textContent.includes('был подтверждён')")
            page.screenshot(path=str(out/'confirmed-web.png'),full_page=True)
            time.sleep(3);subprocess.run(['screencapture','-x',str(out/'confirmed-cocoa.png')],check=True)
            assert not errors,errors
            browser.close()
        # Close both actual windows through their authenticated consumer.
        for path in list(root.glob('.python-window-*.json')):
            value=json.loads(path.read_text());invoke(value,'python_window',{'action':'exit'})
        migration.wait(30)
        wait(lambda:not list(root.glob('.python-window-*.json')),40)
        (out/'result.json').write_text(json.dumps({'native_macos':True,'served_form':True,'finder_entry':True,'process_refusal':True,'flock_refusal':True,'failed_start_retry':True,'startup_proof':note['startup_proof'],'preserved':got,'source_retained':True,'scope':'Synthetic local setup_complete=false profile, channel and rendered UI. No authenticated model/runner/phone/TCC proof.'},indent=2))
        print('MAC_LEGACY_MIGRATION_PASS',flush=True)
    finally:
        for path in list(root.glob('.python-window-*.json')):
            try:invoke(json.loads(path.read_text()),'python_window',{'action':'exit'})
            except (OSError,ValueError):pass
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(15)
        for name in ('python-migration.json','mac-migration-status.json','migration-start.log','startup-error.log'):
            if (root/name).is_file():shutil.copy2(root/name,out/name)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program',type=Path,default=os.environ.get('HELENE_MIGRATION_PILOT_PROGRAM'))
    p.add_argument('--evidence',type=Path,default=os.environ.get('HELENE_MIGRATION_PILOT_EVIDENCE'))
    a=p.parse_args()
    if not a.program or not a.evidence:p.error('Provide program/evidence through environment variables; see the migration document')
    if '--program' in sys.argv:
        # The real census correctly refuses ANY process naming its selected
        # destination in argv. Keep this external test driver path-neutral.
        env=dict(os.environ,HELENE_MIGRATION_PILOT_PROGRAM=str(a.program),HELENE_MIGRATION_PILOT_EVIDENCE=str(a.evidence))
        os.execve(sys.executable,[sys.executable,str(Path(__file__).resolve())],env)
    main(a.program,a.evidence)
