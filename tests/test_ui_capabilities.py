import tempfile
import unittest
from pathlib import Path

from manga_ai.ui_capabilities import ui_features


class UiCapabilitiesTests(unittest.TestCase):
    def test_missing_optional_models_do_not_load_or_download_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = list(Path(tmp).iterdir())
            features = ui_features(tmp, lambda _: False)
            self.assertTrue(features['inpaint_white']['ready'])
            self.assertFalse(features['scan_ai']['ready'])
            self.assertIn('package:onnxruntime', features['scan_ai']['missing'])
            self.assertEqual(before, list(Path(tmp).iterdir()))

    def test_file_presence_and_package_checks_remain_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            features = ui_features(tmp, lambda _: True)
            for row in features.values():
                for name in row['missing']:
                    path = Path(tmp) / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            self.assertTrue(all(row['ready'] for row in ui_features(tmp, lambda _: True).values()))
            self.assertFalse(ui_features(tmp, lambda name: name != 'torch')['mask_mask']['ready'])
