"""Opt-in shadow evidence for residual text near crop, polygon and head boxes.

Uncalibrated heuristics: a text box or dark-component separation alone is not
evidence that a region is safe to clean. Never use to authorize production.
"""
from dataclasses import asdict, dataclass
import cv2
import numpy as np


@dataclass(frozen=True)
class Config:
    ink_threshold: int = 200
    min_area: int = 3
    min_residual: int = 3
    text_overlap: float = .70
    ctd_overlap: float = .55
    ctd_direct_overlap: float = .15
    dilation_px: int = 2
    safe_other_dark_distance: float = 3.0
    background_dark_fraction_review: float = .10


def background_evidence(gray, ctd, config=Config()):
    ink=np.asarray(ctd)>0
    band=(cv2.dilate(ink.astype('uint8'),np.ones((21,21),np.uint8))>0)&~ink
    values=np.asarray(gray)[band]
    fraction=float((values<180).mean()) if values.size else None
    return {'sample_pixels':int(values.size),'dark_fraction':fraction,
            'complex_for_review':bool(values.size and fraction>config.background_dark_fraction_review),
            'threshold':config.background_dark_fraction_review,'calibrated':False}


def propose(source,current,used,text_support,ctd,protected,config=Config()):
    src=np.asarray(source,np.uint8);out=np.asarray(current,np.uint8)
    used=np.asarray(used)>0;support=np.asarray(text_support)>0;ctd=np.asarray(ctd)>0;protected=np.asarray(protected)>0
    h,w=used.shape
    if src.shape!=(h,w,3) or out.shape!=src.shape or any(z.shape!=(h,w) for z in (support,ctd,protected)):
        raise ValueError('geometry mismatch')
    gray=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY); now=cv2.cvtColor(out,cv2.COLOR_RGB2GRAY)
    n,labels,stats,_=cv2.connectedComponentsWithStats((gray<config.ink_threshold).astype('uint8'),8)
    near_ctd=cv2.dilate(ctd.astype('uint8'),np.ones((5,5),np.uint8))>0
    components=[]; chosen=np.zeros((h,w),np.uint8)
    for i in range(1,n):
        x,y,bw,bh,area=map(int,stats[i]);pixels=labels==i
        remaining=int((pixels&(now<config.ink_threshold)&~used).sum())
        if area<config.min_area or remaining<config.min_residual:continue
        text=float((pixels&support).sum()/area); cover=float((pixels&near_ctd).sum()/area);direct=float((pixels&ctd).sum()/area)
        reasons=[]
        if text<config.text_overlap:reasons.append('TEXT_SUPPORT_LOW')
        if cover<config.ctd_overlap:reasons.append('CTD_SUPPORT_LOW')
        if direct<config.ctd_direct_overlap:reasons.append('CTD_DIRECT_SUPPORT_LOW')
        if x==0 or y==0 or x+bw>=w or y+bh>=h:reasons.append('CONTEXT_EDGE')
        if bw>w*.70 or bh>h*.80:reasons.append('LARGE_COMPONENT')
        components.append({'id':i,'box':[x,y,bw,bh],'area':area,'remaining':remaining,
             'text_fraction':round(text,4),'ctd_fraction':round(cover,4),'ctd_direct_fraction':round(direct,4),
             'head_box_pixels':int((pixels&protected).sum()),'reasons':reasons})
        if not reasons:chosen[pixels]=1
    # Treat non-selected dark components as potential structure, even within head
    # boxes. Head box intersection itself is a warning; local clearance is not GT.
    other=(gray<config.ink_threshold)&~(chosen>0)
    other_distance=cv2.distanceTransform((~other).astype('uint8'),cv2.DIST_L2,5)
    unsafe=(chosen>0)&(other_distance<=config.safe_other_dark_distance)
    for c in components:
        if not c['reasons'] and (unsafe&(labels==c['id'])).any():
            c['reasons'].append('DARK_STRUCTURE_TOO_CLOSE');chosen[labels==c['id']]=0
    radius=config.dilation_px
    raw=cv2.dilate(chosen,np.ones((2*radius+1,2*radius+1),np.uint8))>0
    other=(gray<config.ink_threshold)&~(chosen>0)
    other_distance=cv2.distanceTransform((~other).astype('uint8'),cv2.DIST_L2,5)
    result=raw&(other_distance>config.safe_other_dark_distance)&~used
    # Do not silently clip dark ink from selected glyphs; leave region for review.
    missing=int(((chosen>0)&~result&~used).sum())
    if missing:result[:]=False
    return result,{'components':components,'candidate_pixels':int(result.sum()),'clipped_ink_pixels':missing,
                   'head_box_mask_intersection':int((result&protected).sum()),
                   'thresholds':asdict(config),'threshold_status':'not_calibrated',
                   'artwork_safety':'unverified','production_authorized':False}
