import tempfile
import unittest
from pathlib import Path

from manga_ai.io import write_json
from manga_ai.translation import autopilot, service, triage


def region(rid, source, detector='ai_balloon', clean='japanese_bubble_components', box=(10, 100, 50, 50)):
    return {'id': rid, 'box': list(box), 'safe': list(box), 'fill': [255, 255, 255], 'auto_clean': False, 'source': source,
            'detector': detector, 'clean_method': clean}


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.project = self.dir / 'project.json'
        service.save_profile(self.project, {'group_size': 20})
        page = self.dir / 'p'
        page.mkdir()
        (page / 'original.png').write_bytes(b'img')
        regions = [
            region('B001', 'ありがとう'),
            region('B002', 'さよなら', detector='comic_text_ai', clean='review_only'),
            region('B003', '新連載'),
            region('B004', '★この物語はフィクションであり、実在の人物とは関係ありません。'),
            region('B005', '１％'),
            region('B006', '12', detector='comic_text_ai', clean='opencv', box=(400, 1370, 40, 20)),
            region('B007', '完璧だ'),
            region('B008', '「つづく」'),
        ]
        write_json(page / 'manifest.json', {'schema': 1, 'width': 960, 'height': 1400, 'regions': regions})
        service.index_page(self.project, page / 'manifest.json', 'page1', 1)

    def reasons(self):
        return {i['region_id']: i['reason'] for i in triage.auto_exclude(self.project, dry_run=True)['excluded']}

    def test_only_clear_non_dialogue_is_excluded(self):
        self.assertEqual(self.reasons(), {'B002': 'outside_bubble', 'B003': 'banner', 'B004': 'copyright',
                                          'B006': 'page_number', 'B008': 'banner'})
        # Ordinary dialogue, a lone "1%" and a word that merely contains 完 stay in.

    def test_exclusion_is_applied_recorded_and_hides_segments_from_the_run(self):
        result = triage.auto_exclude(self.project)
        self.assertTrue(result['applied'])
        state = service.load(self.project)
        excluded = {s['region_id']: s for s in state['pages'][0]['segments'] if s['source_status'] == 'excluded'}
        self.assertEqual(set(excluded), {'B002', 'B003', 'B004', 'B006', 'B008'})
        self.assertTrue(excluded['B003']['exclusion']['auto'])
        run = service.prepare(self.project)['data']
        sent = [t['jp'] for g in run['groups'] for t in g['targets']]
        self.assertEqual(sorted(sent), sorted(['ありがとう', '１％', '完璧だ']))

    def test_restoring_an_exclusion_is_never_overridden_again(self):
        triage.auto_exclude(self.project)
        seg = next(s for s in service.load(self.project)['pages'][0]['segments'] if s['region_id'] == 'B003')
        service.exclude_source(self.project, seg['id'], False)
        again = triage.auto_exclude(self.project)
        self.assertNotIn('B003', [i['region_id'] for i in again['excluded']])
        restored = next(s for s in service.load(self.project)['pages'][0]['segments'] if s['region_id'] == 'B003')
        self.assertEqual(restored['source_status'], 'unreviewed')

    def test_human_verified_sources_are_not_touched(self):
        seg = next(s for s in service.load(self.project)['pages'][0]['segments'] if s['region_id'] == 'B003')
        service.edit_source(self.project, seg['id'], '新連載', verified=True)
        self.assertNotIn('B003', self.reasons())

    def test_a_run_with_translated_groups_is_not_invalidated(self):
        from unittest.mock import patch
        import json
        run = service.prepare(self.project)['data']
        def provider(profile, prompt, payload):
            return json.dumps({'translations': [{'id': x['id'], 'vi': 'Ok', 'flags': []} for x in payload['segments']]}), {}
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        result = triage.auto_exclude(self.project)
        self.assertFalse(result['applied'])
        self.assertEqual(result['skipped'], 'run_in_progress')

    def test_autopilot_excludes_before_preparing_a_fresh_run(self):
        from unittest.mock import patch
        import json
        def provider(profile, prompt, payload):
            return json.dumps({'translations': [{'id': x['id'], 'vi': 'Ok', 'flags': []} for x in payload['segments']]}), {}
        with patch.object(service, 'call_provider', side_effect=provider):
            report = autopilot.autopilot(self.project)
        self.assertEqual(report['auto_excluded']['count'], 5)
        self.assertTrue(report['done'])


if __name__ == '__main__':
    unittest.main()
