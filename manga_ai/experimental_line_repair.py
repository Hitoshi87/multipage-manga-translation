"""Opt-in, approval-gated straight-line repair in already editable pixels."""
import cv2
import numpy as np


def repair_confirmed_lines(original, cleaned, edit_mask, approval_mask, segments, max_gap=100):
    """Try explicitly supplied endpoint pairs with dark evidence on both sides.

    A segment is (x1, y1, x2, y2). Endpoints must be dark source pixels outside
    the edit mask, at least four of the five samples at each end must be dark,
    and the segment's editable gap must be short and entirely approved. No
    detection or approval is inferred. Writes are restricted to edit_mask AND
    approval_mask. Declined segments are returned with their reasons.
    """
    if original.shape != cleaned.shape or original.shape[:2] != edit_mask.shape or edit_mask.shape != approval_mask.shape:
        raise ValueError('Shapes do not match')
    result = cleaned.copy(); repaired = np.zeros(edit_mask.shape, np.uint8); decisions = []
    h, w = edit_mask.shape; gray = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY)
    for segment in segments:
        x1,y1,x2,y2 = map(int,segment); decision = {'segment':[x1,y1,x2,y2]}
        if not (0 <= x1 < w and 0 <= x2 < w and 0 <= y1 < h and 0 <= y2 < h):
            decision['reason'] = 'outside_image'; decisions.append(decision); continue
        length=max(abs(x2-x1),abs(y2-y1))+1
        if length < 12:
            decision['reason']='insufficient_anchors';decisions.append(decision);continue
        xs=np.rint(np.linspace(x1,x2,length)).astype(int); ys=np.rint(np.linspace(y1,y2,length)).astype(int)
        gap=edit_mask[ys,xs]>0; approved=approval_mask[ys,xs]>0
        if not gap.any() or gap.sum()>max_gap or np.any(gap & ~approved):
            decision['reason']='gap_unapproved_or_too_long';decisions.append(decision);continue
        if np.any(gap[:5]) or np.any(gap[-5:]) or np.count_nonzero(gray[ys[:5],xs[:5]] < 100)<4 or np.count_nonzero(gray[ys[-5:],xs[-5:]] < 100)<4:
            decision['reason']='anchors_not_verified';decisions.append(decision);continue
        # Multiple separated gaps make a single pair ambiguous.
        runs=np.count_nonzero(np.diff(np.r_[False,gap,False].astype(np.int8))==1)
        if runs!=1:
            decision['reason']='ambiguous_gaps';decisions.append(decision);continue
        anchors=original[np.r_[ys[:5],ys[-5:]],np.r_[xs[:5],xs[-5:]]]
        color=np.median(anchors,axis=0).astype(np.uint8)
        result[ys[gap],xs[gap]]=color; repaired[ys[gap],xs[gap]]=1
        decision.update(reason='repaired_approved_line',pixels=int(gap.sum()));decisions.append(decision)
    return result,repaired,decisions
