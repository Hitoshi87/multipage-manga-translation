import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from manga_ai.bubble_refinement import split_closed_balloons, closed_interior, lobe_candidates
from manga_ai.engine import analyse, render_clean


def fixture():
    rgb=np.full((600,600,3),255,np.uint8)
    interior=np.zeros((200,280),np.uint8)
    for cx in (110,270):
        cv2.ellipse(rgb,(cx,150),(60,90),0,0,360,(0,0,0),2)
        cv2.putText(rgb,'ABC',(cx-25,150),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
        cv2.ellipse(interior,(cx-50,100),(55,85),0,0,360,255,-1)
    candidate={'box':[50,50,280,200],'interior':interior,'detector':'ai_balloon','detector_confidence':.86}
    return rgb,candidate


class RefinementTests(unittest.TestCase):
    def setUp(self):
        # These tests isolate geometry/OCR rules; model accuracy belongs in native benchmarks.
        self.enterContext(patch('manga_ai.comic_text_ai.detect', return_value=[]))
        self.enterContext(patch('manga_ai.comic_text_ai.detect_multiscale', return_value=[]))
        self.enterContext(patch('manga_ai.head_protection.detect', return_value=[]))
        self.enterContext(patch('manga_ai.model_preview.ctd_mask', side_effect=lambda rgb: np.zeros(rgb.shape[:2], np.uint8)))

    def test_plain_oval_and_single_tail_are_not_two_speech_lobes(self):
        rgb=np.full((600,600,3),255,np.uint8);mask=np.zeros((220,220),np.uint8)
        cv2.ellipse(mask,(110,95),(95,80),0,0,360,255,-1)
        candidate={'box':[100,100,220,220],'interior':mask,'detector':'ai_balloon','detector_confidence':.97}
        self.assertEqual(lobe_candidates(rgb,candidate),[])
        cv2.fillPoly(mask,[np.array([[130,150],[160,210],[180,140]])],255)
        self.assertEqual(lobe_candidates(rgb,candidate),[])

    def test_lobe_replacement_requires_clear_japanese_in_both_children_and_reuses_ocr(self):
        rgb,candidate=fixture();candidate['detector_confidence']=.97
        children=split_closed_balloons(rgb,[candidate])
        for child in children:
            child['detector']='ai_balloon';child['geometry_evidence']='ai_mask_lobes'
        # Keep the mother during initial detection so the loop tests OCR-driven refinement.
        for second_confidence,expected in ((60,1),(94,2)):
            with self.subTest(second=second_confidence),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);Image.fromarray(rgb).save(root/'input.png');calls=[]
                def words(_rgb,c,_lang,_cancel):
                    x,y,w,h=c['box'];calls.append(c)
                    confidence=60 if len(calls)==1 else (94 if len(calls)==2 else second_confidence)
                    box=[x+30,y+70,40,20] if len(calls)==1 else [x+w//2-20,y+h//2-10,40,20]
                    return [{'text':'こんにちは','confidence':confidence,'box':box}]
                with patch('manga_ai.comic_text_ai.detect',return_value=[]),patch('manga_ai.balloon_ai.detect',return_value=[copy.deepcopy(candidate)]),patch('manga_ai.bubble_refinement.split_closed_balloons',side_effect=lambda _,cs:cs),patch('manga_ai.bubble_refinement.lobe_candidates',side_effect=lambda _rgb,c:copy.deepcopy(children) if not c.get('geometry_evidence') else []),patch('manga_ai.engine.region_ocr',side_effect=words),patch('manga_ai.engine.tesseract_path'),patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']):
                    result=analyse(root/'input.png',root/'out',lang='jpn_vert',detector='ai')
                self.assertEqual(len(result['regions']),expected)
                self.assertEqual(len(calls),3)

    def test_separate_closed_interiors_split_without_raising_model_confidence(self):
        rgb,candidate=fixture();found=split_closed_balloons(rgb,[candidate])
        self.assertEqual(len(found),2)
        for item in found:
            self.assertEqual(item['detector_confidence'],.86)
            self.assertEqual(item['detector'],'hybrid_closed_balloon')
            self.assertIsNotNone(closed_interior(rgb,item['box']))

    def test_open_border_and_missing_second_component_do_not_split(self):
        rgb,candidate=fixture();rgb[50:250,325:335]=255
        # Remove an actual section of the right outline, opening it to page white.
        rgb[140:160,325:335]=255
        self.assertEqual(split_closed_balloons(rgb,[candidate]),[candidate])
        rgb,candidate=fixture();rgb[:,200:]=255
        self.assertEqual(split_closed_balloons(rgb,[candidate]),[candidate])

    def test_low_model_score_remains_reviewable(self):
        rgb,candidate=fixture();candidate['detector_confidence']=.79
        self.assertEqual(split_closed_balloons(rgb,[candidate]),[candidate])

    def test_real_geometry_proof_is_repeated_before_clean_and_mask_tampering_blocked(self):
        rgb,candidate=fixture()
        def words(_rgb,c,_lang,_cancel):
            x,y,w,h=c['box']
            return [{'text':'こんにちは','confidence':94,'box':[x+w//2-25,y+h//2-15,55,25]}]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.fromarray(rgb).save(root/'input.png')
            with patch('manga_ai.balloon_ai.detect',return_value=[candidate]),patch('manga_ai.engine.region_ocr',side_effect=words),patch('manga_ai.engine.tesseract_path'),patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']):
                result=analyse(root/'input.png',root/'out',lang='jpn_vert',detector='ai')
            self.assertEqual(len(result['regions']),2)
            mapping=[{'id':r['id'],'translation':'Xin chào','force':True} for r in result['regions']]
            self.assertEqual(len(render_clean(result['manifest'],mapping)['applied']),2)
            mask=root/'out/masks/B001.png';pixels=np.array(Image.open(mask));pixels[0,0]=255;Image.fromarray(pixels).save(mask)
            clean=render_clean(result['manifest'],mapping)
            self.assertIn('B001',clean['blocked'])
            self.assertNotIn('B001',clean['applied'])


if __name__=='__main__':unittest.main()
