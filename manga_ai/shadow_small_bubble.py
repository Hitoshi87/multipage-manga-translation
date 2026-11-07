"""P0.3-B shadow-only experiments; does not alter production clean rules."""
from dataclasses import asdict,dataclass
import re
import cv2,numpy as np

@dataclass(frozen=True)
class ShadowConfig:
    min_ocr_confidence: float = 85.0
    min_bubble_confidence: float = .9
    min_text_detection_confidence: float = .9
    min_border_distance_px: float = 3.0
    roi_padding_fraction: float = .18
    max_dilation_radius: int = 4
    min_japanese_characters: int = 1
    max_japanese_characters: int = 3
    require_independent_text_box: bool = True
    dark_pixel_threshold: int = 210
    min_ocr_ink_coverage: float = .90


def adaptive_roi_mask(image,ctd,words,polygon,config):
    """Return an experimental OCR-box supported mask and diagnostics.

    Only components touching an OCR ROI seed are admitted. Components touching
    the edge of the crop, or intersecting outside the ROI, are flagged rather
    than silently clipped. Coordinates and radii are crop-local pixels.
    """
    h,w=ctd.shape;roi=np.zeros((h,w),np.uint8)
    for word in words:
        x,y,bw,bh=word['box'];pad=max(1,round(min(bw,bh)*config.roi_padding_fraction))
        x0,y0=max(0,int(x-pad)),max(0,int(y-pad));x1,y1=min(w,int(x+bw+pad)),min(h,int(y+bh+pad))
        if x1>x0 and y1>y0:roi[y0:y1,x0:x1]=1
    count,labels,stats,_=cv2.connectedComponentsWithStats((ctd>0).astype(np.uint8),8)
    chosen=np.zeros((h,w),np.uint8);partial=0;at_edge=0
    for label in range(1,count):
        x,y,bw,bh,area=map(int,stats[label]); comp=labels[y:y+bh,x:x+bw]==label
        if not np.any(comp & (roi[y:y+bh,x:x+bw]>0)):continue
        if np.any(comp & (roi[y:y+bh,x:x+bw]==0)):partial+=1
        if x==0 or y==0 or x+bw==w or y+bh==h:at_edge+=1
        chosen[y:y+bh,x:x+bw][comp]=1
    radius=1
    if chosen.any():
        dist=cv2.distanceTransform(chosen,cv2.DIST_L2,3);radius=max(1,min(config.max_dilation_radius,round(float(np.median(dist[chosen>0])))))
    dil=cv2.dilate(chosen,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))
    # Never silently clip to bubble: leave the candidate intact and reject it.
    inner=(polygon>0).astype(np.uint8);distance=cv2.distanceTransform(inner,cv2.DIST_L2,3)
    outside=int(np.count_nonzero((dil>0)&(inner==0)))
    mindist=float(distance[dil>0].min()) if dil.any() else None
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    dark_roi=(gray<config.dark_pixel_threshold)&(roi>0)
    dark_count=int(dark_roi.sum())
    coverage=float(np.count_nonzero(dark_roi&(dil>0))/dark_count) if dark_count else None
    return roi,chosen,dil,{'selected_pixels':int(chosen.sum()),'dilated_pixels':int(dil.sum()),'partial_roi_components':partial,'crop_edge_components':at_edge,'dilation_radius':radius,'outside_polygon_pixels':outside,'min_border_distance_px':mindist,'ocr_roi_dark_pixels_heuristic':dark_count,'ocr_roi_ink_coverage_heuristic':coverage}


def shadow_decision(region,words,text_conf,mask_diag,config):
    text=''.join(w['text'] for w in words);chars=re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]',text)
    conf=sum(w['confidence'] for w in words)/len(words) if words else None
    validity={'japanese_chars':len(chars),'ocr_mean_model':conf,'ocr_words':words,'text_detector_confidence_model':text_conf,'bubble_confidence_model':region.get('detector_confidence')}
    reasons=[]
    if not config.min_japanese_characters<=len(chars)<=config.max_japanese_characters:reasons.append('NOT_1_TO_3_CJK')
    if conf is None or conf<config.min_ocr_confidence:reasons.append('OCR_CONFIDENCE_LOW_OR_MISSING')
    if float(region.get('detector_confidence') or 0)<config.min_bubble_confidence:reasons.append('BUBBLE_CONFIDENCE_LOW_OR_MISSING')
    if config.require_independent_text_box and text_conf<config.min_text_detection_confidence:reasons.append('TEXT_BOX_CONFIDENCE_LOW_OR_MISSING')
    if mask_diag['selected_pixels']==0:reasons.append('EMPTY_TEXT_MASK')
    if mask_diag['partial_roi_components']:reasons.append('COMPONENT_EXTENDS_BEYOND_ROI')
    if mask_diag['crop_edge_components']:reasons.append('COMPONENT_TOUCHES_CROP_EDGE')
    if mask_diag['outside_polygon_pixels']:reasons.append('MASK_OUTSIDE_BUBBLE')
    if mask_diag['min_border_distance_px'] is None or mask_diag['min_border_distance_px']<config.min_border_distance_px:reasons.append('MASK_NEAR_BORDER')
    if mask_diag.get('ocr_roi_ink_coverage_heuristic') is None or mask_diag['ocr_roi_ink_coverage_heuristic']<config.min_ocr_ink_coverage:reasons.append('OCR_ROI_INK_COVERAGE_INSUFFICIENT')
    decision = 'review' if reasons else 'candidate_only'
    if decision == 'candidate_only':
        reasons.append('ARTWORK_NOT_MANUALLY_VERIFIED_SHADOW_ONLY')
    return {'text_validity':validity,'mask_quality':mask_diag,'artwork_safety':'not_proven_by_polygon_or_head_boxes','decision':decision,'reason_codes':reasons,'uncalibrated':True,'authorized_to_clean':False}


def provenance_from_trace(region, gate_event, fallback_event):
    """Preserve measured OCR separately from eligibility; never change manifest."""
    words = gate_event.get('group', [])
    reason_codes = []
    chars = re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]', ''.join(w['text'] for w in words))
    if gate_event.get('touches_edge') and len(chars) < 3:
        reason_codes.append('CJK_NEAR_BORDER_REQUIRES_3_CHARS')
    if fallback_event and fallback_event.get('rule_id'):
        reason_codes.append(fallback_event['rule_id'])
    return {'region_id':region['id'],'source_text':region.get('source'),
            'ocr_confidence_model_mean':gate_event.get('confidence'),
            'ocr_words_model':words,'legacy_manifest_confidence':region.get('confidence'),
            'legacy_confidence_is_placeholder':region.get('ocr_status')=='unconfirmed',
            'clean_decision':'review','reason_codes':reason_codes,
            'fallback_observed_ratio_heuristic':fallback_event.get('observed') if fallback_event else None}
