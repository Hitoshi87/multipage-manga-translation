import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from manga_ai.io import write_json
from manga_ai.translation import service

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name); self.project=self.dir/'project.json'
        service.save_profile(self.project, {'group_size':1})
        for n in (1,2):
            page=self.dir/str(n);page.mkdir();(page/'original.png').write_bytes(b'same image'+bytes([n]))
            region={'id':'B001','box':[1,1,8,8],'safe':[1,1,8,8],'fill':[255,255,255], 'auto_clean':False,'source':'こんにちは'+str(n)}
            write_json(page/'manifest.json',{'schema':1,'width':10,'height':10,'regions':[region]})
            service.index_page(self.project,page/'manifest.json','page'+str(n),n)
    def provider(self, profile, prompt, payload):
        return json.dumps({'translations':[{'id':x['id'],'vi':'Xin chào','flags':[]} for x in payload['segments']]}), {'usage':{'total_tokens':10},'latency_ms':1,'model_returned':'mock'}

    def test_unverified_numerals_are_queued_for_review(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            row=service.run_group(self.project,run['id'],group['id'])['data']['results'][0]
        self.assertIn('numeric_source_unverified',row['qa_warnings'])
        self.assertIn('needs_review',row['flags'])

    def test_human_corrected_numerals_do_not_get_unverified_warning(self):
        seg=service.load(self.project)['pages'][0]['segments'][0]
        service.edit_source(self.project,seg['id'],'１００円')
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            row=service.run_group(self.project,run['id'],group['id'])['data']['results'][0]
        self.assertNotIn('numeric_source_unverified',row.get('qa_warnings',[]))
    def test_resume_approval_and_invalidation(self):
        run=service.prepare(self.project)['data']; g1,g2=run['groups']
        with patch.object(service,'call_provider',side_effect=self.provider) as provider:
            service.run_group(self.project,run['id'],g1['id'])
            service.run_group(self.project,run['id'],g1['id'])
            self.assertEqual(provider.call_count,1)
            service.run_group(self.project,run['id'],g2['id'])
        data=service.load(self.project); rows=data['runs'][0]['groups'][0]['results']
        service.accept(self.project,run['id'],[{'id':rows[0]['id'],'text':'Xin chào'}])
        self.assertEqual(len(service.export_mapping(self.project,run['id'])['data']['pages'][0]['mapping']),1)
        service.edit_source(self.project,rows[0]['id'],'さようなら')
        self.assertEqual(service.export_mapping(self.project,run['id'])['data']['pages'][0]['mapping'],[])
    def test_invalid_json_does_not_save_results(self):
        run=service.prepare(self.project)['data']; group=run['groups'][0]
        with patch.object(service,'call_provider',return_value=('{',{'finish_reason':'stop','usage':{'total_tokens':17}})):
            with self.assertRaises(ValueError): service.run_group(self.project,run['id'],group['id'])
        actual=service.load(self.project)['runs'][0]['groups'][0]
        self.assertEqual(actual['status'],'failed');self.assertEqual(actual['results'],[])
        self.assertEqual(actual['attempts'][-1]['usage']['total_tokens'],17)
    def test_reindex_preserves_only_matching_source_page_geometry(self):
        before=service.load(self.project)['pages'][0]['segments'][0]['id']
        service.index_page(self.project,self.dir/'1/manifest.json','page1',1)
        self.assertEqual(before,service.load(self.project)['pages'][0]['segments'][0]['id'])
        (self.dir/'1/original.png').write_bytes(b'different')
        service.index_page(self.project,self.dir/'1/manifest.json','page1',1)
        self.assertNotEqual(before,service.load(self.project)['pages'][0]['segments'][0]['id'])

    def test_changed_context_invalidates_prepared_group(self):
        run=service.prepare(self.project)['data']; second=run['groups'][1]
        service.edit_source(self.project, run['groups'][0]['targets'][0]['id'], 'さようなら')
        with patch.object(service,'call_provider') as provider:
            with self.assertRaises(ValueError): service.run_group(self.project,run['id'],second['id'])
            provider.assert_not_called()

    def test_invalid_placeholder_edit_cannot_be_approved(self):
        state=service.load(self.project); segment=state['pages'][0]['segments'][0]
        service.edit_source(self.project,segment['id'],'こんにちは {name}')
        run=service.prepare(self.project)['data']; group=run['groups'][0]
        def translated(profile,prompt,payload):
            return json.dumps({'translations':[{'id':segment['id'],'vi':'Chào {name}','flags':[]}]}), {}
        with patch.object(service,'call_provider',side_effect=translated):
            service.run_group(self.project,run['id'],group['id'])
        with self.assertRaises(ValueError): service.accept(self.project,run['id'],[{'id':segment['id'],'text':'Chào'}])

    def test_unverified_ocr_cannot_auto_accept(self):
        service.save_profile(self.project, {'group_size':1,'auto_accept':True})
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            result=service.run_group(self.project,run['id'],group['id'])['data']
        self.assertEqual(result['results'][0]['status'],'needs_review')
        segment=service.load(self.project)['pages'][0]['segments'][0]
        service.edit_source(self.project,segment['id'],segment['jp'],verified=True)
        self.assertEqual(service.export_mapping(self.project,run['id'])['data']['pages'][0]['mapping'],[])
        fresh=service.prepare(self.project)['data'];group=fresh['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            result=service.run_group(self.project,fresh['id'],group['id'])['data']
        self.assertEqual(result['results'][0]['status'],'auto_accepted')

    def test_excluded_region_is_not_required_for_mapping(self):
        segment=service.load(self.project)['pages'][0]['segments'][0]
        service.exclude_source(self.project,segment['id'])
        run=service.prepare(self.project)['data']
        self.assertNotIn(segment['id'],[t['id'] for g in run['groups'] for t in g['targets']])
        page=service.export_mapping(self.project,run['id'])['data']['pages'][0]
        self.assertEqual(page['required_count'],0)
        self.assertEqual(page['excluded_regions'],['B001'])

    def test_provider_failure_metadata_is_preserved(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=service.ProviderResponseError('truncated',{'finish_reason':'length','usage':{'total_tokens':19}})):
            with self.assertRaises(ValueError):service.run_group(self.project,run['id'],group['id'])
        attempt=service.load(self.project)['runs'][0]['groups'][0]['attempts'][-1]
        self.assertEqual(attempt['finish_reason'],'length')
        self.assertEqual(attempt['usage']['total_tokens'],19)

    def test_advisory_review_does_not_overwrite_translation(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            result=service.run_group(self.project,run['id'],group['id'])['data']
        row=result['results'][0]
        review={'issues':[{'segment_id':row['id'],'category':'meaning','severity':'major','explanation':'thiếu ý','proposed_fix':'Chào bạn'}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(review),{'usage':{}})):
            self.assertEqual(service.review_group(self.project,run['id'],group['id'])['data']['issues'][0]['severity'],'major')
        current=service.load(self.project)['runs'][0]['groups'][0]
        self.assertEqual(current['results'][0]['semantic_translation'],'Xin chào')
        self.assertEqual(current['results'][0]['status'],'needs_review')

    def test_failed_advisory_review_records_usage_without_changing_translation(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):
            service.run_group(self.project,run['id'],group['id'])
        with patch.object(service,'call_provider',return_value=('',{'usage':{'total_tokens':23},'finish_reason':'stop'})):
            with self.assertRaises(ValueError):service.review_group(self.project,run['id'],group['id'])
        saved=service.load(self.project)['runs'][0]['groups'][0]
        self.assertEqual(saved['review_attempts'][0]['metadata']['usage']['total_tokens'],23)
        self.assertEqual(saved['results'][0]['semantic_translation'],'Xin chào')

    def test_crop_and_baberu_suggestion_do_not_change_source(self):
        from PIL import Image
        path=self.dir/'1/original.png';Image.new('RGB',(10,10),'white').save(path)
        page=service.index_page(self.project,self.dir/'1/manifest.json','page1',1)['data']
        segment=page['segments'][0]
        with patch('manga_ai.baberu_ocr.read',return_value='おはよう'):
            result=service.ocr_crop(self.project,segment['id'],candidate=True)['data']
        self.assertTrue(Path(result['crop']).is_file())
        self.assertEqual(result['candidate'],'おはよう')
        self.assertEqual(service.load(self.project)['pages'][0]['segments'][0]['jp'],segment['jp'])

    def test_batch_suggestions_are_bounded_and_do_not_change_sources(self):
        ids=[p['segments'][0]['id'] for p in service.load(self.project)['pages']]
        with patch.object(service,'ocr_crop',side_effect=lambda path, sid, **kw: {'data':{'segment_id':sid,'candidate':'候補'}}) as crop:
            result=service.ocr_suggest_batch(self.project,ids)['data']['items']
        self.assertEqual([x['segment_id'] for x in result],ids)
        self.assertEqual(crop.call_count,2)
        with self.assertRaises(ValueError):service.ocr_suggest_batch(self.project,ids*5)
        self.assertTrue(all(p['segments'][0]['source_status']=='unreviewed' for p in service.load(self.project)['pages']))

    def test_legacy_segment_hash_and_provenance_invalidation(self):
        segment=service.load(self.project)['pages'][0]['segments'][0]
        keys=('id','page_id','page_ordinal','region_id','order','panel_id','panel_status','source_revision','source_status')
        old={'source_revision':segment['source_revision'],'source_status':segment['source_status'],
             'segment_version':service.digest({key:segment.get(key) for key in keys})}
        self.assertTrue(service.same_source(old,segment))
        service.edit_source(self.project,segment['id'],segment['jp'],based_on='baberu')
        updated=service.load(self.project)['pages'][0]['segments'][0]
        self.assertFalse(service.same_source(old,updated))
        self.assertEqual(updated['source_provenance']['based_on'],'baberu')

    def test_preview_matches_sent_system_and_user_payload(self):
        from manga_ai.cli import dispatch
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        preview=dispatch({'operation':'translation_preview_group','project':str(self.project),
                          'run_id':run['id'],'group_id':group['id']})
        with patch.object(service,'call_provider',side_effect=self.provider) as provider:
            service.run_group(self.project,run['id'],group['id'])
        self.assertEqual(provider.call_args.args[1],preview['system'])
        self.assertEqual(provider.call_args.args[2],preview['payload'])

    def test_draft_mapping_is_visible_without_approval_and_does_not_approve(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        with patch.object(service,'call_provider',side_effect=self.provider):service.run_group(self.project,run['id'],group['id'])
        self.assertEqual(service.export_mapping(self.project,run['id'])['data']['pages'][0]['mapping'],[])
        draft=service.export_mapping(self.project,run['id'],draft=True)
        self.assertEqual(len(draft['data']['pages'][0]['mapping']),1)
        self.assertEqual(draft['data']['pages'][0]['review'][0]['source_status'],'unreviewed')
        self.assertEqual(service.load(self.project)['runs'][0]['groups'][0]['results'][0]['status'],'needs_review')

    def test_ruby_is_proposed_and_changes_invalidate_run(self):
        segment=service.load(self.project)['pages'][0]['segments'][0];service.edit_source(self.project,segment['id'],'日本')
        run=service.prepare(self.project)['data'];self.assertEqual(service.resume_or_prepare(self.project)['data']['id'],run['id'])
        service.edit_ruby(self.project,segment['id'],[{'base':'日本','reading':'にほん'}])
        newer=service.resume_or_prepare(self.project)['data'];self.assertNotEqual(newer['id'],run['id'])
        from manga_ai.translation.grouping import payload_for_group
        self.assertEqual(payload_for_group(newer['groups'][0])['segments'][0]['furigana'][0]['status'],'proposed')
        with self.assertRaises(ValueError):service.edit_ruby(self.project,segment['id'],[{'base':'不存在','reading':'x'}])
        service.edit_source(self.project,segment['id'],'東京')
        self.assertNotIn('ruby',service.load(self.project)['pages'][0]['segments'][0])

    def test_vision_sends_image_and_keeps_disagreement_unverified(self):
        from PIL import Image
        for n in (1,2):
            Image.new('RGB',(10,10),'white').save(self.dir/str(n)/'original.png')
            service.index_page(self.project,self.dir/str(n)/'manifest.json','page'+str(n),n)
        service.save_profile(self.project,{'group_size':1,'vision_mode':'target_crop','auto_accept':True})
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        def provider(profile,system,payload):
            self.assertEqual(len(profile['_vision_images']),1)
            self.assertEqual(payload['image_context'][0]['target_ids'],[group['targets'][0]['id']])
            return json.dumps({'translations':[{'id':group['targets'][0]['id'],'vi':'Chào','flags':[],
                'source_evidence':{'main_text':'別の文字','furigana':[{'base':'文字','reading':'もじ'}]}}]}),{}
        with patch.object(service,'call_provider',side_effect=provider):result=service.run_group(self.project,run['id'],group['id'])['data']
        row=result['results'][0];self.assertIn('ocr_suspect',row['flags']);self.assertEqual(row['status'],'needs_review')
        self.assertEqual(row['source_evidence']['status'],'proposed')
        self.assertNotIn('data:image',self.project.read_text())

    def test_invalid_optional_vision_evidence_keeps_translation_and_flags(self):
        from manga_ai.translation.qa import validate_response
        raw=json.dumps({'translations':[{'id':'x','vi':'Chào','flags':[],
            'source_evidence':{'main_text':'日本','furigana':[{'base':'東京','reading':'とうきょう'}]}}]})
        row=validate_response(raw,[{'id':'x','jp':'日本'}])[0]
        self.assertNotIn('source_evidence',row);self.assertIn('needs_review',row['flags'])
        self.assertEqual(row['_source_evidence_error'],'invalid_visual_evidence')
        raw=json.dumps({'translations':[{'id':'x','vi':'Chào','flags':[], 'source_evidence':{'main_text':'日本'}}]})
        self.assertEqual(validate_response(raw,[{'id':'x','jp':'日本'}])[0]['source_evidence']['furigana'],[])

    def test_gendered_quote_retries_from_source_without_auto_approval(self):
        s=service.load(self.project)['pages'][0]['segments'][0]
        service.edit_source(self.project,s['id'],'「愛してる」と言ってくれ')
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        def initial(profile,system,payload):
            return json.dumps({'translations':[{'id':s['id'],'vi':'Nói “Em yêu anh”.','flags':[]}]}),{}
        with patch.object(service,'call_provider',side_effect=initial):
            result=service.run_group(self.project,run['id'],group['id'])['data']
        self.assertIn('ambiguous_reference',result['results'][0]['flags'])
        def retried(profile,system,payload):
            self.assertNotIn('Em yêu anh',json.dumps(payload,ensure_ascii=False))
            return json.dumps({'translations':[{'id':s['id'],'vi':'Nói “Tớ yêu cậu”.','flags':[]}]}),{'usage':{'total_tokens':12}}
        with patch.object(service,'call_provider',side_effect=retried):
            repaired=service.repair_quote_group(self.project,run['id'],group['id'])['data']
        self.assertEqual(repaired['changed'],[s['id']])
        row=service.load(self.project)['runs'][-1]['groups'][0]['results'][0]
        self.assertEqual(row['semantic_translation'],'Nói “Tớ yêu cậu”.')
        self.assertEqual(row['status'],'needs_review');self.assertIn('needs_review',row['flags'])
        self.assertEqual(row['history'][-1]['text'],'Nói “Em yêu anh”.')

    def test_gendered_quote_retry_does_not_accept_partial_pronoun(self):
        s=service.load(self.project)['pages'][0]['segments'][0]
        service.edit_source(self.project,s['id'],'「愛してる」と言ってくれ')
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        def fake(text):return json.dumps({'translations':[{'id':s['id'],'vi':text,'flags':[]}]}),{}
        with patch.object(service,'call_provider',return_value=fake('Nói “Em yêu anh”.')):
            service.run_group(self.project,run['id'],group['id'])
        with patch.object(service,'call_provider',return_value=fake('Nói “Yêu anh”.')):
            result=service.repair_quote_group(self.project,run['id'],group['id'])['data']
        self.assertEqual(result['changed'],[])
        row=service.load(self.project)['runs'][-1]['groups'][0]['results'][0]
        self.assertEqual(row['semantic_translation'],'Nói “Em yêu anh”.')

    def test_page_auto_ocr_preserves_manual_source(self):
        from PIL import Image
        path=self.dir/'1/original.png';Image.new('RGB',(10,10),'white').save(path)
        page=service.index_page(self.project,self.dir/'1/manifest.json','page1',1)['data'];sid=page['segments'][0]['id']
        with patch('manga_ai.baberu_ocr.read',return_value='日本'):
            service.auto_ocr_page(self.project,'page1')
        item=service.load(self.project)['pages'][0]['segments'][0];self.assertEqual(item['jp'],'日本');self.assertEqual(item['source_status'],'unreviewed')
        service.edit_source(self.project,sid,'東京',verified=True)
        with patch('manga_ai.baberu_ocr.read') as read:
            service.auto_ocr_page(self.project,'page1');read.assert_not_called()
        self.assertEqual(service.load(self.project)['pages'][0]['segments'][0]['jp'],'東京')

    def test_changed_reading_order_invalidates_prepared_group(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        state=service.load(self.project);state['pages'][0]['segments'][0]['order']=9;service.save(self.project,state)
        with patch.object(service,'call_provider') as provider:
            with self.assertRaises(ValueError):service.run_group(self.project,run['id'],group['id'])
            provider.assert_not_called()

    def test_prepared_run_uses_frozen_composed_prompt(self):
        run=service.prepare(self.project)['data'];group=run['groups'][0];seen=[]
        def provider(profile,prompt,payload):
            seen.append(prompt)
            return self.provider(profile,prompt,payload)
        with patch.object(service,'compose',return_value='changed after preparation'), patch.object(service,'call_provider',side_effect=provider):
            service.run_group(self.project,run['id'],group['id'])
        self.assertEqual(seen,[run['compiled_system']])
        self.assertNotEqual(seen[0],'changed after preparation')

    def test_unfinished_legacy_run_without_prompt_snapshot_requires_rebuild(self):
        run=service.prepare(self.project)['data'];state=service.load(self.project)
        del state['runs'][0]['compiled_system'];service.save(self.project,state)
        with patch.object(service,'call_provider') as provider:
            with self.assertRaisesRegex(ValueError,'tạo lượt dịch mới'):
                service.run_group(self.project,run['id'],run['groups'][0]['id'])
            provider.assert_not_called()
