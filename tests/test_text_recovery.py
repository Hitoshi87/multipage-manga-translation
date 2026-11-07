import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

from manga_ai.engine import Cancelled, render_clean, analyse
from manga_ai.io import write_json
from manga_ai.text_recovery import punctuation_mask, recover_words


def dot_fixture():
    image=np.full((100,80,3),255,np.uint8)
    interior=np.zeros((100,80),np.uint8);interior[5:95,5:75]=255
    for x in (25,50):
        for y in (20,30,40,50,60,70):cv2.rectangle(image,(x,y),(x+2,y+2),(0,0,0),-1)
    return image,interior


class PunctuationTests(unittest.TestCase):
    def test_repeated_dots_produce_ink_mask_without_touching_border(self):
        image,interior=dot_fixture();cv2.rectangle(image,(0,0),(79,99),(0,0,0),2)
        mask,kind=punctuation_mask(image,interior)
        self.assertEqual(kind,'ellipsis')
        self.assertTrue(np.all(mask[np.all(image==0,axis=2)&(interior>0)]>0))
        self.assertFalse(np.any(mask[interior==0]))

    def test_exclamation_detects_dark_stem_and_dot_despite_faint_jpeg_bridge(self):
        image=np.full((100,80,3),255,np.uint8);inside=np.full((100,80),255,np.uint8)
        for x in (25,40):
            image[20:38,x:x+4]=0;image[40:44,x:x+4]=0;image[38:40,x+1:x+2]=180
        mask,kind=punctuation_mask(image,inside)
        self.assertEqual(kind,'!!')
        self.assertTrue(np.all(mask[np.any(image<220,axis=2)]>0))

    def test_face_marks_or_extra_art_never_count_as_pure_punctuation(self):
        image,inside=dot_fixture();cv2.line(image,(10,80),(65,85),(0,0,0),3)
        self.assertIsNone(punctuation_mask(image,inside))
        image[:]=255;cv2.circle(image,(20,30),6,(0,0,0),2);cv2.circle(image,(55,30),6,(0,0,0),2);cv2.line(image,(35,45),(40,65),(0,0,0),2)
        self.assertIsNone(punctuation_mask(image,inside))

    def test_render_revalidates_original_pixels_and_rejects_tampered_mask(self):
        image,inside=dot_fixture();mask,kind=punctuation_mask(image,inside)
        # Polygon is identical to the fixture's inclusive interior.
        region={'id':'B001','box':[10,10,80,100],'safe':[16,16,65,85],
                'outline':[[15,15],[84,15],[84,104],[15,104]],'source':'…','confidence':0,
                'detector':'ai_balloon','detector_confidence':.93,'ocr_status':'punctuation_geometry',
                'punctuation_kind':kind,'auto_clean':True,'warnings':[],'fill':[255]*3,'clean_method':'punctuation_components'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'masks').mkdir();full=np.full((400,400,3),255,np.uint8);full[10:110,10:90]=image
            Image.fromarray(full).save(root/'original.png');Image.fromarray(mask).save(root/'masks/B001.png')
            manifest={'schema':1,'lang':'jpn_vert','width':400,'height':400,'regions':[region]};write_json(root/'manifest.json',manifest)
            mapping=[{'id':'B001','translation':'...','force':True}]
            self.assertEqual(render_clean(root/'manifest.json',mapping)['applied'],['B001'])
            mask[80:85,20:30]=255;Image.fromarray(mask).save(root/'masks/B001.png')
            self.assertEqual(render_clean(root/'manifest.json',mapping)['applied'],[])
            Image.fromarray(punctuation_mask(image,inside)[0]).save(root/'masks/B001.png');region['detector_confidence']=.89;write_json(root/'manifest.json',manifest)
            self.assertEqual(render_clean(root/'manifest.json',mapping)['applied'],[])


class OCRRetryTests(unittest.TestCase):
    def setUp(self):
        # These tests isolate geometry/OCR rules; model accuracy belongs in native benchmarks.
        self.enterContext(patch('manga_ai.comic_text_ai.detect', return_value=[]))
        self.enterContext(patch('manga_ai.comic_text_ai.detect_multiscale', return_value=[]))
        self.enterContext(patch('manga_ai.head_protection.detect', return_value=[]))
        self.enterContext(patch('manga_ai.model_preview.ctd_mask', side_effect=lambda rgb: np.zeros(rgb.shape[:2], np.uint8)))

    def test_timeout_retains_ai_frame_for_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(240,240),'white').save(root/'input.png')
            candidate={'box':[20,20,60,80],'interior':np.full((80,60),255,np.uint8),'detector':'ai_balloon','detector_confidence':.97}
            with patch('manga_ai.balloon_ai.detect',return_value=[candidate]),patch('manga_ai.engine.region_ocr',side_effect=RuntimeError('timeout')),patch('manga_ai.engine.tesseract_path'),patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']):
                result=analyse(root/'input.png',root/'out',lang='jpn_vert',detector='ai')
            self.assertEqual(len(result['regions']),1)
            self.assertEqual(result['regions'][0]['ocr_status'],'unconfirmed')

    def test_scan_does_not_swallow_cancel_as_ocr_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(240,240),'white').save(root/'input.png')
            candidate={'box':[20,20,60,80],'interior':np.full((80,60),255,np.uint8),'detector':'ai_balloon','detector_confidence':.97}
            with patch('manga_ai.balloon_ai.detect',return_value=[candidate]),patch('manga_ai.engine.region_ocr',side_effect=Cancelled('cancel')),patch('manga_ai.engine.tesseract_path'),patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']),self.assertRaises(Cancelled):
                analyse(root/'input.png',root/'out',lang='jpn_vert',detector='ai')
            self.assertFalse((root/'out/manifest.json').exists())

    def fixture(self):
        rgb=np.full((180,180,3),255,np.uint8);rgb[50:80,60:70]=0
        candidate={'box':[40,30,80,100],'interior':np.full((100,80),255,np.uint8)}
        return rgb,candidate

    def test_retry_selects_japanese_and_keeps_actual_confidence_and_page_coordinates(self):
        rgb,candidate=self.fixture()
        word={'text':'こんにちは','confidence':80,'box':[15,15,30,30]}
        reader=Mock(side_effect=[[word],[{'text':'LATIN','confidence':99,'box':[15,15,30,30]}],[]]);check=Mock()
        result=recover_words(rgb,candidate,[{'text':'foo','confidence':99,'box':[1,1,1,1]}],reader,check)
        self.assertEqual(result[0]['confidence'],80)
        self.assertEqual(result[0]['box'],[55,45,10,10])
        self.assertEqual(result[0]['ocr_pass'],'tight_vertical')
        self.assertEqual(check.call_count,3)

    def test_good_ocr_does_not_spawn_more_processes(self):
        rgb,candidate=self.fixture();reader=Mock();base=[{'text':'こんにちは','confidence':95,'box':[50,50,10,30]}]
        self.assertIs(recover_words(rgb,candidate,base,reader,Mock()),base)
        reader.assert_not_called()

    def test_cancel_during_retry_propagates(self):
        rgb,candidate=self.fixture();reader=Mock()
        with self.assertRaises(Cancelled):recover_words(rgb,candidate,[],reader,Mock(side_effect=Cancelled('cancel')))
        reader.assert_not_called()


if __name__=='__main__':unittest.main()
