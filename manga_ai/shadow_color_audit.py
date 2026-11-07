"""Opt-in P0.4 targeted fill audit. Does not alter or authorize baseline clean."""
from dataclasses import dataclass, asdict
import cv2
import numpy as np

@dataclass(frozen=True)
class ColorAuditConfig:
    sigma_px: float = 12.0
    bright_floor: int = 245
    minimum_weight: float = .02
    warning_delta: float = 3.0

def audit_fill(source, output, mask, config=ColorAuditConfig()):
    source=np.asarray(source,dtype=np.uint8); output=np.asarray(output,dtype=np.uint8); mask=np.asarray(mask)>0
    if source.shape!=output.shape or source.shape[:2]!=mask.shape or source.ndim!=3 or source.shape[2]!=3:
        raise ValueError('source, output and mask dimensions must match')
    # Estimate background from original unmasked bright pixels in a local Gaussian
    # neighborhood. This is a diagnostic estimate, not a ground-truth label.
    valid=((np.min(source,axis=2)>=config.bright_floor)&~mask).astype(np.float32)
    weights=cv2.GaussianBlur(valid,(0,0),config.sigma_px)
    value=cv2.GaussianBlur(source.astype(np.float32)*valid[:,:,None],(0,0),config.sigma_px)
    estimate=np.clip(np.rint(value/np.maximum(weights[:,:,None],1e-6)),0,255).astype(np.uint8)
    supported=mask & (weights>=config.minimum_weight)
    delta=np.max(np.abs(output.astype(np.int16)-estimate.astype(np.int16)),axis=2)
    preview=output.copy();preview[supported]=estimate[supported]
    heat=np.zeros(mask.shape,np.uint8);heat[supported]=np.clip(delta[supported]*16,0,255).astype(np.uint8)
    values=delta[supported]
    report={'mask_pixels':int(mask.sum()),'supported_pixels':int(supported.sum()),'unsupported_pixels':int((mask&~supported).sum()),
            'baseline_delta_mean':float(np.mean(values)) if values.size else None,'baseline_delta_p95':float(np.percentile(values,95)) if values.size else None,
            'warning_pixels':int((supported&(delta>=config.warning_delta)).sum()),'warning_threshold_status':'exploratory_not_calibrated',
            'estimate':'Gaussian weighted unmasked bright original pixels; may be biased by texture, neighboring text or shading',
            'configuration':asdict(config),'authorized_to_clean':False,'pixel_ground_truth':'not_available'}
    return preview,heat,report
