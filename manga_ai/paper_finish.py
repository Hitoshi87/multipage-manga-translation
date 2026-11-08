"""Flatten the paper of cleaned opaque balloons so no ghost of the old text remains.

The clean fill is a single colour taken as the median of the bright pixels, which JPEG ringing and
anti-aliasing pull a little below the real paper (for example 253 against 255). A patch of the wrong tone,
shaped like the old glyphs, plus a faint fringe around it, shows up as a ghost of the original text
(clearly so after a CMYK conversion). For balloons whose interior is flat paper this step

  1. takes the paper colour as the most frequent value (per channel),
  2. repaints the cleaned pixels with it, and
  3. repaints the faint fringe right around them (not ink, not paper) with it.

It never leaves the balloon interior (the inset shape, so the outline is untouched), never touches
dark pixels (real ink or artwork), and skips balloons whose interior is not flat paper (screentone,
artwork) and regions redrawn by the AI.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

BAND = 5                # how far the fringe may extend from a cleaned pixel
INK_BELOW = 150         # darker than this is ink or artwork: never repainted
FLAT_SHARE = .9         # share of untouched interior pixels that must already be paper


def _inside(shape, size):
    mask = np.zeros(size, bool)
    for y, left, right in shape['rows']:
        if 0 <= y < size[0]:
            mask[y, max(0, left):max(0, right)] = True
    return mask


def paper_colour(rgb, gray, free):
    """Most frequent value per channel among bright, untouched interior pixels, or None."""
    sample = free & (gray >= 235)
    if int(sample.sum()) < 200:
        return None
    colour = []
    for channel in range(3):
        values = rgb[:, :, channel][sample]
        colour.append(int(np.bincount(values, minlength=256).argmax()))
    return colour


def finish_region(rgb, gray, overlay, shape):
    """Flatten one balloon in place; returns the number of pixels repainted (0 when skipped)."""
    inside = _inside(shape, gray.shape)
    painted = (overlay[:, :, 3] > 0) & inside
    if not painted.any():
        return 0
    near = cv2.dilate(painted.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * BAND + 1, 2 * BAND + 1))) > 0
    free = inside & ~near                                 # interior away from the cleaned area
    colour = paper_colour(rgb, gray, free)
    if colour is None:
        return 0
    deviation = np.abs(rgb.astype(int) - np.array(colour)).max(axis=2)
    if float((deviation[free] <= 8).mean()) < FLAT_SHARE:
        return 0                                          # not flat paper: screentone or artwork
    fringe = near & inside & ~painted & (gray >= INK_BELOW) & (deviation > 1)
    target = painted | fringe
    overlay[target, :3] = colour
    overlay[target, 3] = 255
    return int(target.sum())


def finish_overlay(original_path, overlay_path, shapes, skip=()):
    """Apply finish_region to every shape (id -> shape) and rewrite the overlay; returns {id: pixels}."""
    with Image.open(original_path) as image:
        rgb = np.asarray(image.convert('RGB')).copy()
    with Image.open(overlay_path) as image:
        overlay = np.asarray(image.convert('RGBA')).copy()
    if overlay.shape[:2] != rgb.shape[:2]:
        return {}
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    changed = {}
    for rid, shape in shapes.items():
        if rid in skip or not shape or not shape.get('rows'):
            continue
        count = finish_region(rgb, gray, overlay, shape)
        if count:
            changed[rid] = count
    if changed:
        Image.fromarray(overlay, 'RGBA').save(overlay_path)
    return changed


def finish_result(result, manifest_path, regions_by_id):
    """Engine hook: flatten the paper of cleaned balloons; never raises."""
    overlay = result.get('overlay')
    if not overlay:
        return result
    try:
        skip = set(result.get('art_inpaint_ids', []))
        shapes = {rid: regions_by_id[rid].get('shape') for rid in result.get('applied', [])
                  if rid in regions_by_id and regions_by_id[rid].get('detector') in ('ai_balloon', 'hybrid_closed_balloon')}
        changed = finish_overlay(Path(manifest_path).resolve().parent / 'original.png', overlay, shapes, skip)
        result['paper_finish'] = changed
    except Exception as exc:
        result['paper_finish'] = {}
        result['paper_finish_error'] = str(exc)[:160]
    return result
