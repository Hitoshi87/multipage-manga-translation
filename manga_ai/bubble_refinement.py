"""Split AI proposals using independent closed-white geometry, never line counts.

Connected lobes remain reviewable. Parent model confidence is preserved.
"""
import cv2
import numpy as np
from itertools import combinations


def split_text_groups(rgb, candidates, detections):
    """Separate horizontally disjoint text groups inside one learned balloon.

    Keep the parent silhouette and cut only through whitespace. A column of
    Japanese within one detected text group is never split into sentences.
    """
    result=[]
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    for parent in candidates:
        x,y,w,h=parent['box'];groups=[]
        for d in detections:
            if d['kind']!='in_bubble' or d['confidence']<.85:continue
            tx,ty,tw,th=d['box']
            overlap=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
            if overlap/(tw*th)>=.9:groups.append(d['box'])
        groups.sort(key=lambda b:b[0])
        if len(groups)<2 or len(groups)>8 or any(a[0]+a[2]+3>b[0] for a,b in zip(groups,groups[1:])):
            result.append(parent);continue
        cuts=[0];valid=True
        for a,b in zip(groups,groups[1:]):
            left=max(1,a[0]+a[2]-x);right=min(w-1,b[0]-x)
            # The cut must not cross any ink in the balloon interior.
            costs=np.count_nonzero((gray[y:y+h,x+left:x+right]<210)&(parent['interior'][:,left:right]>0),axis=0)
            if not len(costs) or costs.min()>0:valid=False;break
            middle=(a[0]+a[2]+b[0])/2-x
            choices=np.flatnonzero(costs==0)+left
            def span(column):
                ys=np.flatnonzero(parent['interior'][:,max(0,min(w-1,column))])
                return int(ys[-1]-ys[0]+1) if len(ys) else 0
            # Whitespace alone can separate columns of the same sentence.
            # Also require a neck in the balloon silhouette at this join.
            cut=int(min(choices,key=lambda c:(span(c),abs(c-middle))))
            neighbour=max(span(a[0]+a[2]//2-x),span(b[0]+b[2]//2-x))
            if span(cut)>.95*neighbour:valid=False;break
            cuts.append(cut)
        if not valid:result.append(parent);continue
        cuts.append(w)
        children=[]
        for left,right in zip(cuts,cuts[1:]):
            mask=parent['interior'][:,left:right].copy()
            if right-left<20 or cv2.countNonZero(mask)<500:break
            child=dict(parent);child.update(box=[x+left,y,right-left,h],interior=mask,
                geometry_evidence='text_groups_whitespace',parent_box=parent['box'][:])
            children.append(child)
        result.extend(children if len(children)==len(groups) else [parent])
    return result


def white_core(rgb):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # Disconnect scan leaks up to four pixels; larger openings stay review-only.
    return cv2.erode((gray >= 220).astype(np.uint8), np.ones((5, 5), np.uint8),
                     borderType=cv2.BORDER_CONSTANT, borderValue=0)


def recover_text_balloons(rgb, candidates, detections):
    """Recover missed enclosed white balloons supported by independent text."""
    _,labels,stats,_=cv2.connectedComponentsWithStats(white_core(rgb),8)
    result=list(candidates);page_area=rgb.shape[0]*rgb.shape[1]
    for d in detections:
        if d['kind']!='in_bubble' or d['confidence']<.85:continue
        x,y,w,h=d['box']
        if any(max(0,min(x+w,r['box'][0]+r['box'][2])-max(x,r['box'][0]))*max(0,min(y+h,r['box'][1]+r['box'][3])-max(y,r['box'][1]))/(w*h)>.45 for r in result):continue
        ids,counts=np.unique(labels[y:y+h,x:x+w],return_counts=True)
        for label in ids[np.argsort(-counts)]:
            if not label:continue
            xx,yy,ww,hh,area=map(int,stats[label])
            overlap=max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
            if ww*hh>page_area*.08 or overlap/(w*h)<.9:continue
            mask=closed_interior(rgb,[xx,yy,ww,hh])
            if mask is not None:
                result.append({'box':[xx,yy,ww,hh],'interior':mask,'detector':'hybrid_closed_balloon',
                    'detector_confidence':d['confidence'],'geometry_evidence':'closed_white_component'})
                break
    return result


def closed_interior(rgb, box):
    """Reconstruct an enclosed white component from its exact bounding box."""
    x, y, w, h = box
    height, width = rgb.shape[:2]
    if x <= 3 or y <= 3 or x+w >= width-3 or y+h >= height-3:
        return None
    count, labels, stats, _ = cv2.connectedComponentsWithStats(white_core(rgb[y-3:y+h+3, x-3:x+w+3]), 8)
    for label in range(1, count):
        xx, yy, ww, hh, area = map(int, stats[label])
        if [xx, yy, ww, hh] != [3, 3, w, h] or area < 500 or area/(w*h) < .45:
            continue
        component = (labels[3:h+3, 3:w+3] == label).astype(np.uint8)*255
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(component)
        cv2.drawContours(filled, [max(contours, key=cv2.contourArea)], -1, 255, -1)
        return cv2.erode(filled, np.ones((5, 5), np.uint8),
                         borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return None


def split_closed_balloons(rgb, candidates):
    _, labels, stats, _ = cv2.connectedComponentsWithStats(white_core(rgb), 8)
    result = []
    for candidate in candidates:
        if candidate.get('detector') != 'ai_balloon' or candidate['detector_confidence'] < .8:
            result.append(candidate)
            continue
        x, y, w, h = candidate['box']
        interior = candidate['interior'] > 0
        local = labels[y:y+h, x:x+w]
        ids, overlap = np.unique(local[interior], return_counts=True)
        matches = []
        total = np.count_nonzero(interior)
        for label, pixels in zip(ids, overlap):
            if label == 0 or pixels < max(500, total*.15):
                continue
            xx, yy, ww, hh, area = map(int, stats[label])
            if min(ww, hh) < 25 or area > total*1.1 or pixels/area < .7:
                continue
            if xx < x-5 or yy < y-5 or xx+ww > x+w+5 or yy+hh > y+h+5:
                continue
            box = [xx, yy, ww, hh]
            mask = closed_interior(rgb, box)
            if mask is not None:
                matches.append({'box': box, 'interior': mask, 'detector': 'hybrid_closed_balloon',
                                'detector_confidence': candidate['detector_confidence'],
                                'geometry_evidence': 'closed_white_component'})
        if 2 <= len(matches) <= 4 and sum(np.count_nonzero(v['interior']) for v in matches) >= total*.7:
            result.extend(matches)
        else:
            result.append(candidate)
    return result


def lobe_candidates(rgb, candidate):
    """Two concave joins can separate connected lobes without crossing text.

    These are only proposals: the caller must confirm strong Japanese OCR in
    BOTH parts before replacing the parent. Ordinary ovals and tails stay whole.
    """
    if candidate.get('geometry_evidence') or candidate.get('detector') != 'ai_balloon':
        return []
    if candidate.get('detector_confidence', 0) < .9:
        return []
    x, y, w, h = candidate['box']
    mask = candidate['interior']
    contour = max(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    hull = cv2.convexHull(contour, returnPoints=False)
    defects = cv2.convexityDefects(contour, hull) if len(hull) >= 4 else None
    if defects is None:
        return []
    deep = sorted((v[0] for v in defects if v[0][3]/256 > max(12, min(w,h)*.04)), key=lambda v:-v[3])[:4]
    ink = ((cv2.cvtColor(rgb[y:y+h, x:x+w], cv2.COLOR_RGB2GRAY) < 210) & (mask > 0)).astype(np.uint8)
    _, ink_labels, ink_stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    area = cv2.countNonZero(mask)
    for a, b in combinations(deep, 2):
        start, end = tuple(contour[a[2], 0]), tuple(contour[b[2], 0])
        if np.linalg.norm(np.array(start)-end) > min(w,h)*.6:
            continue
        seam = np.zeros_like(mask); cv2.line(seam, start, end, 255, 4)
        crossing = np.unique(ink_labels[(seam > 0) & (ink > 0)])
        if sum(int(ink_stats[i, 4]) for i in crossing) > 4:
            continue
        cut = mask.copy(); cv2.line(cut, start, end, 0, 2)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(cut, 8)
        parts = [(i, stats[i]) for i in range(1,count) if stats[i,4] >= area*.1]
        if len(parts) != 2 or sum(v[1][4] for v in parts) < area*.98:
            continue
        children = []
        for label, stat in parts:
            xx, yy, ww, hh, _ = map(int, stat)
            if min(ww,hh) < 30:
                break
            child = dict(candidate)
            child.update(box=[x+xx,y+yy,ww,hh], interior=(labels[yy:yy+hh,xx:xx+ww] == label).astype(np.uint8)*255,
                         geometry_evidence='ai_mask_lobes', parent_box=candidate['box'][:])
            children.append(child)
        if len(children) == 2:
            return children
    return []
