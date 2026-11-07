"""Geometry/AI balloon detection and conservative glyph-only cleaning.

No model downloads during inference, GPU or full-page background inpainting.
Unclosed, dark, textured and unrecognised regions are deliberately left alone.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import math
import re
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps

from .io import checked_mapping, read_json, write_json, validate_manifest
from .coordinates import analysis_image, project_regions, project_box, project_mask

cv2.setNumThreads(1)
MAX_PIXELS = 30_000_000
LANGUAGES = ("eng", "jpn", "jpn_vert", "chi_sim", "chi_tra", "kor")


def bubble_font_style(region):
    """Conservative shape hint; OCR-only rectangles are not balloon outlines."""
    if region.get('detector') == 'comic_text_ai':
        return 'dialogue'
    points = region.get('outline') or []
    if len(points) < 4:
        return 'dialogue'
    contour = np.asarray(points, np.int32).reshape(-1, 1, 2)
    _, _, w, h = cv2.boundingRect(contour)
    if min(w, h) < 20:
        return 'dialogue'
    area = abs(cv2.contourArea(contour))
    corners = cv2.approxPolyDP(contour, cv2.arcLength(contour, True) * .01, True)
    if area / (w * h) >= .89 and len(corners) <= 5:
        return 'box'
    try:
        simplified = cv2.approxPolyDP(contour, max(1.0, min(w, h) * .008), True)
        hull = cv2.convexHull(simplified, returnPoints=False)
        if hull is not None and len(hull) >= 3 and len(simplified) >= 5:
            defects = cv2.convexityDefects(simplified, hull)
            if defects is not None:
                deep = sum(1 for d in defects[:, 0, 3] if d / 256 >= min(w, h) * .045)
                sharp=0
                orientation=cv2.contourArea(simplified,oriented=True)
                for i in range(len(simplified)):
                    tip=simplified[i,0].astype(float)
                    a=simplified[(i-1)%len(simplified),0]-tip;b=simplified[(i+1)%len(simplified),0]-tip
                    cosine=np.dot(a,b)/max(1e-8,np.linalg.norm(a)*np.linalg.norm(b))
                    cross=float(a[0]*b[1]-a[1]*b[0])
                    if cosine>.4 and cross*orientation<0:sharp+=1
                if deep >= 4 and sharp >= 4:
                    return 'shout'
    except cv2.error:
        pass
    return 'dialogue'


class Cancelled(RuntimeError):
    pass


def check_cancel(path):
    if path and Path(path).exists():
        raise Cancelled("Đã hủy tác vụ")


def tesseract_path():
    candidates = [os.environ.get("TESSERACT_CMD"), shutil.which("tesseract"),
                  "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return candidate
    raise RuntimeError("Thiếu Tesseract. Chạy setup_macos.command --install")


def read_image(path):
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Trang vượt 30 triệu pixel; hãy chia trang manhwa dài thành nhiều phần")
        image = ImageOps.exif_transpose(image)
        if "A" in image.getbands() or "transparency" in image.info:
            rgba = image.convert("RGBA")
            base = Image.new("RGBA", rgba.size, "white")
            image = Image.alpha_composite(base, rgba)
        return np.asarray(image.convert("RGB")).copy()


def save_image(path, array):
    Image.fromarray(array).save(path)


def safe_rectangle(interior, margin=5):
    """Find an inscribed rectangle, not merely the OCR bounding box.

    Search aspect ratios around the distance-transform peak and centroid; integral
    sums verify that every pixel is inside an eroded bubble. Work on local crops.
    """
    safe = cv2.erode(interior, np.ones((margin * 2 + 1,) * 2, np.uint8),
                     borderType=cv2.BORDER_CONSTANT, borderValue=0)
    if not np.any(safe):
        return None
    dist = cv2.distanceTransform(safe, cv2.DIST_L2, 3)
    _, _, _, peak = cv2.minMaxLoc(dist)
    ys, xs = np.nonzero(safe)
    centers = [peak, (int(xs.mean()), int(ys.mean()))]
    integral = cv2.integral((safe > 0).astype(np.uint8))
    height, width = safe.shape
    best = None
    for cx, cy in centers:
        for ratio in np.linspace(.3, 3.5, 22):
            low, high = 1, max(width, height)
            while low <= high:
                half_h = (low + high) // 2
                half_w = max(1, round(half_h * ratio))
                x, y, r, b = cx - half_w, cy - half_h, cx + half_w + 1, cy + half_h + 1
                valid = x >= 0 and y >= 0 and r <= width and b <= height
                area = (r - x) * (b - y)
                if valid:
                    total = integral[b, r] - integral[y, r] - integral[b, x] + integral[y, x]
                    valid = total == area
                if valid:
                    if best is None or area > best[2] * best[3]:
                        best = [x, y, r - x, b - y]
                    low = half_h + 1
                else:
                    high = half_h - 1
    return best


def bubble_candidates(gray):
    """Connected white interiors retain closed outlines; OCR cannot invent regions."""
    white = (gray >= 220).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(white, 8)
    height, width = gray.shape
    result = []
    for label in range(1, count):
        x, y, w, h, area = map(int, stats[label])
        if min(w, h) < 30 or area < 850 or w * h > width * height * .65:
            continue
        if x <= 1 or y <= 1 or x + w >= width - 1 or y + h >= height - 1:
            continue
        if area / (w * h) < .40 or max(w / h, h / w) > 12:
            continue
        component = (labels[y:y+h, x:x+w] == label).astype(np.uint8) * 255
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        filled = np.zeros_like(component)
        cv2.drawContours(filled, [contour], -1, 255, -1)
        rect = safe_rectangle(filled, margin=max(4, min(10, round(min(w, h) * .035))))
        if not rect or min(rect[2:]) < 20:
            continue
        result.append({"box": [x, y, w, h], "interior": filled,
                       "safe": [x + rect[0], y + rect[1], rect[2], rect[3]]})
    return result


def panel_rectangles(gray):
    """High rectangularity panel borders; reject nested caption/balloon boxes."""
    contours,_ = cv2.findContours((gray < 150).astype(np.uint8)*255, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for c in contours:
        x,y,w,h=cv2.boundingRect(c); area=cv2.contourArea(c)
        # Narrow full-height panels are common in manga. Absolute width150
        # dropped them after high-resolution pages were normalized for OCR.
        if area > gray.size*.03 and w>=max(30,gray.shape[1]*.06) and h>=max(30,gray.shape[0]*.06) and area/(w*h)>.965:
            boxes.append([x,y,w,h])
    def contains(a,b):
        return b[0]>=a[0]-2 and b[1]>=a[1]-2 and b[0]+b[2]<=a[0]+a[2]+2 and b[1]+b[3]<=a[1]+a[3]+2
    # Remove a page/container only when children cover most of it.
    containers=[]
    for a in boxes:
        children=[b for b in boxes if b!=a and b[2]*b[3]<a[2]*a[3]*.9 and contains(a,b)]
        if len(children)>=2 and sum(b[2]*b[3] for b in children)>a[2]*a[3]*.75:
            containers.append(a)
    boxes=[a for a in boxes if a not in containers]
    return [a for a in boxes if not any(b!=a and b[2]*b[3]>a[2]*a[3] and contains(b,a) for b in boxes)]


def panel_order(boxes, rtl):
    """Recursive gutter cuts handle a tall panel beside multiple stacked panels."""
    if len(boxes)<2:
        return boxes
    for axis in (1,0):
        ordered=sorted(boxes,key=lambda b:b[axis]); end=ordered[0][axis]+ordered[0][axis+2]
        groups=[];group=[ordered[0]]
        for b in ordered[1:]:
            if b[axis]-end>=3:
                groups.append(group);group=[]
            group.append(b);end=max(end,b[axis]+b[axis+2])
        groups.append(group)
        if len(groups)>1:
            if axis==0 and rtl:groups.reverse()
            return [b for group in groups for b in panel_order(group,rtl)]
    return sorted(boxes,key=lambda b:(b[1],-b[0] if rtl else b[0]))


def reading_order(regions, rtl, panels=None, panels_sorted=False):
    if panels:
        ordered_panels=panels if panels_sorted else panel_order(panels,rtl); buckets=[[] for _ in ordered_panels];outside=[]
        for r in regions:
            x,y,w,h=r['box'];cx=x+w/2;cy=y+h/2
            owners=[i for i,b in enumerate(ordered_panels) if b[0]-3<=cx<=b[0]+b[2]+3 and b[1]-3<=cy<=b[1]+b[3]+3]
            if owners:buckets[min(owners,key=lambda i:ordered_panels[i][2]*ordered_panels[i][3])].append(r)
            else:outside.append(r)
        return [r for group in buckets for r in reading_order(group,rtl)]+reading_order(outside,rtl)
    """Group vertically overlapping bubbles into rows, then sort within each row."""
    rows = []
    for region in sorted(regions, key=lambda r: (r["box"][1], r["box"][0])):
        x, y, w, h = region["box"]
        target = None
        for row in rows:
            overlap = min(row["bottom"], y + h) - max(row["top"], y)
            if overlap >= .4 * min(row["bottom"] - row["top"], h):
                target = row
                break
        if target is None:
            rows.append({"top": y, "bottom": y+h, "items": [region]})
        else:
            target["items"].append(region)
            # Common overlap prevents a tall bubble merging separate rows.
            target["top"], target["bottom"] = max(target["top"], y), min(target["bottom"], y+h)
    ordered = []
    for row in sorted(rows, key=lambda r: r["top"]):
        ordered.extend(sorted(row["items"], key=lambda r: r["box"][0], reverse=rtl))
    return ordered


def ocr_words(rgb, lang, psm, timeout):
    data = pytesseract.image_to_data(Image.fromarray(rgb), lang=lang,
                                    config=f"--psm {int(psm)}", timeout=timeout,
                                    output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        conf = float(data["conf"][i])
        if text and conf >= 15:
            words.append({"text": text, "confidence": conf,
                          "box": [int(data[k][i]) for k in ("left", "top", "width", "height")]})
    return words


def region_ocr(rgb, candidate, lang, cancel=None):
    """OCR a geometry-defined interior at 2x; never expand the cleaning region."""
    x, y, w, h = candidate["box"]
    crop = rgb[y:y+h, x:x+w].copy()
    crop[candidate["interior"] == 0] = 255
    scale = min(2.0, 1600 / max(w, h))
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    crop = cv2.copyMakeBorder(crop, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=(255,255,255))
    local = ocr_words(crop, lang, 5 if "vert" in lang else 6, 8)
    for word in local:
        wx, wy, ww, wh = word["box"]
        word["box"] = [x + round((wx-12)/scale), y + round((wy-12)/scale),
                       max(1, round(ww/scale)), max(1, round(wh/scale))]
    if lang.startswith('jpn') and candidate.get('detector')=='ai_balloon':
        from .text_recovery import recover_words
        local=recover_words(rgb,candidate,local,ocr_words,lambda:check_cancel(cancel))
    return local


def japanese_bubble_ink(gray, interior):
    """Pick complete dark components inside an inset, including OCR-missed dashes.

    Components touching the protected perimeter are excluded in their entirety.
    This is gated by Japanese OCR + a closed flat-white bubble by the caller.
    """
    inner = cv2.erode(interior, np.ones((3, 3), np.uint8),
                      borderType=cv2.BORDER_CONSTANT, borderValue=0)
    dark = (gray < 220).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    mask = np.zeros_like(gray)
    for label in range(1, count):
        x, y, w, h, area = map(int, stats[label])
        if area > max(80, np.count_nonzero(inner) * .06):
            continue
        component = labels[y:y+h, x:x+w] == label
        if np.any(interior[y:y+h, x:x+w][component] == 0):
            continue
        mask[y:y+h, x:x+w][component] = 255
    return cv2.bitwise_and(cv2.dilate(mask, np.ones((3, 3), np.uint8)), inner)


def bubble_shape(candidate):
    """Outline + exact horizontal interior spans, without reducing an oval to a box."""
    x,y,w,h=candidate["box"]
    mask=candidate["interior"]
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    contour=cv2.approxPolyDP(max(contours,key=cv2.contourArea),.8,True).reshape(-1,2)
    outline=(contour+np.array([x,y])).astype(int).tolist()
    inset=max(5,min(12,round(min(w,h)*.045)))
    inner=cv2.erode(mask,np.ones((inset*2+1,)*2,np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)
    sx,sy,sw,sh=candidate["safe"];cx=min(w-1,max(0,round(sx+sw/2-x)))
    rows=[]
    for yy in range(h):
        if not inner[yy,cx]:continue
        left=right=cx
        while left>0 and inner[yy,left-1]:left-=1
        while right+1<w and inner[yy,right+1]:right+=1
        if right-left>=12:rows.append([y+yy,x+left,x+right+1])
    if not rows:return outline,None
    left=min(r[1] for r in rows);right=max(r[2] for r in rows)
    return outline,{"rows":rows,"center":[sx+sw/2,sy+sh/2],"box":[left,rows[0][0],right-left,rows[-1][0]-rows[0][0]+1]}


def cjk_region_allowed(text, confidence, touches_edge, ink_ratio, variation, fill):
    characters = re.findall(r"[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff\uac00-\ud7af]", text)
    if not characters:
        return False
    if touches_edge:
        # Rescue well-read dialogue clipped by a panel edge; retain manual warnings.
        return len(characters) >= 3 and confidence >= 70 and ink_ratio <= .30 and variation <= 10 and min(fill) >= 235
    return not (len(characters) == 1 and confidence < 70)


def clean_block_reason(manifest, region):
    """Force is a review preference, never permission to erase weak CJK/art.

    Re-evaluate legacy manifests too: a new scan is not required for the gate.
    This is a confidence/geometry guard, not a semantic face detector.
    """
    if region.get('detector') == 'comic_text_ai':
        return 'Khung AI chữ chưa phải mask nét chữ: cần clean thủ công'
    if region.get('clean_method')=='model_supported_text' and region.get('auto_clean'):
        return None  # Renderer recomputes the model agreement and head exclusion.
    lang = manifest.get('lang', '')
    cjk = any(v.startswith(('jpn', 'chi_', 'kor')) for v in lang.split('+'))
    if not cjk:
        return None
    if region.get('detector') == 'ai_balloon' and float(region.get('detector_confidence') or 0) < .9:
        return 'AI chưa đủ tin cậy: không cho ép clean'
    _, _, w, h = region['box']
    if w*h > manifest['width']*manifest['height']*.08:
        return 'Vùng lớn có thể gộp panel/nhân vật: cần clean thủ công'
    if region.get('clean_method')=='punctuation_components':
        if region.get('detector')=='ai_balloon' and float(region.get('detector_confidence') or 0)>=.9 and region.get('ocr_status')=='punctuation_geometry' and region.get('auto_clean') and not region.get('warnings'):
            return None  # Renderer independently recomputes this geometric proof.
        return 'Chưa xác nhận hình học dấu câu'
    confidence = float(region.get('confidence', 0))
    chars = re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff\uac00-\ud7af]', region.get('source', ''))
    if region.get('detector') == 'hybrid_closed_balloon':
        if confidence < 85 or len(chars) < 3 or region.get('geometry_evidence') != 'closed_white_component' or region.get('clean_method') != 'japanese_bubble_components':
            return 'Bong bóng tách cần OCR Nhật rõ và hình học khép kín'
    if confidence < 70 or (len(chars) < 3 and confidence < 85):
        return 'OCR yếu: không cho ép clean nét có thể là tranh'
    if not region.get('auto_clean') and region.get('clean_method') != 'japanese_bubble_components':
        return 'Mask chưa đủ bằng chứng chữ: cần clean thủ công'
    if not region.get('auto_clean'):
        warnings = region.get('warnings', [])
        if not warnings or any(w != 'Chữ sát viền' for w in warnings):
            return 'Nền/nét chưa xác định là chữ: không cho ép clean tranh'
    return None


def unexplained_ink_limit(candidate, text, confidence):
    """A strong learned balloon mask can admit a few OCR-missed punctuation strokes.

    This does not relax background flatness, total ink, perimeter or component gates.
    """
    chars=re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]',text)
    if candidate.get('detector')=='ai_balloon' and candidate.get('detector_confidence',0)>=.95 and confidence>=80 and len(chars)>=3:
        return .06
    return .015


def analyse(input_path, out, lang="eng", rtl=True, psm=11, cancel=None, detector='opencv', layout='opencv', detail='standard'):
    started = time.monotonic()
    check_cancel(cancel)
    if psm not in (3, 5, 6, 11, 12):
        raise ValueError("PSM được hỗ trợ: 3, 5, 6, 11, 12")
    tesseract_path()
    available = pytesseract.get_languages(config="")
    missing = [s for s in lang.split("+") if s not in available]
    if missing:
        raise ValueError("Thiếu ngôn ngữ OCR: " + ", ".join(missing))
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise FileExistsError("Thư mục đã có manifest; dùng thư mục mới để giữ mapping cũ")
    original_rgb = read_image(input_path)
    rgb = analysis_image(original_rgb,detector)
    analysis_size=[rgb.shape[1],rgb.shape[0]]
    original_size=[original_rgb.shape[1],original_rgb.shape[0]]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if detail not in ('standard', 'multiscale', 'koharu'):
        raise ValueError('Chế độ quét không hợp lệ')
    layout_tensors = None
    if detector == 'ai':
        from .balloon_ai import detect
        from .comic_text_ai import detect as detect_comic_text
        if detail == 'standard':
            text_detections=detect_comic_text(rgb)
        else:
            from .comic_text_ai import detect_multiscale
            text_detections=detect_multiscale(rgb,cancel=cancel)
        proposals = detect(rgb)
        if detail == 'koharu':
            from .model_preview import koharu_outputs, koharu_text
            layout_tensors = koharu_outputs(rgb)
            for item in koharu_text(rgb, layout_tensors):
                x,y,w,h=item['box']
                def coverage(box):
                    xx,yy,ww,hh=box
                    return max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))/max(1,min(w*h,ww*hh))
                if any(coverage(d['box'])>.35 for d in text_detections):continue
                if any(coverage(p['box'])>.9 for p in proposals):item['kind']='in_bubble'
                text_detections.append(item)
        # Replace a coarse inset AI silhouette only when an independently
        # enclosed white component agrees spatially. This restores text near
        # balloon edges without growing a rectangle into surrounding artwork.
        closed_candidates=bubble_candidates(gray)
        for proposal in proposals:
            x,y,w,h=proposal['box'];matches=[]
            for closed in closed_candidates:
                xx,yy,ww,hh=closed['box']
                overlap=max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
                iou=overlap/max(1,w*h+ww*hh-overlap)
                if iou>=.55 and ww*hh<=w*h*1.8 and ww*hh<=gray.size*.08:matches.append((iou,closed))
            if matches:
                closed=max(matches,key=lambda item:item[0])[1]
                proposal.update(box=closed['box'][:],interior=closed['interior'].copy())
        if lang.startswith('jpn'):
            from .bubble_refinement import split_closed_balloons, split_text_groups, recover_text_balloons
            proposals = split_closed_balloons(rgb, proposals)
            proposals = recover_text_balloons(rgb, proposals, text_detections)
            proposals = split_text_groups(rgb, proposals, text_detections)
        candidates = []
        for candidate in proposals:
            check_cancel(cancel)
            rect = safe_rectangle(candidate['interior'])
            if rect and min(rect[2:]) >= 20:
                x,y,_,_ = candidate['box']
                candidate['safe'] = [x+rect[0], y+rect[1], rect[2], rect[3]]
                candidates.append(candidate)
    elif detector == 'opencv':
        candidates = bubble_candidates(gray)
    else:
        raise ValueError('Detector không được hỗ trợ: '+str(detector))
    check_cancel(cancel)
    regional = any(v.startswith(("jpn", "chi_", "kor")) for v in lang.split("+"))
    words = [] if regional else ocr_words(rgb, lang, psm, 45)
    region_calls = 0
    regions = []
    ignored = len(words)
    def retain_unread(candidate, group):
        # An AI balloon is useful for mapping even when OCR misses punctuation.
        # Never invent OCR confidence or a clean mask for it.
        if candidate.get('detector') not in ('ai_balloon', 'hybrid_closed_balloon'):
            return
        outline, shape = bubble_shape(candidate)
        _,_,cw,ch = candidate['box']
        regions.append({'outline':outline, 'shape':shape, 'box':candidate['box'],
                        'safe':candidate['safe'], 'source':' '.join(g['text'] for g in group) or '[OCR chưa đọc được]',
                        'confidence':0, 'ocr_status':'unconfirmed', 'clean_method':'review_only',
                        'ocr_evidence':{'source':'tesseract','coordinate_space':'analysis_pixels','confidence_scale':'word_0_100',
                            'words':[{'text':g['text'],'confidence':g['confidence'],'box':g['box']} for g in group],
                            'mean_word_confidence':sum(g['confidence'] for g in group)/len(group) if group else None,
                            'note':'Legacy confidence=0 is a decision placeholder, not OCR evidence.'},
                        'auto_clean':False, 'fill':[255,255,255],
                        'warnings':['Chưa xác nhận được chữ gốc; chỉ giữ vùng để ghép bản dịch'],
                        'detector':candidate['detector'], 'detector_confidence':candidate['detector_confidence'],
                        '_mask':np.zeros((ch,cw),np.uint8)})
    for candidate in candidates:
        check_cancel(cancel)
        x, y, w, h = candidate["box"]
        interior = candidate["interior"]
        if lang.startswith('jpn') and candidate.get('detector_confidence',0)>=.9 and w*h<=gray.size*.08:
            from .text_recovery import punctuation_mask, outline_interior
            outline,shape=bubble_shape(candidate)
            polygon=outline_interior({'box':candidate['box'],'outline':outline})
            punctuation=punctuation_mask(rgb[y:y+h,x:x+w],polygon)
            if punctuation:
                mask,kind=punctuation
                regions.append({'box':candidate['box'],'safe':candidate['safe'],'outline':outline,'shape':shape,
                                'source':'…' if kind=='ellipsis' else kind,'confidence':0,
                                'ocr_status':'punctuation_geometry','punctuation_kind':kind,
                                'clean_method':'punctuation_components','auto_clean':True,'warnings':[],
                                'fill':[255,255,255],'detector':'ai_balloon',
                                'detector_confidence':candidate['detector_confidence'],'_mask':mask})
                continue
        group = []
        candidate_words = words
        if regional and '_words' in candidate:
            candidate_words = candidate.pop('_words')
        elif regional:
            # Bound cost and exclude large panel backgrounds from regional OCR.
            if w*h > gray.size*.16 or region_calls >= 32 or time.monotonic()-started > 90:
                retain_unread(candidate, [])
                continue
            region_calls += 1
            try:
                candidate_words = region_ocr(rgb, candidate, lang, cancel)
            except Cancelled:
                raise
            except RuntimeError:  # timed out region; retain page processing
                check_cancel(cancel)
                retain_unread(candidate, [])
                continue
        for word in candidate_words:
            wx, wy, ww, wh = word["box"]
            cx, cy = int(wx + ww / 2) - x, int(wy + wh / 2) - y
            if 0 <= cx < w and 0 <= cy < h and interior[cy, cx]:
                group.append(word)
        if not group:
            retain_unread(candidate, [])
            continue
        if lang.startswith('jpn') and region_calls <= 29 and time.monotonic()-started < 75:
            base_confidence = sum(v['confidence'] for v in group)/len(group)
            if base_confidence < 80:
                from .bubble_refinement import lobe_candidates
                children = lobe_candidates(rgb, candidate)
                confirmed = []
                for child in children:
                    check_cancel(cancel)
                    rect = safe_rectangle(child['interior'])
                    if rect is None or min(rect[2:]) < 20:
                        break
                    cx,cy,_,_ = child['box']; child['safe']=[cx+rect[0],cy+rect[1],rect[2],rect[3]]
                    region_calls += 1
                    try:
                        child_words = region_ocr(rgb, child, lang, cancel)
                    except Cancelled:
                        raise
                    except RuntimeError:
                        break
                    text = ''.join(v['text'] for v in child_words)
                    chars = re.findall(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]', text)
                    confidence = sum(v['confidence'] for v in child_words)/max(1,len(child_words))
                    if len(chars) < 3 or confidence < 85:
                        break
                    child['_words'] = child_words; confirmed.append(child)
                if len(confirmed) == 2:
                    candidates.extend(confirmed)
                    continue
        ignored -= len(group)
        inner = cv2.erode(interior, np.ones((7, 7), np.uint8),
                          borderType=cv2.BORDER_CONSTANT, borderValue=0)
        crop_gray = gray[y:y+h, x:x+w]
        glyph_mask = np.zeros((h, w), np.uint8)
        touches_edge = False
        for word in group:
            wx, wy, ww, wh = word["box"]
            left, top = max(0, wx-x-2), max(0, wy-y-2)
            right, bottom = min(w, wx-x+ww+2), min(h, wy-y+wh+2)
            if right <= left or bottom <= top:
                continue
            dark = (crop_gray[top:bottom, left:right] < 210).astype(np.uint8) * 255
            if np.any((dark > 0) & (inner[top:bottom, left:right] == 0)):
                touches_edge = True
            glyph_mask[top:bottom, left:right] |= dark
        glyph_mask = cv2.dilate(glyph_mask, np.ones((3, 3), np.uint8))
        glyph_mask = cv2.bitwise_and(glyph_mask, inner)
        pixels = rgb[y:y+h, x:x+w][(inner > 0) & (crop_gray >= 220)]
        ink_ratio = float(np.count_nonzero((crop_gray < 210) & (inner > 0)) / max(1, np.count_nonzero(inner)))
        confidence = sum(v["confidence"] for v in group) / len(group)
        color = np.median(pixels, axis=0) if len(pixels) else np.array([255, 255, 255])
        variation = float(np.max(np.std(pixels.astype(np.float32), axis=0))) if len(pixels) else 255
        # Unaccounted ink is guarded independently of flat background and model confidence.
        unexplained = np.count_nonzero((crop_gray < 210) & (inner > 0) & (glyph_mask == 0))
        unexplained_ratio = unexplained / max(1, np.count_nonzero(inner))
        reasons = []
        if touches_edge:
            reasons.append("Chữ sát viền")
        ink_limit=unexplained_ink_limit(candidate,''.join(g['text'] for g in group),confidence)
        if variation > 7 or min(color) < 235 or ink_ratio > .24 or unexplained_ratio > ink_limit:
            reasons.append("Nền/chi tiết chưa đủ tin cậy")
        if confidence < 70:
            reasons.append("OCR có độ tin cậy thấp")
        if candidate.get('detector') == 'ai_balloon' and candidate.get('detector_confidence', 1) < .9:
            reasons.append('AI chưa đủ tin cậy: cần duyệt vùng')
        if candidate.get('detector') == 'hybrid_closed_balloon' and confidence < 85:
            reasons.append('Bong bóng tách cần OCR Nhật rõ')
        if regional and w*h > gray.size*.08:
            reasons.append("Vùng lớn có thể gộp panel/nhân vật; chỉ nhận diện để duyệt")
        if not np.any(glyph_mask):
            reasons.append("Không có mặt nạ chữ")
        if regional and not cjk_region_allowed("".join(g["text"] for g in group), confidence, touches_edge, ink_ratio, variation, color):
            # CJK OCR can hallucinate letters from panel edges and illustration lines.
            retain_unread(candidate, group)
            continue
        clean_method = "ocr_boxes"
        japanese = any(v.startswith("jpn") for v in lang.split("+")) and re.search(r"[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]", "".join(g["text"] for g in group))
        if japanese and (not touches_edge or confidence >= 70) and confidence >= 45 and variation <= 7 and min(color) >= 235 and ink_ratio <= .24:
            # Component filtering may reject a large or boundary-connected glyph.
            # Do not report a successful clean if recognized ink survives the mask.
            recognized_ink = (crop_gray < 210) & (inner > 0) & (glyph_mask > 0)
            glyph_mask = japanese_bubble_ink(crop_gray, interior)
            clean_method = "japanese_bubble_components"
            if np.any(recognized_ink & (glyph_mask == 0)):
                reasons.append('Mask chưa phủ hết chữ đã nhận diện')
            if candidate.get('detector') == 'hybrid_closed_balloon' and confidence >= 85:
                # The independently closed white contour supplies a complete
                # component mask; OCR boxes may miss a dash or an entire glyph.
                ink = (crop_gray < 210) & (inner > 0)
                if np.any(ink) and not np.any(ink & (glyph_mask == 0)):
                    reasons = [reason for reason in reasons if reason != 'Nền/chi tiết chưa đủ tin cậy']
            # Retain prior warnings: additional ink may still need manual review.
            if candidate.get('detector_confidence',0)>=.95 and confidence>=85:
                ink=(crop_gray<210)&(interior>0)
                if np.any(ink) and not np.any(ink&(glyph_mask==0)):
                    reasons=[reason for reason in reasons if reason!='Chữ sát viền']
        outline, shape = bubble_shape(candidate)
        regions.append({"outline": outline, "shape": shape, "box": candidate["box"], "safe": candidate["safe"],
                        "source": " ".join(g["text"] for g in group),
                        'detector': candidate.get('detector', 'opencv'),
                        'detector_confidence': candidate.get('detector_confidence'),
                        'geometry_evidence': candidate.get('geometry_evidence'),
                        'parent_box': candidate.get('parent_box'),
                        'ocr_method': group[0].get('ocr_pass','base'),
                        "confidence": round(confidence, 1), "clean_method": clean_method, "auto_clean": not reasons,
                        "warnings": reasons, "fill": color.astype(int).tolist(),
                        "_mask": glyph_mask})
    extra_text_count = 0
    if detector == 'ai':
        from .comic_text_ai import detect as detect_comic_text, uncovered_regions
        check_cancel(cancel)
        extra = uncovered_regions(text_detections, regions)
        extra_text_count = len(extra)
        regions.extend(extra)
        proof_manifest={'lang':lang,'width':rgb.shape[1],'height':rgb.shape[0]}
        unresolved=[r for r in regions if r.get('detector')=='ai_balloon' and
                    (not r.get('auto_clean') or clean_block_reason(proof_manifest,r))]
        if unresolved:
            from .model_preview import ctd_mask
            from .head_protection import detect as detect_heads
            from .balloon_clean import supported_mask
            pixel_mask=ctd_mask(rgb);heads=detect_heads(rgb)
            proof_detections=detect_comic_text(rgb)
            for region in unresolved:
                proof=supported_mask(rgb,region,pixel_mask,proof_detections,heads)
                if proof is not None:
                    region.update(_mask=proof,clean_method='model_supported_text',auto_clean=True,warnings=[],fill=[255,255,255])
    if layout not in ('opencv','koharu','magi'):raise ValueError('Model bố cục không hợp lệ')
    if layout=='koharu':
        from .model_preview import koharu_panels, koharu_mask, koharu_outputs, MODELS
        tensors=layout_tensors if layout_tensors is not None else koharu_outputs(rgb)
        panels=koharu_panels(rgb,tensors)
        # Reuse only when both operations see the identical pixels. Large AI
        # scans use a reduced image, so they deliberately take the old path.
        if analysis_size==original_size:
            import hashlib
            cached_mask=koharu_mask(rgb,tensors)
            np.savez_compressed(out/'koharu_mask_cache.npz', mask=cached_mask,
                image_digest=hashlib.sha256(rgb.tobytes()).hexdigest(),
                mask_digest=hashlib.sha256(cached_mask.tobytes()).hexdigest(),
                model_digest=MODELS['koharu'][1])
    elif layout=='magi':
        from .magi_layout import panels as magi_panels
        panels=magi_panels(rgb)
    else:panels = panel_rectangles(gray) if detector == 'ai' else []
    regions = reading_order(regions, rtl, panels, panels_sorted=layout=='magi' and rtl)
    project_regions(regions,analysis_size,original_size)
    panels=[project_box(box,analysis_size,original_size) for box in panels]
    preview = original_rgb.copy()
    preview_scale=max(1,max(original_size)/1440)
    masks = out / "masks"
    masks.mkdir(exist_ok=True)
    for index, region in enumerate(regions, 1):
        region["id"] = f"B{index:03d}"
        region['bubble_font_style'] = bubble_font_style(region)
        save_image(masks / (region["id"] + ".png"), region.pop("_mask"))
        x, y, w, h = region["box"]
        sx, sy, sw, sh = region["safe"]
        color = (0, 160, 70) if region["auto_clean"] else (230, 120, 0)
        cv2.polylines(preview, [np.array(region["outline"],np.int32)], True, color, round(2*preview_scale))
        cv2.putText(preview, region["id"], (x, max(18, y-5)), cv2.FONT_HERSHEY_SIMPLEX, .6*preview_scale, color, round(2*preview_scale))
    save_image(out / "original.png", original_rgb)
    save_image(out / "preview.png", preview)
    # A small thumbnail keeps ScriptUI previews cheap even for tall pages.
    thumb = Image.fromarray(preview)
    thumb.thumbnail((440, 520))
    thumb.save(out / "preview_small.png")
    manifest = {"schema": 1, "input": str(Path(input_path).resolve()), "width": original_size[0],
                "height": original_size[1], 'analysis_size':analysis_size, 'detection_detail':detail, "lang": lang, "rtl": bool(rtl), "regions": regions,
                "ignored_words": max(0, ignored), "seconds": round(time.monotonic()-started, 3),
                "mapping": [], 'detector': detector, 'panels': panels,
                'extra_text_regions': extra_text_count,'layout_model':layout}
    if detector=='ai':
        from .hardware import runtime_info, SESSION_REPORTS
        manifest['hardware']={'profile':runtime_info(),'sessions':dict(SESSION_REPORTS)}
    write_json(out / "manifest.json", manifest)
    return {"manifest": str(out / "manifest.json"), **manifest}


def render_clean(manifest_path, mapping, cancel=None, preview=False):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    manifest = validate_manifest(read_json(manifest_path))
    mapping = checked_mapping(manifest, mapping)
    selected = {v["id"] for v in mapping if v["clean"]}
    forced = {v["id"] for v in mapping if v["clean"] and v["force"]}
    rgb = read_image(root / "original.png")
    if rgb.shape[:2] != (manifest["height"], manifest["width"]):
        raise ValueError("Ảnh gốc không khớp kích thước manifest")
    overlay = np.zeros((*rgb.shape[:2], 4), np.uint8)
    applied, skipped, blocked, skip_reason_codes = [], [], {}, {}
    proof_rgb=None
    model_proof=None
    for region in manifest["regions"]:
        check_cancel(cancel)
        if region["id"] not in selected:
            continue
        reason = clean_block_reason(manifest, region)
        if reason:
            skipped.append(region['id'])
            blocked[region['id']] = reason
            skip_reason_codes[region['id']] = 'SAFETY_GATE_REJECTED'
            continue
        mask_path = root / "masks" / (region["id"] + ".png")
        if (not region["auto_clean"] and region["id"] not in forced) or not mask_path.is_file():
            skipped.append(region["id"])
            if not region['auto_clean'] and region['id'] not in forced:
                warnings = region.get('warnings') or []
                detail = '; '.join(map(str, warnings)) if isinstance(warnings, list) else str(warnings)
                blocked[region['id']] = 'Chưa được phép clean tự động' + (': ' + detail if detail else '')
                skip_reason_codes[region['id']] = 'AUTO_CLEAN_DISABLED_REVIEW'
            else:
                blocked[region['id']] = 'Thiếu file mask chữ: cần clean thủ công'
                skip_reason_codes[region['id']] = 'TEXT_MASK_FILE_MISSING'
            continue
        x, y, w, h = region["box"]
        with Image.open(mask_path) as image:
            mask = np.array(image.convert("L"))
        if mask.shape != (h, w):
            raise ValueError("Mask không khớp kích thước vùng: " + region["id"])
        if not np.any(mask):
            skipped.append(region['id'])
            blocked[region['id']] = 'Mask rỗng: chưa xóa được chữ, cần clean thủ công'
            skip_reason_codes[region['id']] = 'TEXT_MASK_EMPTY'
            continue
        if region.get('clean_method')=='model_supported_text':
            from .balloon_clean import supported_mask
            from .model_preview import ctd_mask
            from .comic_text_ai import detect as detect_text
            from .head_protection import detect as detect_heads
            size=manifest.get('analysis_size',[manifest['width'],manifest['height']])
            if proof_rgb is None:proof_rgb=cv2.resize(rgb,tuple(size),interpolation=cv2.INTER_AREA)
            if model_proof is None:model_proof=(ctd_mask(proof_rgb),detect_text(proof_rgb),detect_heads(proof_rgb))
            geometry=region.get('analysis_geometry',region)
            proof=supported_mask(proof_rgb,geometry,*model_proof)
            expected=project_mask(proof,region['box']) if proof is not None else None
            if (project_box(geometry['box'],size,[manifest['width'],manifest['height']])!=region['box'] or
                expected is None or not np.array_equal(mask,expected)):
                skipped.append(region['id']);blocked[region['id']]='Không xác minh được mask chữ và vùng bảo vệ mặt';continue
        if region.get('detector') == 'hybrid_closed_balloon':
            from .bubble_refinement import closed_interior
            geometry = region.get('analysis_geometry', region)
            size = manifest.get('analysis_size', [manifest['width'], manifest['height']])
            if project_box(geometry['box'], size, [manifest['width'], manifest['height']]) != region['box']:
                skipped.append(region['id']); blocked[region['id']] = 'Tọa độ bong bóng tách không khớp'; continue
            if proof_rgb is None:
                proof_rgb = cv2.resize(rgb, tuple(size), interpolation=cv2.INTER_AREA)
            interior = closed_interior(proof_rgb, geometry['box'])
            gx, gy, gw, gh = geometry['box']
            expected = None if interior is None else japanese_bubble_ink(
                cv2.cvtColor(proof_rgb[gy:gy+gh, gx:gx+gw], cv2.COLOR_RGB2GRAY), interior)
            if expected is None or not np.array_equal(mask, project_mask(expected, region['box'])):
                skipped.append(region['id']); blocked[region['id']] = 'Không xác minh được viền/mask bong bóng tách'; continue
        if region.get('clean_method')=='punctuation_components':
            from .text_recovery import punctuation_mask, outline_interior
            geometry=region.get('analysis_geometry',region)
            size=manifest.get('analysis_size',[manifest['width'],manifest['height']])
            if region.get('analysis_geometry'):
                if project_box(geometry['box'],size,[manifest['width'],manifest['height']])!=region['box']:
                    skipped.append(region['id']);blocked[region['id']]='Tọa độ mask dấu câu không khớp';continue
                if proof_rgb is None:proof_rgb=cv2.resize(rgb,tuple(size),interpolation=cv2.INTER_AREA)
                gx,gy,gw,gh=geometry['box'];crop=proof_rgb[gy:gy+gh,gx:gx+gw]
            else:crop=rgb[y:y+h,x:x+w]
            polygon=outline_interior(geometry)
            proof=punctuation_mask(crop,polygon) if polygon is not None else None
            expected=project_mask(proof[0],region['box']) if proof is not None else None
            if proof is None or proof[1]!=region.get('punctuation_kind') or not np.array_equal(mask,expected):
                skipped.append(region['id']);blocked[region['id']]='Mask dấu câu không khớp kiểm tra pixel';continue
        patch = overlay[y:y+h, x:x+w]
        patch[mask > 0, :3] = region["fill"]
        patch[mask > 0, 3] = 255
        applied.append(region["id"])
    cleaned = rgb.copy()
    cleaned[overlay[:, :, 3] > 0] = overlay[:, :, :3][overlay[:, :, 3] > 0]
    for region_id in skipped:
        skip_reason_codes.setdefault(region_id, 'MASK_PROOF_REJECTED')
    prefix = "trial_" if preview else ""
    save_image(root / (prefix + "clean_overlay.png"), overlay)
    save_image(root / (prefix + "clean.png"), cleaned)
    if not preview:
        manifest["mapping"] = mapping
        manifest["clean_ids"] = applied
        manifest['clean_policy_version'] = 2
        manifest['clean_blocked'] = blocked
        manifest['clean_skip_reason_codes'] = skip_reason_codes
        write_json(manifest_path, manifest)
    thumb = Image.fromarray(cleaned)
    thumb.thumbnail((440, 520))
    thumb.save(root / (prefix + "clean_small.png"))
    return {"overlay": str(root / (prefix + "clean_overlay.png")), "preview": str(root / (prefix + "clean_small.png")), "applied": applied, "skipped": skipped, "blocked": blocked, "skip_reason_codes": skip_reason_codes,
            "manifest": str(manifest_path)}


def preview_review(data, folder, selected=None):
    """Render current reviewed order without committing edits to the manifest."""
    import uuid
    validate_manifest(data)
    root = Path(folder)
    image = read_image(root / "original.png")
    if image.shape[:2] != (data["height"], data["width"]):
        raise ValueError("Kích thước preview không khớp")
    scale=max(1,max(data['width'],data['height'])/1440)
    for index, region in enumerate(data["regions"], 1):
        x, y, w, h = region["safe"]
        color = (240,40,40) if region["id"] == selected else (0,120,230)
        if region.get("outline"):
            cv2.polylines(image,[np.array(region["outline"],np.int32)],True,color,round((4 if region["id"] == selected else 2)*scale))
        else:
            cv2.rectangle(image,(x,y),(x+w-1,y+h-1),color,round(2*scale))
        cv2.putText(image, str(index)+":"+region["id"], (x,max(18,y-4)), cv2.FONT_HERSHEY_SIMPLEX,.5*scale,(230,60,0),round(scale))
    thumb=Image.fromarray(image)
    thumb.thumbnail((440,520))
    path=root/("review_"+uuid.uuid4().hex[:8]+".png")
    thumb.save(path)
    return {"preview":str(path.resolve())}
