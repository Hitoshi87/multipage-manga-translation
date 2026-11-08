"""Deterministic checks. Passing these checks does not establish translation quality."""
import json
import re
from collections import Counter

PLACEHOLDER = re.compile(r'\{\{[^{}]+\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%\([^)]+\)[a-zA-Z]|%[0-9]*\$?[sdif]|<[^<>]+>')
JAPANESE = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]')
MAX_LENGTH_RATIO = 4.0
# Symbols that scanlation lettering does not use or that comic fonts cannot draw.
ODD_SYMBOLS = re.compile(
    r'[*_`#|<>\\\[\]{}\u2661\u2665\u266a\u266b\u2605\u2606\u2192\u2740\u2764\u300c\u300d\u300e\u300f\uff01-\uff5e]'
    r'|[\U0001F300-\U0001FAFF\u2600-\u27BF]|\.{4,}|\u2026\.+|[^\W\d_]/[^\W\d_]|\((?:TN|Note|lit\.)[^)]*\)', re.I)
DASH_IN_TEXT = re.compile(r'[\u2014\u2013]|\s-\s|--')
DASH_IN_SOURCE = re.compile(r'[\u2015\u2500\u2014\u2013\uff0d-]')
FLAGS = frozenset(('ocr_suspect', 'speaker_unclear', 'ambiguous_reference', 'glossary_conflict', 'needs_review'))


def validate_response(raw, targets):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('Empty translation response')
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid translation JSON') from exc
    if not isinstance(obj, dict) or set(obj) != {'translations'} or not isinstance(obj['translations'], list):
        raise ValueError('Invalid translation schema')
    expected = [s['id'] for s in targets]
    if len(expected) != len(set(expected)):
        raise ValueError('Duplicate target IDs')
    rows = obj['translations']
    if any(not isinstance(r, dict) or not {'id', 'vi', 'flags'}.issubset(r) or set(r)-{'id','vi','flags','source_evidence'} or not isinstance(r['id'], str)
           or not isinstance(r['vi'], str) or not r['vi'].strip() or not isinstance(r['flags'], list)
           or any(not isinstance(f, str) or f not in FLAGS for f in r['flags']) for r in rows):
        raise ValueError('Invalid translation entry')
    if [r['id'] for r in rows] != expected:
        raise ValueError('Target IDs missing, duplicated, unexpected or out of order')
    for target, row in zip(targets, rows):
        if Counter(PLACEHOLDER.findall(target['jp'])) != Counter(PLACEHOLDER.findall(row['vi'])):
            raise ValueError('Placeholder or markup mismatch: ' + target['id'])
        if 'source_evidence' in row:
            evidence=row['source_evidence']
            valid=isinstance(evidence,dict) and 'main_text' in evidence and not (set(evidence)-{'main_text','furigana'})
            if valid:
                readings=evidence.get('furigana',[]);main=evidence['main_text']
                valid=isinstance(main,str) and bool(main.strip()) and len(main)<=4000 and isinstance(readings,list) and len(readings)<=32
                if valid:
                    for item in readings:
                        if not isinstance(item,dict) or set(item)!={'base','reading'} or not isinstance(item['base'],str) or not item['base'].strip() or item['base'] not in main or len(item['base'])>80 or not isinstance(item['reading'],str) or not item['reading'].strip() or len(item['reading'])>80:
                            valid=False;break
            if valid:evidence['furigana']=readings
            else:
                # The optional vision observation can fail independently of a
                # structurally valid translation. Keep the draft, flag review.
                row.pop('source_evidence');row['_source_evidence_error']='invalid_visual_evidence'
                for flag in ('ocr_suspect','needs_review'):
                    if flag not in row['flags']:row['flags'].append(flag)
    for target, row in zip(targets, rows):
        warnings = qa_warnings(target['jp'], row['vi'])
        if warnings:
            row['_qa_warnings'] = warnings
            if 'japanese_left' in warnings and 'needs_review' not in row['flags']:
                row['flags'].append('needs_review')
    return rows


def qa_warnings(source, text):
    """Deterministic hints for review; they do not judge translation quality."""
    result = []
    if JAPANESE.search(text):
        result.append('japanese_left')
    # Very short interjections inflate the ratio, so require some source text.
    if DASH_IN_TEXT.search(text) and not DASH_IN_SOURCE.search(source):
        result.append('dash_added')
    if ODD_SYMBOLS.search(text):
        result.append('odd_symbols')
    stripped = text.strip()
    if stripped[:1] in ('\u2026', '.') and re.match(r'^(\u2026|\.{2,})', stripped):
        result.append('leading_ellipsis')
    if len(re.findall(r'\u2026|\.{3}', text)) > 1:
        result.append('ellipsis_heavy')
    if len(source.strip()) >= 3 and len(text.strip()) / len(source.strip()) > MAX_LENGTH_RATIO:
        result.append('long_for_bubble')
    return result
