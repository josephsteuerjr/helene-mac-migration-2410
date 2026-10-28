"""Local protocol/fixture checks, never a native Mac or product acceptance PASS."""
import ast
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import ModuleType, SimpleNamespace
import sys
import os
import zipfile

import mac230_prepare as prepare
import mac230_full as full
import mac230_consumer as consumer
from mac230_consumer import install_git_fixture, repository_facts


def encoded(value):
    return json.dumps(value,sort_keys=True).encode()


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def write_zip(self, entries):
        path=self.root/'fixture.zip'
        with zipfile.ZipFile(path,'w') as output:
            for name,value in entries.items():
                info=zipfile.ZipInfo(name);info.create_system=3
                info.external_attr=(stat.S_IFREG|0o755)<<16
                output.writestr(info,value)
        return path

    def valid_manifest(self):
        row={'name':'program.zip','url':'https://example.invalid/program.zip',
             'sha256':'a'*64,'bytes':12}
        return {'format':prepare.FORMAT,'target':prepare.TARGET,'version':'2.3.0-rc.1',
            'base_version':'2.2.17','base':dict(row),'candidate':dict(row),
            'feed_url':'https://api.github.com/repos/example/project/releases/tags/v2.3.0-rc.1',
            'source_inputs_sha256':'b'*64,'verification_bundle_sha256':'c'*64}

    def test_syntax_all_helpers_and_embedded_full_script(self):
        root=Path(__file__).resolve().parent
        for name in ('mac230_prepare.py','mac230_consumer.py','mac230_full.py'):
            tree=ast.parse((root/name).read_text(encoding='utf8'),filename=name)
            compile(tree,name,'exec')
            for item in ast.walk(tree):
                if (isinstance(item,ast.Assign) and isinstance(item.value,ast.Constant)
                        and isinstance(item.value.value,str) and 'from localharness' in item.value.value):
                    compile(item.value.value,'embedded packaged-runtime adapter','exec')

    def test_manifest_exact_identity_and_rc(self):
        path=self.root/'inputs.json';path.write_bytes(encoded(self.valid_manifest()))
        self.assertEqual(prepare.manifest(path)['version'],'2.3.0-rc.1')
        value=self.valid_manifest();value['version']='latest';path.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError,'parent-frozen'):
            prepare.manifest(path)

    def test_manifest_rejects_missing_bundle_or_source_identity_as_declared(self):
        value=self.valid_manifest();value['source_inputs_sha256']='';path=self.root/'inputs.json'
        path.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError,'source-inputs'):
            prepare.manifest(path)

    def test_no_authenticated_or_downgraded_input_urls(self):
        for address in ('http://example.invalid/a','https://user:password@example.invalid/a',
                        'https://example.invalid/a#fragment','file:///tmp/a'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                prepare.https_url(address)

    def test_archive_hash_and_nonzero_size_are_not_interchangeable(self):
        path=self.root/'input';path.write_bytes(b'actual bytes')
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        prepare.check_archive(path,sha,path.stat().st_size)
        with self.assertRaisesRegex(ValueError,'byte length'):
            prepare.check_archive(path,sha,1)
        with self.assertRaisesRegex(ValueError,'SHA256'):
            prepare.check_archive(path,'b'*64)

    def test_mode_preserving_extract_and_refuse_overwrite(self):
        path=self.write_zip({'Helene/runtime/bin/python3':b'synthetic executable'})
        root=prepare.extract(path,self.root/'unpack')
        self.assertEqual((root/'runtime/bin/python3').read_bytes(),b'synthetic executable')
        if __import__('os').name!='nt':
            self.assertTrue((root/'runtime/bin/python3').stat().st_mode&0o111)
        with self.assertRaisesRegex(ValueError,'must be new'):
            prepare.extract(path,self.root/'unpack')

    def test_traversal_and_casefold_collision_refuse_before_extraction(self):
        for index,names in enumerate(({'Helene/../escape':b'x'},
            {'Helene/a':b'x','Helene/A':b'y'},{'Other/a':b'x'})):
            path=self.write_zip(names);target=self.root/('bad'+str(index))
            with self.assertRaisesRegex(ValueError,'Unsafe'):
                prepare.extract(path,target)
            self.assertFalse(target.exists())

    def test_symlink_refused_before_extraction(self):
        path=self.root/'link.zip'
        with zipfile.ZipFile(path,'w') as out:
            info=zipfile.ZipInfo('Helene/link');info.external_attr=(stat.S_IFLNK|0o777)<<16
            out.writestr(info,'elsewhere')
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            prepare.extract(path,self.root/'link-out')

    def test_broken_next_is_declared_entry_fault_not_new_version_or_forged_state(self):
        original={'version':'2.3.0-rc.1','target':prepare.TARGET}
        path=self.write_zip({'Helene/python-app.json':encoded(original),
            'Helene/app/python_app.py':b'print("app")\n',
            'Helene/python-package-files.json':encoded({'files':{'app/python_app.py':'oldsha'}}),
            'Helene/cancel.json':b'preserved cancellation evidence'})
        before=prepare.digest(path)
        broken=prepare.broken_archive(path,self.root/'broken.zip')
        self.assertEqual(prepare.digest(path),before)
        with zipfile.ZipFile(broken) as z:
            self.assertEqual(json.loads(z.read('Helene/python-app.json')),original)
            code=z.read('Helene/app/python_app.py')
            self.assertIn(b'os._exit(73)',code)
            inv=json.loads(z.read('Helene/python-package-files.json'))
            self.assertEqual(inv['files']['app/python_app.py'],hashlib.sha256(code).hexdigest())
            self.assertEqual(z.read('Helene/cancel.json'),b'preserved cancellation evidence')
            self.assertNotIn('Helene/python-migration.json',z.namelist())

    def test_git_fixture_has_real_reachable_history_and_both_worktree_states(self):
        code=self.root/'code';code.mkdir();(code/'agent.py').write_text('ORIGINAL = True\n')
        install_git_fixture(code)
        facts=repository_facts(code)
        self.assertEqual(len(facts['reachable_commits']),1)
        self.assertEqual(len(facts['refs']),2)
        status=subprocess.check_output(['git','-C',str(code),'status','--porcelain=v1']).decode()
        self.assertIn('MM workspace/acceptance.txt',status)
        self.assertIn('workspace/untracked.txt',status)
        self.assertEqual((code/'agent.py').read_text(),'ORIGINAL = True\n')

    def test_cache_zip_has_only_explicit_cache_root_and_preserves_bytes(self):
        path=self.write_zip({'cache/_cacache/content-v2/a':b'integrity-pinned content'})
        target=prepare.extract(path,self.root/'npm',top='cache')
        self.assertEqual((target/'_cacache/content-v2/a').read_bytes(),b'integrity-pinned content')
        with self.assertRaises(ValueError):prepare.extract(path,self.root/'wrong-default')

    def test_cache_manifest_requires_exact_supported_archive(self):
        value=self.valid_manifest();value['npm_cache']=dict(value['base'],name='npm-cache.zip')
        path=self.root/'input.json';path.write_bytes(encoded(value))
        self.assertEqual(prepare.manifest(path)['npm_cache']['name'],'npm-cache.zip')
        value['npm_cache']['name']='npm-cache.tar.gz';path.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError,'explicit ZIP'):prepare.manifest(path)

    def test_executor_paths_bind_actual_runtime_native_pair_and_owned_cache(self):
        program=self.root/'program';work=self.root/'work'
        for name in ('runtime/bin/python3','helene-body','helene-bridge'):
            p=program/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode())
        with self.assertRaisesRegex(ValueError,'owned npm cache'):full.executor_for(program,work)
        (work/'npm-cache/cache').mkdir(parents=True)
        with patch.object(full.shutil,'which',side_effect=lambda n:'/explicit/'+n):
            result=full.executor_for(program,work)
        self.assertEqual(result['python'],str((program/'runtime/bin/python3').resolve()))
        self.assertEqual(result['npm_config_cache'],str((work/'npm-cache/cache').resolve()))
        self.assertEqual(set(result['native_env']),{'HELENE_BODY_DIR','HELENE_BODY_BIN'})
        self.assertEqual(result['native_files'],{str((program/n).resolve()):prepare.digest(program/n)
            for n in ('helene-body','helene-bridge')})
        self.assertNotIn('native_lanes',result)

    def execute_full_control(self,script,validate_error=False):
        # Fake API-contract harness, not execution or a verdict about the product.
        program=self.root/'program';plan=self.root/'plan';output=self.root/'full.json';executor=self.root/'executor.json'
        program.mkdir();(program/'python-package-files.json').write_bytes(b'before')
        executor.write_bytes(encoded({'npm_config_cache':'explicit-owned-cache'}))
        events=[];state={'composition':False}
        def read(path):
            path=Path(path)
            if path.name=='python-app.json':return {'version':'2.3.0-rc.1','verification_bundle_sha256':'b'*64}
            if path.name=='source-admission-state.json':return {'state':'ready'}
            return json.loads(path.read_text('utf8'))
        def write(path,value):
            path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded(value))
        def activate(root):
            events.append('activate');(root/'python-package-files.json').write_bytes(b'after');return True
        def create(a,l,b,directory,*,exe):
            self.assertEqual((a,l,b),(program/'tree',)*3);events.append('merge');directory.mkdir();return {'plan':True}
        def composition(directory,op):events.append('composition');state['composition']=True
        def battery_prepare(op,directory,harness,stopped):
            if not state['composition']:raise ValueError('composition missing')
            events.append('prepare');self.assertFalse(stopped());op['battery']={'key':'observed'};return {'sources':'observed'}
        def validate(op,directory):
            events.append('validate')
            if validate_error:raise ValueError('real gate refusal retained')
            return {'full_pass':True,'origin':'fake-contract-only'}
        package=ModuleType('localharness');notice=ModuleType('localharness.package_notice');notice.read=read;notice.write=write
        package.source_admission=SimpleNamespace(activate=activate)
        package.source_merge=SimpleNamespace(create=create,executable=lambda p:'explicit-git',input_signature=lambda p:'input',candidate_signature=lambda p:'candidate')
        package.source_verification_bundle=SimpleNamespace(digest=prepare.digest,load=lambda *a:{'lanes':[{'id':'all-trusted-lanes'}]})
        package.update_composition=SimpleNamespace(prepare=composition,signature=lambda *a:'compound')
        package.source_update_battery=SimpleNamespace(prepare=battery_prepare,validate=validate)
        oldpath=sys.path[:]
        try:
            with patch.dict(sys.modules,{'localharness':package,'localharness.package_notice':notice}),patch.object(sys,'argv',['adapter',str(program),str(plan),str(output),str(executor)]):
                if validate_error:
                    with self.assertRaisesRegex(ValueError,'gate refusal'):exec(compile(script,'full-contract','exec'),{})
                else:exec(compile(script,'full-contract','exec'),{})
        finally:sys.path[:]=oldpath
        return events,read(output),read(output.parent/'source-admission-observation.json')

    def test_embedded_full_api_sequence_and_activation_observation(self):
        events,result,admission=self.execute_full_control(full.FULL_SCRIPT)
        self.assertEqual(events,['activate','merge','composition','prepare','validate'])
        self.assertEqual(result['composition_sha256'],'compound')
        self.assertTrue(result['full_pass'])
        self.assertNotEqual(admission['package_manifest_before'],admission['package_manifest_after'])
        self.assertEqual(admission['state'],{'state':'ready'})

    def test_embedded_full_refusal_never_becomes_pass(self):
        events,result,_=self.execute_full_control(full.FULL_SCRIPT,validate_error=True)
        self.assertEqual(events[-1],'validate');self.assertFalse(result['full_pass'])
        self.assertIn('gate refusal',result['error']);self.assertEqual(result['battery'],{'key':'observed'})

    def test_old_activation_precedes_pristine_code_copy_and_old_api_is_not_new_start(self):
        tree=ast.parse((Path(__file__).parent/'mac230_consumer.py').read_text('utf8'))
        exercise=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='exercise')
        calls=[n for n in ast.walk(exercise) if isinstance(n,ast.Call)]
        activation=next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='activate_old')
        copying=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='copytree')
        self.assertLess(activation.lineno,copying.lineno)
        oldcommands=[n.args[1].value for n in calls if isinstance(n.func,ast.Name) and n.func.id=='invoke'
            and isinstance(n.args[0],ast.Name) and n.args[0].id=='first' and isinstance(n.args[1],ast.Constant)]
        self.assertIn('update_download',oldcommands);self.assertIn('update_install',oldcommands)
        self.assertNotIn('update_start',oldcommands);self.assertNotIn('migration_install',oldcommands)
        self.assertIn("selected_code(root)/'acceptance_authored_runtime.py'",(Path(__file__).parent/'mac230_consumer.py').read_text('utf8'))

    def test_isolation_does_not_inherit_owner_credentials_or_model_profile(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'do-not-inherit','ANTHROPIC_API_KEY':'do-not-inherit','HELENE_CONFIG':'private','AGENTS':'private'},clear=True):
            env=consumer.isolated_environment(self.root)
        self.assertFalse(set(env)&{'OPENAI_API_KEY','ANTHROPIC_API_KEY','HELENE_CONFIG','AGENTS'})
        self.assertEqual(env['HOME'],str(self.root))

    def test_git_facts_preserve_workspace_status_without_claiming_unchanged_upstream_code(self):
        code=self.root/'code';code.mkdir();(code/'agent.py').write_text('OLD=True\n')
        install_git_fixture(code);before=repository_facts(code)
        (code/'agent.py').write_text('UPSTREAM=True\n');self.assertEqual(repository_facts(code),before)
        (code/'workspace/new-untracked.txt').write_text('new owner file\n')
        self.assertNotEqual(repository_facts(code)['workspace_status_sha256'],before['workspace_status_sha256'])

    def test_modified_preserve_observes_real_waiting_agent_not_fabricated_attention(self):
        root=self.root/'program';profile=self.root/'profile';stage=self.root/'.helene-update-job'
        directory=profile/'memory/.source-updates/plan'
        (stage/'Helene').mkdir(parents=True);directory.mkdir(parents=True)
        prepare.dump(stage/'Helene/code-transition-plan.json',{'plans':[{'directory':str(directory)}]})
        prepare.dump(directory/'pipeline.json',{'state':'waiting_agent','resolution_owner':'agent','candidate_sha256':'exact'})
        job={'id':'job','staging':str(stage),'state':'running'}
        native=SimpleNamespace(root=root,profile=profile,job=lambda:job)
        result=consumer.modified_blockage(native,'job')
        self.assertEqual(result['job']['state'],'running')
        self.assertEqual(result['waiting_sources'][0]['state'],'waiting_agent')
        self.assertFalse(result['waiting_sources'][0]['review_clear'])
        self.assertIsNone(consumer.modified_blockage(native,'other'))
        prepare.dump(directory/'pipeline.json',{'state':'ready_to_apply','resolution_owner':'agent','review_clear':True})
        self.assertIsNone(consumer.modified_blockage(native,'job'))

    def test_native_driver_never_injects_ready_or_frozen_review_success(self):
        text=(Path(__file__).parent/'mac230_consumer.py').read_text(encoding='utf8')
        tree=ast.parse(text)
        for call in (n for n in ast.walk(tree) if isinstance(n,ast.Call)):
            if isinstance(call.func,ast.Name) and call.func.id=='invoke':
                values=[n.value for n in call.args if isinstance(n,ast.Constant)]
                self.assertNotIn('python_ready',values)
        self.assertNotIn('ready_to_apply',text)
        self.assertNotIn('cancel_requested\'] = False',text)


if __name__=='__main__':
    unittest.main()
