"""Opt-in shadow-only selective local-color compositor; no production policy changes."""
from dataclasses import asdict
import cv2
import numpy as np
from .shadow_color_audit import ColorAuditConfig, audit_fill


def selective_color_preview(source, candidate_mask, config=ColorAuditConfig(bright_floor=245)):
    """Fill only pixels for which the existing local estimator has support.

    Unsupported pixels are retained and reported. Support is not evidence of
    artwork safety or text completeness. Caller must validate ownership first.
    """
    source=np.asarray(source,dtype=np.uint8)
    candidate=np.asarray(candidate_mask)>0
    if source.ndim!=3 or source.shape[2]!=3 or source.shape[:2]!=candidate.shape:
        raise ValueError('source and mask dimensions must match')
    valid=((source.min(axis=2)>=config.bright_floor)&~candidate).astype(np.float32)
    weights=cv2.GaussianBlur(valid,(0,0),config.sigma_px)
    supported=candidate & (weights>=config.minimum_weight)
    estimate,_,audit=audit_fill(source,source,candidate,config)
    result=source.copy()
    result[supported]=estimate[supported]
    assert not np.any(np.any(result!=source,axis=2)&~supported)
    return result,supported,{'candidate_pixels':int(candidate.sum()),'supported_pixels':int(supported.sum()),'unsupported_pixels':int((candidate&~supported).sum()),'unsupported_action':'retain_for_review','configuration':asdict(config),'audit':audit,'authorized_to_clean':False,'artwork_safety':'not_verified','completeness':'not_verified'}
