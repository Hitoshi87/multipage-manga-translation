import json
import unittest

from manga_ai.translation.prompts import LETTERING_FIT, MANGA_CONVENTIONS, NATURAL_VIETNAMESE, VIETNAMESE_DIALOGUE, compose
from manga_ai.translation.qa import qa_warnings, validate_response


def reply(*items):
    return json.dumps({'translations': [{'id': i, 'vi': v, 'flags': []} for i, v in items]})


class QaWarningTests(unittest.TestCase):
    def test_japanese_left_adds_review_flag_and_warning(self):
        rows = validate_response(reply(('a', 'Trường 楓林 này')), [{'id': 'a', 'jp': '楓林学院'}])
        self.assertEqual(rows[0]['_qa_warnings'], ['japanese_left'])
        self.assertIn('needs_review', rows[0]['flags'])

    def test_overlong_translation_warns_without_flag(self):
        rows = validate_response(reply(('a', 'x' * 50)), [{'id': 'a', 'jp': 'こんにちは'}])
        self.assertEqual(rows[0]['_qa_warnings'], ['long_for_bubble'])
        self.assertEqual(rows[0]['flags'], [])

    def test_short_interjection_and_clean_text_have_no_warning(self):
        self.assertEqual(qa_warnings('あ', 'Ơ kìa, thật không ngờ!'), [])
        self.assertEqual(qa_warnings('ありがとう', 'Cảm ơn nhé.'), [])

    def test_dash_not_in_source_is_warned_but_real_dash_is_not(self):
        self.assertEqual(qa_warnings('今日学校でさー', 'Hôm nay ở trường — ấy'), ['dash_added'])
        self.assertEqual(qa_warnings('みんなー', 'Các bạn ơi—'), ['dash_added'])
        self.assertEqual(qa_warnings('詳しくは会議で――', 'Chi tiết sẽ bàn ở cuộc họp—'), [])
        self.assertEqual(qa_warnings('どうしたの', 'Sao thế?'), [])

    def test_odd_symbols_are_warned_but_normal_punctuation_is_not(self):
        for bad in ('**Thầy** ơi', 'Ừ ♡', 'Hay quá ★', 'Chào 😀', 'anh/chị đâu', 'Gì vậy.....', 'Ơ！', '「Em yêu anh」', 'Ôi (TN: chơi chữ)', 'a | b', '[?]'):
            self.assertIn('odd_symbols', qa_warnings('こんにちは', bad), bad)
        for good in ('Thầy ơi!!', 'Gì vậy...?', 'Ơ… sao thế?', 'Cậu bảo “ổn” mà?', 'Còn 1% nữa.', 'T-tớ không biết!', 'Ừ~', 'Ăn 3/4 phần'):
            self.assertNotIn('odd_symbols', qa_warnings('こんにちは', good), good)

    def test_prompt_sections_are_present_once_and_scope_excludes_sfx(self):
        prompt = compose({})
        for section in (VIETNAMESE_DIALOGUE, NATURAL_VIETNAMESE, LETTERING_FIT, MANGA_CONVENTIONS):
            self.assertEqual(prompt.count(section), 1)
        self.assertIn('Sound effects and lettering outside bubbles are not translated', prompt)
        self.assertIn('Do not use an em dash or en dash', prompt)
        self.assertIn('keep explicit Japanese pronouns', prompt)
        self.assertIn('restore their authentic source-language spelling', prompt)
        self.assertIn('never transliterate katakana loanwords into Japanese romaji', prompt)
        self.assertIn('do not flag ocr_suspect merely because noisy text OCR disagrees', prompt)


if __name__ == '__main__':
    unittest.main()


class ProviderRobustnessTests(unittest.TestCase):
    def test_gateway_outage_inside_http_200_is_not_a_translation(self):
        body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
            'content': 'Upstream temporarily unavailable, please retry.'}}]}).encode()
        with self.assertRaisesRegex(ValueError, 'API upstream temporarily unavailable'):
            self._call([body])

    def _call(self, bodies, retries=1):
        import io
        import os
        from unittest import mock
        from manga_ai.translation import providers

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        queue = list(bodies)
        profile = {'key_env': 'TEST_KEY', 'model': 'm', 'max_tokens': 10, 'json_mode': False, 'thinking': 'default',
                   'base_url': 'http://x', 'retries': retries, 'timeout': 5}
        with mock.patch.dict(os.environ, {'TEST_KEY': 'k'}), \
                mock.patch.object(providers, 'urlopen', side_effect=lambda *a, **k: Resp(queue.pop(0))), \
                mock.patch.object(providers.time, 'sleep'):
            return providers.openai_compatible(profile, 'sys', {})

    def test_malformed_response_is_retried_then_succeeds(self):
        good = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': 'ok'}}]}).encode()
        text, meta = self._call([b'{"error":{"message":"overloaded"}}', good])
        self.assertEqual(text, 'ok')

    def test_persistent_malformed_response_gives_a_readable_error(self):
        with self.assertRaises(ValueError) as ctx:
            self._call([b'{"error":{"message":"overloaded"}}', b'{"error":{"message":"overloaded"}}'])
        self.assertIn('không hợp lệ', str(ctx.exception))
        self.assertIn('overloaded', str(ctx.exception))
        self.assertNotIsInstance(ctx.exception, KeyError)


class KeyLookupTests(unittest.TestCase):
    def test_key_comes_from_the_environment_then_the_user_key_file_and_is_never_returned_by_status(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest import mock
        from manga_ai.translation import providers
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(Path, 'home', return_value=Path(home)), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('TEST_KEY_X', None)
                self.assertEqual(providers.find_key('TEST_KEY_X'), (None, None))
                self.assertFalse(providers.key_status('TEST_KEY_X')['present'])
                file = providers.key_file('TEST_KEY_X')
                file.parent.mkdir(parents=True)
                file.write_text('  secret-from-file \n', encoding='utf8')
                self.assertEqual(providers.find_key('TEST_KEY_X'), ('secret-from-file', 'file'))
                with mock.patch.dict(os.environ, {'TEST_KEY_X': 'secret-from-env'}):
                    self.assertEqual(providers.find_key('TEST_KEY_X'), ('secret-from-env', 'env'))
                status = providers.key_status('TEST_KEY_X')
                self.assertTrue(status['present'])
                self.assertNotIn('secret', json.dumps(status))


class BridgeContractTests(unittest.TestCase):
    """The Photoshop panel reads these results directly (no `.data`); keep them plain dicts."""

    def test_plain_operations_return_dicts_without_a_data_wrapper(self):
        import os
        from unittest import mock
        from manga_ai import cli
        with mock.patch.dict(os.environ, {'MANGA_TRANSLATION_API_KEY': 'x'}):
            status = cli.dispatch({'operation': 'translation_key_status', 'key_env': 'MANGA_TRANSLATION_API_KEY'})
        self.assertEqual((status['present'], status['source']), (True, 'env'))
        self.assertNotIn('data', status)
        pick = cli.dispatch({'operation': 'translation_preflight_pick', 'count': 200})
        self.assertEqual(pick['indices'], [50, 100, 150])
        self.assertNotIn('data', pick)
        card = [{'status': 'draft', 'required': 10, 'mapped': 10, 'clean_skipped': [], 'layout_fallback': [], 'manual_text': []}] * 3
        verdict = cli.dispatch({'operation': 'translation_preflight_decide', 'pages': card, 'engine': 'baseline'})
        self.assertEqual(verdict['action'], 'go')
        self.assertNotIn('data', verdict)
        with mock.patch('manga_ai.environment.check_auto_flow', return_value={'ready': True, 'items': [], 'plan': [], 'engine': 'baseline'}):
            env = cli.dispatch({'operation': 'translation_env_check'})
        self.assertEqual(env['engine'], 'baseline')
        self.assertNotIn('data', env)
