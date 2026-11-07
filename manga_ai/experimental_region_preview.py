"""Manual-only region preview. Uses full-page model inputs and writes unique artifacts."""
import json,tempfile,time
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from .experimental_region_guard import guard_mask
from .shadow_color_audit import audit_fill,ColorAuditConfig
from .io import read_json,validate_manifest
from .coordinates import analysis_image

def evaluate(crop,base,ctd,text_boxes,ocr,fill):
 mask,trace=guard_mask(crop,base,ctd,text_boxes,ocr);tmp=crop.copy();tmp[mask]=fill
 cleaned,heat,color=audit_fill(crop,tmp,mask,ColorAuditConfig(bright_floor=245))
 # Never silently replace pixels without local color evidence.
 if color['unsupported_pixels']:
  trace['rule_ids'].append('COLOR_ESTIMATE_INSUFFICIENT');trace['preview_applicable']=False
 else:trace['preview_applicable']=bool(mask.any())
 trace.update({'color':color,'user_review_required':True,'production_auto_authorized':False})
 assert not np.any(np.any(cleaned!=crop,axis=2)&~mask)
 return cleaned,mask,trace

def preview_region(manifest_path,region_id):
 from .model_preview import ctd_mask
 from .comic_text_ai import detect
 mp=Path(manifest_path).resolve();manifest=validate_manifest(read_json(mp));region=next((r for r in manifest['regions'] if r['id']==region_id),None)
 if region is None:raise ValueError('Không tìm thấy ID vùng')
 source=np.asarray(Image.open(mp.parent/'original.png').convert('RGB'));H,W=source.shape[:2]
 if (W,H)!=(manifest['width'],manifest['height']):raise ValueError('Nguồn và manifest không khớp')
 small=analysis_image(source,'ai');ah,aw=small.shape[:2];ctd=ctd_mask(small);det=detect(small);full=cv2.resize(ctd,(W,H),interpolation=cv2.INTER_NEAREST)
 x,y,w,h=region['box'];crop=source[y:y+h,x:x+w];maskfile=mp.parent/'masks'/(region_id+'.png')
 if not maskfile.is_file():raise ValueError('Không có mask vùng')
 base=np.asarray(Image.open(maskfile).convert('L'))>0;boxes=[]
 for item in det:
  if item['kind']!='in_bubble':continue
  a,b,c,d=item['box'];a=round(a*W/aw);b=round(b*H/ah);c=round(c*W/aw);d=round(d*H/ah)
  overlap=max(0,min(x+w,a+c)-max(x,a))*max(0,min(y+h,b+d)-max(y,b))
  if overlap/max(1,c*d)>=.7:boxes.append([a-x,b-y,c,d])
 clean,mask,trace=evaluate(crop,base,full[y:y+h,x:x+w],boxes,region.get('source',''),region.get('fill',[255,255,255]))
 folder=Path(tempfile.mkdtemp(prefix='region_shadow_',dir=mp.parent));overlay=np.zeros((H,W,4),np.uint8);patch=overlay[y:y+h,x:x+w];patch[mask,:3]=clean[mask];patch[mask,3]=255;Image.fromarray(overlay).save(folder/'overlay.png')
 Image.fromarray(mask.astype('uint8')*255).save(folder/'mask_crop.png');Image.fromarray(clean).save(folder/'clean_crop.png');visual=crop.copy();visual[mask]=np.clip(visual[mask]*.35+np.array([255,0,0])*.65,0,255).astype('uint8');Image.fromarray(visual).save(folder/'mask_overlay_crop.png')
 sheet=Image.new('RGB',(1200,450),'white');draw=ImageDraw.Draw(sheet)
 for i,(img,label) in enumerate([(crop,'Goc'),(visual,'Mask de xuat'),(clean,'Clean thu — can duyet')]):
  v=Image.fromarray(img);v.thumbnail((390,420));sheet.paste(v,(400*i,25));draw.text((400*i+4,4),label,fill='black')
 sheet.save(folder/'comparison.png');trace.update({'region_id':region_id,'source_box':region['box'],'detection_boxes':boxes,'source_detection':'full_page_comic_text_detector','ctd_source':'full_page_analysis','output_folder':str(folder),'mask_overlay':str(folder/'mask_overlay_crop.png'),'comparison':str(folder/'comparison.png'),'overlay':str(folder/'overlay.png'),'mask_crop':str(folder/'mask_crop.png'),'output_crop':str(folder/'clean_crop.png')});(folder/'trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2));return trace
