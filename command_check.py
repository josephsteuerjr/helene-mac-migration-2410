from pathlib import Path
import hashlib,json,platform,sys,unittest
import test_command_process_2810 as tests
with open('command-tests.log','w') as stream:
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.CommandCustody))
proof={'passed':result.wasSuccessful(),'tests':result.testsRun,'skipped':len(result.skipped),'platform':platform.platform(),'python':sys.version,
       'source_sha256':hashlib.sha256(Path('command_process.py').read_bytes()).hexdigest(),
       'test_sha256':hashlib.sha256(Path('test_command_process_2810.py').read_bytes()).hexdigest()}
Path('command-proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof));raise SystemExit(0 if result.wasSuccessful() else 1)
