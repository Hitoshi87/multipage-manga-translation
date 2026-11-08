import unittest

import cv2
import numpy as np

from manga_ai.bubble_refinement import mark_merged_suspects, split_text_groups_separator


def scene(line_cover=1.0, orientation='h'):
    rgb = np.full((240, 320, 3), 255, np.uint8)
    cv2.rectangle(rgb, (10, 10), (309, 229), (0, 0, 0), 3)                       # outer frame
    if orientation == 'h':
        end = 10 + int(299 * line_cover)
        cv2.line(rgb, (10, 120), (end, 120), (0, 0, 0), 3)                       # shared line between two boxes
    else:
        end = 10 + int(219 * line_cover)
        cv2.line(rgb, (160, 10), (160, end), (0, 0, 0), 3)
    mask = np.zeros((220, 300), np.uint8)
    mask[3:217, 3:297] = 255
    parent = {'box': [10, 10, 300, 220], 'interior': mask, 'detector': 'ai_balloon', 'detector_confidence': .97}
    return rgb, parent


def det(x, y, w, h):
    return {'kind': 'in_bubble', 'confidence': .95, 'box': [x, y, w, h]}


class SeparatorSplitTests(unittest.TestCase):
    def test_two_stacked_boxes_sharing_a_line_are_split(self):
        rgb, parent = scene()
        out = split_text_groups_separator(rgb, [parent], [det(60, 40, 180, 40), det(60, 150, 180, 40)])
        self.assertEqual(len(out), 2)
        self.assertTrue(all(c['geometry_evidence'] == 'separator_line' for c in out))
        top, bottom = sorted(out, key=lambda c: c['box'][1])
        self.assertLess(top['box'][1] + top['box'][3], bottom['box'][1] + 2)

    def test_side_by_side_boxes_sharing_a_vertical_line_are_split(self):
        rgb, parent = scene(orientation='v')
        out = split_text_groups_separator(rgb, [parent], [det(30, 80, 100, 60), det(190, 80, 100, 60)])
        self.assertEqual(len(out), 2)

    def test_a_partial_line_is_not_a_separator(self):
        rgb, parent = scene(line_cover=.4)
        out = split_text_groups_separator(rgb, [parent], [det(60, 40, 180, 40), det(60, 150, 180, 40)])
        self.assertEqual(out, [parent])

    def test_no_line_keeps_the_parent_and_marks_it_as_a_suspect(self):
        rgb, parent = scene(line_cover=0)
        dets = [det(60, 40, 180, 40), det(60, 150, 180, 40)]
        out = split_text_groups_separator(rgb, [parent], dets)
        self.assertEqual(out, [parent])
        marked = mark_merged_suspects(out, dets)
        self.assertEqual(marked[0]['merged_suspect'], 2)

    def test_single_group_and_children_are_untouched(self):
        rgb, parent = scene()
        self.assertEqual(split_text_groups_separator(rgb, [parent], [det(60, 40, 180, 40)]), [parent])
        child = dict(parent, parent_box=[0, 0, 1, 1])
        self.assertEqual(split_text_groups_separator(rgb, [child], [det(60, 40, 180, 40), det(60, 150, 180, 40)]), [child])


if __name__ == '__main__':
    unittest.main()
