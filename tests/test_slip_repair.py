import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from manga_ai.io import write_json
from manga_ai.translation import service


class SlipRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        folder=Path(self.temp.name);self.project=folder/'project.json'
        Image.new('RGB',(200,200),'white').save(folder/'original.png')
        region={'id':'B001','box':[20,30,100,110],'safe':[25,35,90,100],
                'fill':[255,255,255],'auto_clean':False,'source':'えーみにゃ．．．皆も聞いている通り'}
        write_json(folder/'manifest.json',{'schema':1,'width':200,'height':200,'regions':[region]})
        service.save_profile(self.project,{'vision_mode':'target_crop','group_size':1})
        service.index_page(self.project,folder/'manifest.json','p',1)
        run=service.prepare(self.project)['data'];self.run=run['id'];self.group=run['groups'][0]['id'];self.id=run['groups'][0]['targets'][0]['id']
        initial={'translations':[{'id':self.id,'vi':'Ờ... mọi người đều nghe rồi','flags':['needs_review']}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(initial,ensure_ascii=False),{})):
            service.run_group(self.project,self.run,self.group)

    def test_source_supported_retry_is_draft_and_preserves_history(self):
        revised={'translations':[{'id':self.id,'vi':'Ờ... mọi ngừi... mọi người đều nghe rồi','flags':[],
            'source_evidence':{'main_text':'えーみにゃ…皆も聞いている通り'}}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(revised,ensure_ascii=False),{})):
            result=service.repair_slip_group(self.project,self.run,self.group)['data']
        row=service.load(self.project)['runs'][0]['groups'][0]['results'][0]
        self.assertEqual(result['changed'],[self.id]);self.assertEqual(row['status'],'needs_review')
        self.assertIn('mọi ngừi',row['semantic_translation'])
        self.assertEqual(row['history'][-1]['text'],'Ờ... mọi người đều nghe rồi')

    def test_unsupported_visual_evidence_never_overwrites_draft(self):
        revised={'translations':[{'id':self.id,'vi':'Một câu thay đổi','flags':[],
            'source_evidence':{'main_text':'違う文字'}}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(revised,ensure_ascii=False),{})):
            result=service.repair_slip_group(self.project,self.run,self.group)['data']
        self.assertEqual(result['changed'],[])
        row=service.load(self.project)['runs'][0]['groups'][0]['results'][0]
        self.assertEqual(row['semantic_translation'],'Ờ... mọi người đều nghe rồi')

    def test_a_later_quotation_is_not_treated_as_a_new_spoken_slip(self):
        service.edit_source(self.project,self.id,'冒頭の「みにゃ．．．」とは何ですか？')
        run=service.prepare(self.project)['data'];group=run['groups'][0]
        initial={'translations':[{'id':self.id,'vi':'Câu ấy là sao?','flags':['needs_review']}]}
        with patch.object(service,'call_provider',return_value=(json.dumps(initial,ensure_ascii=False),{})):
            service.run_group(self.project,run['id'],group['id'])
        with patch.object(service,'call_provider') as provider:
            result=service.repair_slip_group(self.project,run['id'],group['id'])['data']
        self.assertFalse(result['attempted']);provider.assert_not_called()
