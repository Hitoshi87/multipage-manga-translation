"""Experimental multi-region component arbitration, strictly preview only."""
import cv2,numpy as np

def arbitrate(rgb,baseline_masks,extra_masks,text_boxes_by_region,origin=(0,0),minimum_text_overlap=.7):
 rgb=np.asarray(rgb,dtype=np.uint8);h,w=rgb.shape[:2];ids=sorted(baseline_masks)
 if set(ids)!=set(extra_masks) or any(np.asarray(d[k]).shape!=(h,w) for d in (baseline_masks,extra_masks) for k in ids):raise ValueError('invalid masks')
 base={k:np.asarray(baseline_masks[k])>0 for k in ids};extra={k:np.asarray(extra_masks[k])>0 for k in ids};owned={k:np.zeros((h,w),np.uint8) for k in ids}
 gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);n,labels,stats,_=cv2.connectedComponentsWithStats((gray<180).astype('uint8'),8);records=[]
 for i in range(1,n):
  x,y,bw,bh,area=map(int,stats[i]);component=labels[y:y+bh,x:x+bw]==i;support={rid:int((component&extra[rid][y:y+bh,x:x+bw]).sum()) for rid in ids};active=[rid for rid in ids if support[rid]]
  if not active:continue
  if len(active)==1:owner=active[0];reason='ONE_PROPOSAL_ONLY'
  else:
   ordered=sorted(active,key=lambda rid:(-support[rid],rid));owner=ordered[0] if support[ordered[0]]>support[ordered[1]] else None;reason='MORE_COMPONENT_PIXELS' if owner else 'TIE_UNRESOLVED'
   if owner is None:
    cx=x+origin[0]+bw/2;cy=y+origin[1]+bh/2;matches=[rid for rid in active if any(dx<=cx<dx+dw and dy<=cy<dy+dh for dx,dy,dw,dh in text_boxes_by_region.get(rid,[]))]
    if len(matches)==1:owner=matches[0];reason='TIE_UNIQUE_TEXT_BOX_UNCALIBRATED'
  if owner:
   lx=max(0,x-2);ly=max(0,y-2);rx=min(w,x+bw+2);ry=min(h,y+bh+2);part=(labels[ly:ry,lx:rx]==i).astype('uint8');expanded=cv2.dilate(part,np.ones((5,5),np.uint8))>0;owned[owner][ly:ry,lx:rx][expanded&extra[owner][ly:ry,lx:rx]]=1
  records.append({'id':i,'box_global':[x+origin[0],y+origin[1],bw,bh],'source_dark_pixels':area,'owner':owner,'reason':reason,'proposed_dark_overlap':support})
 # Remove ambiguous halos and any ownership proposal colliding with a different baseline.
 assigned_count=np.zeros((h,w),np.uint16)
 for k in ids:assigned_count+=(owned[k]>0).astype('uint16')
 ambiguous=assigned_count>1
 for k in ids:
  foreign=np.zeros((h,w),bool)
  for q in ids:
   if q!=k:foreign|=base[q]
  owned[k][ambiguous|foreign]=0
 masks={k:base[k]|(owned[k]>0) for k in ids};count=np.zeros((h,w),np.uint16)
 for k in ids:count+=masks[k]
 # Baseline collisions are not silently edited; refuse to produce a joint preview.
 conflicting=int((count>1).sum())
 return masks,{'components':records,'ambiguous_halo_pixels':int(ambiguous.sum()),'remaining_mask_conflict_pixels':conflicting,'authorized_to_clean':False,'thresholds_uncalibrated':{'dark_threshold':180,'text_box_containment':minimum_text_overlap,'halo_radius':2},'note':'single-region candidates are not validated artwork or semantic ownership'}
