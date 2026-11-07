"""Shadow-only glyph component proposals; never authorizes cleaning."""
from dataclasses import dataclass,asdict
import cv2,numpy as np
@dataclass(frozen=True)
class Config:
 dark_threshold:int=180
 min_area:int=5
 max_area:int=2500
 dilation_px:int=2
 structural_guard_px:int=1
 minimum_ctd_fraction:float=.05

def propose(image,baseline,ctd,text_boxes,ocr,config=Config(),scope_polygon=None):
 image=np.asarray(image,dtype=np.uint8);base=np.asarray(baseline)>0;ctd=np.asarray(ctd)>0;h,w=base.shape
 if image.shape!=(h,w,3) or ctd.shape!=(h,w):raise ValueError('shape mismatch')
 if config.dilation_px<0 or config.structural_guard_px<0:raise ValueError('negative radius')
 scope=None if scope_polygon is None else np.asarray(scope_polygon)>0
 if scope is not None and scope.shape!=base.shape:raise ValueError('scope shape mismatch')
 gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY);num,labels,stats,_=cv2.connectedComponentsWithStats((gray<config.dark_threshold).astype('uint8'),8);support=np.zeros((h,w),np.uint8)
 for x,y,bw,bh in text_boxes:
  support[max(0,y):min(h,y+bh),max(0,x):min(w,x+bw)]=1
 structure=np.zeros((h,w),np.uint8)
 for i in range(1,num):
  x,y,bw,bh,area=map(int,stats[i]);comp=labels[y:y+bh,x:x+bw]==i
  if area>config.max_area or x==0 or y==0 or x+bw>=w or y+bh>=h:structure[y:y+bh,x:x+bw][comp]=1
 k=2*config.structural_guard_px+1;protect=cv2.dilate(structure,np.ones((k,k),np.uint8))>0;added=np.zeros((h,w),np.uint8);recs=[]
 for i in range(1,num):
  x,y,bw,bh,area=map(int,stats[i]);pad=config.dilation_px;left=max(0,x-pad);top=max(0,y-pad);right=min(w,x+bw+pad);bottom=min(h,y+bh+pad);component=labels[top:bottom,left:right]==i;local_support=support[top:bottom,left:right];local_ctd=ctd[top:bottom,left:right];local_protect=protect[top:bottom,left:right];reasons=[]
  if area<config.min_area:reasons.append('SMALL_DOT_OR_NOISE_REVIEW')
  if area>config.max_area or x==0 or y==0 or x+bw>=w or y+bh>=h:reasons.append('STRUCTURE_OR_CROP_EDGE')
  if not np.any(component & (local_support>0)):reasons.append('NO_TEXT_BOX_SUPPORT')
  fraction=float((component&local_ctd).sum()/max(1,area))
  if fraction<config.minimum_ctd_fraction:reasons.append('LOW_CTD_SUPPORT')
  if not ocr or not ocr.strip():reasons.append('OCR_EVIDENCE_MISSING')
  k=2*config.dilation_px+1;expanded=cv2.dilate(component.astype('uint8'),np.ones((k,k),np.uint8))>0;hits=int((expanded&local_protect).sum())
  if hits:reasons.append('STRUCTURAL_GUARD_COLLISION')
  if scope is not None and np.any(expanded & ~scope[top:bottom,left:right]):reasons.append('OUTSIDE_BUBBLE_SCOPE')
  accepted=not reasons
  if accepted:added[top:bottom,left:right][expanded]=1
  recs.append({'id':i,'box':[x,y,bw,bh],'area':area,'ctd_overlap_fraction':round(fraction,4),'structural_guard_collision_pixels':hits,'preview_candidate':accepted,'reason_codes':reasons})
 added[base]=0
 return added,{'components':recs,'added_pixels':int(added.sum()),'thresholds':asdict(config),'threshold_status':'uncalibrated','artwork_safety':'unverified','authorized_to_clean':False,'method':'dark component candidates + text box + CTD + regional OCR + structural proxy; no manual 111 coordinates'}
