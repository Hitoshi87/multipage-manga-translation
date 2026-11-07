import unittest
import numpy as np

from manga_ai.clean_refinement import recover_flat_bubble_text, split_unverified_mask


class FlatBubbleRecoveryTest(unittest.TestCase):
    def test_restores_only_blocked_text_inside_verified_flat_bubble(self):
        image = np.full((100, 100, 3), 250, np.uint8)
        raw = np.zeros((100, 100), np.uint8)
        raw[35:40, 40:45] = 1
        final = np.zeros_like(raw)
        d = [{'kind': 'in_bubble', 'confidence': .84, 'box': [25, 20, 40, 50]}]
        bubble = [{'box': [15, 10, 60, 75], 'interior': np.ones((75, 60), np.uint8)}]
        recovered, approved = recover_flat_bubble_text(image, raw, final, d, bubble)
        self.assertTrue(np.array_equal(recovered, raw))
        self.assertEqual(len(approved), 1)

    def test_rejects_unverified_or_nonflat_regions(self):
        image = np.full((100, 100, 3), 80, np.uint8)
        raw = np.zeros((100, 100), np.uint8); raw[35:40, 40:45] = 1
        d = [{'kind': 'in_bubble', 'confidence': .84, 'box': [25, 20, 40, 50]}]
        bubble = [{'box': [15, 10, 60, 75], 'interior': np.ones((75, 60), np.uint8)}]
        self.assertFalse(recover_flat_bubble_text(image, raw, np.zeros_like(raw), d, bubble)[0].any())
        image[:] = 250
        bubble[0]['interior'][:] = 0
        self.assertFalse(recover_flat_bubble_text(image, raw, np.zeros_like(raw), d, bubble)[0].any())

    def test_unmatched_mask_is_held_for_review(self):
        mask = np.zeros((100, 100), np.uint8)
        mask[20:25, 20:25] = 1; mask[70:75, 70:75] = 1
        approved, review = split_unverified_mask(mask, [{'box': [18, 18, 10, 10], 'confidence': .9}])
        self.assertEqual(int(approved.sum()), 25)
        self.assertEqual(int(review.sum()), 25)
        self.assertTrue(np.array_equal(approved | review, mask))
        approved, review = split_unverified_mask(mask, [])
        self.assertFalse(approved.any())
        self.assertTrue(np.array_equal(review, mask))


if __name__ == '__main__':
    unittest.main()
