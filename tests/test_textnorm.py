import json
import unittest
from pathlib import Path

from manga_ai.translation.qa import qa_warnings
from manga_ai.translation.textnorm import normalize_page, normalize_text

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'textnorm_cases.json').read_text(encoding='utf8'))


class TextNormTests(unittest.TestCase):
    def test_shared_cases_and_idempotence(self):
        for case in CASES:
            got = normalize_text(case['in'], case.get('case', 'sentence'))
            self.assertEqual(got, case['out'], case['in'])
            self.assertEqual(normalize_text(got, case.get('case', 'sentence')), got, case['in'])

    def test_leading_ellipsis_moves_to_the_previous_unfinished_bubble(self):
        self.assertEqual(normalize_page(['Từ giờ, từng người một,', '…và nói đi.']), ['Từ giờ, từng người một…', 'Và nói đi.'])
        self.assertEqual(normalize_page(['Xong rồi.', '…ừ']), ['Xong rồi.', 'Ừ'])          # finished bubble: just drop it
        self.assertEqual(normalize_page(['Cậu nói', '…gì thế?']), ['Cậu nói…', 'Gì thế?'])

    def test_stored_translation_is_not_changed_by_display_normalisation(self):
        original = ['…và nói「Em」đi']
        normalize_page(original)
        self.assertEqual(original, ['…và nói「Em」đi'])

    def test_a_silent_ellipsis_bubble_is_kept_and_not_flagged(self):
        for text in ('…', '……', '...', '\uff0e\uff0e\uff0e', '…?', '?!…'):
            self.assertTrue(normalize_text(text).strip(), text)                    # never blanked
        self.assertEqual(normalize_page(['Xong rồi.', '…']), ['Xong rồi.', '…'])    # not moved onto the previous bubble
        self.assertEqual(qa_warnings('\uff0e\uff0e\uff0e\uff0e', '……'), [])
        self.assertEqual(qa_warnings('\uff0e\uff0e\uff0e', '…'), [])

    def test_qa_flags_leading_and_repeated_ellipses(self):
        self.assertIn('leading_ellipsis', qa_warnings('こんにちは', '…và nói'))
        self.assertIn('ellipsis_heavy', qa_warnings('こんにちは', 'Ơ… như… mọi người…'))
        self.assertEqual(qa_warnings('こんにちは', 'Ơ… sao vậy?'), [])


if __name__ == '__main__':
    unittest.main()
