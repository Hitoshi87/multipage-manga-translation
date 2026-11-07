"""Install the optional local preview models into the project's venv."""
from pathlib import Path
import hashlib
import subprocess
import sys
import urllib.request

root = Path(__file__).resolve().parent.parent
if sys.prefix == sys.base_prefix:
    raise SystemExit('Dùng .venv/bin/python scripts/setup_preview_models.py')
subprocess.run([sys.executable, str(root/'scripts/setup_ai.py')], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root/'requirements-preview.txt')], check=True)
models = [
    ('comic_ctd.onnx', 'https://huggingface.co/lemondouble/lemon-manga-translator/resolve/e8c08f38f188db684fdc32c4cf88627c7df92096/onnx/comic-text-detector/ctd.onnx', 'eea9f9ccad2364fcb15bdfeca25268be273fea80b111ba6a6f4c03f556c24c26'),
    ('comic_text_mask.pt', 'https://huggingface.co/TareHimself/comic-text-mask/resolve/ebd37f1a9ae9298519678fb96a796573fb602977/model.pt', 'c1de7cd35c5cce1c5eca4e03696129dc9649db6ebe7d03fe1b995d7aca73e605'),
    ('lama_manga.onnx', 'https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/ee4ed4a8447b6730fc41d34f90876b6c48af925a/lama-manga-dynamic.onnx', 'de31ffa5ba26916b8ea35319f6c12151ff9654d4261bccf0583a69bb095315f9'),
    ('koharu_layout.onnx', 'https://huggingface.co/ShiniShiho/koharu-layout-rfdetr-seg-2xl-1152-onnx/resolve/bfbbd4e5ab34a50459865074fa044da496cebb57/rfdetr-seg-2xlarge.onnx', '7cc10d4316371946b8441da3512261a8e148b129abcdb0ea6235ed1d1d06d351'),
]
for filename, url, expected in models:
    path=root/'models'/filename
    path.parent.mkdir(exist_ok=True)
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        part=path.with_suffix(path.suffix+'.part')
        try:
            urllib.request.urlretrieve(url, part)
            if hashlib.sha256(part.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('Checksum sai: '+filename)
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
    print('Sẵn sàng:', path)
