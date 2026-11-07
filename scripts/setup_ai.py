"""Explicit, repeatable optional installation. Run only from project .venv."""
from pathlib import Path
import hashlib
import importlib.metadata
import re
import subprocess
import sys
import urllib.request

root = Path(__file__).resolve().parent.parent
if sys.prefix == sys.base_prefix:
    raise SystemExit('Dùng .venv/bin/python scripts/setup_ai.py')
try:
    installed=importlib.metadata.version('onnxruntime')
except importlib.metadata.PackageNotFoundError:
    installed=None
match=re.match(r'(\d+)\.(\d+)\.(\d+)',installed or '')
compatible=match and (1,23,2)<=tuple(map(int,match.groups()))<(2,0,0)
if not compatible:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root/'requirements-ai.txt')], check=True)
model = root/'models'/'balloon.onnx'
model.parent.mkdir(exist_ok=True)
expected = '88b84105ad2faec516fd164a2783fa6b6007dfd6ab07aa90e92b0241e51ea4cf'
if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest() != expected:
    part = model.with_suffix('.part')
    try:
        urllib.request.urlretrieve('https://raw.githubusercontent.com/igun997/manga-translator/1397af38e3464cdf4931c705857b8bef015030dc/manga_models/bubble.onnx', part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Model tải về sai checksum')
        part.replace(model)
    finally:
        part.unlink(missing_ok=True)
print('AI sẵn sàng:', model)
text_model = root/'models'/'comic_text_int8.onnx'
text_expected = 'b5022ad46416b6fe4f88b0cc082cfd2ff5b1cfc624088c2f19879485493f5913'
if not text_model.exists() or hashlib.sha256(text_model.read_bytes()).hexdigest() != text_expected:
    part = text_model.with_suffix('.part')
    try:
        urllib.request.urlretrieve('https://huggingface.co/ogkalu/comic-text-and-bubble-detector/resolve/16e8a622f91fabc6b5b65c96d32d1183f8843546/detector_int8.onnx', part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != text_expected:
            raise RuntimeError('Model chữ truyện tải về sai checksum')
        part.replace(text_model)
    finally:
        part.unlink(missing_ok=True)
print('AI chữ truyện sẵn sàng:', text_model)
