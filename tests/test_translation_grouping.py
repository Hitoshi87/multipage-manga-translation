import unittest
from manga_ai.translation.grouping import build_groups,input_chars,payload_for_group
from manga_ai.translation.service import digest, _quote_consistency, same_source


def segment(index, size=400):
    return {'id':str(index),'jp':'あ'*size,'source_revision':str(index),
            'source_status':'unreviewed','page_id':str(index//3),
            'panel_id':None,'panel_status':'unknown'}


class GroupingTest(unittest.TestCase):
    def test_alternative_ocr_reaches_model_as_unverified_evidence(self):
        s={**segment(1,10),'jp':'正一お前','raw_ocr':'まさ か ず 正一 お前',
           'ocr_evidence':{'origin':'tesseract'}}
        group=build_groups([s],version=digest,system='rules',group_size=1,context_segments=0,max_input_chars=2500)[0]
        alt=payload_for_group(group)['segments'][0]['ocr_alternative']
        self.assertEqual(alt,{'text':'まさ か ず 正一 お前','status':'unverified','origin':'tesseract'})
        self.assertTrue(same_source({**group['targets'][0], 'segment_version':None},s))
        self.assertFalse(same_source(group['targets'][0],{**s,'raw_ocr':'別の OCR'}))
        same={**s,'raw_ocr':s['jp']}
        group=build_groups([same],version=digest,system='rules',group_size=1,context_segments=0,max_input_chars=2500)[0]
        self.assertNotIn('ocr_alternative',payload_for_group(group)['segments'][0])

    def test_bounded_complete_chronological_targets_and_past_only_context(self):
        ready=[segment(i) for i in range(17)]
        groups=build_groups(ready,version=digest,system='rules',group_size=7,context_segments=3,max_input_chars=2500)
        targets=[t['id'] for g in groups for t in g['targets']]
        self.assertEqual(targets,[s['id'] for s in ready])
        self.assertGreater(len(groups),3)
        for group in groups:
            self.assertLessEqual(input_chars('rules',group),2500)
            first=int(group['targets'][0]['id'])
            self.assertTrue(all(int(c['id'])<first for c in group['context']))
            self.assertTrue(all(c['id'] not in [t['id'] for t in group['targets']] for c in group['context']))
            self.assertEqual(payload_for_group(group)['task']['target_ids'],[t['id'] for t in group['targets']])

    def test_single_oversized_source_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(ValueError,'vượt giới hạn'):
            build_groups([segment(1,4000)],version=digest,system='rules',group_size=7,context_segments=2,max_input_chars=1500)

    def test_vision_group_limits_pages_without_dropping_targets(self):
        ready=[{**segment(i,10),'page_id':str(i)} for i in range(9)]
        groups=build_groups(ready,version=digest,system='rules',group_size=20,context_segments=2,max_input_chars=24000,max_pages=4)
        self.assertEqual([len(g['targets']) for g in groups],[4,4,1])
        self.assertEqual([x['id'] for g in groups for x in g['targets']],[x['id'] for x in ready])

    def test_local_quote_extends_group_and_keeps_ids(self):
        ready=[{**segment(i,10),'page_ordinal':1 if i<9 else 2,'page_id':'a' if i<9 else 'b'} for i in range(12)]
        ready[0]['jp']='えー、みにゃ…皆も聞いている通り'
        ready[9]['jp']='冒頭の「みにゃ…」とはなんですか？'
        groups=build_groups(ready,version=digest,system='rules',group_size=7,context_segments=2,max_input_chars=24000,max_pages=4)
        self.assertEqual([x['id'] for x in groups[0]['targets']],list(map(str,range(10))))
        self.assertEqual(groups[0]['quote_links'][0]['quote_id'],'9')
        self.assertEqual([x['id'] for g in groups for x in g['targets']],[x['id'] for x in ready])

    def test_quote_link_respects_input_limit_and_marks_unresolved(self):
        ready=[{**segment(i,400),'page_ordinal':1,'page_id':'a'} for i in range(10)]
        ready[0]['jp']='みにゃ'+'あ'*400;ready[9]['jp']='「みにゃ」'+'い'*400
        groups=build_groups(ready,version=digest,system='rules',group_size=5,context_segments=0,max_input_chars=2800)
        self.assertEqual([x['id'] for g in groups for x in g['targets']],[x['id'] for x in ready])
        self.assertTrue(any(g.get('unresolved_quote_links') for g in groups))
        self.assertTrue(all(input_chars('rules',g)<=2800 for g in groups))

    def test_translation_quote_mismatch_is_flagged_not_rewritten(self):
        link=[{'source_id':'1','quote_id':'2'}]
        rows=[{'id':'1','vi':'Ờ, các iem...','flags':[]},{'id':'2','vi':'“Mi-nya” là gì?','flags':[]}]
        _quote_consistency(rows,link)
        self.assertTrue(all('needs_review' in r['flags'] for r in rows));self.assertEqual(rows[1]['vi'],'“Mi-nya” là gì?')
        rows=[{'id':'1','vi':'Ờ, các iem...','flags':[]},{'id':'2','vi':'“Các iem” là gì?','flags':[]}]
        _quote_consistency(rows,link)
        self.assertTrue(all(not r['flags'] for r in rows))
