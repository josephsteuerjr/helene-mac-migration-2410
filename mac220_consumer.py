"""Native Darwin qualification, synthetic configured profile; never owner data.

The Cocoa app must show its real window before the separate Chromium DOM
check. The successful update must also record its native UI confirmation before
that browser is opened. Control-file publication alone is only window-shown,
not renderer-ready proof. Neither driver calls python_ready. Stop stays set
in the synthetic HOME: no model, account, relay or physical input is qualified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

from mac220_prepare import OLD_SHA, check_archive, digest, broken_archive


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding='utf-8')


def wait(test, seconds=180):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        found = test()
        if found:return found
        time.sleep(.15)
    raise TimeoutError('Condition not observed: ' + getattr(test, '__name__', 'condition'))


def invoke(row, command, args=None):
    request = urllib.request.Request(row['origin'] + '/__python__/invoke',
        data=json.dumps({'command': command, 'args': args or {}}).encode(),
        headers={'Content-Type':'application/json', 'X-Helene-Window':row['token']})
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.load(response)['result']


def repository_facts(source):
    """Resolve refs and reachable commit objects; HEAD-file text is not history."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args])
    head = git('rev-parse', '--verify', 'HEAD').decode().strip()
    git('cat-file', '-e', head + '^{commit}')
    refs = git('for-each-ref', '--format=%(refname) %(objectname)').decode().splitlines()
    history = git('rev-list', '--all').decode().splitlines()
    for commit in history:git('cat-file', '-e', commit + '^{commit}')
    return {'head':head, 'refs':sorted(refs), 'reachable_commits':sorted(history)}


def main():
    parser = argparse.ArgumentParser()
    for name in ('base', 'candidate', 'work', 'evidence'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--candidate-sha', required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise RuntimeError('Requires actual macOS ARM64, never an emulation')
    import psutil
    import Quartz
    from playwright.sync_api import sync_playwright
    check_archive(args.base, OLD_SHA)
    check_archive(args.candidate, args.candidate_sha)
    work = args.work.resolve()
    root = work / 'program/Helene'
    if not (root / 'Helene.app/Contents/MacOS/Helene').is_file():
        raise ValueError('Run verified extraction first')
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    home = work / 'home';home.mkdir()
    stop_file = home / '.local/state/helene/stop.json'
    stop_file.parent.mkdir(parents=True)
    dump(stop_file, {'reason':'synthetic native qualification; do not start cognition'})
    env = dict(os.environ, HOME=str(home), PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    code = work / 'authored';shutil.copytree(root / 'tree', code)
    profile = work / 'profile'
    (profile / 'memory').mkdir(parents=True)
    (profile / 'soul').mkdir()
    (profile / 'memory/history.txt').write_text('Synthetic history\n', encoding='utf-8')
    (profile / 'soul/identity.md').write_text('Synthetic identity\n', encoding='utf-8')
    def git(*command):
        return subprocess.check_output(['git', '-c', 'user.name=Fixture', '-c',
            'user.email=fixture@example.invalid', '-C', str(code), *command])
    (code / 'fixture_author.py').write_text('base = 1\n')
    git('init', '-q');git('add', 'fixture_author.py');git('commit', '-q', '-m', 'synthetic baseline')
    (code / 'fixture_author.py').write_text('staged = 2\n');git('add', 'fixture_author.py')
    (code / 'fixture_author.py').write_text('unstaged = 3\n')
    (code / 'fixture_untracked.py').write_text('untracked = 4\n')
    config = json.loads((root / 'helene.json').read_text())
    config.update(tree=str(profile), code=str(code), setup_complete=True,
                  fixture_custom={'retained':True}, relay={'enabled':False}, voice={'speak':False})
    dump(root / 'helene.json', config)
    def facts():
        cfg = json.loads((root / 'helene.json').read_text())
        data = Path(cfg['tree']);source = Path(cfg['code'])
        return {'memory':digest(data/'memory/history.txt'),
                'identity':digest(data/'soul/identity.md'),
                'git_head':digest(source/'.git/HEAD'), 'git_index':digest(source/'.git/index'),
                'git_history':repository_facts(source),
                'author':digest(source/'fixture_author.py'),
                'untracked':digest(source/'fixture_untracked.py'),
                'fixture_custom':cfg['fixture_custom'], 'tree':str(data.resolve()),
                'source_mode':(source/'fixture_author.py').stat().st_mode & 0o777,
                'stop_sha256':digest(stop_file)}
    expected = facts()
    result = {'platform':platform.platform(), 'machine':platform.machine(),
        'old_sha256':OLD_SHA, 'candidate_sha256':args.candidate_sha,
        'steps':{}, 'synthetic_stop_kept':True, 'no_cognition_or_auth':True,
        'native_proof':'Cocoa window-shown control + Quartz window + screenshot; successful update UI confirmation before separate browser',
        'now_proof':'separate clean Chromium view of same production origin, not Cocoa DOM'}
    known = {};samples = [];monitor_stop = threading.Event();lock = threading.RLock()
    def remember(pid):
        try:
            p = psutil.Process(pid)
            with lock:known[pid] = p.create_time()
        except psutil.NoSuchProcess:pass
    def control():
        for path in root.glob('.python-window-*.json'):
            try:
                row = json.loads(path.read_text())
                p = psutil.Process(row['pid'])
                if Path(row['root']).resolve() == root and p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    remember(row['pid']);return row
            except (OSError, ValueError, psutil.NoSuchProcess):pass
    def windows():
        with lock:ids = set(known)
        return [{'pid':int(r[Quartz.kCGWindowOwnerPID]), 'id':int(r[Quartz.kCGWindowNumber]),
                 'title':str(r.get(Quartz.kCGWindowName,'')), 'bounds':dict(r[Quartz.kCGWindowBounds])}
                for r in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, 0)
                if int(r[Quartz.kCGWindowOwnerPID]) in ids and int(r.get(Quartz.kCGWindowLayer, 0)) == 0]
    def monitor():
        while not monitor_stop.wait(.2):
            with lock:current = list(known.items())
            for pid, birth in current:
                try:
                    p = psutil.Process(pid)
                    if p.create_time() == birth:
                        for child in p.children(recursive=True):remember(child.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):pass
            control();samples.append({'at':time.time(), 'windows':windows()})
    def capture(row, name):
        observed = wait(lambda:next((w for w in windows() if w['pid'] == row['pid']), None), 60)
        subprocess.run(['screencapture', '-x', '-l', str(observed['id']), str(evidence/(name+'.png'))], check=True, timeout=15)
        dump(evidence/(name+'-window.json'), observed)
        return observed
    def settled_old(process, pid):
        if process is not None:
            process.wait(timeout=60)
        else:
            wait(lambda:not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE, 60)
    log = (evidence/'native-app.log').open('ab')
    thread = threading.Thread(target=monitor, daemon=True);thread.start()
    app = None
    try:
        app = subprocess.Popen([str(root/'Helene.app/Contents/MacOS/Helene'), '--root', str(root)],
            cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        remember(app.pid)
        first = wait(control);capture(first, 'old211-native')
        assert invoke(first, 'app_info')['version'] == '2.1.1'
        local = root.parent / args.candidate.name
        os.link(args.candidate, local)
        for broken, label in ((False, 'update220'), (True, 'rollback-next')):
            incoming = broken_archive(args.candidate, root.parent/'Helene-2.2.1-synthetic-broken.zip') if broken else local
            prior = wait(control)
            before_entry = digest(root/'app/python_app.py')
            response = invoke(prior, 'update_install', {'path':str(incoming), 'forceExtensions':False})
            # Persist no local control token. The normal bridge result is safe fixture metadata.
            result['steps'][label] = {'response':response, 'started_at':time.time()}
            dump(evidence/'result.json', result)
            if response.get('state') == 'needs_resolution':
                raise RuntimeError('Actual old consumer requested source resolution: ' + json.dumps(response))
            old_process = psutil.Process(prior['pid'])
            assert old_process.is_running() and old_process.status() != psutil.STATUS_ZOMBIE, 'Old app exited before admission observation'
            result['steps'][label]['old_alive_at_admission'] = {'pid':prior['pid'], 'birth':old_process.create_time(), 'observed_at':time.time()}
            remember(response['updater_pid'])
            admitted = json.loads((Path(response['staging'])/'updater-admitted.json').read_text())
            assert admitted['pid'] == response['updater_pid'] and Path(admitted['target']).resolve() == root
            # Old 211 bridge need not return a progress path; its NEW helper still creates one.
            capture({'pid':response['updater_pid']}, label+'-observer')
            settled_old(app, prior['pid']);app = None
            if broken:
                wait(lambda:'previous program restored' in Path(response['log']).read_text(errors='replace'), 240)
                assert digest(root/'app/python_app.py') == before_entry
            else:
                def complete():
                    path = root/'python-migration.json'
                    if path.is_file():
                        note = json.loads(path.read_text())
                        if note.get('state') == 'completed':return note
                note = wait(complete, 240)
                assert note.get('startup_proof'), note
                result['steps'][label]['native_startup_confirmation_before_external_browser'] = note
            current = wait(lambda:(lambda r:r if r and r['pid'] != prior['pid'] else None)(control()))
            capture(current, label+'-native')
            assert invoke(current, 'app_info')['version'] == '2.2.0'
            assert facts() == expected, (facts(), expected)
            # No synthetic bridge injection: the normal built UI reads configured state.
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width':1100, 'height':780})
                errors = [];failed_requests = []
                page.on('pageerror', lambda error:errors.append(str(error)))
                from urllib.parse import urlsplit
                page.on('requestfailed', lambda request:failed_requests.append({'path':urlsplit(request.url).path,'reason':request.failure}))
                idle = None
                try:
                    page.goto(current['origin'], wait_until='domcontentloaded')
                    page.locator('[data-page="now"] .now .now-idle').wait_for(state='visible', timeout=30000)
                    idle = page.locator('[data-page="now"] .now-idle').inner_text()
                    assert idle.strip() == 'Подключение…', idle  # synthetic Stop deliberately leaves channel disconnected
                    page.get_by_text('Здесь появятся действия и результаты', exact=True).wait_for(state='visible')
                    assert not errors, errors
                finally:
                    # Retain failure evidence too. Never save page HTML or bridge
                    # configuration: its script contains the synthetic control token.
                    page.screenshot(path=str(evidence/(label+'-now-browser.png')))
                    body = page.locator('body').inner_text()
                    state = page.evaluate("""() => ({pages:[...document.querySelectorAll('[data-page]')].map(x=>({id:x.dataset.page,hidden:x.hidden})),needs_local_setup:window.DESK_CONFIG_OVERRIDE?.needs_local_setup,shell:window.__HELENE__?.shell})""")
                    dump(evidence/(label+'-browser-observation.json'), {'pageerrors':errors,'failed_requests':failed_requests,'idle':idle,'body_text':body,'state':state,'screenshots_visually_judged':False,'expected_disconnected_channel':True})
                    capture(current, label+'-native-after-browser')
                    browser.close()
            result['steps'][label].update(passed=True, admission_before_old_exit=True,
                version='2.2.0', profile_git_exact=True, native_window_observed=True,
                configured_now_rendered_browser=True, screenshots_visually_judged=False, ended_at=time.time())
            dump(evidence/'result.json', result)
            wait(lambda:not any(w['pid'] == response['updater_pid'] for w in windows()), 45)
        row = wait(control)
        invoke(row, 'python_window', {'action':'exit', 'relaunch':False})
        wait(lambda:control() is None, 40)
        wait(lambda:not psutil.pid_exists(row['pid']) or psutil.Process(row['pid']).status() == psutil.STATUS_ZOMBIE, 40)
        result.update(passed=True, explicit_close=True)
    except BaseException as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        try:
            row = control()
            if row:invoke(row, 'python_window', {'action':'exit', 'relaunch':False})
        except Exception as exc:result['close_error'] = str(exc)
        time.sleep(2)
        monitor_stop.set();thread.join(5)
        residual = []
        with lock:current = list(known.items())
        for pid, birth in current:
            try:
                p = psutil.Process(pid)
                if p.create_time() == birth and p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    residual.append({'pid':pid, 'birth':birth});p.terminate()
                    try:p.wait(timeout=10)
                    except psutil.TimeoutExpired:p.kill();p.wait(timeout=10)
            except psutil.NoSuchProcess:pass
        result['cleanup_signalled'] = residual
        if residual:result.update(passed=False, cleanup_required=True)
        log.close()
        dump(evidence/'window-samples.json', samples)
        for path in [*root.parent.glob('helene-update-*.log'), *root.glob('python-update-*.log')]:
            shutil.copy2(path, evidence/path.name)
        dump(evidence/'result.json', result)
    if not result.get('passed'):raise RuntimeError('Native fixture required forced cleanup; inspect retained result')
    print('MAC220_NATIVE_UPDATE_ROLLBACK_PASS', flush=True)

if __name__ == '__main__':main()
