"""Balloon interior measured from the cleaned page, for opaque (white) balloons.

The analysis-time mask can be narrower than the visible balloon on one side, which makes the lettering
sit off-centre. Once the original text is cleaned away, an opaque balloon is simply the white region
inside its outline, so its true extent can be measured from pixels: the bright component that holds the
old text area, holes filled, eroded by the usual outline margin.

The measurement is used only when it is trustworthy: the component must stay inside the detector box
(a leak through a gap in the outline would run to the crop border), cover a plausible share of the box
and agree in size with the mask. Balloons drawn over artwork are not bright, fail the checks, and keep
the mask (optionally completed by shape_completion).
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

BRIGHT = 200
PAD = 6


def cleaned_gray(original_path, overlay_path):
    """Gray image of the page with the clean overlay applied."""
    with Image.open(original_path) as image:
        base = np.asarray(image.convert('RGB')).astype(np.float32)
    if overlay_path:
        with Image.open(overlay_path) as image:
            over = np.asarray(image.convert('RGBA')).astype(np.float32)
        if over.shape[:2] == base.shape[:2]:
            alpha = over[:, :, 3:4] / 255.0
            base = base * (1 - alpha) + over[:, :, :3] * alpha
    return cv2.cvtColor(np.clip(base, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def _rows_area(rows):
    return sum(r[2] - r[1] for r in rows)


def _refine_shape(gray, region, mask_shape, brightness, inset_override=None):
    x, y, w, h = region['box']
    height, width = gray.shape
    x0, y0, x1, y1 = max(0, x - PAD), max(0, y - PAD), min(width, x + w + PAD), min(height, y + h + PAD)
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0 or w < 20 or h < 20:
        return None
    count, labels, stats, _ = cv2.connectedComponentsWithStats((crop >= brightness).astype(np.uint8), 4)
    if count < 2:
        return None
    # The component that holds the old text area: the one overlapping the mask (or the box centre) most.
    votes = {}
    if mask_shape and mask_shape.get('rows'):
        for yy, left, right in mask_shape['rows']:
            row = yy - y0
            if 0 <= row < labels.shape[0]:
                segment = labels[row, max(0, left - x0):max(0, right - x0)]
                for label in np.unique(segment[segment > 0]):
                    votes[int(label)] = votes.get(int(label), 0) + int((segment == label).sum())
    if not votes:
        cy, cx = (y + h // 2) - y0, (x + w // 2) - x0
        if 0 <= cy < labels.shape[0] and 0 <= cx < labels.shape[1] and labels[cy, cx] > 0:
            votes[int(labels[cy, cx])] = 1
    if not votes:
        return None
    label = max(votes, key=votes.get)
    comp = (labels == label).astype(np.uint8)
    # A leak through a gap in the outline reaches the crop border; a real balloon stays inside its box.
    border = np.concatenate([comp[0, :], comp[-1, :], comp[:, 0], comp[:, -1]])
    if int(border.sum()) > 2:
        return None
    # Fill bounded interior holes left by old text remnants without bridging over exterior dark strokes.
    inv = (comp == 0).astype(np.uint8)
    nh, hlabels, hstats, _ = cv2.connectedComponentsWithStats(inv, 8)
    filled = comp.copy()
    max_hole = max(250, int(comp.sum() * .08))
    for hlbl in range(1, nh):
        hc = hlabels == hlbl
        if np.any(hc[0, :]) or np.any(hc[-1, :]) or np.any(hc[:, 0]) or np.any(hc[:, -1]):
            continue
        if hstats[hlbl, cv2.CC_STAT_AREA] <= max_hole:
            filled[hc] = 1
    share = filled.sum() / float(w * h)
    if not .35 <= share <= .95:
        return None
    scale = max(1.0, min(w, h) / 180.0)
    inset = inset_override if inset_override is not None else max(5, min(round(12 * scale), round(min(w, h) * .045)))
    inner = cv2.erode(filled, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inset + 1, 2 * inset + 1)))
    rows = []
    for row in range(inner.shape[0]):
        cols = np.flatnonzero(inner[row])
        if not len(cols):
            continue
        # largest contiguous run of the row
        breaks = np.flatnonzero(np.diff(cols) > 1)
        starts = np.concatenate(([0], breaks + 1))
        ends = np.concatenate((breaks, [len(cols) - 1]))
        k = int(np.argmax(cols[ends] - cols[starts]))
        left, right = int(cols[starts[k]]), int(cols[ends[k]])
        if right - left >= 12:
            rows.append([y0 + row, x0 + left, x0 + right + 1])
    if len(rows) < 12:
        return None
    safe = region.get('safe')
    if safe and len(safe) == 4:
        sx, sy, sw, sh = safe
        core_rows = [r for r in rows if sy <= r[0] < sy + sh] or rows
        left_exts = [max(0, sx - r[1]) for r in core_rows]
        right_exts = [max(0, r[2] - (sx + sw)) for r in core_rows]
        ext_l, ext_r = float(np.median(left_exts)), float(np.median(right_exts))
        max_l, max_r = max(left_exts), max(right_exts)
        if abs(ext_l - ext_r) > inset * .5 or max_l - ext_l > inset * .5 or max_r - ext_r > inset * .5:
            cap_x = round(min(ext_l, ext_r) + inset * .5)
            min_x, max_x = sx - cap_x, sx + sw + cap_x
            trimmed_x = [[r[0], max(min_x, r[1]), min(max_x, r[2])] for r in rows if min(max_x, r[2]) - max(min_x, r[1]) >= 12]
            if len(trimmed_x) >= 12:
                rows = trimmed_x
        ext_t, ext_b = max(0, sy - rows[0][0]), max(0, rows[-1][0] - (sy + sh))
        if abs(ext_b - ext_t) > inset * 2:
            cap_y = round(min(ext_t, ext_b) + inset)
            min_y, max_y = sy - cap_y, sy + sh + cap_y
            trimmed_y = [r for r in rows if min_y <= r[0] <= max_y]
            if len(trimmed_y) >= 12:
                rows = trimmed_y
    if mask_shape and mask_shape.get('rows'):
        ratio = _rows_area(rows) / max(1, _rows_area(mask_shape['rows']))
        if not .7 <= ratio <= 2.0:
            return None
    left = min(r[1] for r in rows)
    right = max(r[2] for r in rows)
    return {'rows': rows, 'center': [(left + right) / 2, (rows[0][0] + rows[-1][0] + 1) / 2],
            'box': [left, rows[0][0], right - left, rows[-1][0] - rows[0][0] + 1], 'source': 'cleaned_pixels'}


def refine_shape(gray, region, mask_shape, inset=None):
    """Try stricter brightness when pale artwork leaks into the white component."""
    for brightness in (BRIGHT, 220, 235):
        shape = _refine_shape(gray, region, mask_shape, brightness, inset)
        if shape is not None:
            shape['brightness'] = brightness
            return shape
    return None


def attach_refined_shapes(result, manifest_path, regions_by_id):
    """Add `refined_shapes` (region id -> shape) to an engine result; never raises."""
    ids = list(dict.fromkeys(list(result.get('applied', [])) + list(result.get('art_inpaint_ids', []))))
    if not ids or not result.get('overlay'):
        return result
    try:
        root = Path(manifest_path).resolve().parent
        gray = cleaned_gray(root / 'original.png', result['overlay'])
        shapes = {}
        for rid in ids:
            region = regions_by_id.get(rid)
            if not region or region.get('detector') not in ('ai_balloon', 'hybrid_closed_balloon'):
                continue
            shape = refine_shape(gray, region, region.get('shape'))
            if shape:
                shapes[rid] = shape
        result['refined_shapes'] = shapes
    except Exception as exc:
        result['refined_shapes'] = {}
        result['shape_refine_error'] = str(exc)[:160]
    return result
