"""Mac migration contracts; portable tests mock only OS-specific admission.
Native lease/process/window consumers live in macos_migration_pilot.py.
"""
from contextlib import ExitStack, nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from localharness import app_migration, mac_migration as m, profile_paths
from mac_migrate import MigrationWindow


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE).decode().strip()


def fixture(base):
    old=base/'Old Mac Helene';new=base/'New Helene';data=base/'New data'
    (old/'data/memory').mkdir(parents=True);(old/'tree').mkdir();new.mkdir()
    (old/'data/memory/entry.md').write_text('synthetic memory')
    (old/'tree/agent.py').write_text('original=1\n')
    (old/'helene.json').write_text(json.dumps({'mode':'local','tree':'data','code':'tree','runner':'app/localharness/runner.py','setup_complete':False,'voice':{'speak':False}}))
    (new/'helene.json').write_text('{"setup_complete":false}')
    (new/'python-app.json').write_text('{"target":"macos-arm64"}')
    return old,new,data


class MigrationTests(unittest.TestCase):
    def platform(self):
        stack=ExitStack()
        stack.enter_context(patch.object(m.sys,'platform','darwin'))
        stack.enter_context(patch('localharness.python_platform.require_runtime'))
        stack.enter_context(patch.object(m,'lease',side_effect=lambda p:nullcontext()))
        stack.enter_context(patch.object(m,'quiescent'))
        stack.enter_context(patch.object(m,'integrations_quiet'))
        return stack

    def test_actual_copy_keeps_git_index_dirty_untracked_and_independent_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder))
            git(old/'tree','init');git(old/'tree','add','agent.py')
            git(old/'tree','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','base')
            (old/'tree/agent.py').write_text('staged=2\n');git(old/'tree','add','agent.py')
            (old/'tree/agent.py').write_text('unstaged=3\n');(old/'tree/untracked.py').write_text('unique=4\n')
            before=git(old/'tree','status','--porcelain');index=(old/'tree/.git/index').read_bytes()
            with self.platform():result=m.Session(new).prepare(old,data,closed=True)
            note=json.loads((new/'python-migration.json').read_text())
            selected=Path(note['source_paths'][0]['selected'])
            self.assertEqual(git(selected,'status','--porcelain'),before)
            self.assertEqual((selected/'.git/index').read_bytes(),index)
            self.assertEqual((selected/'agent.py').read_text(),'unstaged=3\n')
            self.assertEqual((selected/'untracked.py').read_text(),'unique=4\n')
            memory=Path(note['data_paths'][0])/'memory/entry.md'
            self.assertFalse(memory.samefile(old/'data/memory/entry.md'))
            self.assertEqual(result['state'],'prepared');self.assertFalse(result['startup_proof'])
            self.assertEqual((old/'tree/.git/index').read_bytes(),index)

    def test_actual_external_data_and_code_are_copied_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);old,new,data=fixture(base);external=base/'external';external.mkdir()
            (external/'agent.py').write_text('external_self_edit=1')
            value=json.loads((old/'helene.json').read_text());value.update(tree=str(external),code=str(external))
            (old/'helene.json').write_text(json.dumps(value))
            with self.platform():m.Session(new).prepare(old,data,closed=True)
            value=json.loads((new/'helene.json').read_text())
            self.assertNotEqual(Path(value['code']),external)
            self.assertEqual((Path(value['code'])/'agent.py').read_text(),'external_self_edit=1')
            self.assertTrue(Path(value['tree']).resolve().is_relative_to(data.resolve()))

    def test_explicit_closure_and_real_census_refusal_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));session=m.Session(new)
            with self.assertRaisesRegex(ValueError,'Explicitly'):session.prepare(old,data)
            with self.platform(),patch.object(m,'quiescent',side_effect=RuntimeError('still alive')):
                with self.assertRaisesRegex(RuntimeError,'alive'):session.prepare(old,data,closed=True)
            self.assertFalse(data.exists());self.assertEqual(json.loads((new/'helene.json').read_text()),{'setup_complete':False})
            self.assertEqual(session.status()['handoff']['state'],'failed')

    def test_failed_partial_copy_resumes_exact_paths_and_preserves_prior_template(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));original=app_migration.preserve_source;calls=0
            def fail_once(source,destination,progress=None):
                nonlocal calls
                calls+=1
                if calls==1:
                    destination.mkdir(parents=True);(destination/'partial').write_text('retained failure')
                    raise OSError('synthetic full disk')
                return original(source,destination,progress)
            with self.platform(),patch.object(app_migration,'preserve_source',side_effect=fail_once):
                with self.assertRaisesRegex(OSError,'full disk'):m.Session(new).prepare(old,data,closed=True)
            prior=json.loads((new/'python-migration.json').read_text());self.assertEqual(prior['state'],'preserving')
            self.assertTrue((new/'helene.json').is_file())
            with self.platform():
                with self.assertRaisesRegex(ValueError,'different selected paths'):m.Session(new).prepare(old,data/'other',closed=True)
                result=m.Session(new).prepare(old,data,closed=True)
            self.assertEqual(result['state'],'prepared')
            self.assertTrue(list(data.rglob('partial')))
            self.assertTrue(list((new/'.migration-attempts').rglob('helene.json')))

    def test_failed_backup_restores_template_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));before=(new/'helene.json').read_bytes()
            with self.platform(),patch.object(app_migration,'snapshot',side_effect=OSError('backup failure')):
                with self.assertRaisesRegex(OSError,'backup failure'):m.Session(new).prepare(old,data,closed=True)
            self.assertEqual((new/'helene.json').read_bytes(),before)
            with self.platform():self.assertEqual(m.Session(new).prepare(old,data,closed=True)['state'],'prepared')

    def test_killed_snapshot_reopens_same_ui_command_without_journal(self):
        # Real process death skips Session.prepare's except/finally handlers.
        # Only native admission is mocked; ZIP snapshot and all copies are real.
        import time
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);old,new,data=fixture(base)
            git(old/'tree','init');git(old/'tree','add','agent.py')
            git(old/'tree','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','base')
            (old/'tree/agent.py').write_text('staged=2\n');git(old/'tree','add','agent.py')
            (old/'tree/agent.py').write_text('unstaged=3\n')
            (old/'tree/untracked.py').write_text('unique=4\n')
            before={p.relative_to(old):p.read_bytes() for p in old.rglob('*') if p.is_file()}
            template=(new/'helene.json').read_bytes();ready=base/'snapshot-paused'
            driver=r'''
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from t_mac_migration_2410 import MigrationTests,MigrationWindow
from localharness import essential_backup
old,new,data,ready=map(Path,sys.argv[2:])
original=essential_backup.inventory
def paused(*args,**kwargs):
    for index,item in enumerate(original(*args,**kwargs)):
        yield item
        if index==0:
            ready.write_text('first real ZIP member written; no journal yet')
            time.sleep(120)
essential_backup.inventory=paused
with MigrationTests().platform():
    # The killed phase exercises preservation, not HTTP binding/DNS startup.
    # Recovery below still invokes the actual new MigrationWindow consumer.
    from localharness.mac_migration import Session
    Session(new).prepare(old,data,closed=True)
'''
            process=subprocess.Popen([sys.executable,'-c',driver,str(Path(__file__).resolve().parent),str(old),str(new),str(data),str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                end=time.monotonic()+30
                while not ready.exists() and process.poll() is None and time.monotonic()<end:time.sleep(.05)
                if not ready.exists():
                    if process.poll() is None:process.kill()
                    stdout,stderr=process.communicate(timeout=15)
                    self.fail('snapshot pause not reached; child='+str(process.returncode)+' stdout='+stdout+' stderr='+stderr)
                self.assertFalse((new/'helene.json').exists())
                self.assertFalse((new/'python-migration.json').exists())
                self.assertTrue(list(data.rglob('*.zip.tmp')))
                process.kill();process.wait(15)
                self.assertNotEqual(process.returncode,0)
            finally:
                if process.poll() is None:process.kill()
                stdout,stderr=process.communicate(timeout=15)
            self.assertEqual({p.relative_to(old):p.read_bytes() for p in old.rglob('*') if p.is_file()},before)
            # Recreate the actual UI host, without restoring files by hand.
            with self.platform():
                app=MigrationWindow(new);app.serve()
                try:
                    self.assertEqual(app.invoke('migration_status',{})['state'],'not_prepared')
                    result=app.invoke('migration_prepare',{'old':str(old),'data':str(data),'closed':True})
                finally:app.close()
            self.assertEqual(result['state'],'prepared')
            self.assertEqual((new/'.mac-migration-template.json').read_bytes(),template)
            note=json.loads((new/'python-migration.json').read_text())
            selected=Path(note['source_paths'][0]['selected'])
            for name in ('.git/HEAD','.git/index','agent.py','untracked.py'):
                self.assertEqual((selected/name).read_bytes(),before[Path('tree')/name])
            self.assertEqual((Path(note['data_paths'][0])/'memory/entry.md').read_bytes(),before[Path('data/memory/entry.md')])
            self.assertEqual({p.relative_to(old):p.read_bytes() for p in old.rglob('*') if p.is_file()},before)

    def test_interrupted_exception_restore_keeps_complete_retry_template(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));before=(new/'helene.json').read_bytes()
            original=Path.write_bytes
            def interrupted(path,content):
                if path.name=='.helene-template-restore.tmp':
                    original(path,content[:5]);raise OSError('restore interrupted')
                return original(path,content)
            with self.platform(),patch.object(app_migration,'snapshot',side_effect=OSError('backup failed')),patch.object(Path,'write_bytes',interrupted):
                with self.assertRaisesRegex(OSError,'restore interrupted'):m.Session(new).prepare(old,data,closed=True)
            self.assertFalse((new/'helene.json').exists())
            self.assertEqual((new/'.mac-migration-template.json').read_bytes(),before)
            with self.platform():self.assertEqual(m.Session(new).prepare(old,data,closed=True)['state'],'prepared')

    def test_posix_former_path_mapping_is_component_bound(self):
        value={'tree':'/Users/old/Helene/data','code':'/Users/old/Helene/tree','app':'app/deskapp.py'}
        mapped=profile_paths.relocate_config(value,{'/Users/old/Helene':'/tmp/Transferred Helene'})
        self.assertEqual(mapped['tree'],str(Path('/tmp/Transferred Helene/data').resolve()))
        sibling=profile_paths.relocate_config({'tree':'/Users/old/Helene2/data'},{'/Users/old/Helene':'/tmp/copy'})
        self.assertEqual(sibling['tree'],'/Users/old/Helene2/data')

    def test_start_failure_keeps_prepared_copy_and_retry_launch_requires_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));session=m.Session(new)
            with self.platform():session.prepare(old,data,closed=True)
            with self.platform(),patch.object(m.subprocess,'Popen',side_effect=OSError('no entry')):
                with self.assertRaisesRegex(OSError,'no entry'):session.start()
            self.assertEqual(session.status()['state'],'prepared')
            child=Mock(pid=4321);child.poll.return_value=None
            with self.platform(),patch.object(m.subprocess,'Popen',return_value=child) as start:
                result=session.start();self.assertFalse(result['startup_proof'])
                self.assertIn('--migration',start.call_args.args[0])
                with self.assertRaisesRegex(RuntimeError,'already starting'):session.start()
            self.assertTrue(old.is_dir())

    def test_http_consumer_renders_ui_and_authenticates_commands(self):
        import urllib.request,urllib.error
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'app/resources').mkdir(parents=True)
            (root/'app/resources/mac-migration.html').write_bytes((Path(__file__).resolve().parents[1]/'resources/mac-migration.html').read_bytes())
            app=MigrationWindow(root);app.serve()
            try:
                page=urllib.request.urlopen(app.origin).read().decode()
                self.assertIn('migration_prepare',page);self.assertIn('X-Helene-Window',page)
                request=urllib.request.Request(app.origin+'/__python__/invoke',data=b'{"command":"migration_status"}',headers={'Content-Type':'application/json','X-Helene-Window':app.token})
                self.assertEqual(json.load(urllib.request.urlopen(request))['result']['state'],'not_prepared')
                request=urllib.request.Request(app.origin+'/__python__/invoke',data=b'{"command":"migration_status"}')
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(request)
            finally:app.close()

    def test_inventory_admission_covers_external_custom_script_and_git_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);old,new,data=fixture(base);custom=base/'custom-app';custom.mkdir()
            (custom/'entry.py').write_text('pass')
            cfg=json.loads((old/'helene.json').read_text());cfg['app']=str(custom/'entry.py')
            (old/'helene.json').write_text(json.dumps(cfg))
            roots=m.inspect(old,new,data)[-1]
            self.assertIn(custom.resolve(),roots)
            self.assertTrue(m.references(str(custom/'entry.py'),roots))
            self.assertFalse(m.references(str(base/'custom-app-other/entry.py'),roots))

    @unittest.skipIf(os.name=='nt','Native POSIX symlink test; Windows privileges vary')
    def test_external_memory_link_is_refused_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);old,new,data=fixture(base);outside=base/'outside';outside.mkdir()
            (old/'data/memory/link').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'source link'):m.inspect(old,new,data)
            self.assertFalse(data.exists())

    def test_zombie_observation_is_not_a_live_owner_but_denial_remains_unknown(self):
        import psutil
        process=Mock();process.uids.return_value=Mock(real=123)
        process.exe.side_effect=psutil.AccessDenied(pid=123)
        process.status.return_value=psutil.STATUS_ZOMBIE
        with patch.object(m.sys,'platform','darwin'),patch.object(m.os,'getuid',return_value=123,create=True),patch.object(psutil,'pids',return_value=[123]),patch.object(psutil,'Process',return_value=process):
            m.quiescent([Path('/selected')])
            process.status.return_value=psutil.STATUS_SLEEPING
            with self.assertRaisesRegex(RuntimeError,'closure is unverified'):m.quiescent([Path('/selected')])

    def test_start_timeout_is_explicit_without_killing_live_process(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new,data=fixture(Path(folder));session=m.Session(new)
            with self.platform():session.prepare(old,data,closed=True)
            child=Mock(pid=4321);child.poll.return_value=None
            with self.platform(),patch.object(m.subprocess,'Popen',return_value=child):session.start()
            session.start_time-=151
            self.assertEqual(session.status()['handoff']['state'],'launch_unconfirmed')
            child.kill.assert_not_called();child.terminate.assert_not_called()


if __name__=='__main__':unittest.main()
