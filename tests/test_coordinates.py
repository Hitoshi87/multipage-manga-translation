import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from manga_ai.coordinates import analysis_image, project_box, project_regions
from manga_ai.engine import analyse, render_clean, panel_rectangles, reading_order
from manga_ai.io import validate_manifest


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('manga_ai.comic_text_ai.detect', return_value=[]))
        self.enterContext(patch('manga_ai.head_protection.detect', return_value=[]))
        self.enterContext(patch('manga_ai.model_preview.ctd_mask', side_effect=lambda rgb: np.zeros(rgb.shape[:2], np.uint8)))

    def test_narrow_tall_panel_keeps_its_dialogue_before_lower_row(self):
        gray=np.full((1440,1008),255,np.uint8)
        for x,y,w,h in ([80,96,280,610],[378,96,117,610],[508,96,200,225],[508,730,200,250]):
            cv2.rectangle(gray,(x,y),(x+w-1,y+h-1),0,2)
        panels=panel_rectangles(gray)
        self.assertTrue(any(p[0]<=430<p[0]+p[2] and p[1]<=150<p[1]+p[3] for p in panels))
        narrow={'box':[410,130,35,80],'name':'narrow'};lower={'box':[530,750,70,100],'name':'lower'}
        self.assertEqual([r['name'] for r in reading_order([lower,narrow],True,panels)],['narrow','lower'])

    def test_only_large_ai_inputs_are_normalized(self):
        rgb=np.zeros((4320,3024,3),np.uint8)
        self.assertEqual(analysis_image(rgb,'ai').shape,(1440,1008,3))
        self.assertIs(analysis_image(rgb,'opencv'),rgb)
        small=rgb[:100,:80]
        self.assertIs(analysis_image(small,'ai'),small)

    def test_projected_safe_box_rounds_inwards_and_rows_stay_contiguous(self):
        region={'box':[3,5,30,40],'safe':[7,10,20,25],'outline':[[3,5],[32,5],[32,44]],
                'clean_method':'ocr_boxes','_mask':np.ones((40,30),np.uint8)*255,
                'shape':{'rows':[[y,7,27] for y in range(10,35)],'center':[17,22.5]}}
        project_regions([region],[101,144],[215,307])
        self.assertEqual(region['box'],project_box([3,5,30,40],[101,144],[215,307]))
        self.assertEqual(region['_mask'].shape,tuple(region['box'][2:][::-1]))
        rows=region['shape']['rows']
        self.assertEqual([r[0] for r in rows],list(range(rows[0][0],rows[-1][0]+1)))
        sx,sy,sw,sh=region['safe'];x,y,w,h=region['box']
        self.assertTrue(x<=sx<sx+sw<=x+w and y<=sy<sy+sh<=y+h)
        self.assertTrue(all(r[1]>=7*215/101 and r[2]<=27*215/101 for r in rows))

    def test_native_pixels_preserved_and_scaled_punctuation_revalidated(self):
        # Inference is canonical; PSD images/masks remain at original resolution.
        canonical=np.full((1440,1008,3),255,np.uint8)
        for xx in (125,150):
            for yy in range(120,171,10):canonical[yy:yy+3,xx:xx+3]=0
        candidate={'box':[100,100,80,100],'interior':np.full((100,80),255,np.uint8),
                   'detector':'ai_balloon','detector_confidence':.97}
        for size in ((3024,4320),(2151,3073)):
            with self.subTest(size=size),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);original=cv2.resize(canonical,size,interpolation=cv2.INTER_NEAREST)
                Image.fromarray(original).save(root/'nguồn có dấu.png')
                with patch('manga_ai.balloon_ai.detect',return_value=[copy.deepcopy(candidate)]) as detect,patch('manga_ai.engine.tesseract_path'),patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']),patch('manga_ai.engine.region_ocr') as ocr:
                    data=analyse(root/'nguồn có dấu.png',root/'out',lang='jpn_vert',detector='ai')
                self.assertEqual(detect.call_args.args[0].shape,(1440,1008,3))
                ocr.assert_not_called()
                self.assertEqual(data['analysis_size'],[1008,1440])
                self.assertEqual((data['width'],data['height']),size)
                self.assertEqual(data['regions'][0]['ocr_status'],'punctuation_geometry')
                np.testing.assert_array_equal(np.array(Image.open(root/'out/original.png')),original)
                result=render_clean(data['manifest'],[{'id':'B001','translation':'…'}])
                self.assertEqual(result['applied'],['B001'])
                clean=np.array(Image.open(root/'out/clean.png'))
                overlay=np.array(Image.open(result['overlay']))
                np.testing.assert_array_equal(clean[overlay[:,:,3]==0],original[overlay[:,:,3]==0])
                self.assertFalse(np.any(clean[original[:,:,0]<130]<220))
                mask=root/'out/masks/B001.png';pixels=np.array(Image.open(mask));pixels[0,0]=255
                Image.fromarray(pixels).save(mask)
                self.assertEqual(render_clean(data['manifest'],[{'id':'B001','translation':'…','force':True}])['applied'],[])
                broken=copy.deepcopy(data);broken['analysis_size']=[size[0]+1,1440]
                with self.assertRaises(ValueError):validate_manifest(broken)
                broken=copy.deepcopy(data);broken['regions'][0]['analysis_geometry']['box'][0]=10000
                with self.assertRaises(ValueError):validate_manifest(broken)


if __name__=='__main__':unittest.main()
