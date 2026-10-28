"""Assemble explicit native dependency overlay from pip's pinned resolution.
No donor mutations; removed paths bind exact donor SHA, no globs at apply.
"""
from pathlib import Path,PurePosixPath
import argparse,csv,email.parser,hashlib,json,os,shutil,zipfile
p=argparse.ArgumentParser();p.add_argument('--donor',type=Path,required=True);p.add_argument('--donor-sha',required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--platform',required=True);p.add_argument('--pip-report',type=Path,required=True);a=p.parse_args()
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def encoded(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def norm(s):return s.lower().replace('_','-').replace('.','-')
assert digest(a.donor)==a.donor_sha;assert not a.output.exists();a.output.mkdir(parents=True)
site=os.environ['HELENE_OVERLAY_SITE_PREFIX'];assert site.startswith('runtime/') and site.endswith('/') and '..' not in PurePosixPath(site).parts
newdist={}
for meta in a.site.glob('*.dist-info/METADATA'):
 value=email.parser.Parser().parsestr(meta.read_text());newdist[norm(value['Name'])]={'version':value['Version'],'metadata':meta.parent.name}
assert newdist['cryptography']['version']=='48.0.1';assert newdist['pytest']['version']=='8.4.2';assert newdist['aiogram']['version']=='3.31.0'
files={}
for source in sorted(a.site.rglob('*')):
 if not source.is_file():continue
 relative=source.relative_to(a.site)
 if relative.parts[0]=='bin' or '__pycache__' in relative.parts or source.suffix=='.pyc':continue
 name=site+relative.as_posix();q=a.output/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,q);mode='100755' if source.stat().st_mode&0o111 else '100644';q.chmod(0o755 if mode=='100755' else 0o644);files[name]={'sha256':digest(q),'size':q.stat().st_size,'mode':mode}
removed={};oldversions={}
with zipfile.ZipFile(a.donor) as z:
 names=set(z.namelist())
 for name in sorted(names):
  if not name.startswith('Helene/'+site) or not name.endswith('.dist-info/METADATA'):continue
  value=email.parser.Parser().parsestr(z.read(name).decode('utf8'));key=norm(value['Name'])
  if key not in newdist:continue
  oldversions[key]=value['Version'];distroot=name.rsplit('/',1)[0];record=distroot+'/RECORD';assert record in names,(key,'missing donor RECORD')
  for row in csv.reader(z.read(record).decode('utf8').splitlines()):
   relative=PurePosixPath(row[0]);joined=PurePosixPath(site)/relative
   parts=[]
   for part in joined.parts:
    if part=='..':assert parts;parts.pop()
    elif part!='.':parts.append(part)
   local='/'.join(parts)
   assert local.startswith('runtime/'),local
   oldname='Helene/'+local
   if oldname in names and local not in files and not oldname.endswith('/'):
    removed[local]=hashlib.sha256(z.read(oldname)).hexdigest()
  # Runtime-generated old .pyc belongs to a replaced named package too.
  roots={PurePosixPath(row[0]).parts[0] for row in csv.reader(z.read(record).decode('utf8').splitlines()) if row and not row[0].startswith('../')}
  for oldname in names:
   local=oldname.removeprefix('Helene/')
   if local.startswith(site) and '__pycache__' in PurePosixPath(local).parts and PurePosixPath(local).relative_to(site).parts[0] in roots and local not in files and not oldname.endswith('/'):
    removed[local]=hashlib.sha256(z.read(oldname)).hexdigest()
assert not set(removed)&set(files)
report=json.loads(a.pip_report.read_text());manifest={'format':'helene-portable-runtime-overlay.v1','platform':a.platform,'inputs':{'donor_sha256':a.donor_sha,'requirements':['cryptography==48.0.1','pytest==8.4.2','aiogram==3.31.0'],'resolved_packages':newdist,'replaced_versions':oldversions,'pip_report_sha256':digest(a.pip_report),'distributions':[{'name':r['metadata']['name'],'version':r['metadata']['version'],'archive_info':r['download_info']['archive_info']} for r in report['install']]},'files':files,'remove':dict(sorted(removed.items()))}
(a.output/'manifest.json').write_bytes(encoded(manifest));print(json.dumps({'root':str(a.output),'sha256':digest(a.output/'manifest.json'),'files':len(files),'remove':len(removed),'resolved_packages':{n:r['version'] for n,r in newdist.items()},'replaced_versions':oldversions},sort_keys=True))
