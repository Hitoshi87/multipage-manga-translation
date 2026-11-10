import json
import unittest
from manga_ai.translation.contracts import envelope
from manga_ai.translation.evidence import normalize
from manga_ai.translation.prompts import compose,preset,CORE,OUTPUT,FIELDS,VIETNAMESE_DIALOGUE
from manga_ai.translation.qa import validate_response

class TranslationContractTests(unittest.TestCase):
    def test_coverage_and_context_rejected(self):
        targets = [{'id': 'a', 'jp': 'こんにちは {name}'}]
        good = {'translations': [{'id': 'a', 'vi': 'Chào {name}', 'flags': []}]}
        self.assertEqual(validate_response(json.dumps(good), targets)[0]['id'], 'a')
        for rows in ([], good['translations'] * 2, [{'id': 'context', 'vi': 'Chào {name}', 'flags': []}], [{'id': 'a', 'vi': 'Chào', 'flags': []}]):
            with self.assertRaises(ValueError): validate_response(json.dumps({'translations': rows}), targets)
        # Recoverable model quirks: missing flags, unknown flag string, extra key, null evidence, silent ellipsis
        quirky = {'translations': [{'id': 'a', 'vi': 'Chào {name}', 'flags': ['uncertain', ''], 'notes': 'ok', 'source_evidence': None}]}
        norm = validate_response('```json\n' + json.dumps(quirky) + '\n```', targets)[0]
        self.assertEqual(norm['flags'], ['needs_review'])
        self.assertNotIn('notes', norm)
        self.assertNotIn('source_evidence', norm)
        silent = validate_response(json.dumps({'translations': [{'id': 's', 'vi': '   '}]}), [{'id': 's', 'jp': '・・・・・・'}])[0]
        self.assertEqual(silent['vi'], '…')
        self.assertEqual(silent['flags'], [])
    def test_unknown_source_is_blocked(self):
        row = normalize({'regions': [{'id':'B001', 'source':'[OCR chưa đọc được]'}]}, 'page1')[0]
        self.assertIsNone(row['jp'])
        self.assertEqual(row['speaker']['status'], 'unknown')
    def test_profile_fields_and_envelope(self):
        self.assertIn('STYLE_PROMPT:\nTự nhiên', compose({'style_prompt':'Tự nhiên'}))
        self.assertEqual(envelope('translation', 'review_required')['schema_version'], '1.0')
        with self.assertRaises(ValueError): envelope('translation', 'invented')

    def test_sample_fields_are_composed_once_between_core_and_contract(self):
        values=preset('mayonaka_sample');prompt=compose(values)
        self.assertTrue(prompt.startswith(CORE))
        self.assertTrue(prompt.endswith(OUTPUT))
        for field in FIELDS:
            self.assertTrue(values[field])
            self.assertEqual(prompt.count(values[field].strip()),1)
        with self.assertRaises(ValueError):preset('../untrusted')

    def test_dialogue_contract_is_shared_with_vision_and_keeps_user_style(self):
        for mode in ('off','target_crop'):
            prompt=compose({'vision_mode':mode,'style_prompt':'Giọng riêng của bộ truyện.'})
            self.assertEqual(prompt.count(VIETNAMESE_DIALOGUE),1)
            self.assertIn('Giọng riêng của bộ truyện.',prompt)
            self.assertLess(prompt.index(VIETNAMESE_DIALOGUE),prompt.index('STYLE_PROMPT:'))


class NameStabilityTests(unittest.TestCase):
    def test_prompt_prefers_furigana_reading(self):
        self.assertIn('romanise the furigana reading', compose({}))
