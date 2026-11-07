import unittest
import numpy as np
from manga_ai.engines import role_guard as g


def rect_shape(x, y, w, h):
    return {'rows': [[row, x, x + w] for row in range(y, y + h)]}


def oval_shape(cx, cy, rx, ry):
    rows = []
    for row in range(cy - ry, cy + ry):
        half = int(rx * (1 - ((row - cy) / ry) ** 2) ** .5)
        rows.append([row, cx - half, cx + half])
    return {'rows': rows}


def region(rid, detector, shape=None, box=(0, 0, 60, 80), parent=None):
    return {'id': rid, 'box': list(box), 'safe': list(box), 'detector': detector,
            'shape': shape, 'parent_box': parent}


def page(ink_fraction):
    gray = np.full((100, 100), 255, np.uint8)
    gray[:int(80 * ink_fraction), :60] = 0  # thick dark block inside the box
    return gray


class RoleGuardTests(unittest.TestCase):
    def test_free_text_is_never_processed_but_text_inside_a_bubble_is(self):
        self.assertTrue(g.is_free_text(region('B1', 'comic_text_ai')))
        self.assertFalse(g.is_free_text(region('B2', 'comic_text_ai', parent=[0, 0, 90, 90])))
        self.assertFalse(g.is_free_text(region('B3', 'ai_balloon')))

    def test_heavy_rectangular_banner_is_guarded(self):
        r = region('B1', 'ai_balloon', rect_shape(0, 0, 60, 80))
        self.assertEqual(g.guarded_regions([r], {'B1'}, page(.5)), {'B1': g.BANNER_REASON})

    def test_ordinary_and_hand_drawn_bubbles_are_not_guarded(self):
        oval = region('B1', 'ai_balloon', oval_shape(30, 40, 30, 40))
        self.assertEqual(g.guarded_regions([oval], {'B1'}, page(.5)), {})  # heavy ink alone is not enough
        jagged = region('B2', 'ai_balloon', {'rows': [[i, 5 + i % 7, 55 - i % 5] for i in range(80)]})
        self.assertEqual(g.guarded_regions([jagged], {'B2'}, page(.5)), {})

    def test_thin_text_caption_box_is_not_guarded(self):
        caption = region('B1', 'ai_balloon', rect_shape(0, 0, 60, 80))
        self.assertEqual(g.guarded_regions([caption], {'B1'}, page(.05)), {})

    def test_unselected_regions_are_ignored(self):
        self.assertEqual(g.guarded_regions([region('B1', 'comic_text_ai')], set(), page(0)), {})

    def test_restore_only_touches_the_guarded_box_and_spares_neighbours(self):
        h = w = 40
        original = np.zeros((h, w, 3), np.uint8)
        clean = original.copy(); clean[:, :] = 255
        mask = np.ones((h, w), bool)
        regions = [{'id': 'A', 'box': [0, 0, 20, 40]}, {'id': 'B', 'box': [10, 0, 30, 40]}]
        out, out_mask, counts = g.restore_regions(original, clean, mask, regions, {'A': 'x'}, {'A', 'B'})
        self.assertTrue((out[:, :10] == 0).all())      # A's own area restored
        self.assertTrue((out[:, 10:] == 255).all())    # B's overlap and area stay clean
        self.assertFalse(out_mask[:, :10].any())
        self.assertTrue(out_mask[:, 10:].all())
        self.assertEqual(counts['A'], 400)
        self.assertTrue((clean == 255).all())          # input untouched


if __name__ == '__main__':
    unittest.main()
