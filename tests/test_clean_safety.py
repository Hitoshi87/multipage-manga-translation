import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from manga_ai.engine import render_clean
from manga_ai.io import write_json, read_json


class CleanSafetyTests(unittest.TestCase):
    def test_review_only_and_missing_mask_have_specific_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'masks').mkdir()
            Image.new('RGB', (100, 100), 'white').save(root / 'original.png')
            Image.new('L', (20, 20), 255).save(root / 'masks/B001.png')
            regions = [
                {'id': 'B001', 'box': [10, 10, 20, 20], 'safe': [10, 10, 20, 20],
                 'fill': [0, 0, 0], 'auto_clean': False, 'confidence': 95,
                 'source': 'text', 'warnings': ['Chữ sát viền']},
                {'id': 'B002', 'box': [50, 50, 20, 20], 'safe': [50, 50, 20, 20],
                 'fill': [0, 0, 0], 'auto_clean': True, 'confidence': 95,
                 'source': 'text', 'warnings': []},
            ]
            write_json(root / 'manifest.json', {'schema': 1, 'lang': 'eng', 'width': 100,
                                                'height': 100, 'regions': regions})
            mapping = [{'id': r['id'], 'translation': 'x', 'clean': True} for r in regions]
            result = render_clean(root / 'manifest.json', mapping)
            self.assertEqual(result['applied'], [])
            self.assertEqual(result['skipped'], ['B001', 'B002'])
            self.assertEqual(result['skip_reason_codes']['B001'], 'AUTO_CLEAN_DISABLED_REVIEW')
            self.assertEqual(result['skip_reason_codes']['B002'], 'TEXT_MASK_FILE_MISSING')
            self.assertIn('Chữ sát viền', result['blocked']['B001'])
            self.assertEqual(read_json(root / 'manifest.json')['clean_skip_reason_codes'], result['skip_reason_codes'])
            self.assertEqual(np.count_nonzero(np.asarray(Image.open(result['overlay']))[:, :, 3]), 0)

    def test_empty_mask_is_not_reported_as_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'masks').mkdir()
            Image.new('RGB', (100, 100), 'white').save(root / 'original.png')
            Image.new('L', (40, 40), 0).save(root / 'masks/B001.png')
            write_json(root / 'manifest.json', {
                'schema': 1, 'lang': 'eng', 'width': 100, 'height': 100,
                'regions': [{'id': 'B001', 'box': [10, 10, 40, 40], 'safe': [10, 10, 40, 40],
                             'fill': [255, 255, 255], 'auto_clean': True,
                             'confidence': 99, 'source': 'hello', 'warnings': []}]})
            result = render_clean(root / 'manifest.json', [{'id': 'B001', 'translation': 'Xin chào'}])
            self.assertEqual(result['applied'], [])
            self.assertEqual(result['skipped'], ['B001'])
            self.assertIn('Mask rỗng', result['blocked']['B001'])

    def render(self, confidence=95, warnings=None, box=None, auto=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'masks').mkdir()
            Image.new('RGB', (200, 200), 'black').save(root / 'original.png')
            box = box or [10, 10, 40, 40]
            mask = np.full((box[3], box[2]), 255, np.uint8)
            Image.fromarray(mask).save(root / 'masks/B001.png')
            write_json(root / 'manifest.json', {
                'schema': 1, 'lang': 'jpn_vert', 'width': 200, 'height': 200,
                'regions': [{'id': 'B001', 'box': box, 'safe': box,
                             'fill': [255, 255, 255], 'auto_clean': auto,
                             'confidence': confidence, 'source': 'こんにちは',
                             'clean_method': 'japanese_bubble_components',
                             'warnings': warnings if warnings is not None else ['Chữ sát viền']}]})
            result = render_clean(root / 'manifest.json',
                                  [{'id': 'B001', 'translation': 'Xin chào', 'force': True}])
            saved = read_json(root / 'manifest.json')
            self.assertEqual(saved['clean_policy_version'], 2)
            self.assertEqual(saved['clean_ids'], result['applied'])
            self.assertEqual(saved['clean_blocked'], result['blocked'])
            pixels = np.array(Image.open(result['overlay']))
            return result, np.count_nonzero(pixels[:, :, 3])

    def test_legacy_face_ocr_cannot_be_forced_even_if_auto(self):
        for confidence in (20.7, 33.0, 36.3, 49.7):
            for auto in (False, True):
                result, changed = self.render(confidence=confidence, auto=auto)
                self.assertEqual(result['applied'], [])
                self.assertIn('B001', result['blocked'])
                self.assertEqual(changed, 0)

    def test_art_warning_blocks_even_high_confidence_override(self):
        result, changed = self.render(confidence=96, warnings=['Nền/chi tiết chưa đủ tin cậy'])
        self.assertEqual(result['skipped'], ['B001'])
        self.assertEqual(changed, 0)

    def test_large_merged_region_remains_review_only(self):
        result, changed = self.render(box=[10, 10, 100, 80], auto=True)
        self.assertEqual(result['applied'], [])
        self.assertEqual(changed, 0)

    def test_strong_edge_only_dialogue_still_allows_individual_review(self):
        result, changed = self.render()
        self.assertEqual(result['applied'], ['B001'])
        self.assertEqual(changed, 1600)


if __name__ == '__main__':
    unittest.main()
