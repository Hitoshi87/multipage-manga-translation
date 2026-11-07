"""General shadow residual recovery over all regions; cached inputs, no production."""

from manga_ai.runtime.resources import read_rgb, read_gray, sha256_file
import argparse, hashlib, json, sys, time, zipfile
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[3]
from manga_ai.experimental_residual_recovery import propose
from manga_ai.experimental_selective_color import selective_color_preview
from manga_ai.shadow_color_audit import ColorAuditConfig

P04=ROOT/'work/p04_volume_audit/pages'; PRIOR=ROOT/'work/volume22_unified_shadow_v3/pages'
OUT=ROOT/'work/volume22_general_recovery_shadow'; VERSION='general-region-shadow-1'
SELECTED_IDS=None


def rgb(path):return read_rgb(path)
def gray(path):return read_gray(path)


def process(page, p04=None, prior=None, out=None, selected_ids=None, make_previews=True):
    p04=P04 if p04 is None else p04;prior=PRIOR if prior is None else prior;out=OUT if out is None else out
    selected_ids=SELECTED_IDS if selected_ids is None else selected_ids
    started=time.monotonic();p=p04/page;old=prior/page;d=out/'pages'/page;d.mkdir(parents=True,exist_ok=True)
    for pattern in ('B*_added_mask.png','B*_overlay.png','B*_comparison.jpg'):
        for artifact in d.glob(pattern):artifact.unlink()
    src=rgb(p/'scan/original.png');before=rgb(old/'shadow.png');output=before.copy();mask=gray(old/'mask.png')>0
    H,W=src.shape[:2];manifest=json.loads((p/'scan/manifest.json').read_text());regs=manifest['regions']
    ds=json.loads((p/'independent_text_detections.json').read_text());aw,ah=ds['resolution']
    ctd=cv2.resize(gray(p/'ctd_full_page_analysis.png'),(W,H),interpolation=cv2.INTER_NEAREST)>0
    det=[]
    for q in ds['original']:
        if q['kind']!='in_bubble':continue
        a,b,c,e=q['box'];det.append({'box':[round(a*W/aw),round(b*H/ah),round(c*W/aw),round(e*H/ah)],'model_confidence':q.get('confidence')})
    head=np.zeros((H,W),np.uint8)
    for a,b,c,e in json.loads((p/'audit_heads.json').read_text())['boxes_analysis']:
        a,b,c,e=round(a*W/aw),round(b*H/ah),round(c*W/aw),round(e*H/ah)
        head[max(0,b):min(H,b+e),max(0,a):min(W,a+c)]=1
    # Assign text boxes once only when a single speech region has sufficient overlap.
    assignment={r['id']:[] for r in regs};unassigned=[]
    for q in det:
        a,b,c,e=q['box']; owners=[]
        for r in regs:
            x,y,w,h=r['box']; area=max(0,min(x+w,a+c)-max(x,a))*max(0,min(y+h,b+e)-max(y,b))
            if area/max(1,c*e)>=.7:owners.append(r['id'])
        if len(owners)==1:assignment[owners[0]].append(q)
        else:unassigned.append({'box':q['box'],'owners':owners,'reason':'NO_OWNER' if not owners else 'AMBIGUOUS_OWNERSHIP'})
    events=[]
    for r in regs:
        rid=r['id'];x,y,w,h=r['box'];sl=np.s_[y:y+h,x:x+w]; event={'region_id':rid,'source':r.get('source'),'detector':r.get('detector'),
            'decision':'REVIEW','reason':None,'model_confidence':r.get('detector_confidence'),'text_boxes':assignment[rid],
            'authorized_to_clean':False}
        try:
            if selected_ids is not None and rid not in selected_ids:continue
            if r.get('detector') not in ('ai_balloon','hybrid_closed_balloon'):
                event['reason']='NOT_SPEECH_BUBBLE_DETECTOR';events.append(event);continue
            if not assignment[rid]:event['reason']='NO_UNIQUE_TEXT_BOX';events.append(event);continue
            polygon=np.zeros((h,w),np.uint8);pts=np.asarray([[a-x,b-y] for a,b in r.get('outline',[])],np.int32)
            if len(pts)<3:event['reason']='NO_POLYGON';events.append(event);continue
            cv2.fillPoly(polygon,[pts],1);support=np.zeros((h,w),np.uint8)
            for q in assignment[rid]:
                a,b,c,e=q['box'];support[max(0,b-y):min(h,b-y+e),max(0,a-x):min(w,a-x+c)]=1
            candidate,trace=propose(src[sl],output[sl],mask[sl],polygon,support,ctd[sl],head[sl]);event['proposal']=trace
            if not candidate.any():event['reason']='NO_SAFE_CANDIDATE';events.append(event);continue
            candidate_image,used,color=selective_color_preview(src[sl],candidate,ColorAuditConfig(sigma_px=24,bright_floor=245))
            if not used.any():event['reason']='NO_COLOR_SUPPORT';events.append(event);continue
            output[sl][used]=candidate_image[used];mask[sl][used]=True
            Image.fromarray((used*255).astype('uint8')).save(d/f'{rid}_added_mask.png')
            crop=src[sl].copy();crop[used]=np.clip(crop[used]*.35+np.array([255,0,0])*.65,0,255).astype('uint8');Image.fromarray(crop).save(d/f'{rid}_overlay.png')
            event.update(decision='SHADOW_PREVIEW_REVIEW',reason='MULTI_EVIDENCE_COMPONENT',applied_pixels=int(used.sum()),color=color)
        except Exception as exc:
            event.update(decision='ERROR_REGION',reason=repr(exc))
        events.append(event)
    outside=int((np.any(output!=src,axis=2)&~mask).sum())
    if outside:raise RuntimeError(f'{outside} pixels outside mask')
    Image.fromarray(output).save(d/'shadow.png',compress_level=3);Image.fromarray(mask.astype('uint8')*255).save(d/'mask.png')
    if make_previews:
        Image.fromarray(output).save(d/'shadow.jpeg',quality=95,subsampling=0)
        # Every region gets a crop, including abstentions, to make the regression inspectable.
        for r in regs:
            rid=r['id'];x,y,w,h=r['box'];box=(max(0,x-30),max(0,y-30),min(W,x+w+30),min(H,y+h+30));sheet=Image.new('RGB',(1500,850),'white');draw=ImageDraw.Draw(sheet)
            for i,(array,label) in enumerate([(src,'Original'),(before,'V3 before'),(output,'General shadow - review')]):
                im=Image.fromarray(array).crop(box);im.thumbnail((495,810));sheet.paste(im,(i*500,30));draw.text((i*500+4,5),label,fill='black')
            sheet.save(d/f'{rid}_comparison.jpg',quality=90)
    row={'page':page,'status':'complete','events':events,'unassigned_boxes':unassigned,'outside_mask_changed':outside,
         'seconds_cached':round(time.monotonic()-started,3),'input_v3_sha256':sha256_file(old/'shadow.png')}
    (d/'trace.json').write_text(json.dumps(row,ensure_ascii=False,indent=2));return row


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pages',nargs='+',required=True);args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();rows=[]
    for pg in args.pages:
        try:row=process(pg)
        except Exception as exc:
            import traceback;row={'page':pg,'status':'error','reason':repr(exc),'traceback':traceback.format_exc()}
        rows.append(row);print(pg,row['status'],[(e['region_id'],e['reason']) for e in row.get('events',[]) if e['decision']!='REVIEW'],flush=True)
    report={'version':VERSION,'pages':args.pages,'seconds_cached':round(time.monotonic()-start,2),'no_fresh_inference':True,'ground_truth':False,'results':rows}
    (OUT/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(OUT/'regression.zip','w',zipfile.ZIP_DEFLATED) as z:
        for row in rows:
            if row['status']=='complete':z.write(OUT/'pages'/row['page']/'shadow.jpeg',row['page']+'.jpeg')
    print('done',report['seconds_cached'])


if __name__=='__main__':main()
