#!/usr/bin/env python3
"""Explicit pinned model installation; standard-library only, offline check by default."""
import argparse,hashlib,json,os,re,tempfile,urllib.request,sys,time,http.client
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from manga_ai.model_registry import PROFILES, models


def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()


def target_path(root,item):
 relative=Path(item['path'])
 if relative.is_absolute() or '..' in relative.parts or '\\' in item['path']:raise ValueError('Unsafe model path')
 target=(root/relative).resolve()
 if not target.is_relative_to(root.resolve()):raise ValueError('Model path escapes directory')
 if not re.fullmatch('[a-f0-9]{64}',item['sha256']) or not item['url'].startswith('https://'):raise ValueError('Invalid pinned model metadata')
 return target


def install(item,root,download=False):
 target=target_path(root,item)
 if target.is_file() and target.stat().st_size==item['size_bytes'] and digest(target)==item['sha256']:return 'verified'
 if not download:return 'missing_or_invalid'
 target.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix='.model-',suffix='.part',dir=target.parent);os.close(fd);part=Path(name)
 try:
  with urllib.request.urlopen(item['url'],timeout=60) as response,part.open('wb') as out:
   for block in iter(lambda:response.read(1024*1024),b''):out.write(block)
  if part.stat().st_size!=item['size_bytes'] or digest(part)!=item['sha256']:raise ValueError('Checksum/size mismatch: '+item['id'])
  os.replace(part,target)
 finally:part.unlink(missing_ok=True)
 return 'downloaded_and_verified'


def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--profile',choices=PROFILES,default='auto')
 ap.add_argument('--download',action='store_true',help='Explicitly download pinned upstream files')
 ap.add_argument('--model-dir',type=Path,default=ROOT/'models')
 ap.add_argument('--retries',type=int,default=3)
 a=ap.parse_args(argv)
 if not 1 <= a.retries <= 5:ap.error('--retries must be between 1 and 5')
 rows=models(a.profile);bad=[]
 print(f"Profile {a.profile}: {len(rows)} files, {sum(r['size_bytes'] for r in rows)/1_000_000:.1f} MB total",flush=True)
 for index,item in enumerate(rows,1):
  print(f"[{index}/{len(rows)}] {item['path']} ({item['size_bytes']/1_000_000:.1f} MB)",flush=True)
  for attempt in range(a.retries if a.download else 1):
   try:
    result=install(item,a.model_dir,a.download)
    print('  '+result,flush=True)
    if result=='missing_or_invalid':bad.append(item['path'])
    break
   except (OSError,ValueError,http.client.HTTPException) as exc:
    print(f"  Attempt {attempt+1}: {exc}",flush=True)
    if attempt+1 == a.retries or not a.download:
     bad.append(item['path']);break
    time.sleep(min(attempt+1,3))
 if bad:print('Missing/failed: '+', '.join(bad)+'. Re-run the same command; verified files are reused.',flush=True)
 return int(bool(bad))

if __name__=='__main__':raise SystemExit(main())
