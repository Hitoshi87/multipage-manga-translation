"""Opt-in reconstruction of text over artwork for editable, reviewable drafts.

The restored pixels are generated, never verified original artwork. The engine
only modifies text-supported regions selected in mapping and clips to the
balloon interior. It does not silently change the default clean engine.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .engine import check_cancel,read_image,render_clean,save_image
from .io import checked_mapping,read_json,validate_manifest
from .text_recovery import outline_interior


def _local_glyph_mask(rgb,region,base,detections):
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);height,width=gray.shape
    x,y,w,h=region['box'];polygon=outline_interior(region)
    if polygon is None or region.get('detector')!='ai_balloon':return None
    interior=cv2.erode(polygon,np.ones((7,7),np.uint8))>0
    mask=np.zeros((height,width),np.uint8);matched=0
    for d in detections:
        if d.get('kind')!='in_bubble' or d.get('confidence',0)<.9:continue
        tx,ty,tw,th=d['box'];overlap=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
        if overlap/max(1,tw*th)<.85:continue
        matched+=1;x0=max(0,tx-8);y0=max(0,ty-8);x1=min(width,tx+tw+8);y1=min(height,ty+th+8)
        black=(gray[y0:y1,x0:x1]<110).astype(np.uint8)
        n,labels,stats,_=cv2.connectedComponentsWithStats(black,8)
        for i in range(1,n):
            xx,yy,ww,hh,area=stats[i]
            # Avoid large artwork components and clipped shapes.
            if area<3 or area>1600 or ww>75 or hh>75 or xx==0 or yy==0 or xx+ww>=x1-x0 or yy+hh>=y1-y0:continue
            component=labels[yy:yy+hh,xx:xx+ww]==i
            evidence=base[y0+yy:y0+yy+hh,x0+xx:x0+xx+ww]>0
            if np.count_nonzero(component&evidence)/area<.3:continue
            patch=mask[y0+yy:y0+yy+hh,x0+xx:x0+xx+ww];patch[component]=1
    if not matched or np.count_nonzero(mask)<8:return None
    mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
    mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))
    allowed=np.zeros_like(mask);allowed[y:y+h,x:x+w]=interior.astype(np.uint8);mask*=allowed
    # Refuse an almost whole-balloon erasure or a suspiciously tiny mask.
    if np.count_nonzero(mask)<8 or np.count_nonzero(mask)>np.count_nonzero(interior)*.65:return None
    return mask


def render(manifest_path,mapping,cancel=None,preview=False):
    from .model_preview import detailed_mask,lama_clean
    manifest_path=Path(manifest_path).resolve();root=manifest_path.parent
    manifest=validate_manifest(read_json(manifest_path));mapping=checked_mapping(manifest,mapping)
    original=read_image(root/'original.png')
    result=render_clean(manifest_path,mapping,cancel,preview=True)
    skipped=set(result['skipped']);regions={r['id']:r for r in manifest['regions']}
    selected=[m['id'] for m in mapping if m['clean'] and m['id'] in skipped]
    with Image.open(result['overlay']) as im:overlay=np.asarray(im.convert('RGBA')).copy()
    risk=[];art_mask=np.zeros(original.shape[:2],np.uint8)
    if selected:
        check_cancel(cancel);base,detections=detailed_mask(original,'ctd',cancel)
        for rid in selected:
            check_cancel(cancel);candidate=_local_glyph_mask(original,regions[rid],base,detections)
            if candidate is None:continue
            # Never let one selected region erase pixels of an unselected bubble.
            for other in manifest['regions']:
                if other['id']==rid or other['id'] in selected:continue
                ox,oy,ow,oh=other['box'];candidate[oy:oy+oh,ox:ox+ow]=0
            if not np.any(candidate):continue
            art_mask=np.maximum(art_mask,candidate);risk.append(rid)
    if risk:
        reconstructed=lama_clean(original,art_mask,cancel);active=(art_mask>0)&(overlay[:,:,3]==0)
        overlay[active,:3]=reconstructed[active];overlay[active,3]=255
    path=root/('trial_art_draft_overlay.png' if preview else 'art_draft_overlay.png');save_image(path,overlay)
    return {'overlay':str(path),'applied':result['applied']+risk,'skipped':[x for x in result['skipped'] if x not in risk],
            'blocked':{k:v for k,v in result['blocked'].items() if k not in risk},
            'skip_reason_codes':{k:v for k,v in result.get('skip_reason_codes',{}).items() if k not in risk},
            'art_inpaint_ids':risk,'review_required':True,'manifest':str(manifest_path)}
