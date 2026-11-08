"""Normalize OCR without inventing speaker attribution or OCR confidence."""
import hashlib
import uuid

SENTINELS = frozenset(('[OCR chưa đọc được]', '[AI tìm thấy chữ — cần kiểm tra]', 'Vùng thủ công'))


def revision(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalize(manifest, page_id):
    result = []
    for order, region in enumerate(manifest['regions']):
        text = region.get('source', '')
        if not isinstance(text, str):
            raise ValueError('Invalid OCR source')
        blocked = not text.strip() or text.strip() in SENTINELS
        box = region.get('box')
        owners = []
        if isinstance(box, list) and len(box) == 4:
            cx, cy = box[0] + box[2]/2, box[1] + box[3]/2
            for idx, panel in enumerate(manifest.get('panels') or []):
                if len(panel)==4 and panel[0]-3 <= cx <= panel[0]+panel[2]+3 and panel[1]-3 <= cy <= panel[1]+panel[3]+3:
                    owners.append((panel[2]*panel[3],idx))
        panel_index = min(owners)[1] if owners else None
        result.append({'id': 'seg_' + uuid.uuid4().hex,
                       'page_id': page_id, 'region_id': region['id'], 'order': order,
                       'panel_id': str(page_id) + ':panel_' + str(panel_index+1) if panel_index is not None else None,
                       'panel_status': 'predicted' if panel_index is not None else 'unknown',
                       'raw_ocr': text, 'jp': None if blocked else text, 'source_revision': revision(text),
                       'source_status': 'blocked_source' if blocked else 'unreviewed',
                       'ocr_evidence': {'origin': 'geometry' if region.get('ocr_status') == 'punctuation_geometry' else ('tesseract' if region.get('ocr_method') or (region.get('ocr_evidence') or {}).get('source') == 'tesseract' else 'unknown'),
                           'method': region.get('ocr_method'),
                           'confidence': None if region.get('ocr_status') == 'punctuation_geometry' else ((region.get('ocr_evidence') or {}).get('mean_word_confidence') if region.get('ocr_status') == 'unconfirmed' else region.get('confidence')),
                           'confidence_scale': 'tesseract_word_mean_0_100',
                           'warnings': list(region.get('warnings') or [])},
                       'speaker': {'status': 'unknown', 'candidate': None},
                       'addressee': {'status': 'unknown', 'candidate': None}})
    return result
