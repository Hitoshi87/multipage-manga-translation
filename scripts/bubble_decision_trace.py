"""Opt-in baseline audit. No production inference or safety rules are changed.

Example: .venv/bin/python scripts/bubble_decision_trace.py --input ... --box 702 1242 156 222 --out work/audit_small_036
"""
import argparse,json,math,shutil,sys,time
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from manga_ai import engine,comic_text_ai,model_preview,head_protection
from manga_ai.coordinates import analysis_image

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--box',nargs=4,type=int,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--lang',default='jpn_vert');p.add_argument('--detail',choices=['standard','multiscale','koharu'],default='multiscale');p.add_argument('--layout',choices=['opencv','magi','koharu'],default='opencv');args=p.parse_args()
out=args.out.resolve();out.mkdir(parents=True,exist_ok=False);scan=out/'baseline_scan';rgb=engine.read_image(args.input);h,w=rgb.shape[:2];scaled=analysis_image(rgb,'ai');ah,aw=scaled.shape[:2];sx=w/aw;sy=h/ah;target=args.box;tx,ty,tw,th=target
page_id=args.input.parent.name if args.input.stem=='original' else args.input.stem

def hit(box):
 x,y,bw,bh=box;ax,ay,ar,ab=tx/sx,ty/sy,(tx+tw)/sx,(ty+th)/sy;inter=max(0,min(x+bw,ar)-max(x,ax))*max(0,min(y+bh,ab)-max(y,ay));return inter/max(1,min(bw*bh,(ar-ax)*(ab-ay)))>.3

def save(name,arr):Image.fromarray(arr).save(out/name)
def snap(v):
 if isinstance(v,np.generic):return v.item()
 if isinstance(v,(str,int,float,bool)) or v is None:return v
 if isinstance(v,(list,tuple)):return [snap(x) for x in v]
 if isinstance(v,dict):return {k:snap(x) for k,x in v.items() if k not in ('interior','_mask','shape')}
 return str(type(v))

logs=[]; stored={}; previous_ocr=engine.region_ocr;old_ctd=model_preview.ctd_mask;old_heads=head_protection.detect

def traced_ocr(image,candidate,lang,cancel=None):
 res=previous_ocr(image,candidate,lang,cancel)
 if hit(candidate['box']):logs.append({'event':'region_ocr_return','box_analysis':candidate['box'],'words':snap(res)})
 return res

def traced_ctd(image):
 result=old_ctd(image)
 if image.shape[:2]==scaled.shape[:2]:stored['ctd_analysis']=result.copy()
 return result

def traced_heads(image,*a,**kw):
 result=old_heads(image,*a,**kw)
 if image.shape[:2]==scaled.shape[:2]:logs.append({'event':'head_boxes_analysis','boxes':result})
 return result

watch={475:'candidate_enter',495:'ocr_budget_check',505:'ocr_timeout',510:'ocr_centroid_polygon_check',512:'ocr_group_check',559:'mask_before_dilation',560:'mask_after_dilation',565:'mask_after_interior_clip',585:'cjk_gate',587:'cjk_retain_unread',638:'fallback_before',639:'fallback_after',640:'fallback_accepted'}
engine_lines=Path(engine.__file__).read_text(encoding='utf8').splitlines()
for line, fragment in {585:'cjk_region_allowed',587:'retain_unread(candidate, group)',638:'supported_mask(',639:'proof is not None',640:'region.update'}.items():
 if fragment not in engine_lines[line-1]:raise RuntimeError(f'Trace line {line} changed; update the instrumentation before use')
def trace(frame,event,arg):
 name=frame.f_code.co_name;file=frame.f_code.co_filename
 if event=='call':
  if name=='analyse' and file.endswith('/manga_ai/engine.py'):return trace
  if name=='supported_mask' and file.endswith('/manga_ai/balloon_clean.py'):return trace
  return None
 if name=='analyse' and event=='line' and frame.f_lineno in watch:
  loc=frame.f_locals;cand=loc.get('candidate')
  if frame.f_lineno>=638:cand=loc.get('region')
  if isinstance(cand,dict) and 'box' in cand and hit(cand['box']):
   e={'event':watch[frame.f_lineno],'line':frame.f_lineno,'box_analysis':snap(cand['box'])}
   meaningful=('group','confidence','touches_edge','ink_ratio','variation','color','unexplained_ratio','ink_limit','reasons') if frame.f_lineno in (585,587) else (('group',) if frame.f_lineno in (510,512) else ())
   for key in meaningful:
    if key in loc:
     v=loc[key];e[key]=v.tolist() if isinstance(v,np.ndarray) else snap(v)
   if frame.f_lineno==475:
    e['candidate']=snap(cand);interior=cand.get('interior');
    if interior is not None:
     stored['target_candidate']={'box':cand['box'][:],'interior':interior.copy()}
     save('bubble_interior_analysis.png',interior)
     contours,_=cv2.findContours(interior,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
     if contours:e['polygon_analysis']=(max(contours,key=cv2.contourArea).reshape(-1,2)+np.array(cand['box'][:2])).tolist()
   if frame.f_lineno in (559,560,565) and 'glyph_mask' in loc:
    m=loc['glyph_mask'].copy();e['mask_pixels']=int(np.count_nonzero(m));save(watch[frame.f_lineno]+'.png',m)
   if frame.f_lineno==639:e['proof_returned']=loc.get('proof') is not None
   logs.append(e)
 if name=='supported_mask' and event=='return':
  loc=frame.f_locals;region=loc.get('region',{})
  if isinstance(region,dict) and hit(region.get('box',[0,0,0,0])):
   e={'event':'supported_mask_return','return_line':frame.f_lineno,'accepted':arg is not None}
   for k in ('support','target','allowed','mask','ring'):
    if k in loc and isinstance(loc[k],np.ndarray):
     e[k+'_pixels']=int(np.count_nonzero(loc[k]));save('fallback_'+k+'.png',(loc[k]>0).astype(np.uint8)*255)
   if arg is None and frame.f_lineno==40 and 'mask' in loc and 'allowed' in loc:
    e.update(rule_id='MODEL_MASK_AREA_MAX',threshold=.24,observed=float(loc['mask'].sum()/max(1,np.count_nonzero(loc['allowed']))),reason='model mask occupies too much of allowed interior')
   logs.append(e)
 return trace

with patch.object(engine,'region_ocr',side_effect=traced_ocr),patch.object(model_preview,'ctd_mask',side_effect=traced_ctd),patch.object(head_protection,'detect',side_effect=traced_heads):
 sys.settrace(trace)
 try:data=engine.analyse(args.input,scan,args.lang,True,5,detector='ai',layout=args.layout,detail=args.detail)
 finally:sys.settrace(None)
# Match the final region by overlap; IDs are assigned after sorting, not stable across rescans.
def score(r):
 x,y,bw,bh=r['box'];inter=max(0,min(x+bw,tx+tw)-max(x,tx))*max(0,min(y+bh,ty+th)-max(y,ty));return inter/max(1,min(bw*bh,tw*th))
region=max(data['regions'],key=score);assert score(region)>.3,(target,region['box']);rid=region['id'];box=region['box'];x,y,bw,bh=box
for name,arr in [('source_crop.png',rgb[y:y+bh,x:x+bw]),('target_original.png',rgb[ty:ty+th,tx:tx+tw])]:save(name,arr)
shutil.copyfile(scan/'masks'/f'{rid}.png',out/'baseline_final_mask.png')
if 'ctd_analysis' in stored:
 m=stored['ctd_analysis'];save('baseline_ctd_analysis.png',m*255);ax,ay,ar,ab=map(round,(x/sx,y/sy,(x+bw)/sx,(y+bh)/sy));save('baseline_ctd_crop_analysis.png',m[ay:ab,ax:ar]*255)
# Same saved mask and selected mapping, not a Photoshop call.
results={}
for force in (False,True):
 r=engine.render_clean(data['manifest'],[{'id':rid,'translation':'audit','clean':True,'force':force}],preview=True)
 tag='forced' if force else 'normal';results[tag]=r;shutil.copyfile(scan/'trial_clean.png',out/(tag+'_clean.png'));shutil.copyfile(scan/'trial_clean_overlay.png',out/(tag+'_overlay.png'))
# Explicit raw detector predictions before Python filtering; selected class/threshold is not applied here.
def text_preds(image):
 hh,ww=image.shape[:2];inp=np.ascontiguousarray(cv2.resize(image,(640,640)).transpose(2,0,1)[None],dtype=np.float32)/255
 labels,boxes,scores=comic_text_ai.session().run(None,{'images':inp,'orig_target_sizes':np.array([[ww,hh]],dtype=np.int64)})
 raw=[{'class_id':int(k),'box_xyxy':[float(n) for n in b],'confidence_model':float(s)} for k,b,s in zip(labels[0],boxes[0],scores[0]) if np.isfinite(b).all() and np.isfinite(s)]
 return raw,comic_text_ai.detect(image)
raw_page,filtered_page=text_preds(scaled)
comparisons={}
# Crop includes context; every mapping states origin and scale.
margin=max(30,round(max(bw,bh)*.5));left=max(0,x-margin);top=max(0,y-margin);right=min(w,x+bw+margin);bottom=min(h,y+bh+margin);crop=rgb[top:bottom,left:right];save('crop_with_context.png',crop)
for factor in (1,2):
 im=crop if factor==1 else cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
 raw,filtered=text_preds(im);cm=model_preview.ctd_mask(im);save(f'ctd_crop_{factor}x_raw.png',cm*255);save(f'ctd_crop_{factor}x_dilated_3x3.png',cv2.dilate(cm,np.ones((3,3),np.uint8))*255)
 for entry in raw:
  xx1,yy1,xx2,yy2=entry['box_xyxy'];entry['box_page_xyxy']=[left+xx1/factor,top+yy1/factor,left+xx2/factor,top+yy2/factor]
 for entry in filtered:
  xx,yy,ww,hh=entry['box'];entry['box_page_xywh']=[left+xx/factor,top+yy/factor,ww/factor,hh/factor]
 try:words=engine.ocr_words(im,args.lang,5,20);ocr={'status':'ok','words':words,'coordinates':'crop pixels, factor '+str(factor)}
 except Exception as e:ocr={'status':'error','error':str(e)}
 comparisons[str(factor)]={'transform':{'crop_xyxy':[left,top,right,bottom],'scale':factor,'page_from_crop':'(x/scale + left, y/scale + top)'},'raw_text_proposals':raw,'filtered_text_proposals':filtered,'ocr_tesseract':ocr,'ctd_pixels':int(cm.sum()),'auto_clean':'not run for crop-only diagnostic; proposals are not full regions'}
try:
 from ultralytics import YOLO
 net=YOLO('models/shadowb_yolo26s.pt');pred=net.predict(crop[:,:,::-1],imgsz=1280,conf=.25,device='mps',verbose=False)[0]
 comparisons['fallback_yolo26']={'status':'ok','proposals':[{'class':net.names[int(z.cls.item())],'confidence_model':float(z.conf.item()),'box_crop_xyxy':z.xyxy[0].tolist()} for z in pred.boxes]}
except Exception as e:comparisons['fallback_yolo26']={'status':'error','error':repr(e)}
ocr_transform=None
if 'target_candidate' in stored:
 cand=stored['target_candidate']; bx,by,bw,bh=cand['box'];base_scale=min(2.,1600/max(bw,bh));inter=cv2.erode(cand['interior'],np.ones((3,3),np.uint8));small=scaled[by:by+bh,bx:bx+bw].copy();small[inter==0]=255;gg=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY);yy,xx=np.nonzero((gg<190)&(inter>0));tight=None
 if len(xx):
  lx=max(0,int(xx.min())-5);ly=max(0,int(yy.min())-5);rx=min(bw,int(xx.max())+6);ry=min(bh,int(yy.max())+6);tight={'box_within_candidate':[lx,ly,rx-lx,ry-ly],'scale':min(3.,1600/max(rx-lx,ry-ly)),'border':15,'note':'Reconstructed from the same source pixels and rule used by recover_words; selection of OCR pass is recorded in events.'}
 ocr_transform={'candidate_box_analysis':cand['box'],'base_scale':base_scale,'base_border':12,'tight_retry':tight,'analysis_to_original_scale':[sx,sy]}
report={'page_id':page_id,'target_box_original':target,'analysis_size':[aw,ah],'original_size':[w,h],'analysis_to_original_scale':[sx,sy],'bubble_id':'target matched geometrically, no stable baseline bubble id','region_id':rid,'region_match_overlap':score(region),'final_region':snap(region),'ocr_transforms':ocr_transform,'events':logs,'raw_text_predictions_analysis':raw_page,'filtered_text_predictions_analysis':filtered_page,'crop_experiments':comparisons,'render_clean_preview':results,'inpainting':{'called':False,'reason':'baseline render_clean uses masked flat-color RGBA overlay, not LaMa'},'photoshop_composited':'not observed; backend preview only','note':'Raw text predictions are ONNX outputs before application-side filters; internal model postprocessing is unknown. confidence=0 in unread manifest is a placeholder, not OCR confidence. Raw/dilated glyph mask previews exist only if that baseline branch executed.'}
(out/'trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'region_id':rid,'box':box,'source':region.get('source'),'auto_clean':region['auto_clean'],'events':logs,'clean':results},ensure_ascii=False),flush=True)
region_dir=out/'regions';region_dir.mkdir(exist_ok=True)
all_regions=[]
for item in data['regions']:
 ident=item['id'];xx,yy,ww,hh=item['box']; mask=np.asarray(Image.open(scan/'masks'/f'{ident}.png').convert('L'))
 crop=Image.fromarray(rgb[yy:yy+hh,xx:xx+ww]);crop.thumbnail((600,600));crop.save(region_dir/f'{ident}_crop.png')
 entry={'page_id':page_id,'bubble_id':None,'bubble_id_note':'Baseline has no separate persistent bubble ID', 'region_id':ident,'box_original':item['box'],'box_analysis':item.get('analysis_box'),'polygon_original':item.get('outline'), 'model_source':item.get('detector'), 'bubble_confidence_model':item.get('detector_confidence'), 'ocr_text':item.get('source'),'ocr_confidence':None if item.get('ocr_status') in ('unconfirmed','punctuation_geometry') else item.get('confidence'), 'ocr_status':item.get('ocr_status','not_recorded_by_baseline'),'mask_pixels_final':int(np.count_nonzero(mask)),'raw_and_dilated_mask':'captured for target only; baseline does not persist these stages','auto_clean_eligible':item.get('auto_clean'),'decision_for_this_run':('target_rendered' if ident==rid else 'not_selected_for_render'),'block_reason':engine.clean_block_reason(data,item),'warnings':item.get('warnings',[]),'mask_file':f'../baseline_scan/masks/{ident}.png','crop_file':f'{ident}_crop.png','inpainting_called':False,'photoshop_composited':'not observed'}
 all_regions.append(entry)
(out/'regions_trace.json').write_text(json.dumps(all_regions,ensure_ascii=False,indent=2),encoding='utf8')
