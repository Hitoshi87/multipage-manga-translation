"""Review report for a finished volume run: what the machine did and what a person should look at.

Written for non-technical users: one HTML page, plain Vietnamese, traffic-light status per page,
and a card for each bubble that needs a look (cropped image, the lettered text and why it was
flagged). Pages and items are ordered by how likely they need a fix, so a quick pass through the
top of the list covers the real problems.
"""
import base64
import io
import json
from html import escape
from pathlib import Path

from .io import read_json
from .translation import service

# Reasons in plain language, grouped by how urgently a person should act.
FIX, LOOK, NOTE = 'fix', 'look', 'note'
REASONS = {
    'page_failed': (FIX, 'Trang này chưa làm xong (lỗi khi xử lý)'),
    'clean_skipped': (FIX, 'Chưa xoá được chữ gốc ở bong bóng này'),
    'manual_text': (FIX, 'Chữ đang ẩn, cần xoá chữ gốc bằng tay'),
    'layout_fallback': (FIX, 'Chữ không vừa khung nên đang đặt tạm'),
    'geometry_clipped': (LOOK, 'Vùng xoá vượt lòng bong bóng; phần vượt đã được giữ lại, cần kiểm tra chữ sót'),
    'lettering_needs_review': (LOOK, 'Có đề xuất rút gọn cần đối chiếu nghĩa trước khi dùng'),
    'merged_suspect': (FIX, 'Nghi hai bong bóng bị gộp thành một'),
    'not_translated': (FIX, 'Chưa có bản dịch cho vùng này'),
    'clean_single_layer': (LOOK, 'Phần xoá chữ của trang này nằm chung một layer, không tách theo từng bong bóng'),
    'art_inpaint': (LOOK, 'Máy vẽ lại nền, hãy nhìn xem có tự nhiên không'),
    'contrast': (LOOK, 'Chữ trên nền tranh, kiểm tra viền chữ có đọc được'),
    'ocr_suspect': (LOOK, 'Máy có thể đọc sai chữ Nhật'),
    'needs_review': (NOTE, 'Máy chưa chắc bản dịch'),
    'speaker_unclear': (LOOK, 'Chưa rõ ai nói với ai (cách xưng hô)'),
    'ambiguous_reference': (NOTE, 'Câu có chỗ mơ hồ'),
    'glossary_conflict': (LOOK, 'Tên hoặc thuật ngữ chưa thống nhất'),
    'japanese_left': (LOOK, 'Còn chữ Nhật trong bản dịch'),
    'odd_symbols': (LOOK, 'Có ký hiệu lạ'),
    'dash_added': (NOTE, 'Có dấu gạch dài không có trong bản gốc'),
    'long_for_bubble': (NOTE, 'Câu khá dài so với bong bóng'),
    'leading_ellipsis': (NOTE, 'Câu mở đầu bằng dấu …'),
    'ellipsis_heavy': (NOTE, 'Có nhiều dấu … trong một câu'),
}
STATUS_LABEL = {'ok': 'ỔN', 'look': 'XEM LẠI', 'fix': 'CẦN SỬA'}


def reason_text(code):
    return REASONS.get(code, (LOOK, code))[1]


def severity(codes):
    """fix > look > note > ok. A note never makes a page "worth a look" by itself."""
    levels = [REASONS.get(c, (LOOK, ''))[0] for c in codes]
    for level in (FIX, LOOK, NOTE):
        if level in levels:
            return level
    return 'ok'


def collect_items(log, texts):
    """Flatten a draft log into per-bubble items and per-page statuses."""
    items, pages = [], []
    for page in log.get('pages', []):
        pid = page['page']
        if page.get('status') == 'failed':
            pages.append({'page': pid, 'status': FIX, 'reasons': ['page_failed'], 'detail': page.get('error', '')})
            items.append({'page': pid, 'region': None, 'codes': ['page_failed'], 'severity': FIX, 'detail': page.get('error', '')})
            continue
        per = {}

        def add(region, code):
            per.setdefault(region, [])
            if code not in per[region]:
                per[region].append(code)
        for region in page.get('clean_skipped', []):
            add(region, 'clean_skipped')
        for region in page.get('manual_text', []):
            add(region, 'manual_text')
        for region in page.get('geometry_clipped', {}):
            add(region, 'geometry_clipped')
        for entry in page.get('layout_fallback', []):
            add(entry['id'] if isinstance(entry, dict) else entry, 'layout_fallback')
        for region in page.get('art_inpaint_review', []):
            add(region, 'art_inpaint')
        for region in page.get('contrast_review', []):
            add(region, 'contrast')
        segments = {}
        for entry in page.get('review', []):
            region = entry.get('region_id')
            segments[region] = entry.get('segment_id')
            for flag in entry.get('flags', []):
                add(region, flag)
            for code in entry.get('qa_warnings', []):
                add(region, code)
            if entry.get('merged_suspect'):
                add(region, 'merged_suspect')
        mapped_regions = {e.get('region_id') for e in page.get('review', [])}
        if page.get('required', 0) > page.get('mapped', 0):
            add(None, 'not_translated')
        # Cleaned bubbles but no per-bubble clean layers: the page fell back to a single overlay layer.
        if page.get('clean_applied', 0) > 0 and page.get('clean_layers', 1) == 0:
            add(None, 'clean_single_layer')
        codes_all = sorted({c for codes in per.values() for c in codes}, key=lambda c: REASONS.get(c, (LOOK, ''))[0])
        page_level = severity(codes_all)
        pages.append({'page': pid, 'status': 'ok' if page_level == NOTE else page_level, 'reasons': codes_all, 'detail': ''})
        for region, codes in per.items():
            sev = severity(codes)
            if sev == 'ok':
                continue
            items.append({'page': pid, 'region': region, 'codes': codes, 'severity': sev, 'files': page.get('files', {}),
                          'segment_id': segments.get(region), 'manifest': page.get('manifest'),
                          **texts.get((pid, region), {})})
    order = {FIX: 0, LOOK: 1, NOTE: 2}
    items.sort(key=lambda i: (order.get(i['severity'], 2), i['page'], str(i['region'])))
    return items, pages


def summarise(pages, items):
    counts = {'ok': 0, 'look': 0, 'fix': 0}
    for p in pages:
        counts[p['status']] += 1
    return {'pages': len(pages), 'ok': counts['ok'], 'look': counts['look'], 'fix': counts['fix'],
            'items_fix': sum(1 for i in items if i['severity'] == FIX), 'items_look': sum(1 for i in items if i['severity'] == LOOK),
            'items_note': sum(1 for i in items if i['severity'] == NOTE)}


def _texts(project):
    state = service.load(project)
    rows = {}
    if state['runs']:
        for g in state['runs'][-1]['groups']:
            for v in g['results']:
                rows[v['id']] = (v.get('lettering_translation') if v.get('lettering_status') == 'human_approved' else None) or v['semantic_translation']
    out = {}
    for page in state['pages']:
        for s in page['segments']:
            out[(page['page_id'], s['region_id'])] = {'jp': s.get('jp') or '', 'vi': rows.get(s['id'], ''),
                                                      'manifest': page['manifest'], 'box': s.get('box')}
    return out


def _thumb(manifest, box, size=260):
    try:
        from PIL import Image
        image_path = Path(manifest).parent / 'original.png'
        if not box or not image_path.is_file():
            return ''
        x, y, w, h = box
        with Image.open(image_path) as image:
            pad = 12
            crop = image.convert('RGB').crop((max(0, x - pad), max(0, y - pad), x + w + pad, y + h + pad))
        crop.thumbnail((size, size))
        buffer = io.BytesIO()
        crop.save(buffer, 'JPEG', quality=70)
        return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return ''


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#5b6675;--line:#dde2ea;--ok:#1f8a4c;--look:#b7791f;--fix:#c53030}
@media (prefers-color-scheme:dark){:root{--bg:#14181e;--card:#1d232c;--ink:#e8ecf2;--mute:#9aa6b5;--line:#2c3541;--ok:#4cc38a;--look:#e0a64a;--fix:#ff7a7a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,'Segoe UI',sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:32px 0 12px}
.sub{color:var(--mute);margin:0 0 20px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}.stat b{display:block;font-size:1.9rem;line-height:1.1}
.stat.ok b{color:var(--ok)}.stat.look b{color:var(--look)}.stat.fix b{color:var(--fix)}
.item{display:grid;grid-template-columns:150px 1fr;gap:14px;background:var(--card);border:1px solid var(--line);border-left:5px solid var(--look);border-radius:12px;padding:12px;margin:0 0 12px}
.item.fix{border-left-color:var(--fix)}.item img{width:150px;border-radius:8px;border:1px solid var(--line);background:#fff}
.item .noimg{width:150px;height:90px;border-radius:8px;border:1px dashed var(--line)}
.where{font-weight:600}.vi{font-size:1.1rem;margin:6px 0}.jp{color:var(--mute);font-size:.9rem}
.chip{display:inline-block;font-size:.8rem;padding:2px 9px;border-radius:99px;border:1px solid var(--line);margin:2px 4px 2px 0}
.chip.fix{border-color:var(--fix);color:var(--fix)}.chip.look{border-color:var(--look);color:var(--look)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
td,th{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:.95rem}th{color:var(--mute);font-weight:600}
.pill{font-weight:700;font-size:.8rem}.pill.ok{color:var(--ok)}.pill.look{color:var(--look)}.pill.fix{color:var(--fix)}
.hint{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;color:var(--mute)}
@media (max-width:560px){.item{grid-template-columns:1fr}}
"""


def render_html(title, summary, pages, items, notes=None):
    parts = ['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{escape(title)}</title><style>{CSS}</style><main>',
             f'<h1>{escape(title)}</h1><p class="sub">Máy đã làm xong. Bạn chỉ cần xem các mục bên dưới, theo thứ tự quan trọng.</p>',
             '<div class="cards">']
    for key, label in (('pages', 'Tổng số trang'), ('ok', 'Trang ổn'), ('look', 'Trang nên xem lại'), ('fix', 'Trang cần sửa')):
        cls = key if key in ('ok', 'look', 'fix') else ''
        parts.append(f'<div class="stat {cls}"><b>{summary[key]}</b>{label}</div>')
    parts.append('</div>')
    for line in notes or []:
        parts.append(f'<p class="hint">{escape(line)}</p>')
    for severity_key, heading in ((FIX, 'Cần sửa trước'), (LOOK, 'Nên nhìn qua')):
        group = [i for i in items if i['severity'] == severity_key]
        if not group:
            continue
        parts.append(f'<h2>{heading} ({len(group)})</h2>')
        for item in group:
            where = f"Trang {escape(item['page'])}" + (f" · bong bóng {escape(str(item['region']))}" if item['region'] else '')
            chips = ''.join(f'<span class="chip {REASONS.get(c, (LOOK, ""))[0]}">{escape(reason_text(c))}</span>' for c in item['codes'])
            image = f'<img alt="" src="{item["thumb"]}">' if item.get('thumb') else '<div class="noimg"></div>'
            vi = f'<div class="vi">{escape(item["vi"])}</div>' if item.get('vi') else ''
            jp = f'<div class="jp">Gốc: {escape(item["jp"])}</div>' if item.get('jp') else ''
            detail = f'<div class="jp">{escape(item["detail"])}</div>' if item.get('detail') else ''
            hint = (f'<div class="jp">Trong Photoshop: tìm layer có tên <b>{escape(str(item["region"]))}</b></div>' if item['region'] else '')
            parts.append(f'<div class="item {severity_key}">{image}<div><div class="where">{where}</div>{chips}{vi}{jp}{detail}{hint}</div></div>')
    notes_group = [i for i in items if i['severity'] == NOTE]
    if notes_group:
        parts.append(f'<h2>Ghi chú nhẹ ({len(notes_group)}), không cần làm gì nếu bạn thấy ổn</h2><div class="hint">')
        for item in notes_group:
            where = f"Trang {escape(item['page'])}" + (f" · {escape(str(item['region']))}" if item['region'] else '')
            why = '; '.join(reason_text(c) for c in item['codes'])
            line = f' — {escape(item["vi"])}' if item.get('vi') else ''
            parts.append(f'<div><b>{where}</b>: {escape(why)}{line}</div>')
        parts.append('</div>')
    parts.append('<h2>Tất cả các trang</h2><table><tr><th>Trang</th><th>Tình trạng</th><th>Ghi chú</th></tr>')
    for page in pages:
        notes_text = '; '.join(reason_text(c) for c in page['reasons'][:3])
        parts.append(f'<tr><td>{escape(page["page"])}</td><td><span class="pill {page["status"]}">{STATUS_LABEL[page["status"]]}</span></td>'
                     f'<td>{escape(notes_text or "Không có gì cần làm")}</td></tr>')
    parts.append('</table></main></html>')
    return ''.join(parts)


def build_report(project, log_path, out_path=None, title='Báo cáo dịch truyện'):
    """Create the HTML report next to the draft log and return its path and a summary."""
    log = read_json(log_path)
    texts = _texts(project)
    items, pages = collect_items(log, texts)
    for item in items:
        info = texts.get((item['page'], item['region']))
        item['thumb'] = _thumb(info['manifest'], info['box']) if info else ''
    summary = summarise(pages, items)
    notes = []
    if log.get('auto_excluded'):
        notes.append(f"Máy đã tự bỏ qua {log['auto_excluded']} vùng không phải thoại (banner, tựa, bản quyền, chữ ngoài bong bóng).")
    sizes = [p['pdf_mb'] for p in log.get('pages', []) if isinstance(p.get('pdf_mb'), (int, float))]
    if sizes:
        average = sum(sizes) / len(sizes)
        line = f"Dung lượng PDF: trung bình {average:.1f} MB mỗi trang, lớn nhất {max(sizes):.1f} MB, tổng {sum(sizes):.0f} MB."
        if average > 25:
            line += " PDF giữ layer nhúng cả PSD nên nặng; chọn kiểu PDF Phẳng, hoặc đặt Màu xuất là RGB hay giữ nguyên thay vì CMYK, trong tab Tự động để nhẹ hơn."
        notes.append(line)
    if log.get('translation_failures'):
        notes.append(f"{len(log['translation_failures'])} nhóm câu dịch lỗi nhiều lần; những câu đó chưa có bản dịch.")
    out = Path(out_path) if out_path else Path(log_path).with_name('BAO_CAO.html')
    out.write_text(render_html(title, summary, pages, items, notes), encoding='utf8')
    return {'html': str(out), 'summary': summary}


# --- Review queue for the in-Photoshop quick review dialog -------------------------------------

def _item_key(item):
    return f"{item['page']}|{item['region']}"


def load_state(state_path):
    try:
        data = json.loads(Path(state_path).read_text(encoding='utf8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def mark_reviewed(state_path, keys, status='done'):
    """Remember which items a person has dealt with; returns how many items are now marked."""
    if status not in ('done', 'open'):
        raise ValueError('Trạng thái không hợp lệ')
    state = load_state(state_path)
    for key in keys:
        if status == 'done':
            state[key] = 'done'
        else:
            state.pop(key, None)
    Path(state_path).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf8')
    return len(state)


def review_queue(project, log_path, state_path=None):
    """Items still to review, most urgent first, in plain language for the review dialog."""
    log = read_json(log_path)
    items, _pages = collect_items(log, _texts(project))
    done = load_state(state_path) if state_path else {}
    queue = []
    for item in items:
        if item['severity'] == NOTE:
            continue
        key = _item_key(item)
        queue.append({'key': key, 'page': item['page'], 'region': item['region'], 'severity': item['severity'],
                      'codes': item['codes'], 'reasons': [reason_text(c) for c in item['codes']],
                      'vi': item.get('vi', ''), 'jp': item.get('jp', ''), 'segment_id': item.get('segment_id'),
                      'manifest': item.get('manifest'), 'file': (item.get('files') or {}).get('pdf') or (item.get('files') or {}).get('psd'),
                      'psd': (item.get('files') or {}).get('psd'),
                      'done': done.get(key) == 'done'})
    return {'run_id': log.get('run_id'), 'project': log.get('project') or str(project),
            'open': sum(1 for q in queue if not q['done']), 'items': queue}
