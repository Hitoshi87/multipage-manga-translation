"""One-page 1107 core operating on explicitly supplied staging directories."""

from manga_ai.runtime.resources import read_rgb, read_gray
import sys,time,json,hashlib,collections,resource
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw
from manga_ai.experimental_pair_ownership import arbitrate
from manga_ai.experimental_region_preview import evaluate
from manga_ai.experimental_bubble_components import propose_components


def run(R, REC, O, page, make_previews=True):
    O.mkdir(parents=True,exist_ok=True)
    # The caller supplies the scan and model outputs for this page.
    pages=[page]
    (O/'selection.json').write_text(json.dumps({'pages':pages,'selection':'all pages 000-197','input':'cached P04','size':198},indent=2));
    rows=[];start=time.monotonic()
    for page in pages:
     t=time.monotonic();d=O/'pages'/page;d.mkdir(parents=True,exist_ok=True)
     if (d/'trace.json').exists() and (d/'shadow_lossless.png').exists():
      cached=json.loads((d/'trace.json').read_text());rows.append(cached);print(page,'CHECKPOINT',flush=True);continue
     try:
      p=R/page;m=json.loads((p/'scan/manifest.json').read_text());old=json.loads((p/'baseline_complete.json').read_text());src=read_rgb(p/'scan/original.png');H,W=src.shape[:2];base_out=read_rgb(p/'scan/trial_clean.png');ctd=(read_gray(p/'ctd_full_page_analysis.png')>0).astype('uint8');ctd=cv2.resize(ctd,(W,H),interpolation=cv2.INTER_NEAREST);dd=json.loads((p/'independent_text_detections.json').read_text());aw,ah=dd['resolution'];det=[]
      for q in dd['original']:
       if q['kind']=='in_bubble':
        a,b,c,e=q['box'];det.append([round(a*W/aw),round(b*H/ah),round(c*W/aw),round(e*H/ah)])
      regions={r['id']:r for r in m['regions']};eligible=[r['id'] for r in m['regions'] if r['id'] in old['applied']];pending=set(eligible);clusters=[]
      def intersect(a,b):
       x,y,w,h=a;X,Y,U,V=b;return max(x,X)<min(x+w,X+U) and max(y,Y)<min(y+h,Y+V)
      while pending:
       todo=[pending.pop()];group=[]
       while todo:
        k=todo.pop();group.append(k);near=[z for z in pending if intersect(regions[k]['box'],regions[z]['box'])]
        for z in near:pending.remove(z);todo.append(z)
       clusters.append(sorted(group))
      output=src.copy();allmask=np.zeros((H,W),np.uint8);details=[];savedmask=d/'regions';savedmask.mkdir(exist_ok=True)
      for group in clusters:
       x0=min(regions[k]['box'][0] for k in group);y0=min(regions[k]['box'][1] for k in group);x1=max(regions[k]['box'][0]+regions[k]['box'][2] for k in group);y1=max(regions[k]['box'][1]+regions[k]['box'][3] for k in group);crop=src[y0:y1,x0:x1];h,w=crop.shape[:2];bm={};em={};mapping={}
       for rid in group:
        r=regions[rid];x,y,bw,bh=r['box'];a=np.zeros((h,w),np.uint8);b=np.zeros_like(a);a[y-y0:y-y0+bh,x-x0:x-x0+bw]=read_gray(p/'scan/masks'/f'{rid}.png')>0;ep=REC/f'{page}_{rid}'/'mask_extra.png';
        if ep.exists():b[y-y0:y-y0+bh,x-x0:x-x0+bw]=read_gray(ep)>0
        bm[rid]=a;em[rid]=b;mapping[rid]=[q for q in det if max(0,min(x+bw,q[0]+q[2])-max(x,q[0]))*max(0,min(y+bh,q[1]+q[3])-max(y,q[1]))/max(1,q[2]*q[3])>=.7]
       masks,own=arbitrate(crop,bm,em,mapping,origin=(x0,y0))
       if own['remaining_mask_conflict_pixels']:
        details.append({'region_ids':group,'status':'review_mask_conflict','conflict_pixels':own['remaining_mask_conflict_pixels']});continue
       for rid in group:
        r=regions[rid];x,y,bw,bh=r['box'];inputmask=masks[rid][y-y0:y-y0+bh,x-x0:x-x0+bw];boxes=[[a-x,b-y,c,e] for a,b,c,e in mapping[rid]];clean,mask,trace=evaluate(src[y:y+bh,x:x+bw],inputmask,ctd[y:y+bh,x:x+bw],boxes,r.get('source',''),r['fill'])
        # No supported color or empty mask: leave source unchanged and record review.
        if not trace['preview_applicable']:details.append({'region_ids':[rid],'status':'review_no_preview','trace':trace});continue
        # Never resolve cross-cluster mask collisions by silently overwriting.
        used=allmask[y:y+bh,x:x+bw]>0
        if np.any(mask&used):details.append({'region_ids':[rid],'status':'review_cross_cluster_overlap'});continue
        target=output[y:y+bh,x:x+bw];target[mask]=clean[mask];allmask[y:y+bh,x:x+bw]|=mask.astype('uint8');Image.fromarray((mask*255).astype('uint8')).save(savedmask/(rid+'_mask.png'));details.append({'region_ids':[rid],'status':'shadow_clean_review','mask_pixels':int(mask.sum()),'trace':trace,'ownership_component_count':len(own['components']),'baseline_extra_mask_cached':bool(em[rid].any())})
      # Restore prior baseline-applied mask when the experimental preview cannot run.
      # This is a shadow fallback, not a claim that baseline masks are safe.
      alpha=np.asarray(Image.open(p/'scan/trial_clean_overlay.png').convert('RGBA'))[:,:,3]>0
      for item in details:
       if item['status']!='review_no_preview':continue
       rid=item['region_ids'][0];r=regions[rid];x,y,bw,bh=r['box'];local=read_gray(p/'scan/masks'/f'{rid}.png')>0;restore=local&alpha[y:y+bh,x:x+bw]
       if (restore&(allmask[y:y+bh,x:x+bw]>0)).any():item['fallback']='conflict_review';continue
       target=output[y:y+bh,x:x+bw];target[restore]=base_out[y:y+bh,x:x+bw][restore];allmask[y:y+bh,x:x+bw]|=restore.astype('uint8');item['fallback']='baseline_applied_restored_unverified';item['fallback_pixels']=int(restore.sum())
      # Experimental preview of baseline-skipped regions; retain all decisions in trace.
      for rid in old['skipped']:
       r=regions[rid];x,y,bw,bh=r['box'];regioncrop=src[y:y+bh,x:x+bw];bm=read_gray(p/'scan/masks'/f'{rid}.png')>0;boxes=[]
       for a,b,c,e in det:
        overlap=max(0,min(x+bw,a+c)-max(x,a))*max(0,min(y+bh,b+e)-max(y,b))
        if overlap/max(1,c*e)>=.7:boxes.append([a-x,b-y,c,e])
       poly=np.zeros((bh,bw),np.uint8);pts=np.asarray([[a-x,b-y] for a,b in r.get('outline',[])],np.int32)
       if len(pts)>=3:cv2.fillPoly(poly,[pts],1)
       candidate,ct=propose_components(regioncrop,poly);Image.fromarray((candidate*255).astype('uint8')).save(savedmask/(rid+'_geometry_PROPOSAL.png'))
       clean,rm,rt=evaluate(regioncrop,bm,ctd[y:y+bh,x:x+bw],boxes,r.get('source',''),r['fill']);conflict=rm&(allmask[y:y+bh,x:x+bw]>0)
       event={'region_ids':[rid],'status':'baseline_skip_review','reason':old['blocked'].get(rid,'baseline auto_clean false or mask missing'),'warnings':r.get('warnings',[]),'guard':rt,'geometry_proposal_pixels':int(candidate.sum()),'geometry_component_count':len(ct['accepted']),'geometry_recovered_near_glyph':len(ct['near_glyph_recovered']),'geometry_used_for_clean':False,'authorized_to_clean':False}
       if rt['preview_applicable'] and not conflict.any():
        target=output[y:y+bh,x:x+bw];target[rm]=clean[rm];allmask[y:y+bh,x:x+bw]|=rm.astype('uint8');Image.fromarray((rm*255).astype('uint8')).save(savedmask/(rid+'_skip_preview_mask.png'));event['status']='baseline_skip_shadow_unreviewed';event['mask_pixels']=int(rm.sum())
       elif conflict.any():event['conflict_pixels']=int(conflict.sum())
       details.append(event)
      changed=np.any(output!=src,axis=2);outside=int((changed&(allmask==0)).sum());assert outside==0
      Image.fromarray(output).save(d/'shadow_lossless.png',compress_level=3);Image.fromarray(allmask*255).save(d/'compositing_mask.png')
      if make_previews:
       Image.fromarray(src).save(d/'original.png',compress_level=3);Image.fromarray(base_out).save(d/'baseline.jpeg',quality=95,subsampling=0);Image.fromarray(output).save(d/'engine_shadow.jpeg',quality=95,subsampling=0)
      if make_previews:
       thumbs=Image.new('RGB',(1800,900),'white');draw=ImageDraw.Draw(thumbs)
       for i,(im,label) in enumerate([(src,'Goc'),(base_out,'P04 baseline'),(output,'Engine shadow: can duyet')]):
        v=Image.fromarray(im);v.thumbnail((590,860));thumbs.paste(v,(i*600,30));draw.text((i*600+4,5),label,fill='black')
       thumbs.save(d/'comparison.jpg',quality=90)
      row={'page':page,'status':'complete','regions':len(m['regions']),'baseline_applied':len(old['applied']),'baseline_skipped':len(old['skipped']),'shadow_preview_regions':sum(v['status']=='shadow_clean_review' for v in details),'shadow_review_regions':sum(v['status']!='shadow_clean_review' for v in details),'mask_pixels':int(allmask.sum()),'outside_mask_changed_lossless':outside,'seconds_cached':round(time.monotonic()-t,3),'source_sha256':old['source_sha256'],'details':details,'manual_ground_truth':False,'authorized_to_clean':False};(d/'trace.json').write_text(json.dumps(row,ensure_ascii=False,indent=2));rows.append(row);print(page,'OK',row['shadow_preview_regions'],'review',row['shadow_review_regions'],flush=True)
     except Exception as e:
      import traceback;row={'page':page,'status':'ERROR','error':repr(e),'traceback':traceback.format_exc()};rows.append(row);(d/'error.json').write_text(json.dumps(row,ensure_ascii=False,indent=2));print(page,'ERROR',repr(e),flush=True)
     (O/'progress.json').write_text(json.dumps({'completed_or_error':len(rows),'requested':len(pages),'last':page}))
    (O/'benchmark.json').write_text(json.dumps({'selection':pages,'elapsed_seconds':round(time.monotonic()-start,3),'peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576,1),'results':rows,'note':'Cached detection/OCR/CTD and baseline; only shadow processing timed; per-pixel labels absent'},ensure_ascii=False,indent=2));print('DONE',len(rows),round(time.monotonic()-start,2),flush=True)
