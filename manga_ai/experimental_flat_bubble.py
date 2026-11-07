"""P0.3-D isolated shadow experiment. Never imported by the production pipeline.

The caller supplies the *already computed full-page* CTD mask projected to the
crop. This module cannot invoke CTD. Thresholds are uncalibrated experiment
parameters, and decisions never authorize production cleaning.
"""
from dataclasses import dataclass, asdict
import cv2
import numpy as np

@dataclass(frozen=True)
class ShadowConfig:
    dilation_px: int = 1
    min_border_px: float = 2.0
    bright_floor: int = 235
    max_background_std: float = 12.0
    min_background_samples: int = 100
    sigma: float = 12.0


def shadow_clean(context, crop_xywh, full_page_ctd, bubble, evidence, config=ShadowConfig(), protected=None, text_label=None, labels_independent=False):
    """Return previews and auditable checks, not a production clean decision."""
    x,y,w,h = map(int,crop_xywh)
    src = np.asarray(context, dtype=np.uint8)[y:y+h,x:x+w].copy()
    mask = np.asarray(full_page_ctd)>0
    poly = np.asarray(bubble)>0
    if src.shape[:2] != (h,w) or mask.shape != (h,w) or poly.shape != (h,w):
        raise ValueError('crop, full-page CTD mask and bubble must have matching dimensions')
    if config.dilation_px not in (0,1):
        raise ValueError('only 0 or experimental 1 pixel dilation is supported')
    protected_array = None if protected is None else np.asarray(protected)>0
    label = None if text_label is None else np.asarray(text_label)>0
    for a in (protected_array,label):
        if a is not None and a.shape != mask.shape: raise ValueError('label shape mismatch')
    trial = cv2.dilate(mask.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool) if config.dilation_px else mask.copy()
    # Distance is checked on original AND dilated candidate; never clip a mask to force acceptance.
    distance = cv2.distanceTransform(poly.astype(np.uint8),cv2.DIST_L2,5)
    def stats(m):
        return {'pixels':int(m.sum()),'outside_polygon':int((m & ~poly).sum()),
                'min_border_distance_px':round(float(distance[m].min()),3) if m.any() else None,
                'protected_overlap':int((m & protected_array).sum()) if protected_array is not None else None,
                'labeled_text_uncovered':int((label & ~m).sum()) if label is not None else None}
    original_stats, trial_stats = stats(mask), stats(trial)
    ring=cv2.dilate(trial.astype(np.uint8),np.ones((31,31),np.uint8)).astype(bool) & ~trial & poly
    # Estimate flatness from all ring pixels rather than selectively discarding dark pixels.
    if protected_array is not None: ring &= ~protected_array
    samples=src[ring]
    lum=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY)
    flat_std=float(np.std(cv2.cvtColor(samples.reshape(1,-1,3),cv2.COLOR_RGB2GRAY))) if len(samples) else None
    flat = bool(len(samples)>=config.min_background_samples and flat_std is not None and flat_std<=config.max_background_std and np.median(lum[ring])>=config.bright_floor)
    text_valid=bool(evidence.get('japanese_characters',0)>0 and evidence.get('has_text_proposal',False))
    reasons=[]
    if not text_valid: reasons.append('TEXT_EVIDENCE_INSUFFICIENT')
    if not mask.any(): reasons.append('EMPTY_CTD_MASK')
    if not flat: reasons.append('BACKGROUND_NOT_PROVEN_FLAT')
    if trial_stats['outside_polygon'] or trial_stats['min_border_distance_px'] is None or trial_stats['min_border_distance_px'] < config.min_border_px: reasons.append('BUBBLE_BORDER_RISK')
    if trial_stats['protected_overlap']: reasons.append('PROTECTED_ARTWORK_OVERLAP')
    if label is not None and trial_stats['labeled_text_uncovered']: reasons.append('LABELED_TEXT_NOT_FULLY_COVERED')
    if not labels_independent or protected_array is None or label is None: reasons.append('INDEPENDENT_PIXEL_LABELS_MISSING')
    # Preview is deliberately not an authorization, even if independent labels are supplied.
    # For preview we require observable text, measured flatness and geometric safety.
    preview_ok = not any(r in reasons for r in ('TEXT_EVIDENCE_INSUFFICIENT','EMPTY_CTD_MASK','BACKGROUND_NOT_PROVEN_FLAT','BUBBLE_BORDER_RISK','PROTECTED_ARTWORK_OVERLAP','LABELED_TEXT_NOT_FULLY_COVERED'))
    outputs={}
    for name,m in [('original',mask),('dilated',trial)]:
        cm=np.zeros(context.shape[:2],np.uint8);cm[y:y+h,x:x+w]=m
        valid=((np.min(context,axis=2)>=config.bright_floor)&(cm==0)).astype(np.float32)
        weight=cv2.GaussianBlur(valid,(0,0),config.sigma)
        num=cv2.GaussianBlur(context.astype(np.float32)*valid[:,:,None],(0,0),config.sigma)
        fill=np.clip(np.rint(num/np.maximum(weight[:,:,None],1e-6)),0,255).astype(np.uint8)
        if np.any(valid): fill[weight<.01]=np.median(context[valid>0],axis=0).astype(np.uint8)
        patch=fill[y:y+h,x:x+w]; out=src.copy();out[m]=patch[m]
        outputs[name]=(out,m,patch)
    trace={'mode':'shadow_only','authorized_to_clean':False,'preview_eligible':preview_ok,'reasons':reasons,
           'thresholds':asdict(config),'threshold_status':'uncalibrated_exploratory',
           'text_validity':{'heuristic_pass':text_valid,'model_evidence':evidence},
           'background':{'sample_count':int(len(samples)),'luminance_std':round(flat_std,3) if flat_std is not None else None,'flat_heuristic_pass':flat},
           'original_mask':original_stats,'dilated_mask':trial_stats,
           'independent_pixel_labels':bool(labels_independent and protected_array is not None and label is not None),
           'artwork_safety':'unverified' if not labels_independent or protected_array is None else 'requires_manual_quality_review',
           'mask_source':'full_page_ctd_precomputed','ocr_or_bubble_confidence_can_override_safety':False}
    return outputs, trace
