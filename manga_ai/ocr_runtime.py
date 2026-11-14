"""Tesseract discovery shared by doctor and workers, including Windows installs."""
import os
import platform
import shutil
from pathlib import Path

LANGUAGES = ('eng', 'jpn', 'jpn_vert', 'chi_sim', 'chi_tra', 'kor', 'vie')


def configure_tessdata():
    local = Path(__file__).resolve().parents[1] / 'models/tessdata'
    if local.is_dir() and all((local / (lang + '.traineddata')).is_file() for lang in LANGUAGES):
        os.environ.setdefault('TESSDATA_PREFIX', str(local))


def find_tesseract():
    configure_tessdata()
    explicit = os.environ.get('TESSERACT_CMD')
    if explicit:
        candidate = Path(explicit.strip('"'))
        return str(candidate) if candidate.is_file() else None
    candidates = [shutil.which('tesseract')]
    if platform.system() != 'Windows':
        candidates += ['/opt/homebrew/bin/tesseract', '/usr/local/bin/tesseract', '/usr/bin/tesseract']
    for variable in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(variable)
        if base:
            candidates.extend(str(Path(base) / suffix / 'tesseract.exe')
                              for suffix in ('Tesseract-OCR', 'Programs/Tesseract-OCR'))
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)
