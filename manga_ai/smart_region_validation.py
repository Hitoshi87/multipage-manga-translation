"""Opt-in P0.3 primitives. Thresholds are experimental, not calibrated."""
from dataclasses import dataclass, asdict
import hashlib,json
import cv2
import numpy as np

@dataclass(frozen=True)
class RegionConfig:
    grouping_kernel: int = 45
    max_ocr_regions_per_page: int = 4
    min_mask_pixels: int = 20
    min_bubble_overlap: float = .95
    min_flat_fraction: float = .95
    min_mask_agreement: float = .50
    max_protected_overlap: float = 0.0
    max_crop_area_fraction: float = .12
    min_japanese_chars: int = 1
    white_pixel_threshold: int = 235
    min_background_samples: int = 30
    head_padding_fraction: float = .08
    text_box_overlap: float = .10
    orientation_ratio: float = 1.2
    canny_low: int = 80
    canny_high: int = 160
    line_hough_threshold: int = 50
    min_line_length: int = 40
    line_length_divisor: int = 3
    line_max_gap: int = 5
    structural_line_count: int = 2
    screentone_low: int = 45
    screentone_high: int = 210
    screentone_fraction: float = .15
    ocr_max_dimension: int = 1200
    ocr_psm: int = 5
    ocr_timeout: int = 20
    baberu_max_tokens: int = 32
    # P0.3 is a demonstrator; activation is separate from production.
    experiment_enable_candidate_clean: bool = True

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()


def group_regions(mask, kernel):
    """Group strokes by morphology, return labels and bounds; mask pixels remain unchanged."""
    if kernel < 1 or kernel % 2 == 0:
        raise ValueError('grouping kernel must be a positive odd number')
    mask=(mask>0).astype(np.uint8)
    expanded=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_RECT,(kernel,kernel)))
    count,labels,stats,_=cv2.connectedComponentsWithStats(expanded,8)
    regions=[]
    for i in range(1,count):
        x,y,w,h,_=map(int,stats[i]); local=(labels[y:y+h,x:x+w]==i)&(mask[y:y+h,x:x+w]>0)
        if local.any():regions.append({'label':i,'box':[x,y,w,h],'mask_pixels':int(local.sum())})
    return labels,regions


def japanese_evidence(text):
    return sum(1 for c in text if '\u3040'<=c<='\u30ff' or '\u3400'<=c<='\u9fff')


def decide(e, c):
    """No single signal can authorize; low/unknown evidence requires review."""
    reasons=[]
    if not e.get('ocr_ran'):reasons.append('ocr_not_run')
    elif e.get('japanese_chars',0)<c.min_japanese_chars:reasons.append('ocr_no_japanese_evidence')
    if e.get('bubble_overlap',0)<c.min_bubble_overlap:reasons.append('bubble_evidence_insufficient')
    if e.get('flat_fraction',0)<c.min_flat_fraction:reasons.append('complex_or_nonflat_background')
    if e.get('mask_agreement',0)<c.min_mask_agreement:reasons.append('independent_text_mask_disagreement')
    if e.get('protected_overlap',1)>c.max_protected_overlap:reasons.append('protected_art_or_head_overlap')
    if e.get('too_large',True):reasons.append('large_or_ambiguous_region')
    if e.get('mask_pixels',0)<c.min_mask_pixels:reasons.append('insufficient_mask_pixels')
    if not c.experiment_enable_candidate_clean:reasons.append('experimental_clean_disabled')
    return ('candidate_auto' if not reasons else 'review', reasons)


def rollback_region(image, original, region_mask):
    out=image.copy(); out[region_mask>0]=original[region_mask>0];return out


def fill_candidate_flat(rgb, mask, white_threshold, min_background_samples=30):
    """Fill an already verified candidate locally without inventing confidence."""
    background = rgb[(mask == 0) & (np.min(rgb, axis=2) >= white_threshold)]
    result = rgb.copy()
    if len(background) < min_background_samples or not np.any(mask):
        return result, np.zeros(mask.shape, np.uint8)
    result[mask > 0] = np.median(background, axis=0).astype(np.uint8)
    return result, (mask > 0).astype(np.uint8)


def route_for_review(decision, reasons, background):
    """A missing inference can be retried; artwork stays with a human reviewer."""
    if decision == 'candidate_auto':
        return 'candidate_auto'
    if background != 'flat' or 'protected_art_or_head_overlap' in reasons:
        return 'review'
    if 'ocr_not_run' in reasons:
        return 'fallback'
    return 'review'
