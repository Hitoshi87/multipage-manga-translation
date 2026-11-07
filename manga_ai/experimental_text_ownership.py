"""Page-level, opt-in ownership graph. Outputs evidence, never a clean decision."""
from dataclasses import dataclass,asdict
import cv2,numpy as np
@dataclass(frozen=True)
class OwnershipConfig:
 dark_threshold:int=180
 min_component_area:int=2
 max_component_area:int=800
 min_ctd_fraction:float=.05
 min_text_box_fraction:float=.1
 min_score:float=.45
 min_margin:float=.15
 group_x_distance_px:int=12
 group_y_gap_px:int=18

def ownership_graph(rgb,ctd,bubbles,text_boxes,config=OwnershipConfig()):
 rgb=np.asarray(rgb,dtype=np.uint8);ctd=np.asarray(ctd)>0;h,w=ctd.shape
 if rgb.shape!=(h,w,3):raise ValueError('incompatible page geometry')
 text_support=np.zeros((h,w),np.uint8)
 for x,y,bw,bh in text_boxes:
  if bw>0 and bh>0:text_support[max(0,y):min(h,y+bh),max(0,x):min(w,x+bw)]=1
 gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);n,labels,stats,centroids=cv2.connectedComponentsWithStats((gray<config.dark_threshold).astype('uint8'),8)
 comps=[]
 for i in range(1,n):
  x,y,bw,bh,area=map(int,stats[i]);
  if area<config.min_component_area or area>config.max_component_area or x==0 or y==0 or x+bw>=w or y+bh>=h:continue
  local=labels[y:y+bh,x:x+bw]==i;cf=float((local&ctd[y:y+bh,x:x+bw]).sum()/area);tf=float((local&(text_support[y:y+bh,x:x+bw]>0)).sum()/area)
  if cf<config.min_ctd_fraction or tf<config.min_text_box_fraction:continue
  comps.append({'component_id':int(i),'box':[x,y,bw,bh],'area':area,'ctd_fraction':round(cf,4),'text_box_fraction':round(tf,4)})
 # Conservative vertical grouping for reading context only; ownership stays per component.
 parent=list(range(len(comps)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):
  a,b=find(a),find(b)
  if a!=b:parent[b]=a
 for i,a in enumerate(comps):
  ax,ay,aw,ah=a['box']
  for j in range(i):
   bx,by,bw,bh=comps[j]['box'];dx=abs((ax+aw/2)-(bx+bw/2));dy=max(0,max(ay,by)-min(ay+ah,by+bh))
   if dx<=config.group_x_distance_px and dy<=config.group_y_gap_px:union(i,j)
 groups={}
 for i,c in enumerate(comps):groups.setdefault(find(i),[]).append(c['component_id'])
 group_id={cid:'G%04d'%k for k,ids in enumerate(groups.values(),1) for cid in ids}
 masks=[]
 for b in bubbles:
  mask=np.zeros((h,w),np.uint8);pts=np.asarray(b.get('polygon',[]),np.int32)
  if len(pts)>=3:cv2.fillPoly(mask,[pts],1)
  masks.append(mask>0)
 for c in comps:
  x,y,bw,bh=c['box'];sel=labels[y:y+bh,x:x+bw]==c['component_id'];cx=x+bw/2;cy=y+bh/2;links=[]
  for b,poly in zip(bubbles,masks):
   bx,by,bww,bhh=b['box'];in_box=bx<=cx<bx+bww and by<=cy<by+bhh
   inside=float((sel&poly[y:y+bh,x:x+bw]).sum()/c['area'])
   if not in_box and inside==0:continue
   # Exploratory evidence scoring, not calibrated probability or safety proof.
   score=.6*inside+.4*float(in_box);links.append({'bubble_id':b['id'],'polygon_overlap':round(inside,4),'center_in_box':in_box,'heuristic_score':round(score,4),'ocr_text_available':bool(b.get('ocr_text')),'polygon_model':b.get('detector')})
  links.sort(key=lambda z:(-z['heuristic_score'],z['bubble_id']));c['candidate_bubbles']=links;c['group_id']=group_id[c['component_id']];c['owner']=None
  if not links or links[0]['heuristic_score']<config.min_score:c['ownership_status']='unassigned';c['reason']='NO_STRONG_LINK'
  elif len(links)>1 and links[0]['heuristic_score']-links[1]['heuristic_score']<config.min_margin:c['ownership_status']='ambiguous';c['reason']='MULTIPLE_COMPETING_LINKS'
  else:c['owner']=links[0]['bubble_id'];c['ownership_status']='candidate_owner';c['reason']='HEURISTIC_ONLY_REQUIRES_REVIEW'
 return {'components':comps,'groups':[{'group_id':'G%04d'%i,'component_ids':ids} for i,ids in enumerate(groups.values(),1)],'thresholds':asdict(config),'threshold_status':'uncalibrated_not_model_confidence','authorized_to_clean':False,'labels':'no independent ownership or artwork labels'},labels
