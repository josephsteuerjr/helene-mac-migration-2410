"""Real Cocoa consumer, synthetic isolated profile, no injected ready/approval.

Native positive path is pristine-preserve with exact Git metadata and excluded
workspace edits. This does NOT prove authored-runtime merge/review. The separate
modified-preserve case must block when no actual agent/reviewer is configured.
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
import threading
import time
import urllib.request

from mac230_prepare import (check_archive, check_program, digest, dump, manifest)


def wait(test, seconds=180, label='condition'):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        found = test()
        if found:
            return found
        time.sleep(.12)
    raise TimeoutError('Not observed: ' + label)


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf8'))
    except FileNotFoundError:
        return {}


def invoke(row, command, args=None):
    req = urllib.request.Request(row['origin']+'/__python__/invoke',
        data=json.dumps({'command':command,'args':args or {}}).encode(),
        headers={'Content-Type':'application/json','Origin':row['origin'],
                 'X-Helene-Window':row['token']})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)['result']
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode('utf8','replace').replace(row['token'],'[control token withheld]')
        raise RuntimeError(command+' HTTP '+str(exc.code)+': '+detail) from exc


def rpc(row, action, args=None):
    req = urllib.request.Request(row['origin']+'/session',
        data=json.dumps({'generation':row['generation'],'action':action,'args':args or {}}).encode(),
        headers={'Content-Type':'application/json','Origin':row['origin'],
                 'X-Helene-Session':row['token']})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)['result']


def alive(row):
    import psutil
    try:
        process = psutil.Process(row['pid'])
        return (process.create_time() == row['birth'] and process.is_running()
                and process.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD))
    except psutil.NoSuchProcess:
        return False


def git(source, *args):
    return subprocess.check_output(['git','-c','user.name=Synthetic qualification',
        '-c','user.email=fixture@example.invalid','-C',str(source),*args], env={
            **os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,
            'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'})


def repository_facts(source):
    head = git(source, 'rev-parse','--verify','HEAD').decode().strip()
    commits = git(source,'rev-list','--all').decode().splitlines()
    for commit in commits:
        git(source,'cat-file','-e',commit+'^{commit}')
    return {'head':head,'reachable_commits':sorted(commits),
        'refs':sorted(git(source,'for-each-ref','--format=%(refname) %(objectname)').decode().splitlines()),
        'index_sha256':digest(source/'.git/index'),
        'config_sha256':digest(source/'.git/config'),
        'workspace_status_sha256':__import__('hashlib').sha256(git(source,'status','--porcelain=v1','-z','--','workspace/')).hexdigest()}


def isolated_environment(home):
    env = {k:v for k,v in os.environ.items() if k in
        ('PATH','LANG','LC_ALL','SHELL','DISPLAY','__CF_USER_TEXT_ENCODING')}
    env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home/'config'),
        XDG_DATA_HOME=str(home/'data'), XDG_STATE_HOME=str(home/'state'),
        PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HELENE_BROKER_DISABLED='1')
    return env


class Native:
    def __init__(self, root, profile, evidence, env):
        import psutil
        import Quartz
        self.psutil, self.Quartz = psutil, Quartz
        self.root, self.profile, self.evidence, self.env = root, profile, evidence, env
        self.known, self.tokens, self.samples, self.processes = {}, set(), [], []
        self.lock = threading.RLock()
        self.halt = threading.Event()
        self.log = (evidence/'native-app.log').open('ab')
        self.thread = threading.Thread(target=self.monitor, daemon=True)
        self.thread.start()

    def remember(self, pid):
        try:
            process = self.psutil.Process(pid)
            with self.lock:
                self.known[pid] = process.create_time()
        except self.psutil.NoSuchProcess:
            pass

    def window(self, kind='window'):
        for path in sorted(self.root.glob('.python-'+kind+'-*.json')):
            row = read(path)
            if not row or Path(row.get('root','')).resolve() != self.root:
                continue
            try:
                process = self.psutil.Process(row['pid'])
                if process.is_running() and process.status() != self.psutil.STATUS_ZOMBIE:
                    row['birth'] = process.create_time()
                    self.remember(row['pid'])
                    self.tokens.add(row['token'])
                    return row
            except self.psutil.NoSuchProcess:
                pass
        return None

    def session(self):
        row = read(self.profile/'memory/.control/desktop-session.json')
        if row and alive(row):
            self.remember(row['pid'])
            self.tokens.add(row['token'])
            return row
        return None

    def job(self):
        return read(self.profile/'memory/.control/desktop-update-request.json')

    def windows(self):
        q = self.Quartz
        with self.lock:
            ids = set(self.known)
        return [{'pid':int(row[q.kCGWindowOwnerPID]), 'id':int(row[q.kCGWindowNumber]),
                 'title':str(row.get(q.kCGWindowName,'')), 'bounds':dict(row[q.kCGWindowBounds])}
            for row in q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly,0)
            if int(row[q.kCGWindowOwnerPID]) in ids and int(row.get(q.kCGWindowLayer,0)) == 0]

    def monitor(self):
        while not self.halt.wait(.1):
            with self.lock:
                current = list(self.known.items())
            for pid,birth in current:
                try:
                    process = self.psutil.Process(pid)
                    if process.create_time() == birth:
                        for child in process.children(recursive=True):
                            self.remember(child.pid)
                except (self.psutil.NoSuchProcess,self.psutil.AccessDenied):
                    pass
            self.window(); self.window('migrator'); self.session()
            helper=self.job().get('helper') or {}
            if helper.get('pid') and helper.get('birth') and alive(helper):self.remember(helper['pid'])
            self.samples.append({'at':time.time(),'windows':self.windows()})

    def capture(self, row, name):
        observed = wait(lambda:next((r for r in self.windows() if r['pid']==row['pid']),None),
                        45, 'actual Cocoa window '+name)
        subprocess.run(['screencapture','-x','-l',str(observed['id']),str(self.evidence/(name+'.png'))],
                       timeout=15, check=True)
        dump(self.evidence/(name+'-native.json'), observed)
        return observed

    def launch(self):
        executable = self.root/'Helene.app/Contents/MacOS/Helene'
        process = subprocess.Popen([str(executable),'--root',str(self.root)], cwd=self.root,
            env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        self.processes.append(process); self.remember(process.pid)
        return wait(self.window, 100, 'real application control/window')

    def detach(self, row):
        invoke(row,'python_window',{'action':'exit','relaunch':False,'observer_only':True})
        wait(lambda:not alive(row), 30, 'observer exited without terminating host')

    def exit(self):
        row = self.window()
        if row:
            invoke(row,'python_window',{'action':'exit','relaunch':False})
            wait(lambda:not alive(row), 45, 'explicit Cocoa Exit')
        owner = self.session()
        if owner:
            rpc(owner,'exit')
            wait(lambda:not alive(owner),45,'session explicit Exit')

    def finish(self):
        failures = []
        try:
            self.exit()
        except Exception as exc:
            failures.append(type(exc).__name__+': '+str(exc))
        self.halt.set(); self.thread.join(5)
        with self.lock:
            current = list(self.known.items())
        residual = [dict(pid=pid,birth=birth) for pid,birth in current if alive(dict(pid=pid,birth=birth))]
        for row in residual:
            try:
                process=self.psutil.Process(row['pid']); process.terminate()
                try:process.wait(10)
                except self.psutil.TimeoutExpired:process.kill();process.wait(10)
            except self.psutil.NoSuchProcess:
                pass
        self.log.close()
        diagnostics=[self.profile/'memory/.control/desktop-session.log',
            *[self.root/n for n in ('engine-startup-error.log','startup-error.log',
                                   'python-update-start.log','python-update-recovery.log')],
            *self.root.parent.glob('helene-update-*.log'),
            *self.root.parent.glob('.helene-update-*/installation-wizard.log')]
        for index,path in enumerate(diagnostics):
            if path.is_file():
                shutil.copyfile(path,self.evidence/('diagnostic-'+str(index)+'-'+path.name))
        channel_token=self.profile/'memory/.state/desk-token'
        if channel_token.is_file():self.tokens.add(channel_token.read_text('utf8').strip())
        # Input profiles are synthetic, but control capability tokens still do not
        # belong in public artifacts. Never copy descriptors or page HTML.
        for path in self.evidence.glob('*.log'):
            text = path.read_text(encoding='utf8',errors='replace')
            for token in self.tokens:
                if token:text=text.replace(token,'[synthetic control token withheld]')
            path.write_text(text,encoding='utf8')
        dump(self.evidence/'window-samples.json',self.samples)
        return {'cleanup_errors':failures,'forced_cleanup':residual}


ACTIVATE_SCRIPT = r'''
import sys,json,hashlib
from pathlib import Path
root,output=map(Path,sys.argv[1:3]);sys.path[:0]=[str(root/'app'),str(root/'tree')]
from localharness.source_admission import activate
from localharness.package_notice import read,write
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
before=sha(root/'python-package-files.json');changed=activate(root)
write(output,{'consumer':'normal old packaged source_admission.activate','activated':changed,
 'package_manifest_before':before,'package_manifest_after':sha(root/'python-package-files.json'),
 'journal':read(root/'source-admission-state.json')})
'''


def activate_old(root, home, evidence):
    """Normal old-runtime activation BEFORE taking the selected pristine copy."""
    with (evidence/'old-source-admission.log').open('wb') as output:
        subprocess.run([str(root/'runtime/bin/python3'),'-B','-s','-c',ACTIVATE_SCRIPT,
            str(root),str(evidence/'old-source-admission.json')],cwd=root,
            env=isolated_environment(home),stdout=output,stderr=subprocess.STDOUT,check=True,timeout=120)
    observation=read(evidence/'old-source-admission.json')
    if observation.get('journal',{}).get('state')!='ready':
        raise ValueError('Actual old source activation did not produce a ready journal')
    return observation


def configure(root, profile, home, feed, code=None):
    """Not an owner profile. No credentials, Stop bypass or running model."""
    (profile/'memory').mkdir(parents=True)
    (profile/'soul').mkdir()
    (profile/'memory/history.txt').write_text('Synthetic Mac acceptance history\n',encoding='utf8')
    (profile/'soul/identity.md').write_text('Synthetic identity, not a real agent\n',encoding='utf8')
    config = read(root/'helene.json')
    config.update(tree=str(profile),code=str(code or root/'tree'),python=str(root/'runtime/bin/python3'),
        runner=str(root/'app/localharness/runner.py'),app=str(root/'app/deskapp.py'),
        setup_complete=False,relay={'enabled':False},voice={'speak':False},
        update={'url':feed},fixture_custom={'synthetic':True,'retained':True})
    # Actual old config may contain harmless template model entries. Do not
    # supply a token, native login or network account to make the fixture work.
    for name in ('api_key','key','token','accounts','telegram','auth'):
        config.pop(name,None)
    dump(root/'helene.json',config)


def install_git_fixture(code):
    """Excluded workspace edits, not authored runtime code. L remains pristine."""
    (code/'workspace').mkdir(exist_ok=True)
    target=code/'workspace/acceptance.txt'
    target.write_text('baseline\n',encoding='utf8')
    git(code,'init','-q');git(code,'add','-f','workspace/acceptance.txt')
    git(code,'commit','-q','-m','Synthetic excluded workspace baseline')
    git(code,'branch','fixture-retained-ref')
    target.write_text('staged\n',encoding='utf8');git(code,'add','-f','workspace/acceptance.txt')
    target.write_text('unstaged\n',encoding='utf8')
    (code/'workspace/untracked.txt').write_text('untracked\n',encoding='utf8')


def selected_code(root):
    code=Path(read(root/'helene.json')['code'])
    return (code if code.is_absolute() else root/code).resolve()


def assert_pristine_selected(root, env, evidence, label):
    """Observe actual selected M against shipped B; never reseal a fixture tree."""
    script = r'''
import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'app'),str(root/'tree')]
from localharness import source_merge
from localharness.package_notice import read
value=read(root/'helene.json');code=Path(value['code']);code=(code if code.is_absolute() else root/code).resolve()
actual=source_merge.inventory(code);baseline=read(root/'code-upstream.json')['files']
if actual!=baseline:raise AssertionError('Selected source is not pristine release B')
print(json.dumps({'selected':str(code),'inventory_sha256':source_merge.signature(actual),'files':len(actual)}))
'''
    with (evidence/(label+'-pristine.log')).open('wb') as output:
        subprocess.run([str(root/'runtime/bin/python3'),'-B','-s','-c',script,str(root)],
            cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=120)


def facts(root, profile):
    config=read(root/'helene.json')
    code=selected_code(root)
    data=Path(config['tree']);data=(data if data.is_absolute() else root/data).resolve()
    return {'memory':digest(profile/'memory/history.txt'),
        'identity':digest(profile/'soul/identity.md'),
        'git':repository_facts(code),'workspace':digest(code/'workspace/acceptance.txt'),
        'untracked':digest(code/'workspace/untracked.txt'),
        'fixture_custom':config['fixture_custom'],
        'data_path':str(data),
        'profile_identity':read(profile/'memory/.control/profile-identity.json').get('id')}


def modified_blockage(native, identity):
    """A real waiting-agent pipeline is blocked even while its durable job runs.

    No agent is configured in this synthetic profile, so waiting for a semantic
    author is expected, not an attention/error that the driver may fabricate.
    """
    job=native.job()
    if job.get('id')!=identity:return None
    staging=Path(job.get('staging') or '.')
    if staging.parent!=native.root.parent or not staging.name.startswith('.helene-update-'):
        return None
    transition=read(staging/'Helene/code-transition-plan.json')
    pending=[]
    for row in transition.get('plans',[]):
        directory=Path(row['directory']).resolve()
        expected=native.profile/'memory/.source-updates'
        if directory.parent!=expected.resolve():raise ValueError('Unexpected synthetic source-plan custody')
        operation=read(directory/'pipeline.json')
        if operation.get('state')=='waiting_agent' and operation.get('resolution_owner')=='agent':
            if operation.get('review_clear'):
                raise AssertionError('Blocked synthetic source acquired unexpected apply authority')
            pending.append({'directory':str(directory),'state':operation['state'],
                'resolution_owner':operation['resolution_owner'],'candidate_sha256':operation.get('candidate_sha256'),
                'review_clear':operation.get('review_clear',False),'battery':operation.get('battery')})
    if pending or job.get('state') in ('attention','paused'):
        return {'job':job,'waiting_sources':pending}
    return None


def complete(native, old_pid, version, seconds=240):
    def done():
        note=read(native.root/'python-migration.json')
        row=native.window()
        if (row and row['pid'] != old_pid and note.get('state')=='completed'
                and note.get('startup_proof')):
            return row,note
    row,note=wait(done,seconds,'native renderer-confirmed startup, not driver python_ready')
    if invoke(row,'app_info').get('version') != version:
        raise AssertionError('Actual app version differs after native startup')
    return row,note


def browser_observation(native, row, name):
    """Separate browser proof; cannot supply the earlier native ready receipt."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        page=browser.new_page(viewport={'width':1100,'height':800})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(row['origin'],wait_until='domcontentloaded')
            page.locator('body').wait_for(state='visible')
            page.wait_for_timeout(1500)
            body=page.locator('body').inner_text()
            if not body.strip() or errors:
                raise AssertionError('Production UI blank or script error: '+str(errors))
            dump(native.evidence/(name+'-browser.json'),{'body_text':body,'pageerrors':errors,
                'scope':'separate Chromium rendering, not native Cocoa DOM or model proof',
                'screenshots_visually_judged':False})
        finally:
            page.screenshot(path=str(native.evidence/(name+'-browser.png')))
            browser.close()


def exercise(args):
    if sys.platform!='darwin' or platform.machine()!='arm64':
        raise RuntimeError('Requires real macOS ARM64 Cocoa; no Windows/Linux substitute')
    inputs=manifest(args.manifest)
    root=(args.work/'program/Helene').resolve()
    candidate=args.work/'inputs'/inputs['candidate']['name']
    check_archive(candidate,inputs['candidate']['sha256'],inputs['candidate']['bytes'])
    check_program(args.work/'candidate/Helene',inputs)
    args.evidence.mkdir(parents=True,exist_ok=False)
    home=args.work/'synthetic home';home.mkdir()
    activation=activate_old(root,home,args.evidence)
    code=args.work/'synthetic code'
    # Copy only this activated old program's code, not preparation caches/profile.
    # Its released .git (if any) stays intact; Git fixture adds excluded workspace.
    shutil.copytree(root/'tree',code)
    install_git_fixture(code)
    profile=args.work/'synthetic data';configure(root,profile,home,inputs['feed_url'],code)
    native=Native(root,profile,args.evidence,isolated_environment(home))
    result={'format':'helene-mac230-native-result.v1','status':'running',
        'manifest_sha256':digest(args.manifest),'candidate_sha256':inputs['candidate']['sha256'],
        'platform':platform.platform(),'machine':platform.machine(),'steps':{},
        'old_source_admission':activation,
        'claims_not_made':['real owner profile','physical microphone','all provider auth',
            'authored-runtime modified merge success','screenshots visually judged','full battery unless separate full result passes']}
    def save():dump(args.evidence/'native-result.json',result)
    save()
    try:
        first=native.launch();native.capture(first,'base-native')
        assert invoke(first,'app_info')['version']==inputs['base_version']
        expected=facts(root,profile)
        assert_pristine_selected(root,native.env,args.evidence,'old')
        # First entry is the OLD public package's configured feed + normal Update,
        # not manually copying incoming app/core over the old installation.
        release=invoke(first,'update_check',{'url':inputs['feed_url']})
        assert release['newer'] and release['latest']==inputs['version'], release
        assert release['sha256']==inputs['candidate']['sha256'], release
        downloaded=invoke(first,'update_download',{'url':release['url'],'sha256':release['sha256']})
        assert downloaded['sha256']==inputs['candidate']['sha256']
        check_archive(downloaded['path'],inputs['candidate']['sha256'],inputs['candidate']['bytes'])
        response=invoke(first,'update_install',{'path':downloaded['path'],'sourceMode':'preserve'})
        result['steps']['legacy_update']={'response_shape':sorted(response),'started_at':time.time()};save()
        if response.get('state')=='needs_resolution':
            raise RuntimeError('Legacy source resolution needs real agent; no fake ready')
        # Old17 opens the incoming --migration-wizard entry. Final helene_setup
        # recognizes in-place legacy Update and transfers directly into a durable
        # host; its historical .python-migrator descriptor says wizard_opened=False.
        # It is NOT an RPC window and must never receive migration_install.
        job=wait(lambda:native.job() if native.job().get('kind')=='migration' and
            native.job().get('admission') else None,90,'legacy Update durable admission')
        job_id=job['id'];producer=job['admission']
        assert alive(producer) and producer['pid']!=first['pid']
        native.remember(producer['pid'])
        assert job['program']==str(root) and job['tree']==str(profile)
        intent=job['migration']
        assert intent['old']==str(root) and intent['target']==str(root) and intent['source_mode']=='preserve'
        incoming=Path(intent['package'])
        assert incoming.name=='Helene' and incoming.parent.parent==root.parent
        declarations=list(incoming.glob('.python-migrator-*.json'))
        assert declarations, 'Old updater handoff descriptor missing'
        legacy=[read(p) for p in declarations]
        assert any(r.get('job_id')==job_id and r.get('wizard_opened') is False and
            r.get('durable_owner')==producer for r in legacy),legacy
        result['steps']['legacy_update']['admission_observed_alive']=True;save()
        current,note=complete(native,first['pid'],inputs['version'])
        native.capture(current,'rc-first-native')
        observed=facts(root,profile)
        assert_pristine_selected(root,native.env,args.evidence,'first-rc')
        # First new bind may allocate the synthetic profile ID; it must then stay.
        expected['profile_identity']=observed['profile_identity']
        assert expected['profile_identity'] and observed==expected,(observed,expected)
        assert native.job()['id']==job_id
        result['steps']['legacy_update'].update(passed=True,job_id=job_id,
            distinct_host_pid=producer['pid'],native_startup=note,
            scope='pristine runtime source + exact excluded-workspace/Git/profile preservation')
        save()
        browser_observation(native,current,'rc-first')
        # Ordinary RC update takes admission before download; pause is a REAL
        # control intent, not mutation of pipeline state by the test driver.
        owner=wait(native.session,30,'persistent RC session owner')
        response=invoke(current,'update_start',{'url':inputs['candidate']['url'],
            'sha256':inputs['candidate']['sha256'],'sourceMode':'preserve'})
        assert response['state']=='admitted' and response['observer_may_close']
        identity=response['job']['id']
        rpc(owner,'pause_job')
        assert native.job()['id']==identity
        native.detach(current)
        assert alive(owner) and native.job()['id']==identity
        rejoined=native.launch();native.capture(rejoined,'paused-rejoin-native')
        same=wait(native.session,15,'same session after rejoin')
        assert (same['pid'],same['birth'],same['generation'])==(owner['pid'],owner['birth'],owner['generation'])
        assert native.job()['id']==identity and native.job()['state']=='paused'
        rpc(same,'resume_job')
        updated,note=complete(native,rejoined['pid'],inputs['version'])
        native.capture(updated,'ordinary-update-native')
        assert native.job()['id']==identity and facts(root,profile)==expected
        assert_pristine_selected(root,native.env,args.evidence,'ordinary-rc')
        result['steps']['ordinary_detach_rejoin']={'passed':True,'job_id':identity,
            'same_host_before_cutover':{k:owner[k] for k in ('pid','birth','generation')},'native_startup':note}
        save()
        # Parent supplies a coherent, pinned synthetic BADnext package, including
        # its version/admission/inventory contracts. Never mutate installed bytes
        # or manufacture a future-release claim inside the acceptance driver.
        if 'broken' not in inputs:
            raise ValueError('Parent-frozen coherent synthetic BADnext input required')
        broken_input=args.work/'inputs'/inputs['broken']['name']
        check_archive(broken_input,inputs['broken']['sha256'],inputs['broken']['bytes'])
        broken=root.parent/inputs['broken']['name']
        if broken.exists():raise ValueError('Prior synthetic BADnext beside program retained')
        os.link(broken_input,broken)
        before_entry=digest(root/'app/python_app.py')
        assert read(root/'python-app.json')['version']==inputs['version']
        response=invoke(updated,'update_install',{'path':str(broken),'sourceMode':'preserve'})
        assert response['state']=='admitted'
        failed_id=response['job']['id']
        def rolled_back():
            job=native.job();window=native.window()
            if (job.get('id')==failed_id and job.get('state') in ('attention','failed') and
                    window and window['pid']!=updated['pid'] and digest(root/'app/python_app.py')==before_entry):
                progress=read(root.parent/('.helene-update-'+failed_id+'.progress.json'))
                if progress.get('rollback_completed') is True:
                    return window,job
        restored,job=wait(rolled_back,300,'failed startup rollback + actual previous native reopen')
        native.capture(restored,'rollback-native')
        assert invoke(restored,'app_info')['version']==inputs['version']
        assert facts(root,profile)==expected
        result['steps']['failed_next_rollback']={'passed':True,'job_id':failed_id,
            'job_state':job['state'],'entry_restored_sha256':before_entry,'synthetic_not_release':True,
            'synthetic_version':inputs['broken_version'],'synthetic_sha256':inputs['broken']['sha256']}
        save()
        # A rolled-back attention job is still owned work, not an automatic retry.
        # Cancel through the production control; only observed terminal producers
        # may settle it and permit a later unrelated admission.
        rollback_owner=wait(native.session,20,'restored session owner')
        rpc(rollback_owner,'cancel_job')
        wait(lambda:native.job().get('id')==failed_id and native.job().get('state')=='cancelled',
             45,'cancelled rollback attention settles after producer exit')
        # Portable move occurs only after explicit Exit and exact process stop.
        native.exit()
        previous_profile=read(profile/'memory/.control/profile-identity.json')
        moved=root.with_name('Helene moved Unicode-\u03b1');root.rename(moved)
        native.root=moved;root=moved
        moved_window=native.launch();native.capture(moved_window,'portable-move-native')
        assert facts(root,profile)==expected
        assert read(profile/'memory/.control/profile-identity.json')==previous_profile
        result['steps']['portable_move']={'passed':True,'profile_identity':previous_profile['id']}
        save()
        # Modified-preserve MUST NOT receive fake battery/review approval.
        altered=selected_code(root)/'acceptance_authored_runtime.py'
        altered.write_text('VALUE = "synthetic authored runtime delta"\n',encoding='utf8')
        authored_sha=digest(altered)
        response=invoke(moved_window,'update_start',{'url':inputs['candidate']['url'],
            'sha256':inputs['candidate']['sha256'],'sourceMode':'preserve'})
        assert response['state']=='admitted'
        blocked_id=response['job']['id']
        blockage=wait(lambda:modified_blockage(native,blocked_id),240,
            'modified-preserve waits for real semantic author without applying')
        job=blockage['job']
        assert digest(altered)==authored_sha and invoke(moved_window,'app_info')['version']==inputs['version']
        assert native.window()['pid']==moved_window['pid']
        result['steps']['modified_preserve_blocked']={'passed_refusal':True,'job_id':blocked_id,
            'state':job['state'],'error':job.get('error',''),'authored_sha256':authored_sha,
            'waiting_sources':blockage['waiting_sources'],
            'not_claimed':'successful authored-source merge or independent panel'}
        save()
        # Owner-visible Stop remains available without the window and is retained;
        # cancellation is never cleared to obtain another update attempt.
        native.detach(moved_window)
        owner=wait(native.session,15,'owner without window')
        rpc(owner,'cancel_job')
        wait(lambda:native.job().get('cancel_requested') is True,15,'durable stop intent')
        result['steps']['stop_without_window']={'passed':True,'job_id':blocked_id}
        rpc(owner,'exit');wait(lambda:not alive(owner),45,'explicit host Exit')
        result['steps']['explicit_exit']={'passed':True}
        result['status']='passed_native_subset'
        save()
    except BaseException as exc:
        result['status']='failed';result['error']=type(exc).__name__+': '+str(exc)
        save();raise
    finally:
        cleanup=native.finish();result.update(cleanup)
        if cleanup['forced_cleanup'] or cleanup['cleanup_errors']:
            result['status']='failed';result['cleanup_required']=True
        save()
    if result['status']!='passed_native_subset':
        raise RuntimeError('Native acceptance did not complete cleanly; read result')
    print('MAC230_NATIVE_SUBSET_PASS; full verification and modified-agent success remain separate',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    exercise(p.parse_args())


if __name__=='__main__':
    main()
