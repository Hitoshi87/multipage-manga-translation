"""Bounded dialogue continuity and deterministic lettering cleanup."""
import re

HONORIFIC = re.compile(r'(?<=[^\W\d_])\s*[-\u2010-\u2015\u2212\uff0d]\s*'
                       r'(?:senpai|sensei|sama|chan|dono|san|kun)(?!\w)', re.I)
PROTECTED = re.compile(r'\{\{[^{}]+\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%\([^)]+\)[a-zA-Z]|%[0-9]*\$?[sdif]|<[^<>]+>')
ADDRESS = re.compile(r'\b(?:tôi|tớ|tao|mày|mình|bạn|anh|chị|em|cậu|ông|bà|thầy|cô|chú|bác|con|cháu)\b', re.I)


def strip_honorifics(text):
    """Dashes only; do not remove Vietnamese words or edit placeholders."""
    spans = [m.span() for m in PROTECTED.finditer(text)]
    removed = 0
    def replace(match):
        nonlocal removed
        if any(match.start() < end and match.end() > start for start, end in spans):
            return match.group()
        removed += 1
        return ''
    return HONORIFIC.sub(replace, text), removed


def prior_translations(run, group):
    """Earlier completed snapshots only; unverified dialogue is not canon."""
    prior = {}
    for previous in run.get('groups', []):
        if previous['id'] == group['id']:
            break
        if previous.get('status') != 'completed':
            continue
        targets = {t['id']: t for t in previous.get('targets', [])}
        for row in previous.get('results', []):
            target = targets.get(row['id'])
            if target and isinstance(row.get('semantic_translation'), str):
                prior[row['id']] = (target, row)
    result = []
    for context in group.get('context', []):
        if context['id'] not in prior:
            continue
        target, row = prior[context['id']]
        if any(row.get(k) != context.get(k) or target.get(k) != context.get(k)
               for k in ('source_revision', 'segment_version')):
            continue
        result.append({'id':context['id'], 'page_id':context.get('page_id'), 'jp':context['jp'],
                       'vi':row['semantic_translation'], 'status':row.get('status', 'needs_review'),
                       'flags':row.get('flags', []), 'speaker':{'status':'unknown'}, 'addressee':{'status':'unknown'}})
    return result


def adds_address_terms(old, new):
    return bool({m.group().casefold() for m in ADDRESS.finditer(new)} -
                {m.group().casefold() for m in ADDRESS.finditer(old)})
