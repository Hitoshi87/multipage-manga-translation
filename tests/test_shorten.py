import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from manga_ai.io import write_json
from manga_ai.translation import service, shorten

LONG = 'Tôi thật sự rất muốn nói với các bạn rằng chuyện này không hề đơn giản như mọi người vẫn nghĩ đâu'
SHORT = 'Chuyện này không đơn giản đâu'


class ShortenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.project = self.dir / 'project.json'
        service.save_profile(self.project, {'group_size': 20})
        page = self.dir / 'p'
        page.mkdir()
        (page / 'original.png').write_bytes(b'img')
        def region(rid, box, src):
            return {'id': rid, 'box': box, 'safe': box, 'fill': [255, 255, 255], 'auto_clean': False, 'source': src}
        regions = [region('B001', [100, 100, 130, 110], 'とても長い文章です'),            # small balloon, long text
                   region('B002', [400, 100, 360, 300], 'はい'),
                   region('B003', [100, 600, 360, 300], 'そうですね'),
                   region('B004', [500, 600, 360, 300], 'わかった')]
        write_json(page / 'manifest.json', {'schema': 1, 'width': 1008, 'height': 1440, 'regions': regions})
        service.index_page(self.project, page / 'manifest.json', 'page1', 1)
        run = service.prepare(self.project)['data']
        texts = {'B001': LONG, 'B002': 'Ừ', 'B003': 'Đúng vậy', 'B004': 'Hiểu rồi'}
        seg = {s['region_id']: s['id'] for s in service.load(self.project)['pages'][0]['segments']}
        self.ids = {v: k for k, v in seg.items()}
        def provider(profile, prompt, payload):
            rows = [{'id': x['id'], 'vi': texts[self.ids[x['id']]], 'flags': []} for x in payload['segments']]
            return json.dumps({'translations': rows}), {}
        with patch.object(service, 'call_provider', side_effect=provider):
            for g in run['groups']:
                service.run_group(self.project, run['id'], g['id'])
        self.run_id = run['id']
        self.seg = seg

    def row(self):
        run = service.load(self.project)['runs'][0]
        return next(v for g in run['groups'] for v in g['results'] if v['id'] == self.seg['B001'])

    def test_only_the_cramped_long_line_is_a_candidate(self):
        info = shorten.assess(self.project)
        self.assertEqual([c['region_id'] for c in info['candidates']], ['B001'])
        self.assertLess(info['candidates'][0]['budget'], len(LONG))

    def test_a_clean_shorter_rewrite_is_applied_and_history_kept(self):
        def provider(profile, prompt, payload):
            return json.dumps({'items': [{'id': payload['items'][0]['id'], 'vi': SHORT}]}), {}
        with patch.object(service, 'call_provider', side_effect=provider):
            report = shorten.auto_shorten(self.project)
        self.assertEqual(len(report['shortened']), 1)
        row = self.row()
        self.assertEqual(row['semantic_translation'], SHORT)
        self.assertEqual(row['history'][-1]['text'], LONG)
        self.assertEqual(row['history'][-1]['reason'], 'auto_shorten')

    def test_bad_rewrites_are_rejected(self):
        for bad in (LONG + ' nữa', '短くする', 'Chuyện **này** không đơn giản đâu', ''):
            def provider(profile, prompt, payload, bad=bad):
                return json.dumps({'items': [{'id': payload['items'][0]['id'], 'vi': bad}]}), {}
            with patch.object(service, 'call_provider', side_effect=provider):
                report = shorten.auto_shorten(self.project, rounds=1)
            self.assertEqual(report['shortened'], [], bad)
            self.assertEqual(self.row()['semantic_translation'], LONG)
            # attempts are capped, so reset for the next case
            state = service.load(self.project)
            for g in state['runs'][0]['groups']:
                for r in g['results']:
                    r.pop('auto_shorten_attempts', None)
            service.save(self.project, state)

    def test_human_approved_text_and_exhausted_attempts_are_left_alone(self):
        service.accept(self.project, self.run_id, [{'id': self.seg['B001'], 'text': LONG}])
        self.assertEqual(shorten.assess(self.project)['candidates'], [])
        state = service.load(self.project)
        row = next(v for g in state['runs'][0]['groups'] for v in g['results'] if v['id'] == self.seg['B001'])
        row['status'] = 'validated'
        row['auto_shorten_attempts'] = 2
        service.save(self.project, state)
        self.assertEqual(shorten.assess(self.project)['candidates'], [])

    def test_provider_failure_is_reported_not_raised(self):
        with patch.object(service, 'call_provider', side_effect=ValueError('API tạm thời lỗi HTTP 503')):
            report = shorten.auto_shorten(self.project)
        self.assertEqual(report['shortened'], [])
        self.assertEqual(len(report['errors']), 1)


if __name__ == '__main__':
    unittest.main()
