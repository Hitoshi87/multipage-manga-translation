import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from manga_ai.shape_refine import attach_refined_shapes, refine_shape
from manga_ai.clean_layers import protect_opaque_balloons


def page(draw):
    gray = np.full((400, 500), 255, np.uint8)
    draw(gray)
    return gray


def balloon(gray, cx=250, cy=200, rx=120, ry=150, outline=3):
    cv2.ellipse(gray, (cx, cy), (rx, ry), 0, 0, 360, 40, outline)
    return [cx - rx - outline, cy - ry - outline, 2 * rx + 2 * outline + 1, 2 * ry + 2 * outline + 1]


def mask_rows(box, shift_right_cut=0, inset=12):
    """A detector-style mask: the eroded interior, optionally cut short on the right."""
    x, y, w, h = box
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2 - inset, h / 2 - inset
    rows = []
    for yy in range(int(cy - ry) + 1, int(cy + ry)):
        k = np.sqrt(max(0, 1 - ((yy - cy) / ry) ** 2))
        rows.append([yy, int(cx - rx * k), int(cx + rx * k) - shift_right_cut])
    return {'rows': rows, 'center': [cx - shift_right_cut / 2, cy], 'box': [int(cx - rx), int(cy - ry), int(2 * rx), int(2 * ry)]}


class ShapeRefineTests(unittest.TestCase):
    def test_pale_artwork_leak_is_not_a_white_balloon(self):
        gray=np.full((400,500),210,np.uint8)
        cv2.ellipse(gray,(280,200),(120,140),0,0,360,255,-1)
        cv2.ellipse(gray,(280,200),(120,140),0,0,360,20,3)
        gray[195:206,155:165]=210  # pale gap connects exterior only at threshold 200
        # Detector box incorrectly includes the pale artwork to the left.
        shape=refine_shape(gray,{'box':[90,55,315,290]},None)
        self.assertIsNotNone(shape)
        self.assertGreaterEqual(shape['brightness'],220)
        self.assertGreater(shape['box'][0],155)

    def test_clean_overlay_cannot_erase_pale_artwork_outside_true_bubble(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gray=np.full((400,500),210,np.uint8)
            cv2.ellipse(gray,(280,200),(120,140),0,0,360,255,-1)
            cv2.ellipse(gray,(280,200),(120,140),0,0,360,20,3)
            gray[195:206,155:165]=210
            Image.fromarray(gray).save(root/'original.png')
            overlay=np.zeros((400,500,4),np.uint8)
            overlay[180:190,110:120]=[255,255,255,255]  # incorrect clean on artwork
            overlay[180:190,260:270]=[255,255,255,255]  # real text in balloon
            Image.fromarray(overlay).save(root/'overlay.png')
            region={'id':'B001','box':[90,55,315,290],'detector':'ai_balloon','auto_clean':True}
            result={'overlay':str(root/'overlay.png'),'applied':['B001']}
            shape=protect_opaque_balloons(result,root/'manifest.json',{'B001':region})
            saved=np.asarray(Image.open(root/'overlay.png'))
            self.assertIn('B001',shape)
            self.assertEqual(int(saved[180:190,110:120,3].sum()),0)
            self.assertEqual(int(saved[180:190,260:270,3].sum()),25500)
            self.assertEqual(result['geometry_clipped']['B001'],100)
            self.assertIn('B001',result['review_ids'])
    def test_a_mask_cut_short_on_the_right_is_measured_back_to_the_real_balloon(self):
        gray = page(lambda g: None)
        box = balloon(gray)
        short = mask_rows(box, shift_right_cut=45)
        refined = refine_shape(gray, {'box': box}, short)
        self.assertIsNotNone(refined)
        mid = refined['rows'][len(refined['rows']) // 2]
        true_centre = box[0] + box[2] / 2
        self.assertLess(abs((mid[1] + mid[2]) / 2 - true_centre), 3)             # centred on the true balloon
        self.assertGreater(mid[2] - mid[1], short['rows'][len(short['rows']) // 2][2] - short['rows'][len(short['rows']) // 2][1] + 30)

    def test_old_text_remnants_inside_the_balloon_are_filled(self):
        gray = page(lambda g: None)
        box = balloon(gray)
        cv2.putText(gray, 'ab', (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 30, 4)   # leftovers that were not cleaned
        refined = refine_shape(gray, {'box': box}, mask_rows(box))
        self.assertIsNotNone(refined)
        row = next(r for r in refined['rows'] if r[0] == 190)
        self.assertGreater(row[2] - row[1], 150)                                   # the remnants do not split the row

    def test_a_gap_in_the_outline_is_a_leak_and_is_rejected(self):
        gray = page(lambda g: None)
        box = balloon(gray)
        cv2.line(gray, (250 + 118, 150), (250 + 130, 250), 255, 9)                  # erase part of the right outline
        self.assertIsNone(refine_shape(gray, {'box': box}, mask_rows(box)))

    def test_a_balloon_over_artwork_is_not_bright_and_keeps_the_mask(self):
        gray = page(lambda g: None)
        box = balloon(gray)
        art = np.random.default_rng(3).integers(0, 120, gray.shape).astype(np.uint8)
        inside = np.zeros_like(gray)
        cv2.ellipse(inside, (250, 200), (118, 148), 0, 0, 360, 255, -1)
        gray[inside > 0] = art[inside > 0]
        self.assertIsNone(refine_shape(gray, {'box': box}, mask_rows(box)))

    def test_attach_uses_the_cleaned_page_and_only_ai_balloons(self):
        with tempfile.TemporaryDirectory() as tmp:
            gray = page(lambda g: None)
            box = balloon(gray)
            rgb = np.stack([gray] * 3, axis=-1)
            cv2.putText(rgb, 'TEXT', (200, 205), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 5)   # the old text
            Image.fromarray(rgb).save(Path(tmp) / 'original.png')
            overlay = np.zeros((400, 500, 4), np.uint8)
            overlay[170:230, 180:330] = (255, 255, 255, 255)                          # the clean patch over the text
            Image.fromarray(overlay, 'RGBA').save(Path(tmp) / 'overlay.png')
            result = {'applied': ['B001', 'B002'], 'overlay': str(Path(tmp) / 'overlay.png')}
            regions = {'B001': {'id': 'B001', 'box': box, 'detector': 'ai_balloon', 'shape': mask_rows(box)},
                       'B002': {'id': 'B002', 'box': box, 'detector': 'opencv', 'shape': mask_rows(box)}}
            attach_refined_shapes(result, Path(tmp) / 'manifest.json', regions)
        self.assertEqual(list(result['refined_shapes']), ['B001'])
        self.assertEqual(result['refined_shapes']['B001']['source'], 'cleaned_pixels')

    def test_a_missing_page_never_raises(self):
        result = {'applied': ['B001'], 'overlay': '/nope/overlay.png'}
        attach_refined_shapes(result, '/nope/manifest.json', {'B001': {'id': 'B001', 'box': [0, 0, 50, 50], 'detector': 'ai_balloon'}})
        self.assertEqual(result['refined_shapes'], {})
        self.assertIn('shape_refine_error', result)


if __name__ == '__main__':
    unittest.main()
