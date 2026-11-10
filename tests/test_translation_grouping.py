import unittest
from manga_ai.translation.grouping import build_groups,input_chars,payload_for_group,prior_readings
from manga_ai.translation.service import digest, _quote_consistency, same_source


def segment(index, size=400):
    return {'id':str(index),'jp':'あ'*size,'source_revision':str(index),
            'source_status':'unreviewed','page_id':str(index//3),
            'panel_id':None,'panel_status':'unknown'}


class GroupingTest(unittest.TestCase):
    def test_cross_batch_quote_is_flagged_with_prior_source_as_context(self):
        a={**segment(1,2),'page_ordinal':1,'page_id':'a','jp':'みにゃ…皆も聞いている通り'}
        b={**segment(2,2),'page_ordinal':2,'page_id':'b','jp':'冒頭の「みにゃ」とはなんですか？'}
        group=build_groups([b],version=digest,system='rules',group_size=7,context_segments=2,
                           max_input_chars=24000,prior_context=[a])[0]
        self.assertEqual([s['id'] for s in group['context']],['1'])
        self.assertEqual(group['unresolved_quote_links'],[{'source_id':'1','quote_id':'2'}])

    def test_older_quoted_source_is_retrieved_beyond_normal_context_window(self):
        prior=[{**segment(i,2),'page_ordinal':1,'page_id':'a','jp':('みにゃ…皆も聞いている通り' if i==0 else '普通の話')}
               for i in range(8)]
        current={**segment(9,2),'page_ordinal':2,'page_id':'b','jp':'冒頭の「みにゃ」とはなんですか？'}
        group=build_groups([current],version=digest,system='rules',group_size=7,context_segments=2,
                           max_input_chars=24000,prior_context=prior)[0]
        self.assertEqual([s['id'] for s in group['context']],['0','6','7'])
        self.assertEqual(group['unresolved_quote_links'],[{'source_id':'0','quote_id':'9'}])

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

    def test_prior_readings_carries_past_furigana_without_future_leakage(self):
        g1={'id':'g1','targets':[{'id':'s1','jp':'久人さん','ruby':[{'base':'久人','reading':'かずと','status':'verified'}]}],
            'context':[],'results':[{'id':'s1','source_evidence':{'furigana':[{'base':'味沢','reading':'あいざわ'}]}}]}
        g2={'id':'g2','targets':[{'id':'s2','jp':'久人の料理と味沢の言葉'}],'context':[],'results':[]}
        g3={'id':'g3','targets':[{'id':'s3','jp':'船木さん','ruby':[{'base':'船木','reading':'ふなき','status':'verified'}]}],'context':[],'results':[]}
        run={'groups':[g1,g2,g3]}
        readings=prior_readings(run,g2)
        self.assertEqual([(r['base'],r['reading']) for r in readings],[('久人','かずと'),('味沢','あいざわ')])
        self.assertEqual(prior_readings(run,g1),[])
