import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from manga_ai.io import write_json
from manga_ai.translation import cast, service
from manga_ai.translation.prompts import compose


class CastTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.project = self.dir / 'project.json'
        service.save_profile(self.project, {'group_size': 20})
        for n in (1, 2):
            page = self.dir / str(n)
            page.mkdir()
            (page / 'original.png').write_bytes(b'img' + bytes([n]))
            regions = [{'id': 'B00%d' % i, 'box': [i, i, 8, 8], 'safe': [i, i, 8, 8], 'fill': [255] * 3, 'auto_clean': False,
                        'source': 'こんにちは%d%d' % (n, i)} for i in (1, 2)]
            write_json(page / 'manifest.json', {'schema': 1, 'width': 10, 'height': 10, 'regions': regions})
            service.index_page(self.project, page / 'manifest.json', 'page%d' % n, n)
        self.ids = [s['id'] for p in service.load(self.project)['pages'] for s in p['segments']]

    def answer(self, **over):
        body = {'characters': [
            {'id': 'c1', 'name': 'Yamabuki', 'label': 'học sinh mới', 'role': 'thiếu gia', 'speech_style': 'tự tin', 'evidence': [self.ids[0], 'nope'], 'confidence': 'high'},
            {'id': 'c2', 'name': 'ヤマブキ', 'label': 'giáo viên', 'role': '', 'speech_style': '', 'evidence': [self.ids[1]], 'confidence': 'medium'},
            {'id': 'c3', 'name': 'X', 'label': 'người thấp', 'evidence': [], 'confidence': 'low'},
            {'id': 'c1', 'name': 'trùng id'}],
            'relations': [{'a': 'c1', 'b': 'c2', 'a_calls_b': 'thầy', 'b_calls_a': 'em', 'register': 'formal', 'evidence': [self.ids[1]], 'confidence': 'high'},
                          {'a': 'c1', 'b': 'zz', 'a_calls_b': 'x'}],
            'scene': 'Lớp học.'}
        body.update(over)
        return json.dumps(body), {'usage': {'total_tokens': 5}}

    def test_cast_is_validated_stored_as_proposals_and_applied_to_the_prompt(self):
        with patch.object(service, 'call_provider', side_effect=lambda *a: self.answer()):
            cast.analyse(self.project)
        items = {i['id']: i for i in service.load(self.project)['cast']['items']}
        self.assertEqual(items['c1']['evidence'], [self.ids[0]])             # unknown evidence id dropped
        self.assertEqual(items['c2']['name'], '')                            # Japanese script is not a romaji name
        self.assertNotIn('c1>zz', items)                                     # relation to an unknown character dropped
        self.assertTrue(all(i['status'] == 'proposed' for i in items.values()))
        self.assertTrue(cast.apply(self.project)['changed'])
        prompt = compose(service.load(self.project)['profiles'][-1]['values'])
        self.assertNotIn('CAST CONTEXT', prompt)
        self.assertNotIn('Yamabuki', prompt)
        self.assertNotIn('người thấp', prompt)                               # low-confidence hints are left out
        self.assertFalse(cast.apply(self.project)['changed'])                # idempotent

    def test_confirmation_is_authoritative_rejection_removes_and_survives_reanalysis(self):
        with patch.object(service, 'call_provider', side_effect=lambda *a: self.answer()):
            cast.analyse(self.project)
            cast.set_status(self.project, ['c1', 'c1>c2'], 'confirmed')
            cast.set_status(self.project, ['c2'], 'rejected')
            prompt = compose(service.load(self.project)['profiles'][-1]['values'])
            self.assertNotIn('[CONFIRMED] Yamabuki', prompt)
            self.assertNotIn('giáo viên', prompt)
            cast.analyse(self.project)                                       # a second analysis keeps human decisions
        items = {i['id']: i for i in service.load(self.project)['cast']['items']}
        self.assertEqual((items['c1']['status'], items['c2']['status']), ('confirmed', 'rejected'))

    def test_analysis_is_refused_once_groups_are_translated(self):
        run = service.prepare(self.project)['data']
        provider = lambda p, s, payload: (json.dumps({'translations': [{'id': x['id'], 'vi': 'Ok', 'flags': []} for x in payload['segments']]}), {})
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        with self.assertRaises(ValueError):
            cast.analyse(self.project)

    def test_only_the_first_pages_are_sent_and_no_images(self):
        seen = {}
        def provider(profile, system, payload):
            seen.update(payload)
            return self.answer()
        with patch.object(service, 'call_provider', side_effect=provider):
            cast.analyse(self.project, page_limit=1)
        self.assertEqual({s['page'] for s in seen['segments']}, {'page1'})
        self.assertNotIn('image_context', seen)

    def test_old_frozen_cast_prompt_cannot_resume_or_be_sent(self):
        profile=dict(service.load(self.project)['profiles'][-1]['values'])
        profile['cast_prompt']='CAST CONTEXT: bí mật từ trang sau'
        service.save_profile(self.project,profile)
        run=service.prepare(self.project)['data']
        state=service.load(self.project)
        state['runs'][-1]['compiled_system']+='\n'+profile['cast_prompt']
        service.save(self.project,state)
        with self.assertRaisesRegex(ValueError,'chưa giới hạn thời gian'):
            service.run_group(self.project,run['id'],run['groups'][0]['id'])
        replacement=service.resume_or_prepare(self.project)['data']
        self.assertNotEqual(replacement['id'],run['id'])
        self.assertNotIn(profile['cast_prompt'],replacement['compiled_system'])

    def test_role_framing_and_empty_cast(self):
        self.assertIn('scanlation team', compose({}))
        self.assertNotIn('CAST CONTEXT', compose({}))
        self.assertEqual(cast.render_prompt(None), '')


if __name__ == '__main__':
    unittest.main()
