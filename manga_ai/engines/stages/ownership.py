"""Experimental safety gate + context residual recovery on cached sample pages."""

from manga_ai.runtime.resources import read_rgb, read_gray
import argparse,json,sys,time,traceback,zipfile
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3]
from manga_ai.experimental_context_recovery import background_evidence,propose,Config
from manga_ai.experimental_selective_color import selective_color_preview
from manga_ai.shadow_color_audit import ColorAuditConfig

S=ROOT/'work/cross_manga_shadow';O=ROOT/'work/cross_manga_ownership_shadow'
SELECTED_IDS=None


def polygon_iou(a,b):
    pa=a.get('outline',[]);pb=b.get('outline',[])
    if len(pa)<3 or len(pb)<3:return 0.0
    x=min(p[0] for p in pa+pb);y=min(p[1] for p in pa+pb)
    w=max(p[0] for p in pa+pb)-x+1;h=max(p[1] for p in pa+pb)-y+1
    if w<=0 or h<=0 or w*h>20000000:return 0.0
    m=np.zeros((h,w),np.uint8);n=np.zeros_like(m)
    cv2.fillPoly(m,[np.array([[i-x,j-y] for i,j in pa],np.int32)],1)
    cv2.fillPoly(n,[np.array([[i-x,j-y] for i,j in pb],np.int32)],1)
    return float((m&n).sum()/max(1,(m|n).sum()))


def partial_owner(box, confidence, regions, ctd):
    """Find a unique partial owner using geometry and independent ink evidence.

    Heuristics are uncalibrated; this only creates a reviewable shadow candidate.
    Never assign a box competing with another bubble.
    """
    a,b,w,h=box;H,W=ctd.shape
    evidence={'box':list(box),'text_confidence':confidence,'status':'UNASSIGNED',
              'rule':'PARTIAL_OWNER_MULTI_EVIDENCE','calibrated':False}
    if w<=0 or h<=0 or w*h>20000000 or a<0 or b<0 or a+w>W or b+h>H or confidence is None or confidence<.90:
        evidence['reason']='INVALID_GEOMETRY_OR_TEXT_CONFIDENCE';return None,evidence
    ink=ctd[b:b+h,a:a+w]>0;ink_count=int(ink.sum());evidence['ctd_pixels']=ink_count
    if ink_count<10:
        evidence['reason']='INSUFFICIENT_CTD_EVIDENCE';return None,evidence
    candidates=[]
    for r in regions:
        x,y,rw,rh=r['box'];inter=max(0,min(x+rw,a+w)-max(x,a))*max(0,min(y+rh,b+h)-max(y,b))
        fraction=inter/float(w*h)
        if fraction<=0:continue
        outline=r.get('outline',[]);poly_fraction=0.;ink_fraction=0.
        if len(outline)>=3:
            m=np.zeros((h,w),np.uint8)
            cv2.fillPoly(m,[np.array([[px-a,py-b] for px,py in outline],np.int32)],1)
            poly_fraction=float(m.mean());ink_fraction=float((ink&(m>0)).sum()/ink_count)
        candidates.append({'region':r['id'],'box_fraction':fraction,'polygon_fraction':poly_fraction,'ctd_inside_polygon':ink_fraction})
    evidence['candidates']=candidates
    plausible=[c for c in candidates if c['box_fraction']>=.10]
    eligible=[c for c in plausible if c['box_fraction']>=.50 and c['polygon_fraction']>=.50 and c['ctd_inside_polygon']>=.50]
    if len(plausible)!=1 or len(eligible)!=1:
        evidence['reason']='COMPETING_OR_INSUFFICIENT_OWNERSHIP_EVIDENCE';return None,evidence
    evidence.update(status='ASSIGNED_FOR_REVIEW',reason='UNIQUE_PARTIAL_BOX_POLYGON_CTD',region=eligible[0]['region'])
    return eligible[0]['region'],evidence


def process(dataset,page, source_root=None, output_root=None, selected_ids=None, make_previews=True):
    source_root=S if source_root is None else source_root;output_root=O if output_root is None else output_root
    selected_ids=SELECTED_IDS if selected_ids is None else selected_ids
    t=time.monotonic();home=source_root/dataset;p=home/'p04/pages'/page;b=home/'border/pages'/page;dest=output_root/dataset/'pages'/page;dest.mkdir(parents=True,exist_ok=True)
    for pattern in ('B*_mask.png','B*_overlay.png','B*_comparison.jpg'):
        for artifact in dest.glob(pattern):artifact.unlink()
    src=read_rgb(p/'scan/original.png');before=read_rgb(b/'shadow.png');out=before.copy();mask=read_gray(b/'mask.png')>0;H,W=mask.shape
    regs=json.loads((p/'scan/manifest.json').read_text())['regions'];base=json.loads((p/'baseline_complete.json').read_text());ds=json.loads((p/'independent_text_detections.json').read_text());aw,ah=ds['resolution'];ctd=cv2.resize(read_gray(p/'ctd_full_page_analysis.png'),(W,H),interpolation=cv2.INTER_NEAREST)>0
    head=np.zeros((H,W),np.uint8)
    for a,bx,c,e in json.loads((p/'audit_heads.json').read_text())['boxes_analysis']:
        a,bx,c,e=round(a*W/aw),round(bx*H/ah),round(c*W/aw),round(e*H/ah);head[max(0,bx):min(H,bx+e),max(0,a):min(W,a+c)]=1
    matches={r['id']:[] for r in regs};ambiguous=[]; aliases=[];partial_assignments=[];by_id={r['id']:r for r in regs}
    for q in ds['original']:
        if q['kind']!='in_bubble':continue
        a,bx,c,e=q['box'];a,bx,c,e=round(a*W/aw),round(bx*H/ah),round(c*W/aw),round(e*H/ah);owners=[]
        for r in regs:
            x,y,w,h=r['box'];area=max(0,min(x+w,a+c)-max(x,a))*max(0,min(y+h,bx+e)-max(y,bx))
            if area/max(1,c*e)>=.7:owners.append(r['id'])
        if len(owners)==1:matches[owners[0]].append([a,bx,c,e])
        elif len(owners)==2:
            iou=polygon_iou(by_id[owners[0]],by_id[owners[1]])
            if iou>=.80:
                canonical=min(owners,key=lambda k:by_id[k]['box'][2]*by_id[k]['box'][3]);matches[canonical].append([a,bx,c,e]);aliases.append({'box':[a,bx,c,e],'owners':owners,'canonical':canonical,'polygon_iou':iou,'threshold':.80,'calibrated':False})
            else:ambiguous.append({'box':[a,bx,c,e],'owners':owners,'polygon_iou':iou})
        elif not owners:
            owner,ev=partial_owner([a,bx,c,e],q.get('confidence'),regs,ctd)
            partial_assignments.append(ev)
            if owner:matches[owner].append([a,bx,c,e])
            else:ambiguous.append({'box':[a,bx,c,e],'owners':owners,'reason':ev['reason']})
        else:ambiguous.append({'box':[a,bx,c,e],'owners':owners})
    evidence={};gate=np.zeros((H,W),np.uint8);events=[]
    for r in regs:
        x,y,w,h=r['box'];sl=np.s_[y:y+h,x:x+w];g=cv2.cvtColor(src[sl],cv2.COLOR_RGB2GRAY);ev=background_evidence(g,ctd[sl]);evidence[r['id']]=ev
        if selected_ids is not None and r['id'] not in selected_ids:
            gate[sl]=1;events.append({'region':r['id'],'decision':'KEEP_FOR_REVIEW','reason':'NOT_SELECTED'});continue
        if r['id'] in base['skipped'] and ev['complex_for_review']:
            # Conservative rectangle rollback may also restore an overlapping region.
            gate[sl]=1;events.append({'region':r['id'],'decision':'KEEP_FOR_REVIEW','reason':'COMPLEX_BACKGROUND_AND_BASELINE_SKIP','background':ev,'rollback_scope':'entire region box; may restore overlapping text'})
    rolled=(gate>0)&np.any(out!=src,axis=2);out[gate>0]=src[gate>0];mask[gate>0]=False
    for r in regs:
        rid=r['id'];x,y,w,h=r['box'];ev={'region':rid,'decision':'REVIEW','reason':None,'background':evidence[rid]}
        if selected_ids is not None and rid not in selected_ids:continue
        try:
            if evidence[rid]['complex_for_review']:
                ev['reason']='COMPLEX_BACKGROUND';events.append(ev);continue
            if r.get('detector')=='comic_text_ai' and r.get('text_kind')!='in_bubble':
                ev['reason']='TEXT_OUTSIDE_BUBBLE';events.append(ev);continue
            boxes=matches[rid]
            if not boxes:ev['reason']='NO_UNIQUE_TEXT_OWNER';events.append(ev);continue
            # Extend by 8% of region dimension, min 16px; capped by source page.
            pad=max(16,round(.08*max(w,h)));left=max(0,min([x]+[a for a,bb,c,e in boxes])-pad);top=max(0,min([y]+[bb for a,bb,c,e in boxes])-pad);right=min(W,max([x+w]+[a+c for a,bb,c,e in boxes])+pad);bottom=min(H,max([y+h]+[bb+e for a,bb,c,e in boxes])+pad);sl=np.s_[top:bottom,left:right];hh,ww=bottom-top,right-left
            support=np.zeros((hh,ww),np.uint8)
            for a,bb,c,e in boxes:support[max(0,bb-top):min(hh,bb-top+e),max(0,a-left):min(ww,a-left+c)]=1
            # Explicitly blocked boxes cannot be re-enabled by later recovery.
            support[gate[sl]>0]=0
            candidate,trace=propose(src[sl],out[sl],mask[sl],support,ctd[sl],head[sl]);ev.update(context_box=[left,top,ww,hh],proposal=trace)
            if not candidate.any():ev['reason']='NO_SAFE_COMPONENT';events.append(ev);continue
            candidate &= ~(gate[sl]>0)
            clean,used,color=selective_color_preview(src[sl],candidate,ColorAuditConfig(sigma_px=24,bright_floor=245))
            if not used.any():ev['reason']='NO_SUPPORTED_COLOR';events.append(ev);continue
            out[sl][used]=clean[used];mask[sl][used]=True;Image.fromarray((used*255).astype('uint8')).save(dest/f'{rid}_mask.png')
            overlay=src[sl].copy();overlay[used]=np.clip(overlay[used]*.35+np.array([255,0,0])*.65,0,255).astype('uint8');Image.fromarray(overlay).save(dest/f'{rid}_overlay.png')
            ev.update(decision='SHADOW_PREVIEW_REVIEW',reason='CONTEXT_COMPONENT',pixels=int(used.sum()),head_box_pixels=int((used&(head[sl]>0)).sum()),color=color)
        except Exception as exc:ev.update(decision='ERROR_REGION',reason=repr(exc))
        events.append(ev)
    outside=int((np.any(out!=src,axis=2)&~mask).sum());assert outside==0
    Image.fromarray(out).save(dest/'shadow.png');Image.fromarray(mask.astype('uint8')*255).save(dest/'mask.png');Image.fromarray(gate*255).save(dest/'gate.png')
    if make_previews:
        Image.fromarray(out).save(dest/'shadow.jpeg',quality=95,subsampling=0)
        for r in regs:
            rid=r['id'];x,y,w,h=r['box'];box=(max(0,x-30),max(0,y-30),min(W,x+w+30),min(H,y+h+30));sheet=Image.new('RGB',(1500,850),'white');draw=ImageDraw.Draw(sheet)
            for i,(arr,label) in enumerate([(src,'Original'),(before,'Previous shadow'),(out,'Context shadow - review')]):
                im=Image.fromarray(arr).crop(box);im.thumbnail((495,810));sheet.paste(im,(500*i,30));draw.text((i*500+4,5),label,fill='black')
            sheet.save(dest/f'{rid}_comparison.jpg',quality=92)
    result={'dataset':dataset,'page':page,'events':events,'text_boxes_by_region':matches,'ambiguous_text_boxes':ambiguous,'partial_owner_evidence':partial_assignments,'duplicate_aliases':aliases,'rolled_back_pixels':int(rolled.sum()),'outside_mask_changed':outside,'seconds_cached':round(time.monotonic()-t,2),'production':False,'ground_truth':False};(dest/'trace.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('cases',nargs='+',help='dataset:page');args=ap.parse_args();O.mkdir(parents=True,exist_ok=True);start=time.monotonic();rows=[]
    for token in args.cases:
        dataset,page=token.split(':',1)
        try:r=process(dataset,page)
        except Exception as exc:r={'dataset':dataset,'page':page,'error':repr(exc),'traceback':traceback.format_exc()}
        rows.append(r);print(dataset,page,[(e['region'],e['decision'],e['reason']) for e in r.get('events',[]) if e['decision']!='REVIEW'],r.get('error',''),flush=True)
    benchmark={'elapsed_seconds':round(time.monotonic()-start,2),'rows':rows,'input':'cached cross-manga shadow','ground_truth':False};(O/'benchmark.json').write_text(json.dumps(benchmark,ensure_ascii=False,indent=2))
    for dataset in set(r['dataset'] for r in rows):
        with zipfile.ZipFile(O/f'{dataset}_regression.zip','w',zipfile.ZIP_DEFLATED) as z:
            for r in rows:
                if r['dataset']==dataset and 'error' not in r:z.write(O/dataset/'pages'/r['page']/'shadow.jpeg',r['page']+'.jpeg')
    print('done',benchmark['elapsed_seconds'])


if __name__=='__main__':main()
