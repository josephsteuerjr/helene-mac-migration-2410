"""Native desktop update/rollback with an isolated synthetic profile; no account.

The updater choice uses its actual Python bridge callback; screenshots record
native presentation separately. This does not claim physical pointer input.
"""
from pathlib import Path
import argparse,hashlib,json,os,platform,shutil,socket,subprocess,sys,time,urllib.request,zipfile
import psutil

def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,value):Path(p).write_text(json.dumps(value,ensure_ascii=True,indent=2),encoding='utf8')
def wait(fn,seconds=180):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.2)
    raise TimeoutError('Condition not observed: '+str(fn))
def receipt_json(path):
    deadline=time.monotonic()+2
    while True:
        try:return json.loads(Path(path).read_text(encoding='utf8'))
        except PermissionError:
            if time.monotonic()>=deadline:raise
            time.sleep(.025)
def extract(archive,parent):
    assert not parent.exists();parent.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and z.testzip() is None
        for info in z.infolist():
            path=parent/info.filename;assert path.resolve().is_relative_to(parent.resolve()) and info.filename.startswith('Helene/')
            if info.is_dir():path.mkdir(parents=True,exist_ok=True);continue
            path.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as src,path.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
            if os.name!='nt':path.chmod((info.external_attr>>16)&0o777 or 0o644)
    return parent/'Helene'
def broken(source,path):
    with zipfile.ZipFile(source) as z:
        changes={};meta=json.loads(z.read('Helene/python-app.json'));meta.update(version='2.2.10',synthetic_broken_fixture=True)
        changes['Helene/python-app.json']=json.dumps(meta).encode()
        changes['Helene/app/python_app.py']=b'import os;os._exit(73)\n'
        if 'Helene/source-admission.json' in z.namelist():
            row=json.loads(z.read('Helene/source-admission.json'));row['target_version']='2.2.10';changes['Helene/source-admission.json']=json.dumps(row).encode()
        upstream=json.loads(z.read('Helene/code-upstream.json'));upstream['version']='2.2.10';changes['Helene/code-upstream.json']=json.dumps(upstream).encode()
        inputs=json.loads(z.read('Helene/source-inputs.json'))
        inputs['files']['python_app.py']=hashlib.sha256(changes['Helene/app/python_app.py']).hexdigest();changes['Helene/source-inputs.json']=json.dumps(inputs).encode()
        manifest=json.loads(z.read('Helene/python-package-files.json'));manifest['version']='2.2.10'
        for name,data in changes.items():
            rel=name.removeprefix('Helene/')
            if rel in manifest['files']:manifest['files'][rel]=hashlib.sha256(data).hexdigest()
        changes['Helene/python-package-files.json']=json.dumps(manifest).encode()
        with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as out:
            for info in z.infolist():out.writestr(info,changes.get(info.filename,z.read(info)))
    return path

def main():
    p=argparse.ArgumentParser()
    for name in ('base','candidate','work','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--candidate-sha',required=True);p.add_argument('--base-sha',required=True);p.add_argument('--mode',choices=('preserve','clean'),required=True)
    a=p.parse_args();assert digest(a.base)==a.base_sha and digest(a.candidate)==a.candidate_sha
    work=a.work.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=False);root=extract(a.base,work/'program')
    runtime=lambda r:r/('runtime/python.exe' if os.name=='nt' else 'runtime/bin/python3')
    python=runtime(root);home=work/'home';home.mkdir();profile=work/'profile';(profile/'memory').mkdir(parents=True);(profile/'soul').mkdir()
    env=dict(os.environ,HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home/'AppData/Local'),APPDATA=str(home/'AppData/Roaming'),
        PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1')
    env.pop('PYTHONDONTWRITEBYTECODE',None);env.pop('PYTHONPYCACHEPREFIX',None)
    for key in ('QTWEBENGINE_DISABLE_SANDBOX','QTWEBENGINE_CHROMIUM_FLAGS','LIBGL_ALWAYS_SOFTWARE'):env.pop(key,None)
    def run(cmd,timeout=120):
        r=subprocess.run(list(map(str,cmd)),env=env,capture_output=True,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode:raise RuntimeError(r.stderr.decode('utf8','replace')[-6000:])
        return r.stdout.decode('utf8','replace')
    if (root/'source-admission.json').is_file():
        run([python,'-s','-c',"import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from localharness.source_admission import activate;activate(Path(sys.argv[2]))",root/'app',root])
    code=work/'authored';shutil.copytree(root/'tree',code,ignore=shutil.ignore_patterns('__pycache__'))
    (code/'native_owner_fixture.py').write_text('authored_value = 2\n',encoding='utf8')
    (code/'native_owner_untracked.py').write_text('untracked_value = 3\n',encoding='utf8')
    run(['git','-C',code,'init','--quiet']);run(['git','-C',code,'add','native_owner_fixture.py'])
    run(['git','-C',code,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','owner fixture'])
    (code/'native_owner_fixture.py').write_text('authored_value = 4\n',encoding='utf8');run(['git','-C',code,'add','native_owner_fixture.py']);(code/'native_owner_fixture.py').write_text('authored_value = 5\n',encoding='utf8')
    (profile/'memory/history.txt').write_text('Synthetic native profile history\n',encoding='utf8');(profile/'soul/identity.md').write_text('Synthetic identity\n',encoding='utf8')
    llm=profile/'memory/llm.json';save(llm,{'frameworks':{},'roles':{}})
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    config={'mode':'local','python':str(python),'app':'app/deskapp.py','runner':'','tree':str(profile),'code':str(code),'port':port,
        'setup_complete':True,'fixture_custom':{'retained':True},'relay':{'enabled':False},'voice':{'speak':False},'model':{'framework':'openai','model':'','key':''}}
    save(root/'helene.json',config)
    if os.name=='nt':
        # Known Folders ignore LOCALAPPDATA overrides. Do not write the real
        # owner's latch: this fixture instead disables runner and relay in cfg.
        stop=home/'no-cognition-config.json';save(stop,{'runner':'','relay_enabled':False})
    else:
        stop_text=run([python,'-s','-c',"import sys;sys.path.insert(0,sys.argv[1]);from localharness import owner_stop;print(owner_stop.client_file())",root/'app']).strip().splitlines()[-1]
        stop=Path(stop_text);assert stop.resolve().is_relative_to(home.resolve()),stop;stop.parent.mkdir(parents=True,exist_ok=True);save(stop,{'reason':'synthetic native qualification; no cognition'})
    expected={'history':digest(profile/'memory/history.txt'),'identity':digest(profile/'soul/identity.md'),'llm':digest(llm),
        'stop':digest(stop),'original_author':digest(code/'native_owner_fixture.py'),'original_untracked':digest(code/'native_owner_untracked.py'),
        'original_git_index':digest(code/'.git/index'),'original_git_head':run(['git','-C',code,'rev-parse','HEAD']).strip()}
    known={};app=None;log=(out/'native-app.log').open('ab');result={'platform':platform.platform(),'machine':platform.machine(),'mode':a.mode,
        'base_sha256':a.base_sha,'candidate_sha256':a.candidate_sha,'no_cognition_or_real_account':True,'choice_interaction':'actual updater Python bridge callback; native presentation recorded separately','steps':{}}
    def remember(pid):
        try:
            process=psutil.Process(pid);known[pid]=process.create_time()
            for child in process.children(recursive=True):known[child.pid]=child.create_time()
        except psutil.NoSuchProcess:pass
    def control():
        for path in root.glob('.python-window-*.json'):
            try:
                row=json.loads(path.read_text(encoding='utf8'));process=psutil.Process(row['pid'])
                if Path(row['root']).resolve()==root and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE:
                    remember(row['pid']);return row
            except (OSError,ValueError,psutil.NoSuchProcess):pass
    def invoke(row,command,args=None):
        req=urllib.request.Request(row['origin']+'/__python__/invoke',data=json.dumps({'command':command,'args':args or {}}).encode(),headers={'Content-Type':'application/json','X-Helene-Window':row['token']})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=300) as response:return json.load(response)['result']
    def capture(row,name):
        time.sleep(2)  # native control receipt precedes web font/label painting
        if sys.platform=='darwin':
            import Quartz
            def find():return next((w for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0) if int(w[Quartz.kCGWindowOwnerPID])==row['pid'] and int(w.get(Quartz.kCGWindowLayer,0))==0),None)
            window=wait(find,45);number=int(window[Quartz.kCGWindowNumber]);subprocess.run(['screencapture','-x','-l',str(number),str(out/(name+'.png'))],check=True,timeout=15)
        elif sys.platform.startswith('linux'):
            run([python,'-c',"from PySide6.QtGui import QGuiApplication;import sys;a=QGuiApplication([]);assert a.primaryScreen().grabWindow(0).save(sys.argv[1])",out/(name+'.png')])
    def verify():
        got={'history':digest(profile/'memory/history.txt'),'identity':digest(profile/'soul/identity.md'),'llm':digest(llm),'stop':digest(stop),
            'original_author':digest(code/'native_owner_fixture.py'),'original_untracked':digest(code/'native_owner_untracked.py'),
            'original_git_index':digest(code/'.git/index'),'original_git_head':run(['git','-C',code,'rev-parse','HEAD']).strip()}
        assert got==expected,(got,expected)
        cfg=json.loads((root/'helene.json').read_text(encoding='utf8'));assert cfg['tree']==str(profile) and cfg['fixture_custom']==config['fixture_custom']
        assert cfg['model']==config['model'] and cfg['relay']==config['relay'] and cfg['voice']==config['voice']
        selected=Path(cfg['code'])
        if a.mode=='preserve':
            assert digest(selected/'native_owner_fixture.py')==expected['original_author'] and digest(selected/'native_owner_untracked.py')==expected['original_untracked']
        else:
            assert not (selected/'native_owner_fixture.py').exists() and not (selected/'native_owner_untracked.py').exists()
            probe="import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from localharness.source_merge import inventory;p=Path(sys.argv[2]);r=Path(sys.argv[3]);assert inventory(p)==json.loads((r/'code-upstream.json').read_text())['files'];print('PRISTINE_SOURCE_EXACT')"
            assert 'PRISTINE_SOURCE_EXACT' in run([runtime(root),'-s','-c',probe,root/'app',selected,root])
            run(['git','-C',selected,'rev-parse','--verify','HEAD'])
        return got
    try:
        entry=([root/'Helene.app/Contents/MacOS/Helene','--root',root] if sys.platform=='darwin' else [python,root/'app/python_app.py','--root',root])
        app=subprocess.Popen(list(map(str,entry)),cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));remember(app.pid)
        first=wait(control);capture(first,'baseline-native');initial=invoke(first,'app_info')['version']
        local=root.parent/a.candidate.name;os.link(a.candidate,local)
        bad=broken(a.candidate,root.parent/'Helene-2.2.10-synthetic-broken.zip')
        for failed,label,archive in ((False,'update',local),(True,'rollback-next',bad)):
            previous=wait(control);version=invoke(previous,'app_info')['version'];before_entry=digest(root/'app/python_app.py')
            params={'path':str(archive),'forceExtensions':False}
            if version!='2.1.1':params['sourceMode']=a.mode
            response=invoke(previous,'update_install',params);assert response.get('updater_pid'),response;remember(response['updater_pid'])
            receipt=Path(response['staging']).with_name(Path(response['staging']).name+'.progress.json');chosen=version!='2.1.1';deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                if receipt.is_file():
                    progress=receipt_json(receipt)
                    if progress.get('stage')=='choosing_source' and not chosen:
                        time.sleep(.8)  # allow the existing350ms renderer poll to paint
                        capture({'pid':response['updater_pid']},label+'-source-choice')
                        incoming=Path(progress['source_choice']['new'])
                        run([runtime(incoming),'-s','-c',"import sys;sys.path.insert(0,sys.argv[1]);from localharness.update_window import choose_source;choose_source(sys.argv[2],sys.argv[3])",incoming/'app',receipt,a.mode]);chosen=True
                    if progress.get('stage') in ('completed','failed','needs_resolution','cancelled'):break
                remember(response['updater_pid']);time.sleep(.25)
            else:raise TimeoutError('Native update did not reach a terminal receipt')
            save(out/(label+'-progress.json'),progress)
            if failed:
                assert progress['stage']=='failed' and progress.get('rollback_completed'),progress
                assert any(s['stage']=='switching' for s in progress['stages']) and any(s['stage']=='rollback' for s in progress['stages'])
                assert digest(root/'app/python_app.py')==before_entry
            else:assert progress['stage']=='completed',progress
            current=wait(lambda:(lambda r:r if r and r['pid']!=previous['pid'] else None)(control()));capture(current,label+'-native')
            assert invoke(current,'app_info')['version']=='2.2.10';facts=verify()
            result['steps'][label]={'passed':True,'version':'2.2.10','original_profile_and_code_exact':True,'facts':facts,'source_policy':a.mode,'native_pid':current['pid']}
            save(out/'result.json',result);app=None
        row=wait(control);invoke(row,'python_window',{'action':'exit','relaunch':False});wait(lambda:control() is None,45)
        result.update(passed=True,explicit_close=True,baseline_version=initial)
    except BaseException as exc:result['error']=f'{type(exc).__name__}: {exc}';raise
    finally:
        try:
            row=control()
            if row:invoke(row,'python_window',{'action':'exit','relaunch':False})
        except Exception as exc:result['close_error']=str(exc)
        time.sleep(3);residual=[]
        for pid,birth in list(known.items()):
            try:
                process=psutil.Process(pid)
                if process.create_time()==birth and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE:
                    residual.append(pid);process.terminate()
                    try:process.wait(10)
                    except psutil.TimeoutExpired:process.kill();process.wait(10)
            except psutil.NoSuchProcess:pass
        result['cleanup_signalled']=residual
        if residual:result['passed']=False
        log.close();save(out/'result.json',result)
        for path in [*root.parent.glob('helene-update-*.log'),*root.glob('python-update-*.log')]:shutil.copy2(path,out/path.name)
    assert result.get('passed'),result
    print('NATIVE_MODE_UPDATE_ROLLBACK_PASS',sys.platform,a.mode)

if __name__=='__main__':main()
