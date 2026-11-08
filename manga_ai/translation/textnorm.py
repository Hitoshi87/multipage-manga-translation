"""Display-time normalisation of Vietnamese lettering text.

The saved translation is never changed; these rules only shape what is lettered
(see normalizeText in scripts/core.jsxinc, kept in step by tests/fixtures/textnorm_cases.json).

Rules follow common Vietnamese scanlation practice:
 - plain symbols only (Japanese brackets and decorative marks are not drawable by comic fonts)
 - at most one ellipsis per bubble (at the end, or after a short interjection); never leading
 - a leading ellipsis may be moved to the end of the previous, unfinished bubble
 - capitalise the first letter of every bubble and of each sentence
"""
import re

ELLIPSIS = '…'
_RUN = re.compile('[.…]{2,}')
_LEADING = re.compile('^[\\s“‘(—–-]*' + ELLIPSIS + '+\\s*')
_SPACED_DASH = re.compile('(?<=\\S)\\s[—–]\\s(?=\\S)')
_BEFORE_PUNCT = re.compile('\\s+([,.!?;:' + ELLIPSIS + '])')
_LETTER = re.compile('[^\\W\\d_]', re.UNICODE)


def normalize_symbols(text):
    t = str(text)
    t = re.sub('[「『]', '“', t)
    t = re.sub('[」』]', '”', t)
    t = t.replace('！', '!').replace('？', '?')
    t = re.sub('[♡♥♪♫]+', '~', t)
    t = re.sub('[★☆]+', '', t)
    t = re.sub('([^\\s(“‘])“', '\\1 “', t)
    t = re.sub('”([^\\s.,!?' + ELLIPSIS + ';:)”’])', '” \\1', t)
    return t


def _tidy_ellipses(text):
    t = _RUN.sub(ELLIPSIS, text)
    t = _LEADING.sub('', t)
    marks = [m.start() for m in re.finditer(ELLIPSIS, t)]
    if len(marks) <= 1:
        return t
    keep = set()
    stripped = t.rstrip(' !?”’)')
    if stripped.endswith(ELLIPSIS):
        keep.add(len(stripped) - 1)
    elif t.rstrip().endswith(ELLIPSIS):
        keep.add(len(t.rstrip()) - 1)
    # An interjection such as "Ơ…" at the start may keep its ellipsis.
    first = re.match('^\\W*([^\\W\\d_]{1,3})' + ELLIPSIS, t)
    if first:
        keep.add(first.end() - 1)
    out = []
    for i, ch in enumerate(t):
        if ch == ELLIPSIS and i not in keep:
            out.append(',')
        else:
            out.append(ch)
    t = ''.join(out)
    return re.sub(',(\\s*,)+', ',', t)


def _capitalise(text):
    out = []
    new_sentence = True
    for i, ch in enumerate(text):
        if _LETTER.match(ch):
            out.append(ch.upper() if new_sentence else ch)
            new_sentence = False
        else:
            out.append(ch)
            if ch in '.!?':
                nxt = text[i + 1] if i + 1 < len(text) else ' '
                if nxt.isspace() or nxt in '”’)':
                    new_sentence = True
            elif ch.isdigit():
                new_sentence = False
    return ''.join(out)


def normalize_text(text, case='sentence'):
    """case: 'sentence' (capitalise), 'upper' (ALL CAPS font workflow) or 'keep'."""
    t = normalize_symbols(text)
    t = re.sub('[ \\t]+', ' ', t).strip()
    t = _SPACED_DASH.sub(', ', t)
    t = _tidy_ellipses(t)
    t = _BEFORE_PUNCT.sub('\\1', t)
    t = re.sub(',(\\s*,)+', ',', t).strip()
    if case == 'upper':
        return t.upper()
    if case == 'sentence':
        return _capitalise(t)
    return t


def normalize_page(texts, case='sentence'):
    """Normalise bubbles in reading order, moving a leading ellipsis to the previous unfinished bubble."""
    items = [str(t) for t in texts]
    for i in range(1, len(items)):
        if _LEADING.match(items[i]):
            items[i] = _LEADING.sub('', items[i])
            prev = items[i - 1].rstrip()
            if prev.endswith(','):
                items[i - 1] = prev[:-1] + ELLIPSIS
            elif prev and prev[-1] not in '.!?' + ELLIPSION + ':;”’)':
                items[i - 1] = prev + ELLIPSIS
    return [normalize_text(t, case) for t in items]


ELLIPSION = ELLIPSIS
