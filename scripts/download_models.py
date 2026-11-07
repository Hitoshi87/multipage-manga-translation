#!/usr/bin/env python3
"""Explicit pinned model installation; standard-library only, offline check by default."""
import argparse,hashlib,json,os,re,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


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
 if target.is_file() and digest(target)==item['sha256']:return 'verified'
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
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--profile',choices=['1107','preview','assist','aot'],default='1107');ap.add_argument('--download',action='store_true',help='Download from upstream; read upstream license terms first');ap.add_argument('--model-dir',type=Path,default=ROOT/'models');a=ap.parse_args(argv);data=json.loads((ROOT/'models/manifest.json').read_text());bad=False
 for item in data['models']:
  if a.profile not in item['profiles']:continue
  status=install(item,a.model_dir,a.download);print(item['id']+': '+status);bad|=status=='missing_or_invalid'
 return int(bad)

if __name__=='__main__':raise SystemExit(main())
