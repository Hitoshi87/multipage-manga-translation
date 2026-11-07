"""Review-only text recovery and border audit; never grants permission to clean."""
from dataclasses import asdict,dataclass
import cv2
import numpy as np

@dataclass(frozen=True)
class RecoveryConfig:
    min_component_pixels:int=3
    min_border_distance_px:float=3.0
    text_box_padding_px:int=4
    edge_canny_low:int=50
    edge_canny_high:int=150
    edge_protect_radius_px:int=1

def review_components(source,baseline_mask,ctd_mask,polygon,text_boxes,ocr_text,config=RecoveryConfig(),protected_artwork=None):
    source=np.asarray(source,dtype=np.uint8);base=np.asarray(baseline_mask)>0;ctd=np.asarray(ctd_mask)>0;poly=np.asarray(polygon)>0
    if source.ndim!=3 or source.shape[2]!=3 or source.shape[:2]!=base.shape or ctd.shape!=base.shape or poly.shape!=base.shape:raise ValueError('shapes differ')
    h,w=base.shape;protected=None if protected_artwork is None else np.asarray(protected_artwork)>0
    if protected is not None and protected.shape!=base.shape:raise ValueError('protection shape mismatch')
    support=np.zeros((h,w),np.uint8)
    for x,y,bw,bh in text_boxes:
        if bw<=0 or bh<=0:continue
        pad=config.text_box_padding_px;support[max(0,y-pad):min(h,y+bh+pad),max(0,x-pad):min(w,x+bw+pad)]=1
    gray=cv2.cvtColor(source,cv2.COLOR_RGB2GRAY);edges=cv2.Canny(gray,config.edge_canny_low,config.edge_canny_high)>0
    # Image edges include glyphs; only boundary-near edge pixels are a border proxy.
    boundary=cv2.morphologyEx(poly.astype(np.uint8),cv2.MORPH_GRADIENT,np.ones((7,7),np.uint8))>0
    candidate=ctd&~base;n,labels,stats,_=cv2.connectedComponentsWithStats(candidate.astype(np.uint8),8);accepted=np.zeros((h,w),np.uint8);records=[]
    dist=cv2.distanceTransform(poly.astype(np.uint8),cv2.DIST_L2,5);edge_band=cv2.dilate((edges&boundary).astype(np.uint8),np.ones((2*config.edge_protect_radius_px+1,)*2,np.uint8))>0
    for i in range(1,n):
        x,y,bw,bh,area=map(int,stats[i]);comp=labels[y:y+bh,x:x+bw]==i; local=poly[y:y+bh,x:x+bw];supported=support[y:y+bh,x:x+bw]>0;dd=dist[y:y+bh,x:x+bw];border=edge_band[y:y+bh,x:x+bw]
        outside=int((comp&~local).sum());edge=int((comp&border).sum());sup=int((comp&supported).sum());risk=int((comp&protected[y:y+bh,x:x+bw]).sum()) if protected is not None else None;mind=float(dd[comp].min()) if area else None
        reasons=[]
        if area<config.min_component_pixels:reasons.append('SMALL_COMPONENT_REVIEW_PUNCTUATION')
        if sup!=area:reasons.append('TEXT_BOX_NOT_FULLY_SUPPORTED')
        if not ocr_text or not ocr_text.strip():reasons.append('OCR_EVIDENCE_MISSING')
        if outside:reasons.append('OUTSIDE_DETECTOR_POLYGON')
        if edge or (mind is not None and mind<config.min_border_distance_px):reasons.append('BORDER_PROXIMITY_REVIEW')
        if risk:reasons.append('PROTECTED_ARTWORK_OVERLAP')
        if protected is None:reasons.append('ARTWORK_LABEL_UNAVAILABLE')
        # No threshold can authorize a clean; potential candidate is only an overlay.
        potential=not any(v in reasons for v in ('SMALL_COMPONENT_REVIEW_PUNCTUATION','TEXT_BOX_NOT_FULLY_SUPPORTED','OCR_EVIDENCE_MISSING','OUTSIDE_DETECTOR_POLYGON','BORDER_PROXIMITY_REVIEW','PROTECTED_ARTWORK_OVERLAP'))
        if potential:accepted[y:y+bh,x:x+bw][comp]=1
        records.append({'component_id':i,'box_xywh':[x,y,bw,bh],'pixels':area,'text_box_supported_pixels':sup,'outside_polygon_pixels':outside,'border_edge_proxy_overlap':edge,'min_polygon_distance_px':round(mind,2) if mind is not None else None,'protected_overlap':risk,'potential_preview':potential,'decision':'review','reasons':reasons})
    return accepted,{'thresholds':asdict(config),'threshold_status':'uncalibrated','components':records,'candidate_pixels':int(candidate.sum()),'potential_preview_pixels':int(accepted.sum()),'authorized_to_clean':False,'polygon':'detector estimate, not actual labeled contour','artwork_protection':'unknown' if protected is None else 'supplied mask requires verification','ocr_text_model':ocr_text}
