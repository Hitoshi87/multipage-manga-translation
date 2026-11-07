"""Shadow-only residual proposal. Thresholds are exploratory, not calibrated."""
from dataclasses import dataclass, asdict
import cv2
import numpy as np


@dataclass(frozen=True)
class RecoveryConfig:
    ink_threshold: int = 200
    min_component_area: int = 3
    min_remaining_ink_pixels: int = 3
    min_text_box_coverage: float = .98
    min_ctd_coverage: float = .12
    min_polygon_distance_px: float = 3.0
    dilation_px: int = 3


def propose(source, current, allowed_mask, polygon, text_support, ctd, protected,
            config=RecoveryConfig()):
    """Propose mask only; original components must match text box, CTD and polygon.

    Head boxes are only coarse protection. Missing head boxes do not establish safety.
    """
    a=np.asarray(source,dtype=np.uint8); b=np.asarray(current,dtype=np.uint8)
    polygon=np.asarray(polygon)>0; support=np.asarray(text_support)>0; ctd=np.asarray(ctd)>0
    allowed=np.asarray(allowed_mask)>0; protected=np.asarray(protected)>0
    h,w=polygon.shape
    if a.shape!=(h,w,3) or b.shape!=a.shape or any(x.shape!=(h,w) for x in (support,ctd,allowed,protected)):
        raise ValueError('geometry mismatch')
    gray=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY); now=cv2.cvtColor(b,cv2.COLOR_RGB2GRAY)
    n,labels,stats,_=cv2.connectedComponentsWithStats((gray<config.ink_threshold).astype('uint8'),8)
    distance=cv2.distanceTransform(polygon.astype('uint8'),cv2.DIST_L2,5)
    ctd_near=cv2.dilate(ctd.astype('uint8'),np.ones((5,5),np.uint8))>0
    ink=np.zeros((h,w),np.uint8); decisions=[]
    for i in range(1,n):
        x,y,bw,bh,area=map(int,stats[i]); comp=labels==i
        if area<config.min_component_area or not (comp & (now<config.ink_threshold)).any():continue
        box_coverage=float((comp&support).sum()/area); ctd_coverage=float((comp&ctd_near).sum()/area)
        min_distance=float(distance[comp].min()); head_pixels=int((comp&protected).sum())
        reasons=[]
        if box_coverage<config.min_text_box_coverage:reasons.append('TEXT_BOX_UNSUPPORTED')
        if ctd_coverage<config.min_ctd_coverage:reasons.append('CTD_UNSUPPORTED')
        if min_distance<config.min_polygon_distance_px:reasons.append('NEAR_OR_OUTSIDE_POLYGON')
        if head_pixels:reasons.append('HEAD_BOX_OVERLAP')
        if bw>w*.75 or bh>h*.85:reasons.append('LARGE_COMPONENT')
        decisions.append({'component_id':i,'box':[x,y,bw,bh],'area':area,'text_box_coverage':round(box_coverage,4),
                          'ctd_coverage':round(ctd_coverage,4),'min_polygon_distance':round(min_distance,2),
                          'head_box_pixels':head_pixels,'reasons':reasons})
        if not reasons:ink[comp]=1
    radius=config.dilation_px
    mask=cv2.dilate(ink,np.ones((2*radius+1,2*radius+1),np.uint8))>0
    mask &= support & (distance>=config.min_polygon_distance_px) & ~protected & ~allowed
    remaining_ink=int((mask & (now<config.ink_threshold)).sum())
    if remaining_ink<config.min_remaining_ink_pixels:
        mask[:]=False
    return mask, {'components':decisions,'accepted':sum(not c['reasons'] for c in decisions),
                  'remaining_ink_pixels_before_minimum':remaining_ink,
                  'candidate_pixels':int(mask.sum()),'thresholds':asdict(config),
                  'threshold_status':'exploratory_not_calibrated',
                  'decision':'shadow_review','automatic_clean_authorized':False,
                  'artwork_safety':'not_verified'}
