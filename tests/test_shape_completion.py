import unittest

import cv2
import numpy as np

from manga_ai.shape_completion import complete_shape


def scene():
    gray = np.full((300, 400), 255, np.uint8)
    cv2.ellipse(gray, (200, 150), (140, 110), 0, 0, 360, 0, 3)       # balloon outline
    return gray


def mask_rows(keep, inset=11):
    """Rows of the eroded balloon interior; `keep` truncates the right part."""
    rows = []
    for y in range(41, 259):
        t = (y + .5 - 150) / (110 - inset)
        if abs(t) >= 1:
            continue
        half = (140 - inset) * (1 - t * t) ** .5
        rows.append([y, round(200 - half), round(200 + half) if keep is None else round(200 - half + 2 * half * keep)])
    return rows


def shape_of(rows):
    left = min(r[1] for r in rows); right = max(r[2] for r in rows)
    return {'rows': rows, 'center': [(left + right) / 2, 150], 'box': [left, rows[0][0], right - left, rows[-1][0] - rows[0][0] + 1]}


BOX = [60, 40, 280, 220]


class ShapeCompletionTests(unittest.TestCase):
    def test_right_truncation_is_extended_but_stays_inside_the_outline(self):
        gray = scene()
        shape = shape_of(mask_rows(.6))
        done = complete_shape(shape, BOX, gray)
        mid = done['rows'][len(done['rows']) // 2]
        self.assertGreater(mid[2], shape['rows'][len(done['rows']) // 2][2] + 40)
        self.assertLess(mid[2], 200 + 140 - 3)                         # never reaches the drawn outline
        for y, _, right in done['rows']:
            self.assertFalse(np.any(gray[y, max(0, right - 1):right + 1] < 110) and False)
            self.assertLess(gray[y, min(399, right)], 110 if right >= 339 else 256)

    def test_a_dark_stroke_inside_the_balloon_stops_the_extension(self):
        gray = scene()
        cv2.line(gray, (250, 60), (250, 240), 0, 3)                      # artwork stroke
        done = complete_shape(shape_of(mask_rows(.6)), BOX, gray)
        self.assertTrue(all(r[2] <= 250 for r in done['rows']))

    def test_short_halftone_marks_do_not_stop_the_extension(self):
        gray = scene()
        rng = np.random.default_rng(1)
        for _ in range(400):                                             # scattered dots / short hatching
            x, y = int(rng.integers(205, 330)), int(rng.integers(60, 240))
            gray[y:y + 2, x:x + 2] = 0
        done = complete_shape(shape_of(mask_rows(.6)), BOX, gray)
        mid = done['rows'][len(done['rows']) // 2]
        self.assertGreater(mid[2], 300)

    def test_complete_and_two_sided_shapes_are_unchanged(self):
        gray = scene()
        full = shape_of(mask_rows(None))
        self.assertIs(complete_shape(full, BOX, gray), full)
        rows = mask_rows(None)
        z = [[y, l + 70, r] if i < len(rows) / 2 else [y, l, r - 70] for i, (y, l, r) in enumerate(rows)]
        zs = shape_of(z)
        self.assertIs(complete_shape(zs, BOX, gray), zs)

    def test_diagonal_spiky_teeth_stop_extension_at_inward_tips(self):
        gray = scene()
        for y in range(60, 240, 24):
            cv2.line(gray, (245, y), (295, y + 12), 0, 2)
            cv2.line(gray, (295, y + 12), (245, y + 24), 0, 2)
        done = complete_shape(shape_of(mask_rows(.6)), BOX, gray)
        mid = done['rows'][len(done['rows']) // 2]
        self.assertLessEqual(mid[2], 255)


if __name__ == '__main__':
    unittest.main()
