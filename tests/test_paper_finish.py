import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from manga_ai.paper_finish import finish_overlay, finish_region, paper_colour


def shape_for(box, inset=10):
    x, y, w, h = box
    return {'rows': [[yy, x + inset, x + w - inset] for yy in range(y + inset, y + h - inset)]}


def scene():
    """Opaque balloon, paper 255, a glyph with a faint halo; the clean patch is a slightly darker 253."""
    rgb = np.full((300, 300, 3), 255, np.uint8)
    cv2.rectangle(rgb, (40, 40), (260, 260), (30, 30, 30), 3)             # the outline, never part of the text
    text = np.zeros((300, 300), np.uint8)
    cv2.putText(text, 'W', (120, 170), cv2.FONT_HERSHEY_SIMPLEX, 3, 255, 8)
    glyph = text > 0
    halo = cv2.dilate(text, np.ones((9, 9), np.uint8)) > 0
    rgb[halo] = (238, 238, 238)                                           # faint fringe around the ink
    rgb[glyph] = (20, 20, 20)
    overlay = np.zeros((300, 300, 4), np.uint8)
    core = cv2.dilate(text, np.ones((3, 3), np.uint8)) > 0
    overlay[core, :3] = 253
    overlay[core, 3] = 255                                                # what the engine painted
    return rgb, overlay, glyph, halo, shape_for([40, 40, 220, 220])


class PaperFinishTests(unittest.TestCase):
    def test_patch_takes_the_real_paper_tone_and_the_fringe_is_repainted(self):
        rgb, overlay, glyph, halo, shape = scene()
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        count = finish_region(rgb, gray, overlay, shape)
        self.assertGreater(count, 0)
        painted = overlay[:, :, 3] > 0
        self.assertTrue((overlay[painted][:, :3] == 255).all())            # paper, not 253
        self.assertTrue(painted[halo & ~glyph].all())                      # the fringe is covered too
        composed = rgb.copy()
        composed[painted] = overlay[painted][:, :3]
        interior = np.zeros(gray.shape, bool)
        interior[55:245, 55:245] = True
        self.assertEqual(int((composed.mean(axis=2)[interior] < 254).sum()), 0)   # no ghost left inside

    def test_nothing_outside_the_inset_interior_or_dark_is_touched(self):
        rgb, overlay, glyph, halo, shape = scene()
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        finish_region(rgb, gray, overlay, shape)
        painted = overlay[:, :, 3] > 0
        self.assertFalse(painted[:50, :].any() or painted[:, :50].any())    # outline and outside stay untouched
        cv2.rectangle(rgb, (60, 60), (80, 80), (20, 20, 20), -1)            # artwork inside: never repainted
        rgb2, overlay2, *_ = scene()
        rgb2[60:80, 60:80] = 20
        finish_region(rgb2, cv2.cvtColor(rgb2, cv2.COLOR_RGB2GRAY), overlay2, shape)
        self.assertFalse((overlay2[60:80, 60:80, 3] > 0).any())

    def test_a_balloon_over_screentone_is_skipped(self):
        rgb, overlay, glyph, halo, shape = scene()
        tone = (np.indices((300, 300)).sum(axis=0) % 4 < 2)
        rgb[tone] = (170, 170, 170)                                         # not flat paper
        before = overlay.copy()
        self.assertEqual(finish_region(rgb, cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), overlay, shape), 0)
        self.assertTrue(np.array_equal(overlay, before))

    def test_overlay_is_rewritten_only_for_listed_regions_and_ai_redraws_are_skipped(self):
        rgb, overlay, *_ = scene()
        shape = shape_for([40, 40, 220, 220])
        with tempfile.TemporaryDirectory() as tmp:
            Image.fromarray(rgb).save(Path(tmp) / 'original.png')
            Image.fromarray(overlay, 'RGBA').save(Path(tmp) / 'overlay.png')
            self.assertEqual(finish_overlay(Path(tmp) / 'original.png', Path(tmp) / 'overlay.png', {'B001': shape}, skip={'B001'}), {})
            self.assertIn('B001', finish_overlay(Path(tmp) / 'original.png', Path(tmp) / 'overlay.png', {'B001': shape}))
            saved = np.asarray(Image.open(Path(tmp) / 'overlay.png').convert('RGBA'))
            self.assertTrue((saved[saved[:, :, 3] > 0][:, :3] == 255).all())

    def test_paper_colour_is_the_most_frequent_value_not_the_median(self):
        rgb = np.full((60, 60, 3), 255, np.uint8)
        rgb[:20] = 245                                                       # a third of the pixels slightly darker
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        self.assertEqual(paper_colour(rgb, gray, np.ones((60, 60), bool)), [255, 255, 255])


if __name__ == '__main__':
    unittest.main()
