"""Local YOLO11n balloon masks. No network access during inference.

Weights: huyvux3005/manga109-segmentation-bubble (Apache-2.0).
Fixed-shape ONNX export: igun997/manga-translator; see models/NOTICE.md.
"""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / 'models' / 'balloon.onnx'
SHA256 = '88b84105ad2faec516fd164a2783fa6b6007dfd6ab07aa90e92b0241e51ea4cf'
SIZE = 1600


@lru_cache(maxsize=1)
def session():
    if not MODEL.is_file():
        raise RuntimeError('Thiếu model AI. Chạy .venv/bin/python scripts/setup_ai.py')
    if sha256_file(MODEL) != SHA256:
        raise RuntimeError('Model AI sai checksum; tải lại qua scripts/setup_ai.py')
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError('Thiếu ONNX Runtime trong .venv; chạy scripts/setup_ai.py') from exc
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    # Avoid retaining ORT's large 1600px activation arena between pages.
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    from .hardware import create_session
    return create_session(ort, MODEL, options, 'balloon')


def detect(rgb, threshold=.65):
    """Return crop-local masks and page coordinates, never a rectangle-only mask."""
    height, width = rgb.shape[:2]
    scale = min(SIZE / width, SIZE / height)
    nw, nh = round(width*scale), round(height*scale)
    left, top = (SIZE-nw)//2, (SIZE-nh)//2
    canvas = np.full((SIZE, SIZE, 3), 114, np.uint8)
    canvas[top:top+nh, left:left+nw] = cv2.resize(rgb, (nw, nh))
    tensor = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32)/255
    runner = session()
    raw, proto = runner.run(None, {runner.get_inputs()[0].name: tensor})
    detections = raw[0].T
    detections = detections[detections[:, 4] >= threshold]
    if not len(detections):
        return []
    boxes = detections[:, :4].copy()
    boxes[:, :2] -= boxes[:, 2:]/2
    ids = np.asarray(cv2.dnn.NMSBoxes(boxes.tolist(), detections[:, 4].tolist(), threshold, .5)).reshape(-1)
    basis = proto[0].reshape(proto.shape[1], -1)
    found = []
    for idx in ids:
        xx, yy, ww, hh = boxes[idx]
        x = max(0, round((xx-left)/scale)); y = max(0, round((yy-top)/scale))
        right = min(width, round((xx+ww-left)/scale)); bottom = min(height, round((yy+hh-top)/scale))
        if right-x < 20 or bottom-y < 20:
            continue
        logits = (detections[idx, 5:] @ basis).reshape(proto.shape[2:])
        # Interpolate logits (threshold zero == probability .5), then unletterbox.
        logits = cv2.resize(logits, (SIZE, SIZE))
        logits = cv2.resize(logits[top:top+nh, left:left+nw], (width, height))
        mask = (logits[y:bottom, x:right] > 0).astype(np.uint8)*255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        filled = np.zeros_like(mask)
        cv2.drawContours(filled, [max(contours, key=cv2.contourArea)], -1, 255, -1)
        # Coarse AI boundaries must not supply pixels right on a bubble outline.
        inset = cv2.erode(filled, np.ones((7, 7), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        if cv2.countNonZero(inset) < 500:
            continue
        found.append({'box': [x,y,right-x,bottom-y], 'interior': inset,
                      'detector': 'ai_balloon', 'detector_confidence': float(detections[idx,4])})
    return found


def recover_missed(rgb, proposals, text_detections, cancel=None):
    """Zoom around uncovered text; never replace existing balloon geometry.

    Require independent text agreement and reject silhouettes clipped at a crop
    boundary. Recovered geometry remains subject to normal clean verification.
    """
    from .engine import check_cancel
    height, width = rgb.shape[:2]
    result = list(proposals)
    attempts = 0
    def overlap(a, b):
        x,y,w,h=a; xx,yy,ww,hh=b
        return max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    for text in sorted(text_detections, key=lambda d: -d['confidence']):
        if text['kind'] != 'in_bubble' or text['confidence'] < .9:
            continue
        x,y,w,h=text['box']
        if any(overlap(text['box'],p['box'])/(w*h) >= .45 for p in result):
            continue
        if attempts >= 6:
            break
        check_cancel(cancel)
        margin=max(80,w,h)
        left,top=max(0,x-margin),max(0,y-margin)
        right,bottom=min(width,x+w+margin),min(height,y+h+margin)
        attempts += 1
        for candidate in detect(rgb[top:bottom,left:right],threshold=.9):
            cx,cy,cw,ch=candidate['box']
            if ((left>0 and cx<8) or (top>0 and cy<8) or
                (right<width and cx+cw>right-left-8) or
                (bottom<height and cy+ch>bottom-top-8)):
                continue
            box=[left+cx,top+cy,cw,ch]
            if overlap(text['box'],box)/(w*h) < .85:
                continue
            if any(overlap(box,p['box'])/max(1,min(cw*ch,p['box'][2]*p['box'][3])) > .35 for p in result):
                continue
            candidate=dict(candidate,box=box,detection_pass='text_guided_zoom')
            result.append(candidate)
    return result
