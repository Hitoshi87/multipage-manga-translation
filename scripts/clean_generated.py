"""Remove only regenerable code caches and Finder metadata; dry-run by default."""
import argparse,json,os,shutil
from pathlib import Path

EXCLUDED={'work','output','models','.git','node_modules'}
CACHE_DIRS={'__pycache__','.pytest_cache','.ruff_cache'}


def candidates(root):
    root=Path(root).resolve();found=[]
    for folder,dirs,files in os.walk(root,followlinks=False):
        base=Path(folder)
        for name in list(dirs):
            path=base/name
            if path.is_symlink() or name in EXCLUDED or name.startswith('.venv'):
                dirs.remove(name)
            elif name in CACHE_DIRS:
                found.append(path);dirs.remove(name)
        if '.DS_Store' in files and not (base/'.DS_Store').is_symlink():found.append(base/'.DS_Store')
    return found


def clean(root,apply=False):
    root=Path(root).resolve();rows=[]
    for p in candidates(root):
        size=sum(f.stat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink()) if p.is_dir() else p.stat().st_size
        if apply:
            if p.is_dir():shutil.rmtree(p)
            else:p.unlink()
        rows.append({'path':str(p.relative_to(root)),'bytes':size,'removed':apply})
    return {'apply':apply,'root':str(root),'bytes':sum(r['bytes'] for r in rows),'items':rows,'protected':['work','output','models','.venv*','.git','symlinks']}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--apply',action='store_true');ap.add_argument('--report',type=Path);a=ap.parse_args();result=clean(a.root,a.apply);text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.report:a.report.write_text(text)
    print(text)
