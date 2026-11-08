import tempfile
import unittest
from pathlib import Path

from manga_ai import environment as env


def touch(root, names):
    for name in names:
        file = Path(root) / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'x')


GOOD_DOCTOR = lambda: {'tesseract': '/usr/bin/tesseract', 'languages': ['eng', 'jpn', 'jpn_vert']}
KEY = lambda present: (lambda name: {'present': present, 'source': 'env' if present else None})


class EnvironmentCheckTests(unittest.TestCase):
    def check(self, root, **over):
        args = dict(doctor_fn=GOOD_DOCTOR, key_fn=KEY(True), package_fn=lambda n: True)
        args.update(over)
        return env.check_auto_flow(root, **args)

    def test_everything_present_is_ready_and_uses_the_ai_engine(self):
        with tempfile.TemporaryDirectory() as root:
            touch(root, list(env.DETECTOR) + env.baberu_files() + list(env.AI_CLEAN))
            result = self.check(root)
        self.assertTrue(result['ready'])
        self.assertEqual(result['engine'], 'art_draft')
        self.assertTrue(all(i['ok'] for i in result['items']))
        self.assertIn('art_draft', ' '.join(result['plan']))

    def test_missing_baberu_is_reported_up_front_with_the_exact_command(self):
        with tempfile.TemporaryDirectory() as root:
            touch(root, list(env.DETECTOR) + list(env.AI_CLEAN))
            result = self.check(root)
        self.assertFalse(result['ready'])
        baberu = next(i for i in result['items'] if i['id'] == 'baberu')
        self.assertFalse(baberu['ok'])
        self.assertEqual(len(baberu['missing']), 4)
        self.assertEqual(baberu['fix'], 'python manga_typesetter.py download-models --profile assist')

    def test_all_problems_are_listed_together_not_one_at_a_time(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.check(root, doctor_fn=lambda: {'tesseract': None, 'languages': []}, key_fn=KEY(False),
                                package_fn=lambda n: n != 'onnxruntime')
        bad = {i['id'] for i in result['items'] if not i['ok'] and i['required']}
        self.assertEqual(bad, {'packages', 'tesseract', 'detector', 'baberu', 'api_key'})
        self.assertFalse(result['ready'])

    def test_missing_lama_is_not_blocking_but_falls_back_to_baseline_visibly(self):
        with tempfile.TemporaryDirectory() as root:
            touch(root, list(env.DETECTOR) + env.baberu_files())
            result = self.check(root)
        self.assertTrue(result['ready'])                       # LaMa is recommended, not required
        self.assertEqual(result['engine'], 'baseline')
        ai = next(i for i in result['items'] if i['id'] == 'ai_clean')
        self.assertFalse(ai['ok'])
        self.assertFalse(ai['required'])
        self.assertIn('--profile preview', ai['fix'])
        self.assertIn('thiếu model AI', ' '.join(result['plan']))

    def test_tesseract_without_vertical_japanese_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            touch(root, list(env.DETECTOR) + env.baberu_files() + list(env.AI_CLEAN))
            result = self.check(root, doctor_fn=lambda: {'tesseract': '/usr/bin/tesseract', 'languages': ['eng']})
        tess = next(i for i in result['items'] if i['id'] == 'tesseract')
        self.assertEqual(tess['missing'], ['ngôn ngữ jpn_vert'])

    def test_a_crashing_doctor_does_not_hide_the_other_findings(self):
        def boom():
            raise RuntimeError('tesseract exploded')
        with tempfile.TemporaryDirectory() as root:
            result = self.check(root, doctor_fn=boom)
        self.assertTrue(any(i['id'] == 'baberu' and not i['ok'] for i in result['items']))
        self.assertFalse(next(i for i in result['items'] if i['id'] == 'tesseract')['ok'])


if __name__ == '__main__':
    unittest.main()
