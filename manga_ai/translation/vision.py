"""Bounded, provenance-checked visual context for one translation group."""
import base64
import io
from pathlib import Path
from ..runtime.resources import sha256_file

MAX_PAGES = 4
MAX_DIMENSION = 1800
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def image_plan(state, group, mode):
    if mode == 'off':return []
    if mode not in ('target_crop','page'):raise ValueError('Chế độ ảnh không hợp lệ')
    pages={p['page_id']:p for p in state['pages']}
    segments={s['id']:s for p in state['pages'] for s in p['segments']}
    per_page={}
    for target in group['targets']:
        s=segments.get(target['id'])
        if not s:raise ValueError('Không tìm thấy segment ảnh')
        per_page.setdefault(s['page_id'],[]).append(s)
    if len(per_page)>MAX_PAGES:raise ValueError('Một nhóm vision tối đa bốn trang; giảm kích thước nhóm')
    plan=[]
    for page_id,items in per_page.items():
        page=pages[page_id];image=Path(page['manifest']).parent/'original.png'
        if not image.is_file() or not page.get('image_digest') or sha256_file(image)!=page['image_digest']:
            raise ValueError('Ảnh nguồn đã thay đổi; cần index lại')
        from PIL import Image
        with Image.open(image) as im:width,height=im.size
        if mode=='page':box=[0,0,width,height]
        else:
            x1=min(s['box'][0] for s in items);y1=min(s['box'][1] for s in items)
            x2=max(s['box'][0]+s['box'][2] for s in items);y2=max(s['box'][1]+s['box'][3] for s in items)
            pad=max(24,round(max(x2-x1,y2-y1)*.10))
            box=[max(0,x1-pad),max(0,y1-pad),min(width,x2+pad),min(height,y2+pad)]
        plan.append({'page_id':page_id,'target_ids':[s['id'] for s in items],'crop_xyxy':box,
                     'image_sha256':page['image_digest'],'image_path':str(image),'mode':mode})
    return plan


def public_plan(plan):
    return [{k:v for k,v in item.items() if k != 'image_path'} for item in plan]


def image_parts(plan):
    from PIL import Image
    parts=[]
    for item in plan:
        if sha256_file(item['image_path'])!=item['image_sha256']:raise ValueError('Ảnh nguồn đã thay đổi')
        with Image.open(item['image_path']) as image:
            crop=image.convert('RGB').crop(tuple(item['crop_xyxy']))
            crop.thumbnail((MAX_DIMENSION,MAX_DIMENSION),Image.Resampling.LANCZOS)
            stream=io.BytesIO();crop.save(stream,format='PNG',optimize=True)
        data=stream.getvalue()
        if len(data)>MAX_IMAGE_BYTES:raise ValueError('Ảnh crop quá lớn cho request')
        parts.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(data).decode('ascii')}})
    return parts
