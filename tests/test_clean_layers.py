import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from manga_ai.clean_layers import assign_pixels, attach_region_layers, split_overlay


def region(rid, box, polygon=None):
    x, y, w, h = box
    return {'id': rid, 'box': box, 'outline': polygon or [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]}


def overlay_file(tmp, patches, size=(300, 200)):
    rgba = np.zeros((size[1], size[0], 4), np.uint8)
    for (x, y, w, h), colour in patches:
        rgba[y:y + h, x:x + w] = (*colour, 255)
    path = Path(tmp) / 'overlay.png'
    Image.fromarray(rgba, 'RGBA').save(path)
    return path, rgba


class CleanLayerTests(unittest.TestCase):
    def test_each_bubble_gets_a_cropped_layer_at_its_page_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, rgba = overlay_file(tmp, [((20, 30, 60, 40), (255, 255, 255)), ((200, 100, 70, 50), (250, 250, 250))])
            layers = split_overlay(path, [region('B001', [10, 20, 90, 70]), region('B002', [190, 90, 100, 80])], Path(tmp) / 'out')
            by_id = {l['id']: l for l in layers}
            self.assertEqual((by_id['B001']['x'], by_id['B001']['y'], by_id['B001']['w'], by_id['B001']['h']), (20, 30, 60, 40))
            self.assertEqual((by_id['B002']['x'], by_id['B002']['y']), (200, 100))
            self.assertNotIn('REST', by_id)
            # The pieces recombine into exactly the original overlay.
            canvas = np.zeros_like(rgba)
            for l in layers:
                piece = np.asarray(Image.open(l['file']).convert('RGBA'))
                canvas[l['y']:l['y'] + l['h'], l['x']:l['x'] + l['w']] |= piece
            self.assertTrue(np.array_equal(canvas, rgba))

    def test_nested_bubbles_keep_their_own_pixels(self):
        alpha = np.zeros((100, 100), np.uint8)
        alpha[10:90, 10:90] = 255
        big = region('BIG', [0, 0, 100, 100])
        small = region('SMALL', [40, 40, 20, 20])
        labels = assign_pixels(alpha, [big, small], margin=0)
        self.assertEqual(labels[50, 50], 1)       # inside the smaller outline
        self.assertEqual(labels[15, 15], 0)

    def test_pixels_outside_every_outline_join_the_bubble_they_overlap_most(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = overlay_file(tmp, [((20, 20, 40, 40), (255, 255, 255)), ((100, 20, 6, 6), (255, 255, 255))])
            layers = split_overlay(path, [region('B001', [15, 15, 50, 50]), region('B002', [90, 10, 40, 40])], Path(tmp) / 'out', margin=0)
            self.assertEqual({l['id'] for l in layers}, {'B001', 'B002'})

    def test_an_empty_overlay_yields_no_layers_and_failure_falls_back_to_a_single_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = overlay_file(tmp, [])
            self.assertEqual(split_overlay(path, [region('B001', [0, 0, 10, 10])], Path(tmp) / 'out'), [])
            result = {'overlay': str(Path(tmp) / 'missing.png'), 'applied': ['B001']}
            attach_region_layers(result, Path(tmp) / 'manifest.json', {'B001': region('B001', [0, 0, 10, 10])})
            self.assertEqual(result['layer_split'], 'single')
            self.assertIn('layer_split_error', result)

    def test_attach_adds_region_layers_for_applied_and_ai_redrawn_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = overlay_file(tmp, [((20, 30, 60, 40), (255, 255, 255)), ((200, 100, 70, 50), (250, 250, 250))])
            result = {'overlay': str(path), 'applied': ['B001'], 'art_inpaint_ids': ['B002']}
            attach_region_layers(result, Path(tmp) / 'manifest.json',
                                 {'B001': region('B001', [10, 20, 90, 70]), 'B002': region('B002', [190, 90, 100, 80])})
            self.assertEqual(result['layer_split'], 'regions')
            self.assertEqual({l['id'] for l in result['region_layers']}, {'B001', 'B002'})


if __name__ == '__main__':
    unittest.main()
