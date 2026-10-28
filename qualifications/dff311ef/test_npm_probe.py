"""Helper control-flow unit tests. Fake npm is NOT native/npm qualification."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import mac_npm_probe as probe

class Probe(unittest.TestCase):
    def test_fresh_offline_projects_and_no_ambient_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);inputs=root/'inputs';out=root/'out';calls=[]
            for name in probe.ROOTS:
                p=inputs/name;p.mkdir(parents=True)
                (p/'package.json').write_text('{}')
                (p/'package-lock.json').write_text(json.dumps({'packages':{'':{},'node_modules/f':{'resolved':'https://registry.npmjs.org/f/-/f-1.tgz','integrity':'sha512-fixture'}}}))
            def fake(command,**kwargs):
                self.assertNotIn('GITHUB_TOKEN',kwargs['env'])
                self.assertNotEqual(kwargs['env']['NPM_CONFIG_USERCONFIG'],kwargs['env']['NPM_CONFIG_GLOBALCONFIG'])
                calls.append((command,Path(kwargs['cwd'])))
                return SimpleNamespace(returncode=0)
            with patch.object(sys,'argv',['probe','--inputs',str(inputs),'--out',str(out)]),patch.dict(os.environ,{'GITHUB_TOKEN':'PRIVATE_FIXTURE'}),patch.object(probe.shutil,'which',return_value=sys.executable),patch.object(probe.subprocess,'run',side_effect=fake),patch('builtins.print'):
                probe.main()
            self.assertEqual(len(calls),8)
            self.assertTrue(all('--offline' not in row[0] for row in calls[:4]))
            self.assertTrue(all('--offline' in row[0] for row in calls[4:]))
            self.assertTrue(set(row[1] for row in calls[:4]).isdisjoint(row[1] for row in calls[4:]))
            self.assertTrue(json.loads((out/'receipt.json').read_text())['complete'])
            self.assertTrue(all(not row[1].exists() for row in calls))

if __name__=='__main__':unittest.main()
