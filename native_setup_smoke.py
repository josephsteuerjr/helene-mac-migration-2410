"""Exact-package first launch and fresh transaction, using a temporary Desktop.

Only the shortcut destination is adapted in memory in the fixture process.
Program files, startup owner, bridge, bundled runtime and profile are real.
No provider, account, service registration or owner installation is modified.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,urllib.request,zipfile
import psutil
import urllib.error

def wait(fn,seconds=120):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=fn()
        if result:return result
        time.sleep(.2)
    raise TimeoutError('Native setup condition not observed')

def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=True,indent=2),encoding='utf-8')

def rpc(row,command,args=None):
    request=urllib.request.Request(row['origin']+'/__python__/invoke',data=json.dumps({'command':command,'args':args or {}}).encode(),headers={'Content-Type':'application/json','X-Helene-Window':row['token']})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=180) as response:
            result=json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode('utf-8','replace')) from error
    if 'error' in result:raise RuntimeError(result['error'])
    return result['result']

def descriptor(root,kind):
    for path in root.glob('.python-'+kind+'-*.json'):
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            process=psutil.Process(value['pid'])
            if Path(value['root']).resolve()==root and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE:return value
        except (OSError,ValueError,KeyError,psutil.NoSuchProcess):pass

def screenshot(row,path,python,env):
    if sys.platform=='darwin':
        import Quartz
        windows=Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0)
        window=next(w for w in windows if int(w[Quartz.kCGWindowOwnerPID])==row['pid'] and int(w.get(Quartz.kCGWindowLayer,0))==0)
        subprocess.run(['screencapture','-x','-l',str(window[Quartz.kCGWindowNumber]),str(path)],check=True,timeout=15)
    elif os.name=='nt':
        import ctypes
        from ctypes import wintypes
        import struct
        from PIL import Image
        handles=[];u=ctypes.windll.user32;g=ctypes.windll.gdi32
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        def collect(hwnd,_):
            pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==row['pid'] and u.IsWindowVisible(hwnd):handles.append(hwnd)
            return True
        u.EnumWindows(callback(collect),0)
        rect=wintypes.RECT();assert handles;u.GetWindowRect(handles[0],ctypes.byref(rect));width,height=rect.right-rect.left,rect.bottom-rect.top
        u.GetWindowDC.argtypes=[wintypes.HWND];u.GetWindowDC.restype=wintypes.HDC
        g.CreateCompatibleDC.argtypes=[wintypes.HDC];g.CreateCompatibleDC.restype=wintypes.HDC
        g.CreateCompatibleBitmap.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int];g.CreateCompatibleBitmap.restype=wintypes.HBITMAP
        g.SelectObject.argtypes=[wintypes.HDC,wintypes.HANDLE];g.SelectObject.restype=wintypes.HANDLE
        g.GetDIBits.argtypes=[wintypes.HDC,wintypes.HBITMAP,wintypes.UINT,wintypes.UINT,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
        u.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT]
        dc=u.GetWindowDC(handles[0]);memory=g.CreateCompatibleDC(dc);bitmap=g.CreateCompatibleBitmap(dc,width,height);previous=g.SelectObject(memory,bitmap)
        try:
            assert u.PrintWindow(handles[0],memory,2),'Own-window capture failed'
            info=ctypes.create_string_buffer(struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0))
            data=ctypes.create_string_buffer(width*height*4)
            assert g.GetDIBits(memory,bitmap,0,height,data,info,0)==height
            Image.frombytes('RGB',(width,height),data.raw,'raw','BGRX').save(path)
        finally:
            g.SelectObject(memory,previous)
            g.DeleteObject.argtypes=[wintypes.HANDLE];g.DeleteDC.argtypes=[wintypes.HDC];u.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
            g.DeleteObject(bitmap);g.DeleteDC(memory);u.ReleaseDC(handles[0],dc)
    else:
        done=subprocess.run([str(python),'-c','from PySide6.QtGui import QGuiApplication;import sys;a=QGuiApplication([]);assert a.primaryScreen().grabWindow(0).save(sys.argv[1])',str(path)],env=env,capture_output=True,timeout=15)
        assert done.returncode==0,done.stderr

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=True);out=args.evidence;out.mkdir(parents=True,exist_ok=True)
    assert hashlib.file_digest(args.archive.open('rb'),'sha256').hexdigest()==args.sha256
    temporary=Path(tempfile.mkdtemp(prefix='native-setup-211-',dir=args.work)).resolve();root=temporary/'Helene'
    result={'archive_sha256':args.sha256,'platform':sys.platform,'passed':False,'shortcut_destination':'temporary fixture Desktop; in-memory adapter only','owner_installation_modified':False}
    log=(out/'native-app.log').open('ab');processes=[]
    try:
        with zipfile.ZipFile(args.archive) as z:
            assert len(z.namelist())==len(set(z.namelist()))
            for info in z.infolist():
                path=temporary/info.filename;assert path.resolve().is_relative_to(temporary) and info.filename.startswith('Helene/')
                if info.is_dir():path.mkdir(parents=True,exist_ok=True);continue
                path.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as source,path.open('xb') as target:shutil.copyfileobj(source,target,1024*1024)
                if os.name!='nt':path.chmod((info.external_attr>>16)&0o777 or 0o644)
        python=root/('runtime/pythonw.exe' if os.name=='nt' else 'runtime/bin/python3')
        home=temporary/'fixture-home';home.mkdir();desktop=home/'Desktop';desktop.mkdir()
        env=dict(os.environ,HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home/'Local'),APPDATA=str(home/'Roaming'),ProgramFiles=str(home/'Programs'),PYTHONUTF8='1',PYTHONIOENCODING='utf-8',QT_NO_GLIB='1')
        for key in ('QTWEBENGINE_DISABLE_SANDBOX','QTWEBENGINE_CHROMIUM_FLAGS','LIBGL_ALWAYS_SOFTWARE'):env.pop(key,None)
        native=([str(root/'helene.exe')] if os.name=='nt' else [str(root/'Helene.app/Contents/MacOS/Helene'),'--root',str(root)] if sys.platform=='darwin' else [str(root/'Start Helene.sh')])
        processes.append(subprocess.Popen(native,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
        first=wait(lambda:descriptor(root,'migrator'));defaults=rpc(first,'migration_defaults');assert defaults['version']=='2.2.11'
        time.sleep(1);screenshot(first,out/'first-launch.png',python,env);result['first_launch_wizard']=True
        rpc(first,'python_window',{'action':'close'});processes[-1].wait(timeout=30)
        wait(lambda:descriptor(root,'migrator') is None,30)
        # Scope the real shortcut writer to this fixture; all lifecycle code and startup fences remain unchanged.
        entry=temporary/'accept_setup.py'
        entry.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom localharness import migration_lifecycle as lifecycle\noriginal=lifecycle.implementation.install_shortcuts\ndef shortcut(new,folder=None,**kwargs):return original(new,Path(sys.argv[3]),**kwargs)\nlifecycle.implementation.install_shortcuts=shortcut\nfrom helene_setup import main\nraise SystemExit(main(['--root',sys.argv[2]]))\n",encoding='utf-8')
        processes.append(subprocess.Popen([str(python),'-s',str(entry),str(root/'app'),str(root),str(desktop)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
        wizard=wait(lambda:descriptor(root,'migrator'));data=temporary/'agent-data'
        installed=rpc(wizard,'migration_install',{'mode':'fresh','target':str(root),'data':str(data),'sourceMode':'clean','removeOld':False})
        assert installed['state']=='completed' and installed.get('startup_proof'),installed
        app=wait(lambda:descriptor(root,'window'));assert rpc(app,'app_info')['version']=='2.2.11'
        cfg=json.loads((root/'helene.json').read_text(encoding='utf-8'));assert Path(cfg['tree']).resolve()==data
        assert cfg.get('setup_complete') is False and data.is_dir()
        time.sleep(1);screenshot(app,out/'new-application.png',python,env)
        result.update(fresh_transaction=True,startup_proof=installed['startup_proof'],data_folder_selected=True,shortcuts=installed.get('shortcuts'),passed=True)
        rpc(wizard,'python_window',{'action':'close'});rpc(app,'python_window',{'action':'exit'})
    except BaseException as error:
        result['error']=str(error);raise
    finally:
        for name in ('migration-start.log','python-migration.json','migration-ready.json','engine-startup-error.log'):
            if (root/name).is_file():shutil.copy2(root/name,out/name)
        save(out/'result.json',result)
        # Only processes rooted in the newly-created disposable fixture may be stopped.
        owned=[]
        for process in psutil.process_iter(['pid','exe','cmdline']):
            try:
                values=[process.info['exe'],*(process.info['cmdline'] or [])]
                if process.pid!=os.getpid() and any(value and Path(value).is_absolute() and Path(value).resolve().is_relative_to(temporary) for value in values):process.terminate();owned.append(process)
            except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):pass
        _,alive=psutil.wait_procs(owned,timeout=10)
        for process in alive:
            try:process.kill()
            except psutil.NoSuchProcess:pass
        psutil.wait_procs(alive,timeout=5)
        for child in processes:
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        log.close()
        assert temporary.is_relative_to(args.work.resolve()) and temporary.name.startswith('native-setup-211-')
        shutil.rmtree(temporary)  # disposable fixture only; bounded logs/journal were retained above
    print('NATIVE_SETUP_PASS',sys.platform,flush=True)

if __name__=='__main__':main()
