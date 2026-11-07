"""Run baseline scan on native and 2x context crops for an existing audit."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from manga_ai import engine
from manga_ai.balloon_ai import detect
p=Path(sys.argv[1]).resolve();trace=json.loads((p/'trace.json').read_text());crop=np.asarray(Image.open(p/'crop_with_context.png').convert('RGB'));cx,cy,_,_=trace['crop_experiments']['1']['transform']['crop_xyxy'];out=[]
for scale in (1,2):
 t=time.monotonic();im=crop if scale==1 else cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC);image=p/f'crop_{scale}x.png';Image.fromarray(im).save(image)
 # Independent real bubble proposal count; the scan will run detection again.
 balloons=detect(im);data=engine.analyse(image,p/f'crop_scan_{scale}x','jpn_vert',True,5,detector='ai',detail='multiscale',layout='opencv')
 regions=[]
 for r in data['regions']:
  x,y,w,h=r['box']; mask=np.asarray(Image.open(p/f'crop_scan_{scale}x'/'masks'/f"{r['id']}.png"))
  regions.append({'id':r['id'],'box_crop':r['box'],'box_page':[cx+x/scale,cy+y/scale,w/scale,h/scale],'source':r['source'],'ocr_confidence_manifest':None if r.get('ocr_status')=='unconfirmed' else r['confidence'],'ocr_status':r.get('ocr_status'),'detector':r.get('detector'),'auto_clean':r['auto_clean'],'clean_method':r.get('clean_method'),'warnings':r.get('warnings'),'final_mask_pixels_crop':int(np.count_nonzero(mask))})
 selected=[{'id':r['id'],'translation':'audit','clean':True,'force':False} for r in data['regions']]
 result=engine.render_clean(data['manifest'],selected,preview=True)
 out.append({'scale':scale,'crop_origin':[cx,cy],'balloon_proposals':len(balloons),'balloon_boxes_crop':[b['box'] for b in balloons],'text_proposals_filtered':len(trace['crop_experiments'][str(scale)]['filtered_text_proposals']),'ctd_pixels_crop':trace['crop_experiments'][str(scale)]['ctd_pixels'],'regions':regions,'clean_applied':result['applied'],'clean_skipped':result['skipped'],'clean_blocked':result['blocked'],'seconds':round(time.monotonic()-t,2),'note':'Crop scan only; no Photoshop composition. Pixel counts at different scales are not directly comparable.'})
 (p/'crop_runs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'scale':scale,'balloons':len(balloons),'regions':len(regions),'clean':result['applied'],'skipped':result['skipped']}),flush=True)
