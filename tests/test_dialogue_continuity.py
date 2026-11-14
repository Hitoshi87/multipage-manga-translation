import json
import unittest
from pathlib import Path
from manga_ai.translation.dialogue import prior_translations, strip_honorifics
from manga_ai.translation.shorten import acceptable


class DialogueContinuityTest(unittest.TestCase):
    def test_honorific_cleanup_shared_fixtures(self):
        cases=json.loads((Path(__file__).parent/'fixtures/honorific_cases.json').read_text())
        for case in cases:
            with self.subTest(text=case['in']):
                self.assertEqual(strip_honorifics(case['in']), (case['out'],case['count']))

    def test_future_pending_and_stale_rows_are_not_context(self):
        def target(id):return {'id':id,'jp':'こんにちは','page_id':'p','source_revision':'s','segment_version':'v'}
        def group(id,items):return {'id':id,'status':'completed','targets':items,'results':[
            {**t,'semantic_translation':'Tôi chào cậu.','status':'needs_review','flags':['speaker_unclear']} for t in items]}
        before=group('before',[target('a'),target('b')]);before['results'][1]['segment_version']='stale'
        current={'id':'current','context':[target('a'),target('b'),target('c'),target('d')]}
        pending=group('pending',[target('d')]);pending['status']='pending'
        run={'groups':[before,pending,current,group('future',[target('c')])]}
        result=prior_translations(run,current)
        self.assertEqual([r['id'] for r in result],['a'])
        self.assertEqual(result[0]['speaker']['status'],'unknown')
        self.assertEqual(result[0]['flags'],['speaker_unclear'])

    def test_shortening_cannot_change_address_or_introduce_suffix(self):
        old='Tôi sẽ đợi anh ở đây thêm một lúc nữa.'
        self.assertFalse(acceptable(old,'Em đợi anh.','待ちます',20))
        self.assertTrue(acceptable(old,'Tôi đợi anh.','待ちます',20))
        self.assertFalse(acceptable('Tôi chờ Ken ở đây thêm một lúc nữa.','Tôi chờ Ken-san.','待ちます',20))
