"""Losslessly recompress old Photoshop input.png caches; dry-run by default.

IDAT compression changes only. Other PNG chunks and decompressed filter rows
are verified byte-for-byte before atomic replacement. Originals are retained
on any parsing, concurrency or validation error.
"""
import argparse
import json
import os
import shutil
import struct
import tempfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SIGNATURE=b'\x89PNG\r\n\x1a\n'
MAX_FILE=192*1024*1024
MAX_RAW=256*1024*1024


def chunks(blob):
    if blob[:8]!=SIGNATURE:raise ValueError('Not a PNG')
    result=[];offset=8
    while offset<len(blob):
        if offset+12>len(blob):raise ValueError('Truncated PNG')
        size=struct.unpack('>I',blob[offset:offset+4])[0];end=offset+12+size
        if end>len(blob):raise ValueError('Truncated chunk')
        kind=blob[offset+4:offset+8];data=blob[offset+8:end-4]
        if zlib.crc32(kind+data)&0xffffffff!=struct.unpack('>I',blob[end-4:end])[0]:raise ValueError('Invalid CRC')
        result.append((kind,data,blob[offset:end]));offset=end
        if kind==b'IEND':break
    if offset!=len(blob) or not result or result[0][0]!=b'IHDR' or result[-1][0]!=b'IEND':raise ValueError('Unsupported PNG structure')
    return result


def raw_rows(parts):
    packed=b''.join(data for kind,data,_ in parts if kind==b'IDAT')
    decoder=zlib.decompressobj();raw=decoder.decompress(packed,MAX_RAW+1)
    if len(raw)>MAX_RAW or not decoder.eof or decoder.unused_data:raise ValueError('Unsupported or oversized image')
    return raw


def recompress(path,apply=False):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Not a regular cache file')
    before=path.stat()
    if before.st_size>MAX_FILE:raise ValueError('Cache exceeds memory bound')
    parts=chunks(path.read_bytes());raw=raw_rows(parts);packed=zlib.compress(raw,3)
    idat=struct.pack('>I',len(packed))+b'IDAT'+packed+struct.pack('>I',zlib.crc32(b'IDAT'+packed)&0xffffffff)
    output=[SIGNATURE];wrote=False
    for kind,_,original in parts:
        if kind==b'IDAT':
            if not wrote:output.append(idat);wrote=True
        else:output.append(original)
    candidate=b''.join(output)
    if len(candidate)>=before.st_size:return {'path':str(path),'saved':0,'applied':False}
    verified=chunks(candidate)
    if raw_rows(verified)!=raw or [c[2] for c in verified if c[0]!=b'IDAT']!=[c[2] for c in parts if c[0]!=b'IDAT']:
        raise ValueError('Lossless verification failed')
    saved=before.st_size-len(candidate)
    if apply:
        fd,name=tempfile.mkstemp(prefix='.mta-compact-',suffix='.tmp',dir=path.parent)
        temp=Path(name)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(candidate);stream.flush();os.fsync(stream.fileno())
            current=path.stat()
            if (current.st_ino,current.st_size,current.st_mtime_ns)!=(before.st_ino,before.st_size,before.st_mtime_ns):
                raise ValueError('Cache changed while compressing')
            shutil.copystat(path,temp);os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
    return {'path':str(path),'saved':saved,'applied':apply}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'work/pages')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--report',type=Path)
    parser.add_argument('--workers',type=int,choices=(1,2,3),default=1)
    args=parser.parse_args();result={'apply':args.apply,'items':[],'errors':[]};start=time.monotonic()
    paths=sorted(p for p in args.root.glob('*/input.png') if not p.is_symlink() and not p.parent.is_symlink() and p.stat().st_size>=1024*1024 and p.stat().st_mtime<time.time()-3600)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(recompress,path,args.apply):path for path in paths}
        for i,future in enumerate(as_completed(futures),1):
            path=futures[future]
            try:result['items'].append(future.result())
            except (OSError,ValueError,zlib.error) as exc:result['errors'].append({'path':str(path),'error':str(exc)})
            if i%25==0 or i==len(paths):
                print(json.dumps({'processed':i,'total':len(paths),'saved_GiB':round(sum(x['saved'] for x in result['items'])/1024**3,2),'seconds':round(time.monotonic()-start)}),flush=True)
                if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False))
    if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False))
    return 1 if result['errors'] else 0


if __name__=='__main__':raise SystemExit(main())
