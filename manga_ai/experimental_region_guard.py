"""Opt-in region preview mask: baseline ∩ full-page CTD ∩ text evidence.

Uncalibrated; preview only. Does not approve cleaning or modify baseline.
"""
from dataclasses import dataclass,asdict
import cv2,numpy as np
@dataclass(frozen=True)
class GuardConfig:
 text_padding_px:int=3
 ctd_dilation_px:int=2
 min_ocr_characters:int=1

def guard_mask(image,baseline_mask,ctd_mask,text_boxes,ocr_text,config=GuardConfig()):
 image=np.asarray(image,dtype=np.uint8);base=np.asarray(baseline_mask)>0;ctd=np.asarray(ctd_mask)>0;h,w=base.shape
 if image.shape!=(h,w,3) or ctd.shape!=base.shape:raise ValueError('mask geometry mismatch')
 support=np.zeros((h,w),np.uint8)
 for x,y,bw,bh in text_boxes:
  if bw<=0 or bh<=0:continue
  p=config.text_padding_px;support[max(0,y-p):min(h,y+bh+p),max(0,x-p):min(w,x+bw+p)]=1
 if config.ctd_dilation_px<0 or config.text_padding_px<0:raise ValueError('negative padding')
 k=2*config.ctd_dilation_px+1;ctd_safe=cv2.dilate(ctd.astype('uint8'),np.ones((k,k),np.uint8))>0
 output=base&ctd_safe&(support>0);reasons=[]
 if not text_boxes:reasons.append('NO_TEXT_DETECTION')
 if len((ocr_text or '').strip())<config.min_ocr_characters:reasons.append('NO_OCR_EVIDENCE');output[:]=False
 if not output.any():reasons.append('EMPTY_GUARDED_MASK')
 # It is critical that rejection is visible: components are not silently declared complete.
 removed=base&~output
 return output,{'baseline_mask_pixels':int(base.sum()),'ctd_supported_pixels':int((base&ctd_safe).sum()),'text_box_supported_pixels':int((base&(support>0)).sum()),'guarded_pixels':int(output.sum()),'removed_pixels':int(removed.sum()),'removed_reasons':{'outside_ctd':int((base&~ctd_safe).sum()),'outside_text_box':int((base&~(support>0)).sum())},'rule_ids':reasons,'thresholds':asdict(config),'threshold_status':'uncalibrated','decision':'review','authorized_to_clean':False,'artwork_safety':'not_verified','mask_coverage':'unverified'}
