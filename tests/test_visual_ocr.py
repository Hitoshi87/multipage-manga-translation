import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from manga_ai.io import write_json
from manga_ai.translation import service


class VisualOcrTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'project.json';page=self.root/'p';page.mkdir()
        Image.new('RGB',(200,200),'white').save(page/'original.png')
        region={'id':'B001','box':[20,30,100,110],'safe':[25,35,90,100],
                'fill':[255,255,255],'auto_clean':False,'source':'残り１００円'}
        write_json(page/'manifest.json',{'schema':1,'width':200,'height':200,'regions':[region]})
        service.save_profile(self.project,{'vision_mode':'target_crop','group_size':1})
        service.index_page(self.project,page/'manifest.json','p',1)

    def test_proposal_is_independent_cached_and_never_overwrites_ocr(self):
        original=service.load(self.project)['pages'][0]['segments'][0]
        def provider(profile,system,payload):
            self.assertNotIn('１００円',json.dumps(payload,ensure_ascii=False))
            self.assertEqual(len(profile['_vision_images']),1)
            return json.dumps({'items':[{'id':original['id'],'main_text':'残り1800円','uncertain':False}]}),{}
        with patch.object(service,'call_provider',side_effect=provider) as call:
            result=service.visual_ocr_page(self.project,'p')['data']
            again=service.visual_ocr_page(self.project,'p')['data']
        self.assertTrue(result['done']);self.assertEqual(call.call_count,1);self.assertEqual(again['attempted'],0)
        segment=service.load(self.project)['pages'][0]['segments'][0]
        self.assertEqual(segment['jp'],'残り１００円')
        self.assertEqual(segment['visual_ocr']['status'],'proposed')
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        from manga_ai.translation.grouping import payload_for_group
        suggestion=payload_for_group(group)['segments'][0]['independent_visual_transcription']
        self.assertEqual(suggestion['main_text'],'残り1800円')
        translation={'translations':[{'id':segment['id'],'vi':'Còn 1800 yên','flags':[]}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(translation,ensure_ascii=False),{})):
            row=service.run_group(self.project,run['id'],group['id'])['data']['results'][0]
        self.assertIn('ocr_suspect',row['flags'])
        service.edit_source(self.project,segment['id'],'残り1800円')
        self.assertNotIn('visual_ocr',service.load(self.project)['pages'][0]['segments'][0])

    def test_never_mutates_a_page_already_referenced_by_run(self):
        service.prepare(self.project)
        with patch.object(service,'call_provider') as call:
            result=service.visual_ocr_page(self.project,'p')['data']
        self.assertEqual(result['skipped'],'run_already_references_page');call.assert_not_called()

    def test_invalid_response_does_not_commit_partial_proposal(self):
        with patch.object(service,'call_provider',return_value=('{"items":[]}',{})):
            with self.assertRaises(ValueError):service.visual_ocr_page(self.project,'p')
        self.assertNotIn('visual_ocr',service.load(self.project)['pages'][0]['segments'][0])

    def test_multiple_numeric_bubbles_share_a_single_request(self):
        page=self.root/'p';manifest=json.loads((page/'manifest.json').read_text())
        manifest['regions'].append({'id':'B002','box':[130,30,50,110],'safe':[135,35,40,100],
                                    'fill':[255,255,255],'auto_clean':False,'source':'７万'})
        write_json(page/'manifest.json',manifest)
        service.index_page(self.project,page/'manifest.json','p',1)
        def provider(profile,system,payload):
            self.assertEqual(len(profile['_vision_images']),2)
            self.assertEqual([x['image_number'] for x in payload['crops']],[1,2])
            return json.dumps({'items':[{'id':c['id'],'main_text':'１円','uncertain':True}
                                        for c in payload['crops']]}),{}
        with patch.object(service,'call_provider',side_effect=provider) as call:
            result=service.visual_ocr_page(self.project,'p')['data']
        self.assertEqual(result['attempted'],2);self.assertEqual(call.call_count,1)

    def test_kanji_candidate_keeps_furigana_as_unverified_proposal(self):
        page=self.root/'p';manifest=json.loads((page/'manifest.json').read_text())
        manifest['regions'][0]['source']='この楓林女子校は'
        write_json(page/'manifest.json',manifest);service.index_page(self.project,page/'manifest.json','p',1)
        def provider(profile,system,payload):
            self.assertNotIn('楓林',json.dumps(payload,ensure_ascii=False))
            return json.dumps({'items':[{'id':payload['crops'][0]['id'],'main_text':'この楓林女子校は',
                'furigana':[{'base':'楓林','reading':'ふうりん'}],'uncertain':False}]} ,ensure_ascii=False),{}
        with patch.object(service,'call_provider',side_effect=provider):service.visual_ocr_page(self.project,'p')
        candidate=service.load(self.project)['pages'][0]['segments'][0]['visual_ocr']
        self.assertEqual(candidate['status'],'proposed')
        self.assertEqual(candidate['furigana'],[{'base':'楓林','reading':'ふうりん'}])

    def test_invalid_optional_furigana_is_removed_and_marked_uncertain(self):
        def provider(profile,system,payload):
            return json.dumps({'items':[{'id':payload['crops'][0]['id'],'main_text':'残り1800円',
                'furigana':[{'base':'名前','reading':'ふうりん'}],'uncertain':False}]},ensure_ascii=False),{}
        with patch.object(service,'call_provider',side_effect=provider):service.visual_ocr_page(self.project,'p')
        candidate=service.load(self.project)['pages'][0]['segments'][0]['visual_ocr']
        self.assertEqual(candidate['main_text'],'残り1800円')
        self.assertEqual(candidate['furigana'],[]);self.assertTrue(candidate['uncertain'])

    def test_suspected_outside_sound_effect_gets_independent_crop(self):
        state=service.load(self.project);segment=state['pages'][0]['segments'][0]
        segment['jp']='ザワということで…';segment['raw_ocr']='ということで…'
        segment['source_revision']=service.revision(segment['jp']);service.save(self.project,state)
        def provider(profile,system,payload):
            self.assertIn('outside that balloon',system)
            return json.dumps({'items':[{'id':payload['crops'][0]['id'],'main_text':'ということで…',
                'furigana':[],'uncertain':False}]},ensure_ascii=False),{}
        with patch.object(service,'call_provider',side_effect=provider) as call:
            service.visual_ocr_page(self.project,'p')
        self.assertEqual(call.call_count,1)
        self.assertEqual(service.load(self.project)['pages'][0]['segments'][0]['visual_ocr']['main_text'],'ということで…')

    def test_cli_dispatches_visual_ocr_with_envelope(self):
        from manga_ai.cli import dispatch
        expected=service.envelope('visual_ocr','completed',{'done':True})
        with patch.object(service,'visual_ocr_page',return_value=expected) as method:
            result=dispatch({'operation':'translation_visual_ocr_page','project':str(self.project),'page_id':'p'})
        self.assertEqual(result['data']['done'],True)
        method.assert_called_once_with(str(self.project),'p',None)
