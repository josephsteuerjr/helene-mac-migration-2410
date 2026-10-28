from pathlib import Path
import argparse,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--delta',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
record=json.loads(Path('macos-delta.json').read_text());assert hashlib.file_digest(args.base.open('rb'),'sha256').hexdigest()==record['base_sha256']
with zipfile.ZipFile(args.delta) as z:literal=z.read('literal.bin')
assert hashlib.sha256(literal).hexdigest()==record['literal_sha256']
with args.base.open('rb') as source,args.output.open('xb') as target:
    for kind,start,length in record['segments']:
        if kind=='literal':target.write(literal[start:start+length])
        else:
            assert kind=='base';source.seek(start)
            while length:
                data=source.read(min(length,4*1024*1024));assert data;target.write(data);length-=len(data)
assert args.output.stat().st_size==record['size'] and hashlib.file_digest(args.output.open('rb'),'sha256').hexdigest()==record['sha256']
with zipfile.ZipFile(args.output) as z:assert z.testzip() is None
print('EXACT_FINAL_MAC_INPUT',record['sha256'])
