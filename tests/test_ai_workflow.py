import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from manga_ai.io import parse_translations, import_translation_folder
from manga_ai import balloon_ai
from manga_ai.cli import main
from manga_ai.engine import panel_order, unexplained_ink_limit, analyse, render_clean


class TranslationFolderTests(unittest.TestCase):
    def test_batch_ignores_generated_clean_and_typeset_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'input';src.mkdir()
            for name in ('005.jpg','005_clean.png','005_typeset_2.png'):(src/name).touch()
            with patch('manga_ai.engine.analyse',return_value={'manifest':'unused','regions':[]}) as scan:
                self.assertEqual(main(['scan',str(src),'--out',str(root/'out')]),0)
            self.assertEqual(scan.call_count,1)
            self.assertEqual(scan.call_args.args[0].name,'005.jpg')

    def test_vietnamese_markers_and_unicode_linebreak(self):
        parsed = parse_translations('[Trang 013]\nTôi khỏe.\\nCảm ơn!\n[PAGE 14]\nVâng.')
        self.assertEqual(parsed['pages']['13'], ['Tôi khỏe.\nCảm ơn!'])
        self.assertTrue(parsed['filename_pages'])

    def test_polished_priority_and_empty_page_retained(self):
        with tempfile.TemporaryDirectory(prefix='bản dịch ') as tmp:
            root = Path(tmp)
            (root/'Menu_1.txt').write_text('[Trang 003]\nCũ', encoding='utf-8')
            (root/'Menu_1_polished.txt').write_text('[Trang 003]\nĐã sửa\n[Trang 004]\n', encoding='utf-8')
            (root/'Menu_2.txt').write_text('[Trang 010]\nXin chào', encoding='utf-8')
            parsed = import_translation_folder(root)
            self.assertEqual(parsed['pages'], {'3': ['Đã sửa'], '4': [], '10': ['Xin chào']})
            self.assertEqual(len(parsed['files']), 2)

    def test_overlapping_chapters_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('a.txt', 'b.txt'):
                (root/name).write_text('[Trang 5]\nXin chào', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Trùng trang'):
                import_translation_folder(root)


class ModelMaskTests(unittest.TestCase):
    def setUp(self):
        # These tests isolate geometry/OCR rules; model accuracy belongs in native benchmarks.
        self.enterContext(patch('manga_ai.comic_text_ai.detect', return_value=[]))
        self.enterContext(patch('manga_ai.comic_text_ai.detect_multiscale', return_value=[]))
        self.enterContext(patch('manga_ai.head_protection.detect', return_value=[]))
        self.enterContext(patch('manga_ai.model_preview.ctd_mask', side_effect=lambda rgb: np.zeros(rgb.shape[:2], np.uint8)))

    def test_recognized_ink_missing_from_clean_mask_is_not_auto_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pixels = np.full((400, 400, 3), 255, np.uint8)
            pixels[60:70, 60:70] = 0
            Image.fromarray(pixels).save(root/'page.png')
            candidate = {'box': [20, 20, 100, 100], 'interior': np.full((100, 100), 255, np.uint8),
                         'detector': 'ai_balloon', 'detector_confidence': .97}
            word = {'box': [60, 60, 10, 10], 'text': 'こんにちは', 'confidence': 95}
            with patch.object(balloon_ai, 'detect', return_value=[candidate]), \
                 patch('manga_ai.engine.region_ocr', return_value=[word]), \
                 patch('manga_ai.engine.japanese_bubble_ink', return_value=np.zeros((100, 100), np.uint8)), \
                 patch('manga_ai.engine.tesseract_path'), \
                 patch('manga_ai.engine.pytesseract.get_languages', return_value=['jpn_vert']):
                result = analyse(root/'page.png', root/'out', lang='jpn_vert', detector='ai')
            region = result['regions'][0]
            self.assertFalse(region['auto_clean'])
            self.assertIn('Mask chưa phủ hết chữ đã nhận diện', region['warnings'])
            clean = render_clean(result['manifest'], [{'id': region['id'], 'translation': 'Xin chào', 'force': True}])
            self.assertEqual(clean['applied'], [])

    def test_unknown_japanese_text_keeps_balloon_for_mapping_without_erasable_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(240,240),'white').save(root/'page.png')
            candidate={'box':[20,20,60,80],'interior':np.full((80,60),255,np.uint8),
                       'detector':'ai_balloon','detector_confidence':.97}
            with patch.object(balloon_ai,'detect',return_value=[candidate]), patch('manga_ai.engine.region_ocr',return_value=[]), patch('manga_ai.engine.tesseract_path'), patch('manga_ai.engine.pytesseract.get_languages',return_value=['jpn_vert']):
                result=analyse(root/'page.png',root/'out',lang='jpn_vert',detector='ai')
            self.assertEqual(len(result['regions']),1)
            self.assertFalse(result['regions'][0]['auto_clean'])
            self.assertEqual(result['regions'][0]['ocr_status'],'unconfirmed')
            clean=render_clean(result['manifest'],[{'id':'B001','translation':'...','force':True}])
            self.assertEqual(clean['applied'],[])
            self.assertEqual(np.count_nonzero(np.array(Image.open(clean['overlay']))[:,:,3]),0)

    def test_model_checksum_rejected_before_loading_external_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'bad.onnx';file.write_bytes(b'wrong graph')
            balloon_ai.session.cache_clear()
            with patch.object(balloon_ai,'MODEL',file), self.assertRaisesRegex(RuntimeError,'checksum'):
                balloon_ai.session()
            balloon_ai.session.cache_clear()

    def test_extra_ink_budget_requires_both_strong_ai_and_japanese_ocr(self):
        strong={'detector':'ai_balloon','detector_confidence':.97}
        self.assertEqual(unexplained_ink_limit(strong,'こんにちは',90),.06)
        self.assertEqual(unexplained_ink_limit(strong,'と',90),.015)
        self.assertEqual(unexplained_ink_limit(strong,'こんにちは',65),.015)
        self.assertEqual(unexplained_ink_limit({'detector':'ai_balloon','detector_confidence':.8},'こんにちは',90),.015)
        self.assertEqual(unexplained_ink_limit({},'こんにちは',90),.015)
    def test_tall_panel_does_not_interrupt_right_column_reading(self):
        left=[0,0,100,300];right_top=[120,0,100,100];right_bottom=[120,120,100,180]
        self.assertEqual(panel_order([left,right_bottom,right_top],True),[right_top,right_bottom,left])
        self.assertEqual(panel_order([left,right_bottom,right_top],False),[left,right_top,right_bottom])

    def test_segment_mask_preserves_curved_shape_and_scales_coordinates(self):
        raw = np.zeros((1, 37, 1), np.float32)
        raw[0, :5, 0] = [32, 32, 40, 40, .97]
        raw[0, 5, 0] = 1
        proto = np.zeros((1, 32, 16, 16), np.float32)
        yy, xx = np.ogrid[:16, :16]
        proto[0, 0] = np.where((xx-8)**2+(yy-8)**2 < 25, 10, -10)
        class Runner:
            def get_inputs(self):
                return [type('Input', (), {'name':'images'})()]
            def run(self, _, inputs):
                assert inputs['images'].shape == (1, 3, 64, 64)
                return raw, proto
        with patch.object(balloon_ai, 'SIZE', 64), patch.object(balloon_ai, 'session', return_value=Runner()):
            found = balloon_ai.detect(np.full((128, 128, 3), 255, np.uint8))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['box'], [24, 24, 80, 80])
        mask = found[0]['interior']
        self.assertEqual(mask[0,0], 0)
        self.assertEqual(mask[40,40], 255)
        self.assertLess(np.count_nonzero(mask), mask.size*.85)


if __name__ == '__main__':
    unittest.main()
