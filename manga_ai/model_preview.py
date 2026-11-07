"""Experimental, non-destructive comparison of text masks and LaMa inpainting."""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path
import hashlib
import zipfile

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    'ctd': ('comic_ctd.onnx', 'eea9f9ccad2364fcb15bdfeca25268be273fea80b111ba6a6f4c03f556c24c26'),
    'mask': ('comic_text_mask.pt', 'c1de7cd35c5cce1c5eca4e03696129dc9649db6ebe7d03fe1b995d7aca73e605'),
    'lama': ('lama_manga.onnx', 'de31ffa5ba26916b8ea35319f6c12151ff9654d4261bccf0583a69bb095315f9'),
    'koharu': ('koharu_layout.onnx', '7cc10d4316371946b8441da3512261a8e148b129abcdb0ea6235ed1d1d06d351'),
}


def model_path(name):
    filename, checksum = MODELS[name]
    path = ROOT / 'models' / filename
    if not path.is_file() or sha256_file(path) != checksum:
        raise RuntimeError('Thiếu hoặc sai model ' + name + '. Chạy .venv/bin/python scripts/setup_preview_models.py')
    return path


@lru_cache(maxsize=2)
def ort_session(name):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    # LaMa has larger convolutions; four CPU threads benchmark faster on M4.
    opts.intra_op_num_threads = 4 if name == 'lama' else 2
    opts.inter_op_num_threads = 1
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False
    from .hardware import create_session
    return create_session(ort, model_path(name), opts, name)


def ctd_mask(rgb):
    h, w = rgb.shape[:2]
    scale = min(1024 / w, 1024 / h)
    nw, nh = max(1, round(w*scale)), max(1, round(h*scale))
    padded = np.zeros((1024,1024,3), np.uint8)
    # The upstream CTD preprocessing uses BGR channel order and bottom/right padding.
    padded[:nh,:nw] = cv2.resize(rgb, (nw,nh))[:,:,::-1]
    tensor = np.ascontiguousarray(padded.transpose(2,0,1)[None], dtype=np.float32) / 255
    _, mask = ort_session('ctd').run(None, {'image':tensor})
    return (cv2.resize(mask[0,0,:nh,:nw], (w,h), interpolation=cv2.INTER_LINEAR) > .3).astype(np.uint8)


def detailed_mask(rgb, method, cancel=None, cached_koharu_mask=None):
    from .engine import check_cancel
    from .comic_text_ai import detect_multiscale
    from .clean_refinement import complete_glyphs, text_window
    h, w = rgb.shape[:2]
    detections = detect_multiscale(rgb, cancel=cancel)
    base = (ctd_mask(rgb) if method in ('ctd', 'hybrid') else
            crop_mask(rgb) if method == 'mask' else
            cached_koharu_mask.copy() if cached_koharu_mask is not None else koharu_mask(rgb))
    if method == 'hybrid':
        base |= koharu_mask(rgb)
    # Local CTD retains fine glyphs lost when a 4320px page becomes 1024px.
    # Restrict extra evidence to independently detected text, not the whole crop.
    for d in detections:
        check_cancel(cancel)
        if d['confidence'] < .85:
            continue
        x0, y0, x1, y1 = text_window(d['box'], w, h)
        bw, bh = x1-x0, y1-y0
        context = max(20, round(max(bw, bh)*.18))
        left, top, right, bottom = max(0, x0-context), max(0, y0-context), min(w, x1+context), min(h, y1+context)
        local = ctd_mask(rgb[top:bottom, left:right])
        base[y0:y1, x0:x1] |= local[y0-top:y1-top, x0-left:x1-left]
    return complete_glyphs(rgb, base, detections), detections


@lru_cache(maxsize=2)
def _mask_model(device):
    import torch
    return torch.jit.load(str(model_path('mask')), map_location=device).eval()


def crop_mask(rgb):
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError('Thiếu PyTorch cho Comic Text Mask. Chạy .venv/bin/python scripts/setup_preview_models.py') from exc
    from .comic_text_ai import detect
    from .hardware import get_torch_device
    device = get_torch_device()
    if device == 'cpu':
        torch.set_num_threads(2)
    model = _mask_model(device)
    h, w = rgb.shape[:2]
    result = np.zeros((h,w), np.uint8)
    # Text proposals are required by this crop model, and can still miss text.
    for detection in detect(rgb, threshold=.55)[:100]:
        x,y,bw,bh = detection['box']
        margin = max(4, round(max(bw,bh)*.05))
        x0,y0=max(0,x-margin),max(0,y-margin)
        x1,y1=min(w,x+bw+margin),min(h,y+bh+margin)
        crop=rgb[y0:y1,x0:x1]; ch,cw=crop.shape[:2]
        scale=min(384/cw,384/ch); nw=max(1,round(cw*scale)); nh=max(1,round(ch*scale))
        left=(384-nw)//2; top=(384-nh)//2
        canvas=np.zeros((384,384,3),np.uint8)
        canvas[top:top+nh,left:left+nw]=cv2.resize(crop,(nw,nh))
        tensor = torch.from_numpy(np.ascontiguousarray(canvas.transpose(2,0,1)[None]))
        if device != 'cpu':
            tensor = tensor.to(device)
        with torch.inference_mode():
            probability=model(tensor)[0,0].cpu().numpy()
        local=cv2.resize(probability[top:top+nh,left:left+nw],(cw,ch))>.5
        result[y0:y1,x0:x1] |= local.astype(np.uint8)
    return result


def koharu_outputs(rgb):
    h,w=rgb.shape[:2]
    image=cv2.resize(rgb,(1152,1152),interpolation=cv2.INTER_LINEAR).astype(np.float32)/255
    image=(image-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    output=ort_session('koharu').run(None,{'input':np.ascontiguousarray(image.transpose(2,0,1)[None])})
    names=[v.name for v in ort_session('koharu').get_outputs()]
    return dict(zip(names,output))


def koharu_panels(rgb, tensors=None):
    h,w=rgb.shape[:2];tensors=koharu_outputs(rgb) if tensors is None else tensors;logits=tensors['labels'][0,:,:4]
    classes=logits.argmax(axis=1);chosen=np.flatnonzero((classes==3)&(logits[:,3]>=0))
    boxes=[];scores=[]
    for i in chosen:
        cx,cy,bw,bh=tensors['dets'][0,i];x1=max(0,round((cx-bw/2)*w));y1=max(0,round((cy-bh/2)*h))
        x2=min(w,round((cx+bw/2)*w));y2=min(h,round((cy+bh/2)*h))
        if x2>x1 and y2>y1:boxes.append([x1,y1,x2-x1,y2-y1]);scores.append(float(1/(1+np.exp(-logits[i,3]))))
    if not boxes:return []
    keep=np.asarray(cv2.dnn.NMSBoxes(boxes,scores,.5,.7)).reshape(-1)
    return [boxes[i] for i in keep]


def koharu_text(rgb, tensors=None):
    """Text boxes for placement/review, never rectangular erase masks."""
    h, w = rgb.shape[:2]
    tensors = koharu_outputs(rgb) if tensors is None else tensors
    logits = tensors['labels'][0, :, :4]
    selected = np.flatnonzero((logits.argmax(axis=1) == 0) & (logits[:, 0] >= 0))
    boxes, scores = [], []
    for i in selected:
        cx, cy, bw, bh = tensors['dets'][0, i]
        x, y = max(0, int((cx-bw/2)*w)), max(0, int((cy-bh/2)*h))
        right, bottom = min(w, int(np.ceil((cx+bw/2)*w))), min(h, int(np.ceil((cy+bh/2)*h)))
        if min(right-x, bottom-y) < 10 or (right-x)*(bottom-y) > w*h*.2:
            continue
        boxes.append([x, y, right-x, bottom-y])
        scores.append(float(1/(1+np.exp(-logits[i, 0]))))
    if not boxes:
        return []
    keep = np.asarray(cv2.dnn.NMSBoxes(boxes, scores, .5, .5)).reshape(-1)
    return [{'box': boxes[i], 'confidence': scores[i], 'kind': 'free_text', 'detection_pass': 'koharu'} for i in keep]


def koharu_mask(rgb, tensors=None):
    h,w=rgb.shape[:2];tensors=koharu_outputs(rgb) if tensors is None else tensors;logits=tensors['labels'][0,:,:4]
    classes=logits.argmax(axis=1)
    # sigmoid(logit) >= .25 without overflowing for very negative logits.
    chosen=np.flatnonzero((classes==0) & (logits[:,0]>=-1.0986123))
    mask=np.zeros((h,w),np.uint8)
    for index in chosen:
        mask |= (cv2.resize(tensors['masks'][0,index],(w,h),interpolation=cv2.INTER_LINEAR)>0).astype(np.uint8)
    return mask


def lama_infer(rgb, mask):
    image = np.ascontiguousarray(rgb.transpose(2,0,1)[None], dtype=np.float32)/255
    tensor_mask = np.ascontiguousarray(mask[None,None], dtype=np.float32)
    output = ort_session('lama').run(None, {'image':image, 'mask':tensor_mask})[0][0].transpose(1,2,0)
    return np.clip(output*255, 0, 255).astype(np.uint8)


def lama_clean(rgb, mask, cancel=None):
    from .clean_refinement import local_inpaint
    return local_inpaint(rgb, mask, lama_infer, cancel)


def create_clean(rgb, method, use_lama=False, cancel=None, protect_faces=False, cached_koharu_mask=None,
                 inpaint=None, diagnostics=None):
    from .engine import check_cancel
    from .clean_refinement import flat_backgrounds, local_inpaint, coverage_report, enclosed_text_support
    if method not in ('ctd', 'mask', 'koharu', 'hybrid'):
        raise ValueError('Model xem thử không hợp lệ')
    backend = inpaint or ('lama' if use_lama else 'white')
    if backend not in ('lama', 'aot', 'white'):
        raise ValueError('Bộ phục hồi nền không hợp lệ')
    check_cancel(cancel)
    mask, detections = detailed_mask(rgb, method, cancel, cached_koharu_mask)
    check_cancel(cancel)
    blocked_pixels = 0
    if protect_faces:
        from .head_protection import detect, protect
        previous = int(mask.sum())
        protected = protect(mask, detect(rgb))
        exception = enclosed_text_support(rgb, detections)
        mask = np.maximum(protected, mask*exception)
        blocked_pixels = previous-int(mask.sum())
    result, flat_mask = flat_backgrounds(rgb, mask, detections)
    remaining = mask*(1-flat_mask)
    if np.any(remaining):
        if backend == 'lama':
            reconstructed = lama_clean(result, remaining, cancel)
        elif backend == 'aot':
            from .aot_inpaint import infer
            reconstructed = local_inpaint(result, remaining, infer, cancel)
        else:
            reconstructed = np.full_like(rgb, 255)
        result[remaining > 0] = reconstructed[remaining > 0]
    if diagnostics is not None:
        diagnostics.update(coverage_report(rgb, result, mask, detections))
        diagnostics.update(inpaint=backend, protected_pixels=blocked_pixels,
                           flat_pixels=int(flat_mask.sum()), reconstructed_pixels=int(remaining.sum()),
                           text_proposals=len(detections))
    check_cancel(cancel)
    return result, mask


def preview(input_path, out, method, use_lama=False, cancel=None, protect_faces=False, inpaint=None):
    from .engine import read_image, save_image
    if method not in ('ctd','mask','koharu','hybrid'):
        raise ValueError('Model xem thử không hợp lệ')
    rgb=read_image(input_path); h,w=rgb.shape[:2]
    quality={}
    result,mask=create_clean(rgb,method,use_lama,cancel,protect_faces,inpaint=inpaint,diagnostics=quality)
    marked=rgb.copy(); marked[mask>0]=(marked[mask>0]*.35+np.array([255,0,0])*.65).astype(np.uint8)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    paths={}
    for name,image in [('original',rgb),('mask',marked),('clean',result)]:
        save_image(out/(name+'.png'),image)
        thumb=Image.fromarray(image);thumb.thumbnail((540,600));thumb.save(out/(name+'_small.png'))
        paths[name]=str((out/(name+'_small.png')).resolve())
    return {'images':paths,'mask_pixels':int(mask.sum()),'method':method,'lama':bool(use_lama),'width':w,'height':h,'quality':quality,'inpaint':quality['inpaint']}


def batch_clean(manifest_path, mapping, method, use_lama=False, cancel=None, protect_faces=False, inpaint=None):
    """Render the same full-page experiment as a separate transparent overlay.

    Text masks are unverified: never present the mapped regions as safely cleaned.
    """
    from .engine import check_cancel, read_image, save_image
    from .io import checked_mapping, read_json, validate_manifest
    manifest_path=Path(manifest_path).resolve()
    data=validate_manifest(read_json(manifest_path))
    selected=checked_mapping(data,mapping)
    rgb=read_image(manifest_path.parent/'original.png')
    if rgb.shape[:2] != (data['height'],data['width']):
        raise ValueError('Ảnh gốc không khớp kích thước manifest')
    cached=None
    cache_path=manifest_path.parent/'koharu_mask_cache.npz'
    if method=='koharu' and cache_path.is_file():
        model_path('koharu')  # Preserve the normal model-integrity check.
        try:
            with np.load(cache_path, allow_pickle=False) as cache:
                mask=cache['mask']; image_digest=str(cache['image_digest'].item()); model_digest=str(cache['model_digest'].item()); mask_digest=str(cache['mask_digest'].item())
                if (mask.shape==rgb.shape[:2] and mask.dtype==np.uint8 and
                    image_digest==hashlib.sha256(rgb.tobytes()).hexdigest() and
                    model_digest==MODELS['koharu'][1] and mask_digest==hashlib.sha256(mask.tobytes()).hexdigest() and
                    np.all(mask<=1)):
                    cached=mask.copy()
        except (OSError,ValueError,KeyError,EOFError,zipfile.BadZipFile):
            pass
    quality={}
    result,mask=create_clean(rgb,method,use_lama,cancel,protect_faces,cached,inpaint,quality)
    from .io import write_json
    write_json(manifest_path.parent/'experimental_clean_quality.json',quality)
    check_cancel(cancel)
    overlay=np.zeros((*rgb.shape[:2],4),np.uint8)
    overlay[:,:,:3]=result
    overlay[:,:,3]=mask*255
    path=manifest_path.parent/'experimental_clean_overlay.png'
    save_image(path,overlay)
    skipped=[item['id'] for item in selected if item['clean'] and item['translation'].strip()]
    return {'overlay':str(path),'applied':[],'skipped':skipped,'blocked':{},
            'full_page':True,'experimental':True,'method':method,'lama':bool(use_lama),
            'mask_pixels':int(mask.sum()),'protect_faces':bool(protect_faces),'quality':quality,'inpaint':quality['inpaint']}
