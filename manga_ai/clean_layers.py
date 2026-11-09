"""Split a page-wide clean overlay into one cropped layer per bubble.

Engines paint every cleaned or redrawn bubble into a single page overlay. One
Photoshop layer for a whole page is hard to review: a person cannot hide, move,
repaint or delete the fix for one bubble without touching the rest. This module
assigns each painted pixel to the bubble it belongs to and writes one small PNG
per bubble (cropped, with its page position) so Photoshop can create a layer
for each.

Assignment is by the bubble outline (dilated a little), smallest outline first so
nested shapes keep their own pixels; pixels outside every outline join the region
whose box they overlap most. Nothing is invented: the union of the pieces equals
the original overlay.
"""
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

MARGIN = 10
MAX_REGIONS = 120          # beyond this a per-bubble split is slower than useful


def _polygon(region, shape, margin):
    mask = np.zeros(shape, np.uint8)
    points = np.asarray(region.get('outline') or [], np.int32)
    if len(points) >= 3:
        cv2.fillPoly(mask, [points], 1)
    else:
        x, y, w, h = region['box']
        mask[max(0, y):y + h, max(0, x):x + w] = 1
    if margin:
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margin + 1, 2 * margin + 1)))
    return mask > 0


def assign_pixels(alpha, regions, margin=MARGIN):
    """Return (labels, order): labels[y, x] is an index into `order`, -1 where unpainted, -2 if unassigned."""
    painted = alpha > 0
    labels = np.full(alpha.shape, -1, np.int32)
    labels[painted] = -2
    # Compute the exact old order without retaining one full-page mask per
    # region: large scans otherwise use O(page pixels * bubble count) RAM.
    areas = [int(_polygon(r, alpha.shape, margin).sum()) for r in regions]
    order = sorted(range(len(regions)), key=lambda i: areas[i])
    for index in order:
        take = _polygon(regions[index], alpha.shape, margin) & (labels == -2)
        labels[take] = index
    left = (labels == -2)
    if left.any():
        count, comp = cv2.connectedComponents(left.astype(np.uint8), connectivity=8)
        for c in range(1, count):
            ys, xs = np.nonzero(comp == c)
            best, best_overlap = None, 0
            for index, region in enumerate(regions):
                x, y, w, h = region['box']
                overlap = int(((xs >= x - margin) & (xs < x + w + margin) & (ys >= y - margin) & (ys < y + h + margin)).sum())
                if overlap > best_overlap:
                    best, best_overlap = index, overlap
            if best is not None:
                labels[ys, xs] = best
    return labels


def split_overlay(overlay_path, regions, out_dir, margin=MARGIN):
    """Write one PNG per region that owns painted pixels; return the layer list."""
    with Image.open(overlay_path) as image:
        rgba = np.asarray(image.convert('RGBA'))
    if rgba[:, :, 3].max() == 0:
        return []
    labels = assign_pixels(rgba[:, :, 3], regions, margin)
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    layers = []
    for index, region in enumerate(regions):
        mine = labels == index
        if not mine.any():
            continue
        ys, xs = np.nonzero(mine)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        crop = rgba[y0:y1, x0:x1].copy()
        crop[~mine[y0:y1, x0:x1]] = 0
        path = out / f"clean_{region['id']}.png"
        Image.fromarray(crop, 'RGBA').save(path)
        layers.append({'id': region['id'], 'file': str(path), 'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0,
                       'pixels': int(mine.sum())})
    unassigned = int((labels == -2).sum())
    if unassigned:
        # Pixels no bubble claims stay visible rather than being lost.
        mine = labels == -2
        ys, xs = np.nonzero(mine)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        crop = rgba[y0:y1, x0:x1].copy()
        crop[~mine[y0:y1, x0:x1]] = 0
        path = out / 'clean_REST.png'
        Image.fromarray(crop, 'RGBA').save(path)
        layers.append({'id': 'REST', 'file': str(path), 'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'pixels': unassigned})
    return layers


def attach_region_layers(result, manifest_path, regions_by_id):
    """Add `region_layers` to an engine result; never raises (a single overlay still works)."""
    overlay = result.get('overlay')
    if not overlay:
        return result
    ids = list(dict.fromkeys(list(result.get('applied', [])) + list(result.get('art_inpaint_ids', []))
                             + list(result.get('review_ids', []))))
    regions = [regions_by_id[i] for i in ids if i in regions_by_id]
    if not regions or len(regions) > MAX_REGIONS:
        result['layer_split'] = 'single'
        return result
    try:
        result['region_layers'] = split_overlay(overlay, regions, Path(manifest_path).resolve().parent / 'clean_layers')
        result['layer_split'] = 'regions'
    except Exception as exc:                         # fall back to the one-layer overlay
        result['layer_split'] = 'single'
        result['layer_split_error'] = str(exc)[:160]
    return result


def attach_from_manifest(result, manifest_path):
    """Read the manifest's regions and split the overlay; any failure keeps the single overlay."""
    try:
        from .io import read_json
        regions = {r['id']: r for r in read_json(manifest_path).get('regions', [])}
        # Flatten the paper first, so the per-bubble layers and the measured shapes use the final overlay.
        from .paper_finish import finish_result
        finish_result(result, manifest_path, regions)
        original_shapes = protect_opaque_balloons(result, manifest_path, regions)
        attach_region_layers(result, manifest_path, regions)
        # Balloon extents measured from the cleaned page, for centring the lettering (never raises).
        from .shape_refine import attach_refined_shapes
        attach_refined_shapes(result, manifest_path, regions)
        # The unmodified source cannot have been enlarged by a mistaken clean.
        result.setdefault('refined_shapes', {}).update(original_shapes)
        return result
    except Exception as exc:
        result['layer_split'] = 'single'
        result['layer_split_error'] = str(exc)[:160]
        return result


def protect_opaque_balloons(result, manifest_path, regions_by_id):
    """Clip clean pixels to an independently measured original white interior.

    Only ordinary opaque AI balloons with an independently closed bright region
    are handled. If measurement is inconclusive, leave the existing engine path
    alone. Any removed pixels require review because some may have been text.
    """
    from .shape_refine import refine_shape
    overlay_path=result.get('overlay')
    if not overlay_path:
        return {}
    ids=list(dict.fromkeys(result.get('applied', [])))
    eligible=[regions_by_id[rid] for rid in ids if rid in regions_by_id
              and regions_by_id[rid].get('detector')=='ai_balloon'
              and regions_by_id[rid].get('auto_clean') is True
              and rid not in result.get('art_inpaint_ids', [])]
    if not eligible:
        return {}
    root=Path(manifest_path).resolve().parent
    with Image.open(root/'original.png') as image:
        gray=np.asarray(image.convert('L'))
    with Image.open(overlay_path) as image:
        overlay=np.asarray(image.convert('RGBA')).copy()
    if overlay.shape[:2] != gray.shape:
        return {}
    shapes={}; clipped={}
    for region in eligible:
        x,y,w,h=region['box'];rid=region['id']
        # Do not remove another region's pixels in overlapping detector boxes.
        if any(other['id'] != rid and max(x,other['box'][0]) < min(x+w,other['box'][0]+other['box'][2])
               and max(y,other['box'][1]) < min(y+h,other['box'][1]+other['box'][3])
               for other in regions_by_id.values()):
            continue
        shape=refine_shape(gray,region,None)
        if not shape:
            continue
        # Lettering needs a wide margin; clean only needs to stay just inside
        # the ink outline, otherwise glyphs near the edge would be left behind.
        clean_shape=refine_shape(gray,region,None,inset=2)
        if not clean_shape:
            continue
        shape['source']='original_pixels';shapes[rid]=shape
        x0,y0=max(0,x),max(0,y);x1,y1=min(gray.shape[1],x+w),min(gray.shape[0],y+h)
        allowed=np.zeros((y1-y0,x1-x0),np.uint8)
        for yy,left,right in clean_shape['rows']:
            if y0<=yy<y1:
                allowed[yy-y0,max(0,left-x0):min(x1-x0,right-x0)]=1
        target=overlay[y0:y1,x0:x1]
        outside=(target[:,:,3]>0)&(allowed==0)
        if outside.any():
            clipped[rid]=int(outside.sum());target[outside]=0
    if clipped:
        Image.fromarray(overlay,'RGBA').save(overlay_path)
        result['geometry_clipped']=clipped
        result['review_ids']=list(dict.fromkeys(result.get('review_ids',[])+list(clipped)))
    return shapes
