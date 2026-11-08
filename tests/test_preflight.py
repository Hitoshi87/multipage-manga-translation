import unittest

from manga_ai.preflight import AI_ENGINE, decide, pick_sample_pages, scorecard


def page(required=10, mapped=10, clean_skipped=0, fallback=0, manual=0, failed=False):
    if failed:
        return {'page': 'x', 'status': 'failed', 'error': 'boom'}
    return {'page': 'p', 'status': 'draft', 'required': required, 'mapped': mapped,
            'clean_skipped': ['b'] * clean_skipped, 'layout_fallback': ['b'] * fallback, 'manual_text': ['b'] * manual}


class PreflightTests(unittest.TestCase):
    def test_sample_pages_are_spread_through_the_volume(self):
        self.assertEqual(pick_sample_pages(200), [50, 100, 150])
        self.assertEqual(pick_sample_pages(2), [0, 1])
        self.assertEqual(pick_sample_pages(3), [0, 1, 2])
        self.assertEqual(pick_sample_pages(5), [1, 2, 4])
        self.assertEqual(pick_sample_pages(0), [])

    def test_scorecard_rates(self):
        card = scorecard([page(10, 10, clean_skipped=2), page(10, 8, fallback=1), page(failed=True)])
        self.assertEqual((card['pages'], card['failed_pages'], card['required'], card['translated']), (3, 1, 20, 18))
        self.assertAlmostEqual(card['translate_rate'], .9)
        self.assertAlmostEqual(card['clean_rate'], (18 - 2) / 18)
        self.assertAlmostEqual(card['letter_rate'], 17 / 18)

    def test_a_good_sample_goes(self):
        result = decide(scorecard([page(), page(), page(clean_skipped=1)]), 'baseline')
        self.assertEqual(result['action'], 'go')
        self.assertEqual(result['next_engine'], 'baseline')

    def test_weak_cleaning_escalates_once_to_the_ai_engine_then_stops_if_still_weak(self):
        weak = scorecard([page(clean_skipped=6), page(clean_skipped=6), page(clean_skipped=5)])        # 43% cleaned
        first = decide(weak, 'baseline')
        self.assertEqual((first['action'], first['next_engine']), ('escalate', AI_ENGINE))
        second = decide(weak, AI_ENGINE, escalated=True)
        self.assertEqual(second['action'], 'stop')
        self.assertIn('Chạy cả tập', second['message'])

    def test_moderately_weak_cleaning_with_the_ai_engine_still_goes_with_review(self):
        card = scorecard([page(clean_skipped=3), page(clean_skipped=3), page(clean_skipped=2)])        # 73%
        self.assertEqual(decide(card, 'baseline')['action'], 'escalate')
        self.assertEqual(decide(card, AI_ENGINE, escalated=True)['action'], 'go')

    def test_missing_translations_stop_with_a_clear_reason(self):
        card = scorecard([page(10, 2), page(10, 3), page(10, 1)])
        result = decide(card, 'baseline')
        self.assertEqual(result['action'], 'stop')
        self.assertIn('API key', result['message'])

    def test_all_failed_pages_stop(self):
        self.assertEqual(decide(scorecard([page(failed=True)] * 3), 'baseline')['action'], 'stop')
        self.assertEqual(decide(scorecard([]), 'baseline')['action'], 'stop')


if __name__ == '__main__':
    unittest.main()
