#!/usr/bin/env python3
"""Install or check the local worker on Windows, macOS and Linux (Python 3.12)."""
import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from manga_ai.model_registry import PROFILES


def python_in_venv(root=ROOT, system=None):
    return Path(root) / '.venv' / ('Scripts/python.exe' if (system or platform.system()) == 'Windows' else 'bin/python')


def requirements(profile):
    files = ['requirements.txt']
    # Normal automatic OCR/CTD/LaMa uses ONNX only. No Torch/Magi download needed.
    if profile in ('1107', 'assist', 'all'):
        files.append('requirements-ai.txt')
    if profile in ('assist', 'all'):
        files.append('requirements-assist.txt')
    if profile in ('preview', 'aot', 'all'):
        files.append('requirements-preview.txt')
    if len(files) == 1:
        files.append('requirements-auto.txt')
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Create .venv, install dependencies and download models')
    parser.add_argument('--profile', choices=PROFILES, default='auto')
    parser.add_argument('--plan', action='store_true', help='Print plan without modifying anything')
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error('Use Python 3.12 (Windows: py -3.12 setup.py; macOS/Linux: python3.12 setup.py)')
    python = python_in_venv()
    if args.plan:
        print(json.dumps(dict(platform=platform.system(), python=str(python), requirements=requirements(args.profile),
                              profile=args.profile, models='models/manifest.json'), indent=2))
        return 0
    def run(*command):
        subprocess.run([str(c) for c in command], cwd=ROOT, check=True, env={**os.environ, "PYTHONUTF8": "1"})
    try:
        if args.install:
            if not (ROOT / '.venv').exists():
                run(sys.executable, '-m', 'venv', ROOT / '.venv')
            if not python.is_file():
                raise RuntimeError('Existing .venv belongs to another OS or is incomplete. Rename it and rerun setup.')
            run(python, '-c', 'import sys; assert sys.version_info[:2] == (3,12), "Rename the old .venv and rerun setup with Python 3.12"')
            # Both ORT distributions own the same module. Refuse rather than silently break a custom GPU environment.
            run(python, '-c', 'import importlib.metadata as m; names={d.metadata["Name"].lower() for d in m.distributions()}; assert "onnxruntime-gpu" not in names, "Existing CUDA environment: keep it separate; installer uses onnxruntime CPU/CoreML. Rename .venv first."')
            run(python, '-m', 'pip', 'install', '--upgrade', 'pip')
            for file in requirements(args.profile):
                run(python, '-m', 'pip', 'install', '-r', ROOT / file)
            run(python, ROOT / 'scripts/download_models.py', '--profile', 'auto', '--download')
            if args.profile not in ('auto', 'tessdata'):
                run(python, ROOT / 'scripts/download_models.py', '--profile', args.profile, '--download')
        if not python.is_file():
            raise RuntimeError('Missing .venv. Run this command again with --install.')
        run(python, ROOT / 'manga_typesetter.py', 'doctor', '--profile', 'auto', '--verify-models')
        if args.profile != 'auto':
            run(python, ROOT / 'manga_typesetter.py', 'doctor', '--profile', args.profile, '--verify-models')
        print('Setup verified. Configure API key and series style in the tool before translating.')
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'Setup incomplete: {exc}\nSee docs/runtime/installation.md. Rerun after fixing; verified models are reused.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
