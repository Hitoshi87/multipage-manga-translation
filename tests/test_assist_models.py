import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from manga_ai.head_protection import protect
from manga_ai.alignment_assist import suggest
from manga_ai.model_preview import create_clean, koharu_panels


class AssistModelsTest(unittest.TestCase):
    def test_font_style_follows_balloon_shape(self):
        from manga_ai.engine import bubble_font_style
        box={'outline':[[10,10],[110,10],[110,110],[10,110]],'detector':'ai_balloon'}
        circle={'outline':[[round(60+50*math.cos(i*math.pi/20)),round(60+50*math.sin(i*math.pi/20))] for i in range(40)],'detector':'ai_balloon'}
        star={'outline':[[round(60+(50 if i%2==0 else 30)*math.cos(i*math.pi/10)),round(60+(50 if i%2==0 else 30)*math.sin(i*math.pi/10))] for i in range(20)],'detector':'ai_balloon'}
        self.assertEqual(bubble_font_style(box),'box')
        self.assertEqual(bubble_font_style(circle),'dialogue')
        self.assertEqual(bubble_font_style(star),'shout')
        box['detector']='comic_text_ai'
        self.assertEqual(bubble_font_style(box),'dialogue')

    def test_face_exclusion_is_before_inpaint_and_only_removes_pixels(self):
        rgb=np.full((50,60,3),100,np.uint8)
        mask=np.ones((50,60),np.uint8)
        seen=[]
        def fake_lama(image,mask,cancel=None):
            seen.append(mask.copy());return np.full_like(image,255)
        with patch('manga_ai.model_preview.detailed_mask',return_value=(mask,[])), \
             patch('manga_ai.head_protection.detect',return_value=[[20,10,15,20]]), \
             patch('manga_ai.model_preview.lama_clean',side_effect=fake_lama):
            result,output=create_clean(rgb,'ctd',True,protect_faces=True)
        self.assertTrue(np.array_equal(seen[0],output))
        self.assertEqual(output[20,25],0)
        self.assertTrue(np.array_equal(result[20,25],rgb[20,25]))
        self.assertEqual(output[0,0],1)

    def test_head_protection_clamps_to_image(self):
        mask=np.ones((10,10),np.uint8);r=protect(mask,[[0,0,3,3]])
        self.assertEqual(r[0,0],0);self.assertEqual(r[-1,-1],1)

    def test_koharu_panels_ignore_text_and_other_classes(self):
        output={'labels':np.array([[[2,0,0,0],[0,0,0,2]]],np.float32),
                'dets':np.array([[[.5,.5,.2,.2],[.5,.5,.6,.4]]],np.float32)}
        with patch('manga_ai.model_preview.koharu_outputs',return_value=output):
            boxes=koharu_panels(np.zeros((100,200,3),np.uint8))
        self.assertEqual(boxes,[[40,30,120,40]])

    def test_alignment_suggestions_keep_ids_and_do_not_change_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);Image.fromarray(np.ones((50,50,3),np.uint8)*255).save(path/'original.png')
            region={'id':'B001','box':[5,5,30,30],'safe':[5,5,30,30],'fill':[255,255,255],'auto_clean':False}
            manifest={'schema':1,'width':50,'height':50,'regions':[region]};f=path/'manifest.json';f.write_text(json.dumps(manifest))
            with patch('manga_ai.baberu_ocr.read',return_value='おはよう'), \
                 patch('manga_ai.alignment_assist.encode',return_value=np.array([[1.,0.],[0.,1.],[1.,0.]])):
                result=suggest(f,['Tạm biệt','Chào buổi sáng'])
            self.assertEqual(result['regions'][0]['candidates'][0]['index'],1)
            self.assertEqual(json.loads(f.read_text()),manifest)


if __name__=='__main__':unittest.main()
