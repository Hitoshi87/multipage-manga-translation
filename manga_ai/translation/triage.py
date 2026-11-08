"""Deterministic triage: keep text that is not conversation out of translation.

Banners, series titles, copyright lines, page numbers and text found outside any
balloon never reach the model (saving tokens) or the lettering step (nothing to
draw into). The rules are conservative: the classifier only excludes when the
region type or the exact wording says so, never on a guess about meaning.

Exclusion is reversible and recorded on the segment. A person who restores a
segment is never overridden again, and verified or hand-corrected sources are
never touched.
"""
import re

from ..io import read_json
from . import service

BANNER_WORDS = frozenset((
    '新連載', '連載', '連載開始', '読切', '読み切り', '最終回', 'つづく', '続く', '次号', '次回', '次回予告', '予告',
    '巻頭カラー', 'センターカラー', '新章', '完', '終', '終わり', 'おわり', 'END', 'end', 'To be continued'))
COPYRIGHT_MARKERS = ('この物語はフィクション', 'この作品はフィクション', 'フィクションであり', '実在の人物', '無断転載',
                     '著作権', '©', 'Ⓒ')
_STRIP = re.compile('^[\\s　・…「」『』()（）\\[\\]【】.。,、!！-]+|[\\s　・…「」『』()（）\\[\\]【】.。,、!！-]+$')
_DIGITS = re.compile('^[\\d０-９\\s　\\-ー・]{1,4}$')
EDGE = .04                       # a page number sits in the outer 4% of the page height
HUMAN_STATES = ('verified', 'user_corrected', 'excluded')


def classify_non_dialogue(segment, region, page_width=None, page_height=None):
    """Return a reason string when the segment is not conversation text, else None."""
    text = (segment.get('jp') or '').strip()
    detector = (region or {}).get('detector')
    if region and detector == 'comic_text_ai' and region.get('clean_method') == 'review_only':
        return 'outside_bubble'
    if not text:
        return None
    core = _STRIP.sub('', text)
    if core in BANNER_WORDS:
        return 'banner'
    if any(marker in text for marker in COPYRIGHT_MARKERS):
        return 'copyright'
    if _DIGITS.match(text) and region and page_height and detector != 'ai_balloon':
        cy = region['box'][1] + region['box'][3] / 2
        if cy < EDGE * page_height or cy > (1 - EDGE) * page_height:
            return 'page_number'
    return None


def _run_in_progress(state):
    return bool(state['runs']) and any(g['status'] == 'completed' for g in state['runs'][-1]['groups'])


def auto_exclude(path, dry_run=False):
    """Mark non-dialogue segments as excluded. Returns what was (or would be) excluded."""
    state = service.load(path)
    found = []
    for page in state['pages']:
        try:
            manifest = read_json(page['manifest'])
        except (OSError, ValueError):
            continue
        regions = {r['id']: r for r in manifest.get('regions', [])}
        for segment in page['segments']:
            if segment.get('source_status') in HUMAN_STATES or segment.get('auto_exclude_overridden'):
                continue
            reason = classify_non_dialogue(segment, regions.get(segment['region_id']), manifest.get('width'), manifest.get('height'))
            if reason:
                found.append((segment, {'segment_id': segment['id'], 'page_id': page['page_id'],
                                        'region_id': segment['region_id'], 'reason': reason,
                                        'text': (segment.get('jp') or '')[:40]}))
    # Changing the target set invalidates a run that already has translated groups.
    applied = bool(found) and not dry_run and not _run_in_progress(state)
    if applied:
        for segment, info in found:
            segment['previous_source_status'] = segment.get('source_status', 'unreviewed')
            segment['source_status'] = 'excluded'
            segment['exclusion'] = {'auto': True, 'reason': info['reason'], 'at': service.now()}
        service.save(path, state)
    return {'count': len(found), 'applied': applied, 'excluded': [info for _, info in found],
            'skipped': 'run_in_progress' if found and not dry_run and not applied else None}
