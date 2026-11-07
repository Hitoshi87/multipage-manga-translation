"""Full-resolution glyph completion and bounded local reconstruction.

No generative inference on an entire downsampled manga page. White backgrounds
are deterministic; textured pixels are sent to the chosen inpainting backend.
"""
import cv2
import numpy as np


def text_window(box, width, height):
    x, y, w, h = box
    pad = max(3, round(min(w, h)*.06))
    return max(0, x-pad), max(0, y-pad), min(width, x+w+pad), min(height, y+h+pad)


def complete_glyphs(rgb, mask, detections, *, dilate=True):
    """Extend detected strokes to full connected glyphs, never long borders."""
    result = (mask > 0).astype(np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    for d in detections:
        if d['confidence'] < .85:
            continue
        x0, y0, x1, y1 = text_window(d['box'], w, h)
        local = gray[y0:y1, x0:x1]
        seed = result[y0:y1, x0:x1]
        evidence = seed.copy()
        n, labels, stats, _ = cv2.connectedComponentsWithStats((local < 235).astype(np.uint8), 8)
        ids, hits = np.unique(labels[evidence > 0], return_counts=True)
        # In balloon text windows, discard broad model blobs and rebuild from
        # actual glyph components so a mask cannot shave off balloon outlines.
        rebuilt = np.zeros_like(seed)
        for label, count in zip(ids, hits):
            if label == 0:
                continue
            xx, yy, ww, hh, area = stats[label]
            if area < 2 or count/area < .12:
                continue
            # Long connected marks are usually balloon borders or artwork.
            if ww > local.shape[1]*.85 or hh > local.shape[0]*.85 or area > local.size*.2:
                continue
            if (xx == 0 or yy == 0 or xx+ww == local.shape[1] or yy+hh == local.shape[0]) and max(ww, hh) > min(local.shape)*.55:
                continue
            rebuilt[labels == label] = 1
        if d['kind'] == 'in_bubble' and np.mean(local >= 220) > .65:
            seed[:] = rebuilt
        else:
            seed[:] |= rebuilt
    if not dilate:
        return result
    radius = max(1, min(5, round(max(h, w)/1440)))
    return cv2.dilate(result, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1, radius*2+1)))


def enclosed_text_support(rgb, detections):
    """Independent closed-white geometry limits overbroad head rectangles.

    Only text windows inside enclosed white components qualify. Open shapes,
    face interiors without a strong in-balloon text proposal, and page gutters
    remain protected. Return a mask, never permission for a rectangular fill.
    """
    from .bubble_refinement import white_core, closed_interior
    # Bounded geometry computation, project inward before restoring pixels.
    h, w = rgb.shape[:2]
    scale = min(1, 1440/max(h, w))
    image = cv2.resize(rgb, (round(w*scale), round(h*scale)), interpolation=cv2.INTER_AREA)
    ih, iw = image.shape[:2]
    _, labels, stats, _ = cv2.connectedComponentsWithStats(white_core(image), 8)
    support = np.zeros((ih, iw), np.uint8)
    for d in detections:
        if d['kind'] != 'in_bubble' or d['confidence'] < .9:
            continue
        x, y, bw, bh = [round(v*scale) for v in d['box']]
        if min(bw, bh) < 1:
            continue
        ids, counts = np.unique(labels[y:y+bh, x:x+bw], return_counts=True)
        for label in ids[np.argsort(-counts)]:
            if not label:
                continue
            xx, yy, ww, hh, area = map(int, stats[label])
            overlap = max(0, min(x+bw, xx+ww)-max(x, xx))*max(0, min(y+bh, yy+hh)-max(y, yy))
            if area > iw*ih*.12 or overlap/(bw*bh) < .9:
                continue
            interior = closed_interior(image, [xx, yy, ww, hh])
            if interior is None:
                continue
            region = np.zeros((ih, iw), np.uint8)
            region[yy:yy+hh, xx:xx+ww] = (interior > 0).astype(np.uint8)
            x0, y0, x1, y1 = text_window([x, y, bw, bh], iw, ih)
            support[y0:y1, x0:x1] |= region[y0:y1, x0:x1]
            break
    return cv2.resize(support, (w, h), interpolation=cv2.INTER_NEAREST)


def flat_backgrounds(rgb, mask, detections):
    """Fill only masked glyphs in confidently detected flat white text areas."""
    result = rgb.copy()
    filled = np.zeros(mask.shape, np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = mask.shape
    for d in detections:
        if d['kind'] != 'in_bubble' or d['confidence'] < .9:
            continue
        x0, y0, x1, y1 = text_window(d['box'], w, h)
        local_mask = mask[y0:y1, x0:x1] > 0
        local_gray = gray[y0:y1, x0:x1]
        background = rgb[y0:y1, x0:x1][~local_mask]
        if len(background) < 30 or local_mask.mean() > .55:
            continue
        # Uniform near-white, not screentone, gradients or a face silhouette.
        white = background[np.min(background, axis=1) >= 235]
        if len(white)/len(background) < .9:
            continue
        color = np.median(white, axis=0)
        if np.max(np.std(white.astype(float), axis=0)) > 6:
            continue
        patch = result[y0:y1, x0:x1]
        # Interpolate the local paper shade, rather than imprinting bright
        # white letter shapes on a slightly gray scan. Only masked pixels move.
        valid = ((np.min(rgb[y0:y1, x0:x1], axis=2) >= 235) & ~local_mask).astype(np.float32)
        sigma = max(3, max(h, w)/1440*5)
        weight = cv2.GaussianBlur(valid, (0, 0), sigma)
        numerator = cv2.GaussianBlur(rgb[y0:y1, x0:x1].astype(np.float32)*valid[:, :, None], (0, 0), sigma)
        background_map = numerator/np.maximum(weight[:, :, None], 1e-6)
        background_map[weight < .01] = color
        patch[local_mask] = np.clip(np.rint(background_map[local_mask]), 0, 255).astype(np.uint8)
        filled[y0:y1, x0:x1][local_mask] = 1
    return result, filled


def recover_flat_bubble_text(rgb, raw_mask, protected_mask, detections, bubbles):
    """Experimental: recover blocked glyph pixels only with independent evidence.

    Bubble interiors constrain the already predicted text mask; they never become
    erase masks. Unverified candidates remain blocked for human review.
    """
    h, w = raw_mask.shape
    recovered = np.zeros((h, w), np.uint8)
    approved = []
    for d in detections:
        if d.get('kind') != 'in_bubble' or d.get('confidence', 0) < .8:
            continue
        x, y, bw, bh = map(int, d['box'])
        if bw <= 0 or bh <= 0 or x < 0 or y < 0 or x+bw > w or y+bh > h:
            continue
        blocked = (raw_mask[y:y+bh, x:x+bw] > 0) & (protected_mask[y:y+bh, x:x+bw] == 0)
        if blocked.sum() < 8:
            continue
        patch = rgb[y:y+bh, x:x+bw]
        unmasked = raw_mask[y:y+bh, x:x+bw] == 0
        if unmasked.sum() < 30 or np.mean(np.min(patch[unmasked], axis=1) >= 235) < .95:
            continue
        for b in bubbles:
            bx, by, bwidth, bheight = map(int, b['box'])
            left, top, right, bottom = max(x, bx), max(y, by), min(x+bw, bx+bwidth), min(y+bh, by+bheight)
            if right <= left or bottom <= top:
                continue
            inner = np.zeros((bh, bw), np.uint8)
            inner[top-y:bottom-y, left-x:right-x] = (b['interior'][top-by:bottom-by, left-bx:right-bx] > 0)
            if np.count_nonzero(blocked & (inner > 0)) / int(blocked.sum()) < .99:
                continue
            recovered[y:y+bh, x:x+bw] |= (blocked & (inner > 0)).astype(np.uint8)
            approved.append(dict(d, confidence=max(.9, d['confidence'])))
            break
    return recovered, approved


def split_unverified_mask(mask, detections, min_confidence=.85):
    """Separate text-mask evidence outside detector windows for manual review.

    Passing this check is not proof that pixels are safe to erase. This opt-in
    diagnostic gate does not alter the existing production clean workflow.
    """
    h, w = mask.shape
    support = np.zeros((h, w), np.uint8)
    for d in detections:
        if d.get('confidence', 0) < min_confidence:
            continue
        x0, y0, x1, y1 = text_window(d['box'], w, h)
        support[y0:y1, x0:x1] = 1
    source = (mask > 0).astype(np.uint8)
    return source * support, source * (1 - support)


def local_inpaint(rgb, mask, infer, cancel=None):
    """Bound inference to 768px crops with context, preserve every source pixel
    outside mask. Adjacent cores share original context, not generated pixels.
    """
    from .engine import check_cancel
    result = rgb.copy()
    h, w = mask.shape
    # Cluster nearby glyphs into text blocks before choosing bounded crops.
    cluster = cv2.dilate(mask, np.ones((49, 49), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cluster, 8)
    for label in range(1, count):
        x, y, bw, bh, _ = map(int, stats[label])
        for cy in range(y, y+bh, 512):
            for cx in range(x, x+bw, 512):
                ey, ex = min(cy+512, y+bh), min(cx+512, x+bw)
                core = (mask[cy:ey, cx:ex] > 0) & (labels[cy:ey, cx:ex] == label)
                if not np.any(core):
                    continue
                check_cancel(cancel)
                x0, y0, x1, y1 = max(0, cx-96), max(0, cy-96), min(w, ex+96), min(h, ey+96)
                crop, local_mask = rgb[y0:y1, x0:x1], mask[y0:y1, x0:x1]
                # AOT reflection padding needs >=68 pixels in either axis.
                ph = max(0, 80-crop.shape[0]); pw = max(0, 80-crop.shape[1])
                ph += (-(crop.shape[0]+ph)) % 8; pw += (-(crop.shape[1]+pw)) % 8
                padded = cv2.copyMakeBorder(crop, 0, ph, 0, pw, cv2.BORDER_REFLECT_101)
                padded_mask = cv2.copyMakeBorder(local_mask, 0, ph, 0, pw, cv2.BORDER_CONSTANT, value=0)
                reconstructed = infer(padded, padded_mask)
                target = result[cy:ey, cx:ex]
                target[core] = reconstructed[cy-y0:ey-y0, cx-x0:ex-x0][core]
    return result


def coverage_report(original, cleaned, mask, detections):
    """Suspected residuals only, not an OCR accuracy score or clean guarantee."""
    before = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY)
    after = cv2.cvtColor(cleaned, cv2.COLOR_RGB2GRAY)
    suspects = []
    for d in detections:
        x, y, w, h = d['box']
        dark = before[y:y+h, x:x+w] < 180
        if dark.sum() < 8:
            continue
        uncovered = dark & (mask[y:y+h, x:x+w] == 0)
        remaining = dark & (after[y:y+h, x:x+w] < 200)
        if uncovered.sum()/dark.sum() > .08 or remaining.sum()/dark.sum() > .12:
            suspects.append({'box': d['box'], 'uncovered_ink_fraction': round(float(uncovered.sum()/dark.sum()), 3),
                             'remaining_ink_fraction': round(float(remaining.sum()/dark.sum()), 3)})
    return {'suspect_count': len(suspects), 'suspects': suspects,
            'note': 'Kiểm tra pixel trong vùng AI tìm thấy; có thể là chữ còn sót hoặc nét tranh. Không đo được vùng AI bỏ sót.'}
