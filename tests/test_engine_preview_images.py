import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from manga_ai.engines import run_engine
from manga_ai.engines.preview import preview_images


class EnginePreviewImagesTests(unittest.TestCase):
    def test_display_comes_from_exact_overlay_without_changing_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (100, 100), 'white').save(root / 'original.png')
            overlay = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
            overlay.paste((10, 20, 30, 255), (20, 20, 40, 40))
            overlay.save(root / 'overlay.png')
            before = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ('original.png', 'overlay.png')}
            result = {'overlay': str(root / 'overlay.png'), 'applied': ['B001'], 'skipped': [], 'blocked': {}}
            mapping = [{'id': 'B001', 'translation': 'Preview', 'clean': True}]
            with patch('manga_ai.engine.render_clean', return_value=result) as handler:
                output = run_engine('baseline', root / 'manifest.json', mapping, preview=True)
            handler.assert_called_once()
            self.assertEqual(output['engine_id'], 'baseline')
            with Image.open(output['images']['clean']) as image:
                self.assertEqual(image.getpixel((25, 25)), (10, 20, 30))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            for name, digest in before.items():
                self.assertEqual(digest, hashlib.sha256((root / name).read_bytes()).hexdigest())

    def test_mismatched_overlay_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (20, 20)).save(root / 'original.png')
            Image.new('RGBA', (10, 10)).save(root / 'overlay.png')
            with self.assertRaises(ValueError):
                preview_images({'overlay': str(root / 'overlay.png')}, root / 'manifest.json')
