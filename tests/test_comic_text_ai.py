import unittest
from unittest.mock import patch

import numpy as np

from manga_ai import comic_text_ai
from manga_ai.engine import clean_block_reason


class ComicTextDetectorTest(unittest.TestCase):
    def test_detector_respects_classes_coordinates_and_threshold(self):
        class Runner:
            def run(self, _output, inputs):
                self.inputs = inputs
                return (np.array([[0, 1, 2, 1]]),
                        np.array([[[0, 0, 50, 50], [20, 30, 80, 90], [-2, 5, 45, 50], [10, 10, 40, 40]]]),
                        np.array([[.99, .91, .85, .2]]))
        runner = Runner()
        with patch.object(comic_text_ai, 'session', return_value=runner):
            found = comic_text_ai.detect(np.full((2000, 1000, 3), 255, np.uint8))
        self.assertEqual(runner.inputs['orig_target_sizes'].tolist(), [[1000, 2000]])
        self.assertEqual([(r['box'], r['kind']) for r in found],
                         [([20, 30, 60, 60], 'in_bubble'), ([0, 5, 45, 45], 'free_text')])

    def test_uncovered_boxes_are_review_only_and_deduplicated(self):
        boxes = [{'box':[20,20,30,30], 'kind':'in_bubble', 'confidence':.96},
                 {'box':[120,20,30,40], 'kind':'free_text', 'confidence':.91},
                 {'box':[121,21,30,40], 'kind':'free_text', 'confidence':.9}]
        regions = [{'box':[10,10,60,60]}]
        extra = comic_text_ai.uncovered_regions(boxes, regions)
        self.assertEqual(len(extra), 1)
        region = extra[0]
        self.assertFalse(region['auto_clean'])
        self.assertFalse(np.any(region['_mask']))
        self.assertEqual(region['clean_method'], 'review_only')
        self.assertIsNotNone(clean_block_reason({'lang':'jpn_vert','width':200,'height':200}, region))
        self.assertIsNotNone(clean_block_reason({'lang':'eng','width':200,'height':200}, region))

    def test_filters_margin_titles_but_keeps_vertical_speech(self):
        class Runner:
            def run(self, *_):
                return (np.array([[2, 2]]), np.array([[[5, 3, 90, 13], [70, 2, 85, 60]]]), np.array([[.95, .95]]))
        with patch.object(comic_text_ai, 'session', return_value=Runner()):
            found = comic_text_ai.detect(np.full((200, 100, 3), 255, np.uint8))
        self.assertEqual([r['box'] for r in found], [[70, 2, 15, 58]])


if __name__ == '__main__':
    unittest.main()
