"""Review-required paper-field finish for already-cleaned, uniquely owned text.

Never finds new text or authorizes a rejected region. Polygon, text ownership,
existing mask, background donors and artwork clearance are all required.
"""
from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FinishConfig:
    donor_exclusion_px: int = 12
    context_px: int = 32
    text_envelope_padding_px: int = 8
    feather_px: int = 8
    minimum_plane_donors: int = 64
    maximum_plane_residual: float = 4
    extension_px: int = 3
    polygon_inset_px: int = 3
    artwork_clearance_px: int = 4
    unknown_ink_below: int = 180
    bright_floor: int = 245
    minimum_donor_fraction: float = .10
    maximum_background_dark_fraction: float = .03
    maximum_background_spread: float = 8


def dilate(mask, radius):
    return cv2.dilate(mask.astype('uint8'), np.ones((2*radius+1, 2*radius+1), 'uint8')) > 0


def _background_plane(src, donors, config):
    """Robust low-order paper field; exclude full text envelopes, not just ink.

    This models near-white, locally flat paper only. It does not synthesize
    screentone or gain any authority to edit pixels.
    """
    h, w = donors.shape
    yy, xx = np.nonzero(donors)
    if len(xx) < config.minimum_plane_donors:
        return None, {'reason': 'INSUFFICIENT_TEXT_FREE_DONORS', 'plane_donors': len(xx)}
    step = max(1, (len(xx) + 19999) // 20000)
    values = src[donors][::step].astype('float64')
    design = np.column_stack((np.ones(len(xx[::step])), xx[::step]/max(1,w-1), yy[::step]/max(1,h-1)))
    keep = np.ones(len(design), bool)
    for _ in range(4):
        coefficients, _, rank, _ = np.linalg.lstsq(design[keep], values[keep], rcond=None)
        if rank < 3:
            return None, {'reason': 'DEGENERATE_BACKGROUND_DONORS'}
        error = np.max(np.abs(design @ coefficients-values), axis=1)
        keep = error <= max(2., float(np.percentile(error, 80)))
    residual = float(np.percentile(error, 90))
    yy, xx = np.indices((h,w), dtype='float32')
    field = (coefficients[0] + xx[:,:,None]/max(1,w-1)*coefficients[1]
             + yy[:,:,None]/max(1,h-1)*coefficients[2])
    detail = {'plane_donors': int(donors.sum()), 'plane_sample_count': len(design),
              'plane_residual_p90': residual, 'plane_coefficients_rgb': coefficients.tolist()}
    if residual > config.maximum_plane_residual:
        return None, dict(detail, reason='BACKGROUND_PLANE_RESIDUAL_TOO_HIGH')
    return field, detail


def finish_crop(source, current, used, interior, text_support, protected, config=FinishConfig(), donor_text=None):
    src = np.asarray(source, dtype='uint8')
    old = np.asarray(current, dtype='uint8')
    used, inside, text, protected = [np.asarray(a) > 0 for a in (used, interior, text_support, protected)]
    shape = used.shape
    if src.shape != (*shape, 3) or old.shape != src.shape or any(a.shape != shape for a in (inside, text, protected)):
        raise ValueError('Flat finish geometry mismatch')
    if min(config.donor_exclusion_px, config.extension_px, config.polygon_inset_px, config.artwork_clearance_px, config.context_px, config.text_envelope_padding_px, config.feather_px) < 0:
        raise ValueError('Negative flat finish radius')
    trace = {'rule_id': 'FLAT_TEXT_BACKGROUND_FIELD', 'configuration': asdict(config),
             'threshold_status': 'experimental_not_calibrated', 'decision': 'retain',
             'added_pixels': 0, 'refilled_pixels': 0, 'review_required': True}
    added = np.zeros(shape, bool)
    if not (used & text & inside & ~protected).any():
        trace['reason'] = 'NO_EXISTING_OWNED_MASK'
        return old.copy(), used.copy(), added, trace
    gray = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    unknown = (gray < config.unknown_ink_below) & ~used
    blocked = protected | dilate(unknown, config.artwork_clearance_px)
    sample_area = inside & ~dilate(used, config.donor_exclusion_px) & ~protected
    samples = src[sample_area]
    if not samples.size:
        trace['reason'] = 'NO_BACKGROUND_SAMPLES'
        return old.copy(), used.copy(), added, trace
    dark_fraction = float((samples.min(axis=1) < config.bright_floor).mean())
    donors = sample_area & (src.min(axis=2) >= config.bright_floor)
    values = src[donors]
    donor_fraction = float(donors.sum() / max(1, inside.sum()))
    spread = float(np.max(np.percentile(values, 90, axis=0)-np.percentile(values, 10, axis=0))) if values.size else None
    trace.update(background_dark_fraction=dark_fraction, donor_fraction=donor_fraction, background_spread=spread)
    if dark_fraction > config.maximum_background_dark_fraction or donor_fraction < config.minimum_donor_fraction or spread is None or spread > config.maximum_background_spread:
        trace['reason'] = 'BACKGROUND_NOT_FLAT_OR_INSUFFICIENT_DONORS'
        return old.copy(), used.copy(), added, trace
    # Keep the flatness gate above, but do not use white letter counters or
    # compression halos as donors. Context can supply donors outside a narrow
    # text detector rectangle; it never expands the compositing interior.
    donor_text = text if donor_text is None else np.asarray(donor_text) > 0
    if donor_text.shape != shape:
        raise ValueError('Flat finish donor geometry mismatch')
    donors = ~donor_text & ~dilate(used, config.donor_exclusion_px) & ~protected & (src.min(axis=2) >= config.bright_floor)
    estimate, plane = _background_plane(src, donors, config)
    trace.update(plane)
    if estimate is None:
        return old.copy(), used.copy(), added, trace
    allowed = inside & text & ~blocked
    # Each continuous editable envelope must intersect already-authorized ink.
    # Another disconnected text box cannot gain authority from this region.
    _, labels = cv2.connectedComponents(allowed.astype('uint8'), connectivity=8)
    anchored = np.unique(labels[allowed & used])
    anchored = anchored[anchored != 0]
    allowed &= np.isin(labels, anchored)
    if not allowed.any():
        trace['reason'] = 'NO_ANCHORED_TEXT_ENVELOPE'
        return old.copy(), used.copy(), added, trace
    spread = float(np.ptp(estimate[allowed], axis=0).max())
    trace['plane_domain_spread'] = spread
    if spread > config.maximum_background_spread or estimate[allowed].min() < config.bright_floor or estimate[allowed].max() > 256:
        trace['reason'] = 'BACKGROUND_PLANE_EXTRAPOLATION_UNSAFE'
        return old.copy(), used.copy(), added, trace
    estimate = np.clip(estimate, 0, 255)
    distance = cv2.distanceTransform(allowed.astype('uint8'), cv2.DIST_L2, 5)
    alpha = np.minimum(distance / max(1, config.feather_px), 1)
    alpha[allowed & dilate(used & text, config.extension_px)] = 1
    result = old.copy()
    blend = np.rint(old*(1-alpha[:,:,None]) + estimate*alpha[:,:,None]).astype('uint8')
    result[allowed] = blend[allowed]
    refill = used & allowed
    added = allowed & ~used
    trace.update(decision='shadow_finish_review', reason='OWNED_TEXT_ENVELOPE_FLAT_PAPER_FIELD',
                 refilled_pixels=int(refill.sum()), added_pixels=int(added.sum()),
                 feather_px=config.feather_px, envelope_pixels=int(allowed.sum()),
                 protected_pixels_changed=int((np.any(result != old, axis=2) & blocked).sum()))
    assert trace['protected_pixels_changed'] == 0
    assert not (np.any(result != old, axis=2) & ~allowed).any()
    return result, used | added, added, trace


def finish_page(source, current, mask, regions, selected, ownership, heads, analysis_size, cancel=None, artifacts=None, config=FinishConfig()):
    from ..engine import check_cancel
    from ..io import write_json
    from PIL import Image

    height, width = mask.shape
    output, final = current.copy(), mask.copy()
    events = []
    boxes_by_region = ownership.get('text_boxes_by_region', {})
    forbidden = {e['region'] for e in ownership.get('events', [])
                 if e.get('reason') in ('COMPLEX_BACKGROUND', 'COMPLEX_BACKGROUND_AND_BASELINE_SKIP', 'TEXT_OUTSIDE_BUBBLE', 'NOT_SELECTED')}
    aw, ah = analysis_size
    for region in regions:
        check_cancel(cancel)
        rid = region['id']
        if rid not in selected:
            continue
        event = {'region_id': rid, 'decision': 'retain', 'reason': None}
        events.append(event)
        boxes = boxes_by_region.get(rid, [])
        if rid in forbidden or not boxes or len(region.get('outline', [])) < 3:
            event['reason'] = 'REVIEW_GATE_OR_NO_UNIQUE_TEXT_POLYGON'
            continue
        x, y, w, h = region['box']
        # The detector polygon may under-cover text that previous ownership
        # stages have already cleaned. Include its owned text boxes as context.
        left = min([x]+[a for a,b,bw,bh in boxes])
        top = min([y]+[b for a,b,bw,bh in boxes])
        right = min(width, max([x+w]+[a+bw for a,b,bw,bh in boxes])+config.context_px)
        bottom = min(height, max([y+h]+[b+bh for a,b,bw,bh in boxes])+config.context_px)
        x, y = max(0, left-config.context_px), max(0, top-config.context_px)
        w, h = right-x, bottom-y
        event['crop_box'] = [x,y,w,h]
        sl = np.s_[y:y+h, x:x+w]
        inside = np.zeros((h, w), 'uint8')
        cv2.fillPoly(inside, [np.asarray([[a-x, b-y] for a, b in region['outline']], 'int32')], 1)
        inside = cv2.erode(inside, np.ones((2*config.polygon_inset_px+1,)*2, 'uint8'), borderType=cv2.BORDER_CONSTANT, borderValue=0) > 0
        support = np.zeros((h, w), 'uint8')
        for a, b, bw, bh in boxes:
            pad = config.text_envelope_padding_px
            support[max(0,b-y-pad):min(h,b-y+bh+pad), max(0,a-x-pad):min(w,a-x+bw+pad)] = 1
        polygon_interior = inside.copy()
        # Reconstruct only the envelope of ink ALREADY present in the final
        # mask, independently for each uniquely owned text proposal. This
        # avoids a hard polygon cut through previously cleaned letter counters.
        recovered = np.zeros((h,w), 'uint8')
        for a,b,bw,bh in boxes:
            box = np.zeros((h,w), 'uint8')
            box[max(0,b-y):max(0,min(h,b-y+bh)), max(0,a-x):max(0,min(w,a-x+bw))] = 1
            yy,xx = np.nonzero((final[sl]>0) & (box>0))
            if len(xx) < 3:
                continue
            hull = cv2.convexHull(np.column_stack((xx,yy)).astype('int32'))
            cv2.fillConvexPoly(recovered, hull, 1)
        recovered = dilate(recovered, config.text_envelope_padding_px) & (support>0)
        inside |= recovered
        event['reconstructed_envelope_outside_polygon_pixels'] = int((recovered & ~polygon_interior).sum())
        donor_text = np.zeros((h, w), 'uint8')
        for all_boxes in boxes_by_region.values():
            for a, b, bw, bh in all_boxes:
                pad = config.text_envelope_padding_px
                donor_text[max(0,b-y-pad):max(0,min(h,b-y+bh+pad)), max(0,a-x-pad):max(0,min(w,a-x+bw+pad))] = 1
        protected = np.zeros((h, w), 'uint8')
        # Heads remain protected even when an existing text mask crosses them.
        for a, b, bw, bh in heads:
            a, b, bw, bh = round(a*width/aw), round(b*height/ah), round(bw*width/aw), round(bh*height/ah)
            protected[max(0,b-y):max(0,min(h,b-y+bh)), max(0,a-x):max(0,min(w,a-x+bw))] = 1
        for other in regions:
            if other['id'] == rid:
                continue
            a, b, bw, bh = other['box']
            # No extra authority inside another region, selected or otherwise.
            protected[max(0,b-y):max(0,min(h,b-y+bh)), max(0,a-x):max(0,min(w,a-x+bw))] = 1
        cleaned, newmask, added, detail = finish_crop(source[sl], output[sl], final[sl], inside, support, protected, config, donor_text)
        event.update(detail)
        if detail['decision'] != 'shadow_finish_review':
            continue
        changed = np.any(cleaned != output[sl], axis=2)
        event['changed_pixels'] = int(changed.sum())
        if artifacts is not None:
            Image.fromarray(output[sl]).save(artifacts / (rid+'_finish_before.png'))
            Image.fromarray((final[sl]*255).astype('uint8')).save(artifacts / (rid+'_finish_mask_before.png'))
            Image.fromarray((added*255).astype('uint8')).save(artifacts / (rid+'_finish_added_mask.png'))
            Image.fromarray((newmask*255).astype('uint8')).save(artifacts / (rid+'_finish_mask_after.png'))
            Image.fromarray((polygon_interior*255).astype('uint8')).save(artifacts / (rid+'_finish_polygon_interior.png'))
            Image.fromarray((inside*255).astype('uint8')).save(artifacts / (rid+'_finish_reconstructed_interior.png'))
            Image.fromarray((protected*255).astype('uint8')).save(artifacts / (rid+'_finish_protected.png'))
            Image.fromarray((support*255).astype('uint8')).save(artifacts / (rid+'_finish_text_envelope.png'))
            Image.fromarray(cleaned).save(artifacts / (rid+'_finish_after.png'))
            write_json(artifacts / (rid+'_finish_trace.json'), event)
        output[sl] = cleaned
        final[sl] = newmask
    return output, final, {'stage': 'flat_text_background_field', 'events': events, 'configuration': asdict(config),
                           'threshold_status': 'experimental_not_calibrated', 'review_required': True}
