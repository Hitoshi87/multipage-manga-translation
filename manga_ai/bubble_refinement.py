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


def split_vertical_text_groups(rgb, candidates, detections):
    """Split offset stacked lobes only across an ink-free interior band.

    This deliberately handles two strongly supported, vertically separated
    text blocks with shifted horizontal centers; ordinary aligned paragraphs
    and overlapping glyphs remain a single reviewable region.
    """
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);result=[]
    for parent in candidates:
        x,y,w,h=parent['box'];groups=[]
        for d in detections:
            if d['kind']!='in_bubble' or d['confidence']<.9:continue
            tx,ty,tw,th=d['box']
            overlap=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
            if overlap/(tw*th)>=.9:groups.append(d['box'])
        if len(groups)!=2:result.append(parent);continue
        groups.sort(key=lambda b:b[1]);a,b=groups
        if (a[1]+a[3]/2>=b[1]+b[3]/2 or abs((a[0]+a[2]/2)-(b[0]+b[2]/2))<w*.20
                or b[1]-(a[1]+a[3]) < -max(5,round(h*.03))):
            result.append(parent);continue
        low=max(1,a[1]+a[3]-y-15);high=min(h-1,b[1]-y+15)
        if high<=low:result.append(parent);continue
        inside=parent['interior']>0;ink=(gray[y:y+h,x:x+w]<210)&inside
        midpoint=(a[1]+a[3]+b[1])/2-y
        cuts=[v for v in range(low,high) if not np.any(ink[max(0,v-1):min(h,v+2)])]
        cuts=[v for v in cuts if (v+y-a[1])/a[3]>.85 and (b[1]+b[3]-(v+y))/b[3]>.85]
        if not cuts:result.append(parent);continue
        cut=min(cuts,key=lambda c:abs(c-midpoint));children=[]
        for top,bottom in ((0,cut),(cut,h)):
            mask=parent['interior'][top:bottom,:].copy()
            if bottom-top<30 or cv2.countNonZero(mask)<500:break
            child=dict(parent);child.update(box=[x,y+top,w,bottom-top],interior=mask,
                geometry_evidence='vertical_text_groups_whitespace',parent_box=parent['box'][:])
            children.append(child)
        result.extend(children if len(children)==2 else [parent])
    return result


def split_text_groups_watershed(rgb, candidates, detections, max_neck=.6):
    """Split chained balloons holding 2-8 text groups, in any arrangement.

    One marker per confident text group, watershed on the interior distance
    transform. A boundary is accepted only when it is a narrow neck relative to
    both neighbouring basins and carries no ink; otherwise the two basins are
    merged again. Any doubt keeps the parent as one reviewable region.
    """
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);result=[]
    for parent in candidates:
        if parent.get('parent_box'):result.append(parent);continue
        x,y,w,h=parent['box'];boxes=[]
        for d in detections:
            if d['kind']!='in_bubble' or d['confidence']<.9:continue
            tx,ty,tw,th=d['box']
            overlap=max(0,min(x+w,tx+tw)-max(x,tx))*max(0,min(y+h,ty+th)-max(y,ty))
            if overlap/max(1,tw*th)>=.9:boxes.append(d['box'])
        if not 2<=len(boxes)<=8:result.append(parent);continue
        children=_watershed_children(gray,parent,boxes,max_neck)
        result.extend(children if children else [parent])
    return result


def _watershed_children(gray, parent, boxes, max_neck):
    x,y,w,h=parent['box'];inside=(parent['interior']>0).astype(np.uint8)
    dist=cv2.distanceTransform(inside,cv2.DIST_L2,5);n=len(boxes)
    markers=np.zeros((h,w),np.int32)
    for i,(tx,ty,tw,th) in enumerate(boxes,1):
        # Marker is the core of the text box that lies inside the balloon.
        x0=max(0,tx-x+tw//4);x1=min(w,tx-x+tw-tw//4);y0=max(0,ty-y+th//4);y1=min(h,ty-y+th-th//4)
        core=inside[y0:y1,x0:x1]>0
        if x1<=x0 or y1<=y0 or not core.any() or np.any(markers[y0:y1,x0:x1][core]):return None
        markers[y0:y1,x0:x1][core]=i
    markers[inside==0]=n+1
    surface=(255-np.clip(dist/max(dist.max(),1)*255,0,255)).astype(np.uint8)
    labels=cv2.watershed(cv2.merge([surface]*3),markers)
    ink=(gray[y:y+h,x:x+w]<210)
    parent_of=list(range(n+2))
    def find(a):
        while parent_of[a]!=a:parent_of[a]=parent_of[parent_of[a]];a=parent_of[a]
        return a
    line=(labels==-1)&(inside>0)
    for a in range(1,n+1):
        for b in range(a+1,n+1):
            near_a=cv2.dilate((labels==a).astype(np.uint8),np.ones((3,3),np.uint8))>0
            near_b=cv2.dilate((labels==b).astype(np.uint8),np.ones((3,3),np.uint8))>0
            cut=line&near_a&near_b
            if not cut.any():continue
            # Watershed lines can be several pixels thick; use their span.
            ys,xs=np.nonzero(cut);length=max(cv2.minAreaRect(np.column_stack([xs,ys]).astype(np.float32))[1])
            reach=min(dist[labels==a].max(),dist[labels==b].max())*2
            neck=length/max(reach,1);inked=ink[cut].mean()
            if neck>=max_neck or inked>.05:parent_of[find(b)]=find(a)
    groups={}
    for i in range(1,n+1):groups.setdefault(find(i),[]).append(i)
    if len(groups)<2:return None
    # Boundary pixels go to the nearest basin so children tile the balloon.
    masks=[np.isin(labels,members)&(inside>0)&(labels>0) for members in groups.values()]
    owner=np.argmin(np.stack([cv2.distanceTransform((~m).astype(np.uint8),cv2.DIST_L2,3) for m in masks]),axis=0)
    children=[]
    for k in range(len(masks)):
        mask=((owner==k)&(inside>0)).astype(np.uint8)*255
        ys,xs=np.nonzero(mask)
        if not len(xs):return None
        left,right,top,bottom=xs.min(),xs.max()+1,ys.min(),ys.max()+1
        if right-left<20 or bottom-top<20 or cv2.countNonZero(mask)<500:return None
        child=dict(parent);child.update(box=[x+int(left),y+int(top),int(right-left),int(bottom-top)],
            interior=mask[top:bottom,left:right].copy(),geometry_evidence='watershed_text_groups',
            parent_box=parent['box'][:])
        children.append(child)
    children.sort(key=lambda c:(c['box'][1],c['box'][0]))
    return children


def confident_text_boxes(parent, detections, confidence=.9):
    """Text-group boxes (>=confidence) that lie inside the parent's box."""
    x, y, w, h = parent['box']
    boxes = []
    for d in detections:
        if d['kind'] != 'in_bubble' or d['confidence'] < confidence:
            continue
        tx, ty, tw, th = d['box']
        overlap = max(0, min(x + w, tx + tw) - max(x, tx)) * max(0, min(y + h, ty + th) - max(y, ty))
        if overlap / max(1, tw * th) >= .9:
            boxes.append(d['box'])
    return boxes


def _separator_cuts(gray, parent, boxes, axis, dark=110, cover=.7, max_thickness=9):
    """Cut positions (relative to the parent box) across one axis, or None.

    A cut is a straight dark stroke between two consecutive text groups that
    covers most of the balloon width (axis 'y') or height (axis 'x').
    """
    x, y, w, h = parent['box']
    inside = parent['interior'] > 0
    order = sorted(boxes, key=lambda b: b[1] if axis == 'y' else b[0])
    cuts = []
    for a, b in zip(order, order[1:]):
        a_end = (a[1] + a[3] - y) if axis == 'y' else (a[0] + a[2] - x)
        b_start = (b[1] - y) if axis == 'y' else (b[0] - x)
        if b_start - a_end < 3:
            return None
        lo, hi = max(0, a_end), min(h if axis == 'y' else w, b_start)
        scores = []
        for v in range(lo, hi):
            if axis == 'y':
                # Span of the mask around this row: the stroke itself may be outside the mask.
                near = inside[max(0, v - 4):min(h, v + 5), :]
                cols = np.flatnonzero(near.any(axis=0))
                if not len(cols):
                    scores.append(0)
                    continue
                left, right = cols[0], cols[-1] + 1
                line = gray[y + v, x + left:x + right]
            else:
                near = inside[:, max(0, v - 4):min(w, v + 5)]
                rows = np.flatnonzero(near.any(axis=1))
                if not len(rows):
                    scores.append(0)
                    continue
                top, bottom = rows[0], rows[-1] + 1
                line = gray[y + top:y + bottom, x + v]
            scores.append(float(np.mean(line < dark)) if len(line) else 0.0)
        runs, start = [], None
        for i, sc in enumerate(scores + [0]):
            if sc >= cover and start is None:
                start = i
            elif sc < cover and start is not None:
                runs.append((start, i))
                start = None
        runs = [r for r in runs if r[1] - r[0] <= max_thickness]
        if not runs:
            return None
        best = max(runs, key=lambda r: sum(scores[r[0]:r[1]]))
        cuts.append((lo + best[0], lo + best[1]))
    return cuts


def split_text_groups_separator(rgb, candidates, detections):
    """Split adjacent boxes that share one straight ink line (no neck to cut).

    Two or more confident text groups, all separated along the same axis by a
    dark stroke spanning most of the balloon, become one region per group.
    Anything uncertain keeps the parent as a single reviewable region.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    result = []
    for parent in candidates:
        if parent.get('parent_box'):
            result.append(parent)
            continue
        boxes = confident_text_boxes(parent, detections)
        if not 2 <= len(boxes) <= 8:
            result.append(parent)
            continue
        children = None
        for axis in ('y', 'x'):
            cuts = _separator_cuts(gray, parent, boxes, axis)
            if cuts is None:
                continue
            children = _slice_by_cuts(parent, boxes, cuts, axis)
            if children:
                break
        result.extend(children if children else [parent])
    return result


def _slice_by_cuts(parent, boxes, cuts, axis):
    x, y, w, h = parent['box']
    size = h if axis == 'y' else w
    edges = [0] + [c for cut in cuts for c in cut] + [size]
    spans = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
    children = []
    for lo, hi in spans:
        mask = parent['interior'].copy()
        if axis == 'y':
            mask[:lo, :] = 0
            mask[hi:, :] = 0
        else:
            mask[:, :lo] = 0
            mask[:, hi:] = 0
        ys, xs = np.nonzero(mask)
        if not len(xs) or hi - lo < 20 or cv2.countNonZero(mask) < 500:
            return None
        left, right, top, bottom = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        # Each child must hold exactly one text group.
        held = 0
        for b in boxes:
            cx, cy = b[0] + b[2] / 2 - x, b[1] + b[3] / 2 - y
            if left <= cx < right and top <= cy < bottom:
                held += 1
        if held != 1:
            return None
        child = dict(parent)
        child.update(box=[x + int(left), y + int(top), int(right - left), int(bottom - top)],
                     interior=mask[top:bottom, left:right].copy(),
                     geometry_evidence='separator_line', parent_box=parent['box'][:])
        children.append(child)
    return children


def mark_merged_suspects(candidates, detections):
    """Flag regions still holding several text groups after every splitter ran."""
    for candidate in candidates:
        n = len(confident_text_boxes(candidate, detections))
        if n >= 2 and not candidate.get('parent_box'):
            candidate['merged_suspect'] = n
    return candidates


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
    # Lobes may be split again: a chain of 3+ joined bubbles needs nested cuts.
    if candidate.get('geometry_evidence') not in (None, 'ai_mask_lobes') or candidate.get('detector') != 'ai_balloon':
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
