"""Python mirror of the lettering planner in scripts/core.jsxinc.

Photoshop does the real typesetting; this module reproduces the planner so that
fit can be estimated without Photoshop (auto-shorten, QA, previews). The two
implementations are kept in step by tests/test_layout_plan_parity.py.
"""
import math
import re

FUNCTION_WORDS = frozenset(('và', 'của', 'với', 'cho', 'từ', 'để', 'về', 'là', 'một', 'các', 'những', 'tự'))
SMOOTHING = (.97, .94, .91, .88, .85, .82, .79, .76, .73, .70, .67, .64, .61, .58)
_OPEN = re.compile('[“‘(]')
_CLOSE = re.compile('[”’)]')
_OPEN_END = re.compile('[“‘(]$')
_HYPHEN_SPLIT = re.compile(
    r'^([^\s\u2013\u2014-]*[A-Za-z\u00c0-\u024f\u1e00-\u1eff]{2,}[\u2013\u2014-])([A-Za-z\u00c0-\u024f\u1e00-\u1eff]{2,}[^\s\u2013\u2014-]*)$'
    r'|^([^\s\u2013\u2014-]*[A-Za-z\u00c0-\u024f\u1e00-\u1eff]{2,})([\u2013\u2014-]{2,}[.!?\u2026\u201d\u2019)]*)$'
)


def _tokenize_paragraph(p):
    raw = p.strip().split() or ['']
    tokens, glue = [], []
    for w in raw:
        m = _HYPHEN_SPLIT.match(w)
        if m:
            tokens.append(m.group(1) or m.group(3))
            glue.append(True)
            tokens.append(m.group(2) or m.group(4))
            glue.append(False)
        else:
            tokens.append(w)
            glue.append(False)
    return tokens, glue


def wrap_scored(paragraphs, widths, measure):
    """Line breaking with a readability cost; returns (cost, lines) or None."""
    words, glues = [], []
    for p in paragraphs:
        ws, gs = _tokenize_paragraph(p)
        words.append(ws)
        glues.append(gs)
    opened = []
    for ws in words:
        depth = 0
        row = [0]
        for w in ws:
            depth += len(_OPEN.findall(w)) - len(_CLOSE.findall(w))
            row.append(max(0, depth))
        opened.append(row)
    memo = {}

    def solve(row, par, start):
        if row == len(widths):
            return (0, []) if par == len(words) else None
        if par >= len(words) or widths[row] <= 0:
            return None
        key = (row, par, start)
        if key in memo:
            return memo[key]
        best = None
        content = ''
        for end in range(start, len(words[par])):
            sep = '' if (end == start or glues[par][end - 1]) else ' '
            content += sep + words[par][end]
            width = measure(content)
            if width > widths[row]:
                break
            nxt = end + 1 == len(words[par])
            tail = solve(row + 1, par + 1 if nxt else par, 0 if nxt else end + 1)
            if not tail:
                continue
            cost = tail[0] + ((widths[row] - width) / widths[row]) ** 2
            raw = words[par][end]
            last = raw.lower().rstrip('.,!?;:…')
            if not nxt:
                if glues[par][end]:
                    cost += .25
                if last in FUNCTION_WORDS:
                    cost += .35
                if _OPEN_END.search(raw):
                    cost += 2
                if raw in ('…', '...'):
                    cost += 1
                if opened[par][end + 1] > 0:
                    cost += .4
            if end == start and len(words[par]) > 1:
                bare = re.sub('[“”‘’"()]', '', last)
                cost += .5 if len(bare) <= 3 else .08
            if best is None or cost < best[0]:
                best = (cost, [content] + tail[1])
        memo[key] = best
        return best

    return solve(0, 0, 0)


def plan_layout(shape, paragraphs, unit_width, ref_ratio, o):
    """Largest readable size for `paragraphs` inside `shape` (rows of [y, left, right])."""
    rows = {r[0]: r for r in shape['rows']}
    area = sum(r[2] - r[1] for r in shape['rows'])
    max_width = max(r[2] - r[1] for r in shape['rows'])
    cx0, cy0 = shape['center']
    body = [r[0] for r in shape['rows'] if r[2] - r[1] >= max_width * .5]
    if body:
        cy0 = (min(body) + max(body) + 1) / 2
    weights = [(r, r[2] - r[1]) for r in shape['rows'] if r[2] - r[1] >= max_width * .5]
    if weights:
        cx0 = sum((r[1] + r[2]) / 2 * w for r, w in weights) / sum(w for _, w in weights)
    bw, bh = shape['box'][2], shape['box'][3]

    def span(top, bottom):
        lo, hi = math.floor(top), math.ceil(bottom)
        left, right = -math.inf, math.inf
        if hi <= lo:
            return None
        for y in range(lo, hi):
            r = rows.get(y)
            if not r:
                return None
            left = max(left, r[1])
            right = min(right, r[2])
        return (left, right) if right > left else None

    total = sum(unit_width(p.strip()) for p in paragraphs)
    step_y = max(1, bh * .01)
    shifts = sorted((b * step_y for b in range(-3, 4)), key=abs)
    leading = o['leading']

    def try_at(size, n, dy):
        rh = ref_ratio * size
        lead = size * leading
        acc = o.get('accRatio', ref_ratio * .78) * size
        cap = o.get('capRatio', ref_ratio * .56) * size
        top0 = cy0 + dy - acc - (n - 1) * lead / 2 + cap / 2
        spans, widths = [], []
        total_width = 0
        for row in range(n):
            sp = span(top0 + row * lead, top0 + row * lead + rh)
            if not sp or sp[1] - sp[0] - 4 <= 0:
                return None
            spans.append(sp)
            widths.append(sp[1] - sp[0] - 4)
            total_width += widths[-1]
        wrapped = wrap_scored(paragraphs, widths, lambda t: unit_width(t) * size if t else 0)
        if not wrapped:
            return None
        lines = wrapped[1]
        used = 0
        lo, hi = -math.inf, math.inf
        for row, line in enumerate(lines):
            w = unit_width(line) * size
            used += w
            lo = max(lo, spans[row][0] + 2 + w / 2)
            hi = min(hi, spans[row][1] - 2 - w / 2)
        if lo > hi:
            return None
        axis = min(hi, max(lo, cx0))
        if abs(axis - cx0) > .05 * bw:
            return None
        fill = used * rh / max(1, area)
        sparse = o.get('fillWeight', 5) * max(0, o.get('fillTarget', .38) - fill)
        quality = (wrapped[0] / 2.5 + 3 * abs(axis - cx0) / max(1, bw) + 3 * abs(dy) / max(1, bh) + sparse)
        return {'size': size, 'lines': lines, 'dx': axis - cx0, 'dy': dy, 'axis': axis, 'cy': cy0 + dy,
                'top': top0, 'baseline': top0 + acc, 'rh': rh, 'lead': lead, 'usage': used / total_width,
                'quality': quality, 'fill': fill}

    def feasible(size):
        lead = size * leading
        max_lines = min(24, math.floor(bh / lead) + 1)
        nmin = max(1, math.floor(total * size / max(1, bw)))
        for dy in shifts:
            best = None
            for n in range(nmin, min(max_lines, nmin + max(4, math.ceil(nmin * .6))) + 1):
                if o.get('lineCount') and n != o['lineCount']:
                    continue
                c = try_at(size, n, dy)
                if c and (best is None or c['quality'] < best['quality']):
                    best = c
            if best:
                return best
        return None

    best = feasible(o['min'])
    if not best:
        return None
    top = feasible(o['max'])
    if top:
        best = top
    else:
        low, high = o['min'], o['max']
        while high - low >= .5:
            mid = (low + high) / 2
            r = feasible(mid)
            if r:
                best, low = r, mid
            else:
                high = mid
    fit = best
    best_score = best['quality']
    for factor in SMOOTHING:
        size = fit['size'] * factor
        if size < o['min']:
            break
        alt = feasible(size)
        if alt:
            score = alt['quality'] + 1.2 * (1 - factor)
            if score < best_score:
                best, best_score = alt, score
    if not o.get('_boosted') and o.get('sparseBoost', 0) > 1 and best['fill'] < o.get('sparseFill', 0):
        o2 = dict(o, max=o['max'] * o['sparseBoost'], _boosted=True)
        bigger = plan_layout(shape, paragraphs, unit_width, ref_ratio, o2)
        if bigger and bigger['size'] > best['size'] and bigger['fill'] > best['fill']:
            best = bigger
    return best


def page_size_cap(sizes, factor, min_size):
    """Lower median x factor, never below the minimum size."""
    if not sizes:
        return None
    ordered = sorted(sizes)
    return max(min_size, factor * ordered[(len(ordered) - 1) // 2])


class FontMeasure:
    """Width/metrics from a TrueType font via Pillow, normalised to size 1."""

    def __init__(self, path, reference=100):
        from PIL import ImageFont
        self.font = ImageFont.truetype(str(path), reference)
        self.reference = reference
        self.cache = {}
        box = self.font.getbbox('ẤỮộgj')
        self.ref_ratio = (box[3] - box[1]) / reference
        base = self.font.getbbox('x', anchor='ls')[3]
        self.acc_ratio = -self.font.getbbox('Ấ', anchor='ls')[1] / reference
        self.cap_ratio = -self.font.getbbox('H', anchor='ls')[1] / reference
        self.baseline = base

    def unit(self, text):
        if text not in self.cache:
            self.cache[text] = self.font.getlength(text) / self.reference
        return self.cache[text]

    def options(self, **extra):
        return dict({'accRatio': self.acc_ratio, 'capRatio': self.cap_ratio}, **extra)


def rect_shape(box):
    x, y, w, h = box
    return {'box': list(box), 'center': [x + w / 2, y + h / 2],
            'rows': [[yy, x, x + w] for yy in range(int(math.floor(y)), int(math.ceil(y + h)))]}
