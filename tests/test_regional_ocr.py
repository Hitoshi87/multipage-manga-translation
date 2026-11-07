import unittest
from unittest.mock import patch
import numpy as np
from manga_ai.engine import region_ocr

class RegionalOCRTests(unittest.TestCase):
    def test_vertical_coordinates_roundtrip(self):
        image=np.full((100,120,3),255,np.uint8)
        candidate={'box':[20,30,40,50],'interior':np.full((50,40),255,np.uint8)}
        with patch('manga_ai.engine.ocr_words',return_value=[{'text':'太','confidence':90,'box':[22,32,20,24]}]) as ocr:
            result=region_ocr(image,candidate,'jpn_vert')
        self.assertEqual(result[0]['box'],[25,40,10,12])
        self.assertEqual(ocr.call_args.args[2:],(5,8))
        self.assertEqual(ocr.call_args.args[0].shape,(124,104,3))

    def test_horizontal_mode_and_outside_interior_whitened(self):
        image=np.zeros((100,100,3),np.uint8)
        candidate={'box':[10,10,40,40],'interior':np.zeros((40,40),np.uint8)}
        with patch('manga_ai.engine.ocr_words',return_value=[]) as ocr:
            region_ocr(image,candidate,'kor')
        self.assertTrue(np.all(ocr.call_args.args[0]==255))
        self.assertEqual(ocr.call_args.args[2:],(6,8))
