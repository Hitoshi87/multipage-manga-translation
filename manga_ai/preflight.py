"""Preflight for a long run: try a few pages first, then decide whether the full run is worth starting.

A 200-page run takes hours. If the machine is too timid to clean ordinary bubbles, or cannot
read or translate them, the person finds out only when they come back. A short sample run
scores what the pipeline actually did and returns one of three decisions:

  go        the sample worked; start the full volume
  escalate  cleaning is weak with the standard engine; retry the sample with the AI redraw engine
  stop      even the best engine does poorly (or the API/OCR failed); explain before wasting hours

Thresholds are heuristics chosen to catch clearly poor runs, not to grade quality.
"""
AI_ENGINE = 'art_draft'
CLEAN_MIN, TRANSLATE_MIN, LETTER_MIN = .80, .90, .85
FAIL_MAX = .34                       # at most about a third of the sample pages may fail outright


def pick_sample_pages(count, k=3):
    """Indices of sample pages spread through the volume (about 25%, 50%, 75%)."""
    if count <= k:
        return list(range(count))
    return sorted({min(count - 1, round(count * f)) for f in (.25, .5, .75)[:k]})


def scorecard(pages):
    """Rates over the sample pages; `pages` use the same shape as the draft log entries."""
    required = mapped = clean_bad = letter_bad = 0
    failed = 0
    for p in pages:
        if p.get('status') == 'failed':
            failed += 1
            continue
        required += p.get('required', 0)
        got = p.get('mapped', 0)
        mapped += got
        clean_bad += len(p.get('clean_skipped', []))
        letter_bad += len(p.get('layout_fallback', [])) + len(p.get('manual_text', []))
    ok_pages = len(pages) - failed
    rate = lambda num, den: (num / den) if den else 0.0
    return {'pages': len(pages), 'failed_pages': failed, 'required': required, 'translated': mapped,
            'translate_rate': rate(mapped, required),
            'clean_rate': rate(max(0, mapped - clean_bad), mapped),
            'letter_rate': rate(max(0, mapped - letter_bad), mapped),
            'page_fail_rate': rate(failed, len(pages)) if pages else 1.0, 'ok_pages': ok_pages}


def percent(x):
    return f'{round(x * 100)}%'


def decide(card, engine, escalated=False):
    """Return {'action','message','next_engine','problems'} for a scorecard."""
    problems = []
    if card['pages'] == 0 or card['ok_pages'] == 0:
        return {'action': 'stop', 'next_engine': None, 'problems': ['no_page'],
                'message': 'Cả 3 trang thử đều lỗi, nên chưa thể chạy cả tập. Kiểm tra lỗi ở báo cáo thử rồi thử lại.'}
    if card['page_fail_rate'] > FAIL_MAX:
        problems.append('pages_failed')
    if card['translate_rate'] < TRANSLATE_MIN:
        problems.append('translate_low')
    if card['clean_rate'] < CLEAN_MIN:
        problems.append('clean_low')
    if card['letter_rate'] < LETTER_MIN:
        problems.append('letter_low')
    if not problems:
        return {'action': 'go', 'next_engine': engine, 'problems': [],
                'message': f"Bản chạy thử ổn: xoá được {percent(card['clean_rate'])} bong bóng, dịch {percent(card['translate_rate'])}, "
                           f"chèn chữ vừa {percent(card['letter_rate'])}. Bắt đầu chạy cả tập."}
    if 'translate_low' in problems and card['translate_rate'] < .5:
        return {'action': 'stop', 'next_engine': None, 'problems': problems,
                'message': f"Chỉ dịch được {percent(card['translate_rate'])} số câu. Thường do chưa có API key, API lỗi, hoặc máy không đọc được chữ "
                           "trong truyện. Hãy kiểm tra các mục đó trước khi chạy cả tập."}
    if problems == ['clean_low'] or ('clean_low' in problems and engine != AI_ENGINE and not escalated):
        if engine != AI_ENGINE and not escalated:
            return {'action': 'escalate', 'next_engine': AI_ENGINE, 'problems': problems,
                    'message': f"Engine thường chỉ xoá được {percent(card['clean_rate'])} bong bóng. Mình thử lại bằng engine AI vẽ lại nền "
                               "(các chỗ vẽ lại sẽ được đánh dấu để bạn xem)."}
    if 'pages_failed' in problems or card['clean_rate'] < .5 or card['letter_rate'] < .5:
        return {'action': 'stop', 'next_engine': None, 'problems': problems,
                'message': f"Kết quả chạy thử còn kém (xoá {percent(card['clean_rate'])}, dịch {percent(card['translate_rate'])}, "
                           f"chèn chữ vừa {percent(card['letter_rate'])}, {card['failed_pages']} trang lỗi). Chạy cả tập lúc này sẽ tốn thời gian mà "
                           "phải làm lại. Hãy xem báo cáo thử để biết truyện này khó ở đâu."}
    return {'action': 'go', 'next_engine': engine, 'problems': problems,
            'message': f"Chạy thử tạm chấp nhận được (xoá {percent(card['clean_rate'])}, dịch {percent(card['translate_rate'])}, "
                       f"chèn chữ vừa {percent(card['letter_rate'])}). Một phần bong bóng sẽ được đánh dấu để bạn rà soát. Bắt đầu chạy cả tập."}
