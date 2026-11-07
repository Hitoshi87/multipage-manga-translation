"""Experimental second pass for independently detached residual ink, shadow only."""

from manga_ai.runtime.resources import read_rgb, read_gray
import json,sys,time,zipfile
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3]
from manga_ai.experimental_selective_color import selective_color_preview
from manga_ai.shadow_color_audit import ColorAuditConfig
P=ROOT/'work/p04_volume_audit/pages'; BASE=ROOT/'work/volume22_general_recovery_shadow/pages'; OUT=ROOT/'work/volume22_border_recovery_shadow'

def run(pg, p04=None, base=None, out=None, make_previews=True):
    p04=P if p04 is None else p04;base=BASE if base is None else base;out=OUT if out is None else out
    p=p04/pg;b=base/pg;d=out/'pages'/pg;d.mkdir(parents=True,exist_ok=True)
    for pattern in ('B*_mask.png','B*_overlay.png','B*_comparison.jpg'):
        for artifact in d.glob(pattern):artifact.unlink()
    src=read_rgb(p/'scan/original.png');prev=read_rgb(b/'shadow.png');out=prev.copy();mask=read_gray(b/'mask.png')>0;H,W=mask.shape
    regions={r['id']:r for r in json.loads((p/'scan/manifest.json').read_text())['regions']};base=json.loads((b/'trace.json').read_text());events=[]
    for old in base['events']:
        rid=old['region_id'];q=old.get('proposal');
        if not q:continue
        r=regions[rid];x,y,w,h=r['box'];sl=np.s_[y:y+h,x:x+w];crop=src[sl];g=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY);now=cv2.cvtColor(out[sl],cv2.COLOR_RGB2GRAY);n,labels,stats,_=cv2.connectedComponentsWithStats((g<200).astype('uint8'),8);selected=np.zeros((h,w),np.uint8);records=[]
        for comp in q['components']:
            i=comp['component_id'];xx,yy,ww,hh=comp['box'];area=comp['area'];reasons=[]
            if i>=n:raise ValueError('component identity mismatch')
            pixels=labels==i; residual=int((pixels&(now<200)).sum());
            if residual<3:continue
            if comp['text_box_coverage']<.70:reasons.append('TEXT_SUPPORT_LOW')
            if comp['ctd_coverage']<.9:reasons.append('CTD_SUPPORT_LOW')
            if residual/area<.20:reasons.append('INSUFFICIENT_RESIDUAL_FRACTION')
            if comp['head_box_pixels']/area>.15:reasons.append('HEAD_BOX_OVERLAP_HIGH')
            if xx<4 or yy<4 or xx+ww>w-4 or yy+hh>h-4:reasons.append('TOUCH_CROP_EDGE')
            if ww>w*.5 or hh>h*.5:reasons.append('COMPONENT_TOO_LARGE')
            others=(g<200)&~pixels;dist=cv2.distanceTransform((~others).astype('uint8'),cv2.DIST_L2,5);gap=float(dist[pixels].min())
            if gap<5:reasons.append('NEAR_OTHER_DARK_COMPONENT')
            rec={'id':i,'box':comp['box'],'ink_pixels':area,'remaining_ink_pixels':residual,'distance_to_other_dark':round(gap,2),'text_box_coverage':comp['text_box_coverage'],'ctd_coverage':comp['ctd_coverage'],'head_box_pixels':comp['head_box_pixels'],'original_polygon_rejection':'NEAR_OR_OUTSIDE_POLYGON' in comp['reasons'],'reasons':reasons};records.append(rec)
            if not reasons:selected[pixels]=1
        if not records:continue
        expanded=cv2.dilate(selected,np.ones((7,7),np.uint8))>0;other_dark=(g<200)&~(selected>0);other_dist=cv2.distanceTransform((~other_dark).astype('uint8'),cv2.DIST_L2,5);candidate=expanded&(other_dist>=2)&~mask[sl]
        event={'region':rid,'decision':'REVIEW','reason':'NO_ISOLATED_COMPONENT','components':records,'thresholds':'experimental and uncalibrated','artwork_safety':'not independently verified'}
        if candidate.any():
            clean,used,color=selective_color_preview(crop,candidate,ColorAuditConfig(sigma_px=24,bright_floor=245));out[sl][used]=clean[used];mask[sl][used]=True;event.update(decision='SHADOW_REVIEW',reason='TEXT_CTD_AND_DETACHED_INK',pixels=int(used.sum()),color=color);Image.fromarray((used*255).astype('uint8')).save(d/f'{rid}_mask.png');overlay=crop.copy();overlay[used]=np.clip(overlay[used]*.35+np.array([255,0,0])*.65,0,255).astype('uint8');Image.fromarray(overlay).save(d/f'{rid}_overlay.png')
        events.append(event)
    outside=int((np.any(out!=src,axis=2)&~mask).sum());assert not outside
    Image.fromarray(out).save(d/'shadow.png');Image.fromarray(mask.astype('uint8')*255).save(d/'mask.png')
    if make_previews:
        Image.fromarray(out).save(d/'shadow.jpeg',quality=95,subsampling=0)
        for ev in events:
            r=regions[ev['region']];x,y,w,h=r['box'];box=(max(0,x-30),max(0,y-30),min(W,x+w+30),min(H,y+h+30));sheet=Image.new('RGB',(1500,850),'white');draw=ImageDraw.Draw(sheet)
            for i,(im,label) in enumerate([(src,'Original'),(prev,'Before'),(out,'Shadow - review')]):
                im=Image.fromarray(im).crop(box);im.thumbnail((495,810));sheet.paste(im,(i*500,30));draw.text((i*500+3,5),label,fill='black')
            sheet.save(d/f'{ev["region"]}_comparison.jpg',quality=92)
    trace={'page':pg,'events':events,'outside_mask_changed':outside,'production':False};(d/'trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2));return trace

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);t=time.monotonic();rows=[]
    for pg in sys.argv[1:]:
        try:r=run(pg)
        except Exception as exc:
            import traceback;r={'page':pg,'error':repr(exc),'traceback':traceback.format_exc()}
        rows.append(r);print(pg,[(x['region'],x['decision']) for x in r.get('events',[]) if x['decision']=='SHADOW_REVIEW'],flush=True)
    (OUT/'benchmark.json').write_text(json.dumps({'seconds_cached':round(time.monotonic()-t,2),'rows':rows},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(OUT/'regression.zip','w',zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            if not r.get('error'):z.write(OUT/'pages'/r['page']/'shadow.jpeg',r['page']+'.jpeg')
