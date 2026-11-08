import unittest
import cv2
import numpy as np
from manga_ai.bubble_refinement import split_text_groups_watershed


def parent_from(circles, size=(400, 500)):
    mask = np.zeros(size, np.uint8)
    for cx, cy, r in circles:
        cv2.circle(mask, (cx, cy), r, 255, -1)
    ys, xs = np.nonzero(mask)
    x0, y0 = xs.min(), ys.min()
    box = [int(x0), int(y0), int(xs.max() + 1 - x0), int(ys.max() + 1 - y0)]
    return {'box': box, 'interior': mask[y0:y0 + box[3], x0:x0 + box[2]].copy(), 'detector': 'ai_balloon'}


def det(cx, cy):
    return {'kind': 'in_bubble', 'confidence': .95, 'box': [cx - 25, cy - 25, 50, 50]}


class WatershedTests(unittest.TestCase):
    rgb = np.full((400, 500, 3), 255, np.uint8)

    def test_three_chained_lobes_in_triangle_layout_become_three_children(self):
        circles = [(100, 100, 60), (230, 100, 60), (165, 215, 60)]
        parent = parent_from(circles)
        # Overlap just enough to make narrow necks, as in merged balloons.
        out = split_text_groups_watershed(self.rgb, [parent], [det(c[0], c[1]) for c in circles])
        self.assertEqual(len(out), 3)
        self.assertTrue(all(c['geometry_evidence'] == 'watershed_text_groups' for c in out))
        covered = sum(int(np.count_nonzero(c['interior'])) for c in out)
        self.assertEqual(covered, int(np.count_nonzero(parent['interior'])))

    def test_one_round_balloon_with_three_text_groups_is_not_split(self):
        parent = parent_from([(250, 200, 110)])
        out = split_text_groups_watershed(self.rgb, [parent], [det(210, 150), det(290, 150), det(250, 250)])
        self.assertEqual(out, [parent])

    def test_clean_neck_without_ink_splits(self):
        circles = [(100, 100, 60), (205, 100, 60)]
        out = split_text_groups_watershed(self.rgb, [parent_from(circles)], [det(100, 100), det(205, 100)])
        self.assertEqual(len(out), 2)

    def test_ink_on_the_cut_keeps_parent(self):
        circles = [(100, 100, 60), (205, 100, 60)]
        parent = parent_from(circles)
        rgb = self.rgb.copy()
        cv2.line(rgb, (152, 0), (152, 400), (0, 0, 0), 5)
        out = split_text_groups_watershed(rgb, [parent], [det(100, 100), det(205, 100)])
        self.assertEqual(out, [parent])


if __name__ == '__main__':
    unittest.main()
