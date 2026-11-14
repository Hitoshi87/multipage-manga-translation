"""Portable setup regressions: no real network or package installation."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manga_ai import ocr_runtime
from manga_ai.model_registry import models, status
from scripts import download_models

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('project_setup', ROOT / 'setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class InstallationTests(unittest.TestCase):
    def test_auto_inventory_covers_the_runtime_without_magi_or_torch(self):
        from manga_ai.environment import DETECTOR, AI_CLEAN, baberu_files
        inventory = {'models/' + row['path'] for row in models('auto')}
        self.assertTrue(set(DETECTOR + AI_CLEAN).union(baberu_files()) <= inventory)
        self.assertTrue(all('models/tessdata/' + lang + '.traineddata' in inventory for lang in ocr_runtime.LANGUAGES))
        self.assertFalse(any('magi' in path for path in inventory))
        self.assertEqual(set(setup.requirements('auto')), {'requirements.txt', 'requirements-auto.txt'})
        for row in models('all'):
            self.assertGreater(row['size_bytes'], 0)
            self.assertRegex(row['sha256'], r'^[a-f0-9]{64}$')
            self.assertIn(row['revision'], row['url'])

    def test_venv_paths_preserve_spaces_and_unicode_on_each_platform(self):
        root = Path('/project có dấu/Tool')
        self.assertEqual(setup.python_in_venv(root, 'Windows'), root / '.venv/Scripts/python.exe')
        for system in ('Darwin', 'Linux'):
            self.assertEqual(setup.python_in_venv(root, system), root / '.venv/bin/python')

    def test_windows_tesseract_install_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / 'Programs/Tesseract-OCR/tesseract.exe'
            exe.parent.mkdir(parents=True)
            exe.touch()
            with patch.dict(os.environ, {'LOCALAPPDATA': directory}, clear=True), patch.object(ocr_runtime.shutil, 'which', return_value=None), patch.object(ocr_runtime, 'configure_tessdata'), patch.object(ocr_runtime.platform, 'system', return_value='Windows'):
                self.assertEqual(ocr_runtime.find_tesseract(), str(exe))
                os.environ['TESSERACT_CMD'] = '"' + str(exe) + '"'
                self.assertEqual(ocr_runtime.find_tesseract(), str(exe))
                os.environ['TESSERACT_CMD'] = str(exe) + '.missing'
                self.assertIsNone(ocr_runtime.find_tesseract())

    def test_size_and_hash_checks_reject_pointer_and_same_size_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            row = dict(path='model.onnx', size_bytes=4, sha256=hashlib.sha256(b'good').hexdigest())
            file = Path(directory) / row['path']
            self.assertEqual(status(row, directory), 'missing')
            file.write_bytes(b'version https://git-lfs.github.com/spec/v1')
            self.assertEqual(status(row, directory), 'invalid_size')
            file.write_bytes(b'evil')
            self.assertEqual(status(row, directory, verify=True), 'invalid_sha256')
            file.write_bytes(b'good')
            self.assertEqual(status(row, directory, verify=True), 'ok')

    def test_download_retry_then_skip_completed_file_and_aggregate_failure(self):
        row = dict(id='demo', path='nested/model.bin', size_bytes=4,
                   sha256=hashlib.sha256(b'good').hexdigest(), url='https://example.org/model')
        with tempfile.TemporaryDirectory() as directory, patch.object(download_models, 'models', return_value=[row]), patch.object(download_models.time, 'sleep'):
            args = ['--profile', 'auto', '--model-dir', directory, '--download', '--retries', '2']
            with patch.object(download_models.urllib.request, 'urlopen', side_effect=[OSError('interrupted'), io.BytesIO(b'good')]) as network:
                self.assertEqual(download_models.main(args), 0)
                self.assertEqual(network.call_count, 2)
            with patch.object(download_models.urllib.request, 'urlopen', side_effect=AssertionError('unexpected network')):
                self.assertEqual(download_models.main(args), 0)
            other = dict(row, id='missing', path='missing.bin')
            with patch.object(download_models, 'models', return_value=[other, row]), patch.object(download_models.urllib.request, 'urlopen', side_effect=OSError('offline')):
                self.assertEqual(download_models.main(args), 1)
                self.assertEqual((Path(directory) / row['path']).read_bytes(), b'good')
            self.assertEqual(list(Path(directory).rglob('*.part')), [])

    def test_check_only_does_not_create_environment_and_failed_doctor_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)), patch.object(setup, 'python_in_venv', return_value=Path(directory) / '.venv/bin/python'):
            self.assertEqual(setup.main([]), 1)
            self.assertFalse((Path(directory) / '.venv').exists())
        with patch.object(setup.Path, 'is_file', return_value=True), patch.object(setup.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, ['doctor'])):
            self.assertEqual(setup.main([]), 1)

    def test_optional_setup_installs_auto_before_optional_models_and_stops_on_failure(self):
        with patch.object(setup.Path, 'exists', return_value=True), patch.object(setup.Path, 'is_file', return_value=True), patch.object(setup.subprocess, 'run') as run:
            self.assertEqual(setup.main(['--install', '--profile', 'preview']), 0)
            commands = [call.args[0] for call in run.call_args_list]
            downloads = [cmd for cmd in commands if any('download_models.py' in arg for arg in cmd)]
            self.assertEqual([cmd[cmd.index('--profile') + 1] for cmd in downloads], ['auto', 'preview'])
            for call in run.call_args_list:
                self.assertTrue(call.kwargs['check'])
                self.assertEqual(call.kwargs['env']['PYTHONUTF8'], '1')
        with patch.object(setup.Path, 'exists', return_value=True), patch.object(setup.Path, 'is_file', return_value=True), patch.object(setup.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])) as run:
            self.assertEqual(setup.main(['--install']), 1)
            self.assertEqual(run.call_count, 1)

    def test_source_bundle_contains_all_entry_points(self):
        from scripts.build_source_bundle import source_files
        paths = {path.relative_to(ROOT).as_posix() for path in source_files(ROOT)}
        self.assertTrue({'setup.py', 'setup_windows.cmd', 'setup_linux.sh', 'setup_macos.command',
                         'requirements-auto.txt', 'manga_ai/model_registry.py', 'manga_ai/ocr_runtime.py',
                         'docs/runtime/installation.md'} <= paths)


if __name__ == '__main__':
    unittest.main()
