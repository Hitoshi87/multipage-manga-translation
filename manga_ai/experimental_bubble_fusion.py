"""Experimental polygon proposal fusion; it never creates an erase mask."""
import cv2
import numpy as np


def polygon_iou(first, second):
    a = np.asarray(first, dtype=np.float64).reshape(-1, 2)
    b = np.asarray(second, dtype=np.float64).reshape(-1, 2)
    if len(a) < 3 or len(b) < 3 or not np.isfinite(a).all() or not np.isfinite(b).all():
        return 0.0
    left = np.floor(np.minimum(a.min(0), b.min(0))).astype(int)
    right = np.ceil(np.maximum(a.max(0), b.max(0))).astype(int)
    width, height = (right-left+1).tolist()
    if width <= 0 or height <= 0 or width*height > 30_000_000:
        return 0.0
    first_mask = np.zeros((height, width), np.uint8)
    second_mask = np.zeros_like(first_mask)
    cv2.fillPoly(first_mask, [np.rint(a-left).astype(np.int32)], 1)
    cv2.fillPoly(second_mask, [np.rint(b-left).astype(np.int32)], 1)
    union = np.count_nonzero(first_mask | second_mask)
    return float(np.count_nonzero(first_mask & second_mask)/union) if union else 0.0


def fuse_for_review(proposals, text_boxes, iou_threshold=.5):
    """Deduplicate candidates and link text boxes; all output remains review-only.

    A linked text box is evidence to inspect, not an OCR validation or permission
    to erase. A bubble polygon must never be used as the text/inpainting mask.
    Input polygons are page-coordinate points; text boxes are x, y, width, height.
    """
    groups = []
    for proposal in sorted(proposals, key=lambda p: -float(p['confidence'])):
        polygon = proposal['polygon']
        group = next((g for g in groups if polygon_iou(g['polygon'], polygon) >= iou_threshold), None)
        if group is None:
            group = {'polygon': polygon, 'members': [], 'text_boxes': [], 'status': 'review_only'}
            groups.append(group)
        group['members'].append({'source': proposal['source'], 'confidence': float(proposal['confidence'])})
    for group in groups:
        poly = np.asarray(group['polygon'], dtype=np.float32).reshape(-1, 2)
        if len(poly) < 3:
            continue
        for box in text_boxes:
            x, y, w, h = box
            if w <= 0 or h <= 0:
                continue
            # Conservative centre test links a proposal for review only.
            if cv2.pointPolygonTest(poly, (float(x+w/2), float(y+h/2)), False) >= 0:
                group['text_boxes'].append(list(box))
        group['reason'] = 'text_candidate' if group['text_boxes'] else 'no_text_evidence'
    return groups
