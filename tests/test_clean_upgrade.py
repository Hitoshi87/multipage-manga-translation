import unittest
from unittest.mock import patch

import cv2
import numpy as np

from manga_ai.clean_refinement import (local_inpaint, complete_glyphs, enclosed_text_support,
                                      flat_backgrounds, coverage_report)
from manga_ai.comic_text_ai import detect_multiscale
from manga_ai.model_preview import create_clean


class CleanUpgradeTest(unittest.TestCase):
    def test_local_inpaint_retains_thin_strokes_at_original_resolution(self):
        rgb = np.full((1800, 1400, 3), 123, np.uint8)
        mask = np.zeros(rgb.shape[:2], np.uint8)
        mask[400:1100, 700] = 1
        mask[1400, 100:900] = 1
        sizes = []

        def infer(image, selection):
            sizes.append(image.shape)
            self.assertLessEqual(max(image.shape[:2]), 768)
            self.assertEqual(image.shape[0] % 8, 0)
            self.assertTrue(np.any(selection))
            return np.full_like(image, 240)

        result = local_inpaint(rgb, mask, infer)
        self.assertGreater(len(sizes), 1)
        self.assertTrue(np.all(result[mask > 0] == 240))
        self.assertTrue(np.array_equal(result[mask == 0], rgb[mask == 0]))

    def test_closed_balloon_exemption_does_not_extend_to_face_or_gutter(self):
        rgb = np.full((500, 500, 3), 255, np.uint8)
        cv2.ellipse(rgb, (200, 130), (75, 65), 0, 0, 360, (0, 0, 0), 3)
        cv2.putText(rgb, 'HI', (180, 145), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        ds = [{'box': [175, 120, 45, 30], 'confidence': .99, 'kind': 'in_bubble'}]
        support = enclosed_text_support(rgb, ds)
        self.assertEqual(support[130, 190], 1)
        self.assertEqual(support[200, 190], 0)
        self.assertEqual(support[10, 10], 0)
        rgb[60:100, 180:220] = 255  # Open the outline into the page gutter.
        self.assertFalse(np.any(enclosed_text_support(rgb, ds)))

    def test_mask_completion_recovers_glyph_but_rejects_long_border(self):
        rgb = np.full((200, 200, 3), 250, np.uint8)
        rgb[60:75, 70:85] = 0
        rgb[40:120, 110:113] = 0
        mask = np.zeros((200, 200), np.uint8)
        mask[64:70, 74:80] = 1
        mask[45:115, 110:113] = 1
        ds = [{'box': [50, 40, 70, 80], 'confidence': .99, 'kind': 'in_bubble'}]
        result = complete_glyphs(rgb, mask, ds)
        self.assertTrue(np.all(result[60:75, 70:85]))
        self.assertEqual(result[60, 111], 0)

    def test_flat_paper_uses_local_shade_and_only_masked_pixels(self):
        rgb = np.full((100, 120, 3), 248, np.uint8)
        rgb[40:50, 40:50] = 0
        mask = np.zeros((100, 120), np.uint8); mask[38:52, 38:52] = 1
        ds = [{'box': [25, 25, 50, 50], 'confidence': .99, 'kind': 'in_bubble'}]
        result, flat = flat_backgrounds(rgb, mask, ds)
        self.assertEqual(int(result[45, 45, 0]), 248)
        self.assertTrue(np.array_equal(result[mask == 0], rgb[mask == 0]))
        self.assertTrue(np.array_equal(flat, mask))

    def test_zoom_deduplicates_subgroups_and_rejects_clipped_edges(self):
        base = {'box': [100, 100, 150, 150], 'confidence': .95, 'kind': 'in_bubble'}
        subset = {'box': [120, 120, 60, 80], 'confidence': .97, 'kind': 'in_bubble'}
        missed = {'box': [400, 400, 40, 70], 'confidence': .96, 'kind': 'in_bubble'}
        clipped = {'box': [1, 100, 30, 50], 'confidence': .98, 'kind': 'in_bubble'}
        with patch('manga_ai.comic_text_ai.detect', side_effect=[[base], [subset, missed], [clipped], [], []]):
            found = detect_multiscale(np.full((1000, 1000, 3), 255, np.uint8))
        self.assertEqual([p['box'] for p in found], [base['box'], missed['box']])

    def test_backend_selection_and_legacy_lama_flag(self):
        rgb = np.zeros((100, 100, 3), np.uint8)
        mask = np.zeros((100, 100), np.uint8); mask[40:45, 40:45] = 1
        with patch('manga_ai.model_preview.detailed_mask', return_value=(mask, [])), \
             patch('manga_ai.aot_inpaint.infer', return_value=np.full((152, 152, 3), 200, np.uint8)) as aot, \
             patch('manga_ai.model_preview.lama_clean', return_value=np.full_like(rgb, 150)) as lama:
            create_clean(rgb, 'ctd', True)
            self.assertEqual(lama.call_count, 1)
            create_clean(rgb, 'ctd', True, inpaint='aot')
            self.assertEqual(aot.call_count, 1)
            self.assertEqual(lama.call_count, 1)
        with self.assertRaises(ValueError): create_clean(rgb, 'ctd', inpaint='unknown')

    def test_residual_report_flags_untouched_lettering(self):
        rgb = np.full((100, 100, 3), 255, np.uint8); rgb[30:50, 30:40] = 0
        ds = [{'box': [20, 20, 40, 40], 'confidence': .99, 'kind': 'in_bubble'}]
        report = coverage_report(rgb, rgb, np.zeros((100, 100), np.uint8), ds)
        self.assertEqual(report['suspect_count'], 1)
        self.assertEqual(report['suspects'][0]['uncovered_ink_fraction'], 1)


if __name__ == '__main__':
    unittest.main()
