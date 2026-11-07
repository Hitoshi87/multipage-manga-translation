"""Post-clean guard for 1107: keep non-bubble text exactly as in the source.

1107 stays the cleaner. This module only decides which regions must be
restored to the original pixels afterwards. It is deliberately narrow:

* free text (``comic_text_ai`` with no parent bubble) is never processed;
* a *banner box* is restored only when every one of these holds:
  a balloon-detector region whose shape is a perfect axis-aligned rectangle
  AND the text is heavy display type (dense, thick strokes). Ordinary bubbles,
  hand-drawn/jagged bubbles and thin-text caption boxes do not match.

Calibrated on the Chainsaw Man / Mayonaka Heart Tune / Dandadan samples, where
exactly one region (MHT04 B006, a magazine banner) matches. Thresholds are
named constants so they can be re-tuned when more samples are labelled.
"""
from __future__ import annotations

import cv2
import numpy as np

# A bubble outline has dozens of distinct row spans; a rectangle has 1-2.
RECT_MAX_DISTINCT_SPANS = 2
# Display type: dark pixels cover a large share of the text area and are thick.
HEAVY_INK_FRACTION = 0.35
HEAVY_STROKE_PX = 5.0
INK_LEVEL = 90

BANNER_REASON = 'ROLE_GUARD_BANNER_BOX'
FREE_TEXT_REASON = 'ROLE_GUARD_FREE_TEXT'


def is_free_text(region: dict) -> bool:
    """Floating text detected by comic_text_ai that is not inside a bubble."""
    return region.get('detector') == 'comic_text_ai' and not region.get('parent_box')


def is_rectangular(region: dict) -> bool:
    rows = (region.get('shape') or {}).get('rows') or []
    if not rows:
        return False
    return len({(a, b) for _, a, b in rows}) <= RECT_MAX_DISTINCT_SPANS


def ink_metrics(gray: np.ndarray, region: dict) -> tuple[float, float]:
    """Return (ink fraction, max stroke half-width in px) inside the safe box."""
    x, y, w, h = region.get('safe') or region['box']
    crop = gray[max(0, y):max(0, y) + h, max(0, x):max(0, x) + w]
    if crop.size == 0:
        return 0.0, 0.0
    ink = (crop < INK_LEVEL).astype(np.uint8)
    if not ink.any():
        return 0.0, 0.0
    return float(ink.mean()), float(cv2.distanceTransform(ink, cv2.DIST_L2, 3).max())


def is_banner_box(region: dict, gray: np.ndarray) -> bool:
    if region.get('detector') != 'ai_balloon' or not is_rectangular(region):
        return False
    fraction, thickness = ink_metrics(gray, region)
    return fraction >= HEAVY_INK_FRACTION and thickness >= HEAVY_STROKE_PX


def guarded_regions(regions: list[dict], selected: set, gray: np.ndarray) -> dict[str, str]:
    """Map region id -> reason for every selected region that must stay original."""
    found: dict[str, str] = {}
    for region in regions:
        if region['id'] not in selected:
            continue
        if is_free_text(region):
            found[region['id']] = FREE_TEXT_REASON
        elif is_banner_box(region, gray):
            found[region['id']] = BANNER_REASON
    return found


def restore_regions(original, clean, mask, regions, guarded, selected):
    """Put source pixels back inside guarded region boxes.

    Pixels that fall inside the box of a different, non-guarded selected region
    are left alone so a neighbouring bubble's clean is never undone. Returns
    (clean, mask, {region id: restored pixel count}); inputs are not modified.
    """
    clean = clean.copy()
    mask = mask.copy()
    height, width = mask.shape
    by_id = {r['id']: r for r in regions}
    counts: dict[str, int] = {}
    for rid in guarded:
        x, y, w, h = by_id[rid]['box']
        area = np.zeros((height, width), bool)
        area[max(0, y):max(0, y + h), max(0, x):max(0, x + w)] = True
        for other in regions:
            if other['id'] in guarded or other['id'] not in selected:
                continue
            ox, oy, ow, oh = other['box']
            area[max(0, oy):max(0, oy + oh), max(0, ox):max(0, ox + ow)] = False
        restore = area & (np.any(original != clean, axis=2) | mask)
        counts[rid] = int(restore.sum())
        clean[restore] = original[restore]
        mask[restore] = False
    return clean, mask, counts
