"""Prepare a private public-registry-only native npm cache for exact input locks."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse,hashlib,json,os,shutil,subprocess,tempfile

ROOTS=('app','mobile','miniapp','remote')
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.inputs=a.inputs.resolve();a.out=a.out.resolve()
    if a.out.exists():raise ValueError('Keep earlier preparation separately')
    a.out.mkdir(parents=True);cache=a.out/'cache';cache.mkdir()
    inputs={}
    for name in ROOTS:
        for filename in ('package.json','package-lock.json'):
            path=a.inputs/name/filename;inputs[name+'/'+filename]=digest(path)
        lock=json.loads((a.inputs/name/'package-lock.json').read_text('utf-8-sig'))
        for row in lock.get('packages',{}).values():
            if not row.get('resolved'):continue
            u=urlsplit(row['resolved'])
            if u.scheme!='https' or u.hostname!='registry.npmjs.org' or u.username or u.password or not row.get('integrity'):
                raise ValueError('Not a public integrity-locked registry input')
    npm=shutil.which('npm');node=shutil.which('node')
    if not npm or not node:raise ValueError('Native Node/npm unavailable')
    receipt={'scope':'native dependency/cache preparation only; not product/full battery','inputs':inputs,
             'tools':{'npm':digest(npm),'node':digest(node)},'rows':[],'complete':False}
    with tempfile.TemporaryDirectory(prefix='helene-npm-inputs-') as temp:
        base=Path(temp);home=base/'home';home.mkdir()
        user=base/'user.npmrc';glob=base/'global.npmrc';user.write_text('');glob.write_text('')
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT')}
        env.update(HOME=str(home),USERPROFILE=str(home),CI='true',npm_config_cache=str(cache),
                   NPM_CONFIG_USERCONFIG=str(user),NPM_CONFIG_GLOBALCONFIG=str(glob),
                   npm_config_audit='false',npm_config_fund='false')
        for offline in (False,True):
            phase='offline' if offline else 'online'
            for name in ROOTS:
                project=base/phase/name;project.mkdir(parents=True)
                for filename in ('package.json','package-lock.json'):shutil.copyfile(a.inputs/name/filename,project/filename)
                cmd=[npm,'ci','--ignore-scripts']+(['--offline'] if offline else [])
                log=a.out/(phase+'-'+name+'.log')
                with log.open('wb') as stream:done=subprocess.run(cmd,cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
                receipt['rows'].append({'phase':phase,'project':name,'exit':done.returncode,'log_sha256':digest(log)})
                (a.out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
                if done.returncode:raise RuntimeError('npm ci failed; retained '+str(log))
                assert digest(project/'package-lock.json')==inputs[name+'/package-lock.json']
                # Only completed owned CI copies; cache+logs+original immutable inputs remain.
                shutil.rmtree(project)
    receipt['complete']=True
    receipt['cache_files']=sum(1 for q in cache.rglob('*') if q.is_file())
    receipt['cache_bytes']=sum(q.stat().st_size for q in cache.rglob('*') if q.is_file())
    (a.out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
