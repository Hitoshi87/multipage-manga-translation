"""Compare OCR engines on reviewed page/region references, without altering manifests.

Input JSON: {"pages":[{"manifest":"/path/manifest.json","references":{"B001":"..."}}]}.
References may contain manga text and should be stored outside the public source tree.
"""
import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from manga_ai.io import read_json, validate_manifest, write_json


def normalize(text):
    return ''.join(unicodedata.normalize('NFKC', text).split())


def edit_distance(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]+[0]*len(b)
        for j,y in enumerate(b,1):
            current[j]=min(current[j-1]+1,previous[j]+1,previous[j-1]+(x!=y))
        previous=current
    return previous[-1]


def compare(spec):
    from manga_ai.engine import read_image
    from manga_ai.baberu_ocr import read
    results=[]
    for page in spec['pages']:
        path=Path(page['manifest']).resolve();m=validate_manifest(read_json(path));image=read_image(path.parent/'original.png')
        if image.shape[:2]!=(m['height'],m['width']):raise ValueError('Image does not match manifest')
        regions={r['id']:r for r in m['regions']}
        for rid,reference in page['references'].items():
            if rid not in regions or not isinstance(reference,str) or not normalize(reference):raise ValueError('Invalid reference: '+str(rid))
            region=regions[rid];x,y,w,h=region['box'];start=time.monotonic();candidate=read(image[y:y+h,x:x+w])
            results.append({'manifest':str(path),'region_id':rid,'reference':reference,'tesseract':region.get('source',''),
                            'baberu':candidate,'baberu_ms':round((time.monotonic()-start)*1000)})
    totals={}
    for engine in ('tesseract','baberu'):
        edits=sum(edit_distance(normalize(r['reference']),normalize(r[engine])) for r in results)
        characters=sum(len(normalize(r['reference'])) for r in results)
        totals[engine]={'edits':edits,'reference_characters':characters,'cer':edits/characters if characters else None}
    return {'method':'same region crop, NFKC and whitespace normalized CER; depends on supplied references',
            'totals':totals,'rows':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('reference_json',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise FileExistsError('Output exists: '+str(args.out))
    result=compare(read_json(args.reference_json));write_json(args.out,result)
    print(json.dumps({'rows':len(result['rows']),'totals':result['totals']},ensure_ascii=False))

if __name__=='__main__':main()
