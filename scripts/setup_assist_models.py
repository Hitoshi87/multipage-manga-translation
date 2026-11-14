"""Compatibility installer; dependency/model inventory is maintained centrally."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, str(ROOT / 'setup.py'), '--install', '--profile', 'assist']))
