"""Additional comic text proposals. Boxes are evidence, never erase masks."""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path
import math

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / 'models' / 'comic_text_int8.onnx'
SHA256 = 'b5022ad46416b6fe4f88b0cc082cfd2ff5b1cfc624088c2f19879485493f5913'


@lru_cache(maxsize=1)
def session():
    if not MODEL.is_file() or sha256_file(MODEL) != SHA256:
        raise RuntimeError('Thiếu hoặc sai model chữ truyện. Chạy .venv/bin/python scripts/setup_ai.py')
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    from .hardware import create_session
    return create_session(ort, MODEL, options, 'text')


def detect(rgb, threshold=.8):
    h, w = rgb.shape[:2]
    image = cv2.resize(rgb, (640, 640), interpolation=cv2.INTER_LINEAR)
    tensor = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32) / 255
    labels, boxes, scores = session().run(None, {'images': tensor, 'orig_target_sizes': np.array([[w, h]], dtype=np.int64)})
    found = []
    for kind, box, confidence in zip(labels[0], boxes[0], scores[0]):
        if int(kind) not in (1, 2) or float(confidence) < threshold or not np.isfinite(box).all():
            continue
        x1 = max(0, min(w, math.floor(float(box[0])))); y1 = max(0, min(h, math.floor(float(box[1]))))
        x2 = max(0, min(w, math.ceil(float(box[2])))); y2 = max(0, min(h, math.ceil(float(box[3]))))
        if x2-x1 < 12 or y2-y1 < 12 or (x2-x1)*(y2-y1) > w*h*.08:
            continue
        # Repeated horizontal running titles/page labels in outer margins are
        # often detected as free text. Keep vertical dialogue at page edges.
        if int(kind) == 2 and (x2-x1) > 2.5*(y2-y1) and (y2 <= h*.08 or y1 >= h*.92):
            continue
        found.append({'box': [x1, y1, x2-x1, y2-y1], 'confidence': float(confidence),
                      'kind': 'in_bubble' if int(kind) == 1 else 'free_text'})
    return found


def detect_multiscale(rgb, threshold=.8, cancel=None):
    """Keep whole-page groups; recover missed text in overlapping zoomed views.

    Crop-edge fragments and overlapping subsets cannot become extra dialogue.
    These are proposals, not permission to erase their bounding rectangles.
    """
    from .engine import check_cancel
    found = detect(rgb, threshold)
    h, w = rgb.shape[:2]
    if max(h, w) < 900:
        return found
    th, tw = round(h*.65), round(w*.65)
    extras = []
    for y in (0, h-th):
        for x in (0, w-tw):
            check_cancel(cancel)
            for proposal in detect(rgb[y:y+th, x:x+tw], max(.85, threshold)):
                px, py, pw, ph = proposal['box']
                # A group clipped at an internal tile edge is incomplete.
                if ((x > 0 and px < 6) or (y > 0 and py < 6) or
                    (x+tw < w and px+pw > tw-6) or (y+th < h and py+ph > th-6)):
                    continue
                proposal = dict(proposal, box=[x+px, y+py, pw, ph], detection_pass='zoom')
                # Apply the same running-header policy in PAGE coordinates.
                # Crop-relative margins alone let zoomed chapter headers in.
                if (proposal['kind'] == 'free_text' and pw > 2.5*ph and
                    (y+py+ph <= h*.08 or y+py >= h*.92)):
                    continue
                extras.append(proposal)
    for proposal in sorted(extras, key=lambda q: -q['confidence']):
        x, y, bw, bh = proposal['box']
        overlaps = False
        for previous in found:
            px, py, pw, ph = previous['box']
            area = max(0, min(x+bw, px+pw)-max(x, px))*max(0, min(y+bh, py+ph)-max(y, py))
            if area/max(1, min(bw*bh, pw*ph)) > .35:
                overlaps = True
                break
        if not overlaps:
            found.append(proposal)
    return found


def uncovered_regions(detections, regions):
    """Keep only text boxes not already substantially covered by a region.

    Their rectangle is a placement hint; its pixels must never be used to clean.
    """
    added = []
    for detection in detections:
        x, y, w, h = detection['box']
        def overlap(region):
            rx, ry, rw, rh = region['box']
            return max(0, min(x+w, rx+rw)-max(x, rx)) * max(0, min(y+h, ry+rh)-max(y, ry)) / (w*h)
        if any(overlap(r) >= .45 for r in regions + added):
            continue
        added.append({'box':[x,y,w,h], 'safe':[x,y,w,h],
                      'outline':[[x,y],[x+w-1,y],[x+w-1,y+h-1],[x,y+h-1]],
                      'shape':None, 'source':'[AI tìm thấy chữ — cần kiểm tra]', 'confidence':0,
                      'ocr_status':'unconfirmed', 'clean_method':'review_only', 'auto_clean':False,
                      'fill':[255,255,255], 'warnings':['AI tìm thấy chữ ngoài vùng đã nhận; cần kiểm tra và clean tay'],
                      'detector':'comic_text_ai', 'detector_confidence':detection['confidence'],
                      'text_kind':detection['kind'], '_mask':np.zeros((h,w),np.uint8)})
    return added
