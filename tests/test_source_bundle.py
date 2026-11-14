"""Release boundaries: portable runtime, no weights/private data or symlink escape."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('build_source_bundle', Path(__file__).resolve().parents[1] / 'scripts/build_source_bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class SourceBundleTests(unittest.TestCase):
    def put(self, root, name, content='sample'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def test_includes_runtime_metadata_and_portable_checks_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('README.md', 'manga_ai/engines/flat_finish.py', 'models/manifest.json',
                         'scripts/core.jsxinc', 'scripts/lettering_styles.jsxinc', 'scripts/style_manager.jsxinc',
                         'tests/test_contract.py', 'tests/photoshop_engine_smoke.jsx',
                         'docs/validation/photoshop-smoke.example.json'):
                self.put(root, name)
            expected = {p.relative_to(root).as_posix() for p in bundle.source_files(root)}
            self.assertEqual(len(expected), 9)
            self.assertIn('scripts/lettering_styles.jsxinc', expected)
            self.assertIn('scripts/style_manager.jsxinc', expected)
            self.assertIn('models/manifest.json', expected)
            self.assertIn('tests/photoshop_engine_smoke.jsx', expected)

    def test_private_data_weights_and_historical_runners_are_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('models/big.onnx', 'work/source.jpg', 'output/chapter.psd', '.env',
                         'manga_ai/__pycache__/bad.py', 'scripts/engine_1107.py',
                         'tests/photoshop_flat_finish_native.jsx', 'tests/test_shadow_v2_components.py'):
                self.put(root, name)
            self.assertEqual(bundle.source_files(root), [])

    def test_symlinked_file_and_parent_cannot_export_external_content(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root, external = Path(temp), Path(outside)
            secret = self.put(external, 'secret.py', 'private')
            (root / 'README.md').symlink_to(secret)
            (root / 'docs').symlink_to(external, target_is_directory=True)
            (root / 'manga_ai').mkdir()
            (root / 'manga_ai/leak.py').symlink_to(secret)
            self.assertEqual(bundle.source_files(root), [])

    def test_large_source_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.put(root, 'README.md', 'x' * (5*1024*1024 + 1))
            with self.assertRaisesRegex(ValueError, 'large source'):
                bundle.audit(root)

    def test_manifest_hashes_describe_exact_content(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = self.put(root, 'README.md', 'Tiếng Việt')
            _, report = bundle.audit(root)
            self.assertEqual(report['count'], 1)
            self.assertEqual(report['bytes'], len(file.read_bytes()))
            self.assertEqual(report['files'][0]['sha256'], hashlib.sha256(file.read_bytes()).hexdigest())
