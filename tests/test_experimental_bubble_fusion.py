import unittest
from manga_ai.experimental_bubble_fusion import fuse_for_review, polygon_iou


class BubbleFusionTest(unittest.TestCase):
    def test_overlapping_polygons_are_deduplicated_and_never_authorize_clean(self):
        a = [[10, 10], [90, 10], [90, 90], [10, 90]]
        b = [[12, 12], [89, 12], [89, 89], [12, 89]]
        fused = fuse_for_review([{'polygon': a, 'confidence': .9, 'source': 'a'},
                                 {'polygon': b, 'confidence': .8, 'source': 'b'}], [[30, 30, 10, 20]])
        self.assertEqual(len(fused), 1)
        self.assertEqual(len(fused[0]['members']), 2)
        self.assertEqual(fused[0]['reason'], 'text_candidate')
        self.assertEqual(fused[0]['status'], 'review_only')
        self.assertNotIn('erase_mask', fused[0])

    def test_disjoint_and_invalid_polygons(self):
        a = [[0, 0], [10, 0], [10, 10], [0, 10]]
        b = [[20, 20], [30, 20], [30, 30], [20, 30]]
        self.assertEqual(polygon_iou(a, b), 0)
        self.assertEqual(polygon_iou(a, []), 0)
        groups = fuse_for_review([{'polygon': a, 'confidence': .8, 'source': 'a'},
                                  {'polygon': b, 'confidence': .7, 'source': 'b'}], [])
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(g['reason'] == 'no_text_evidence' for g in groups))


if __name__ == '__main__': unittest.main()
