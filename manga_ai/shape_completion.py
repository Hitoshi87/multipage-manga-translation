"""Extend a one-sided truncated balloon mask, never across ink.

Transparent balloons let artwork show through, so a detector mask can stop
short on one side. Compare the mask with the ellipse inscribed in the detector
box; only a single, consistent shortfall is extended, and each row stops before
the first dark stroke so the outline can never be crossed. Split children,
notched or irregular balloons (misses on several sides) are returned unchanged.
"""
import math

import cv2
import numpy as np

DARK = 110
STROKE = 9   # a drawn outline is a long stroke; halftone dots and short hatching are not


def long_strokes(gray):
    """Dark pixels that belong to a long vertical, horizontal, diagonal or connected stroke."""
    dark = (gray < DARK).astype(np.uint8)
    vertical = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((STROKE, 1), np.uint8))
    horizontal = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, STROKE), np.uint8))
    diag1 = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.eye(STROKE, dtype=np.uint8))
    diag2 = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.fliplr(np.eye(STROKE, dtype=np.uint8)))
    strokes = (vertical | horizontal | diag1 | diag2) > 0
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    if n_lbl > 1:
        keep = np.zeros(n_lbl, dtype=bool)
        for i in range(1, n_lbl):
            w, h, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
            if max(w, h) >= STROKE * 2 or area >= STROKE * 3:
                keep[i] = True
        strokes |= keep[labels]
    return strokes


def _ellipse(box, inset):
    cx = box[0] + box[2] / 2
    cy = box[1] + box[3] / 2
    a = box[2] / 2 - inset
    b = box[3] / 2 - inset

    def span(y):
        t = (y + .5 - cy) / b
        if abs(t) >= 1:
            return None
        half = a * math.sqrt(1 - t * t)
        return cx - half, cx + half
    return a, b, span


def complete_shape(shape, box, gray, margin=4):
    if not shape or not shape.get('rows'):
        return shape
    rows = shape['rows']
    inset = max(5, min(12, round(min(box[2], box[3]) * .045)))
    a, b, ellipse = _ellipse(box, inset)
    if a <= 0 or b <= 0:
        return shape
    tolerance = .1 * box[2]
    widest = max(r[2] - r[1] for r in rows)
    body = left_only = right_only = both = 0
    for y, left, right in rows:
        if right - left < widest * .5:
            continue
        e = ellipse(y)
        if not e:
            continue
        body += 1
        lm, rm = left - e[0] > tolerance, e[1] - right > tolerance
        if lm and rm:
            both += 1
        elif lm:
            left_only += 1
        elif rm:
            right_only += 1
    if not body or both > .1 * body:
        return shape
    extend_left = left_only >= .3 * body and right_only <= .1 * left_only
    extend_right = right_only >= .3 * body and left_only <= .1 * right_only
    if not extend_left and not extend_right:
        return shape
    height, width = gray.shape
    x0 = max(0, int(box[0]) - 4); y0 = max(0, int(box[1]) - 4)
    x1 = min(width, int(box[0] + box[2]) + 5); y1 = min(height, int(box[1] + box[3]) + 5)
    strokes = np.zeros(gray.shape, bool)
    strokes[y0:y1, x0:x1] = long_strokes(gray[y0:y1, x0:x1])
    out = []
    for y, left, right in rows:
        e = ellipse(y)
        new_left, new_right = left, right
        if e and 0 <= y < height:
            line = strokes[y]
            if extend_right:
                limit = min(width - 1, int(e[1]))
                x = right
                while x < limit and not line[x]:
                    x += 1
                new_right = max(right, x - margin)
            if extend_left:
                limit = max(0, int(e[0]))
                x = left
                while x > limit and not line[x]:
                    x -= 1
                new_left = min(left, x + margin)
        out.append([y, new_left, new_right])
    # Smooth row-to-row jitter caused by single dark strokes and stop before inward spike tips; never shrink below the mask.
    arr = np.array(out)
    win = max(7, min(31, (len(rows) // 6) | 1))
    pad = win // 2
    for col in (1, 2):
        values = arr[:, col].astype(float)
        base = np.array([r[col] for r in rows], float)
        p3 = np.pad(values, 2, mode='edge')
        med = np.array([np.median(p3[i:i + 5]) for i in range(len(values))])
        pw = np.pad(med, pad, mode='edge')
        if col == 1:
            env = np.array([np.max(pw[i:i + win]) for i in range(len(values))])
            arr[:, col] = np.round(np.minimum(env, base))
        else:
            env = np.array([np.min(pw[i:i + win]) for i in range(len(values))])
            arr[:, col] = np.round(np.maximum(env, base))
    result = arr.tolist()
    if result == rows:
        return shape
    left_edge = min(r[1] for r in result)
    right_edge = max(r[2] for r in result)
    return {'rows': result, 'center': [(left_edge + right_edge) / 2, shape['center'][1]],
            'box': [left_edge, result[0][0], right_edge - left_edge, shape['box'][3]]}
