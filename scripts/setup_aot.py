"""Install the small, pinned AOT model used by Koharu (22.7 MB)."""
from pathlib import Path
import hashlib
import sys
import urllib.request

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from manga_ai.aot_inpaint import MODEL, SHA256

if sys.prefix == sys.base_prefix:
    raise SystemExit('Dùng .venv/bin/python scripts/setup_aot.py')
if not MODEL.is_file() or hashlib.sha256(MODEL.read_bytes()).hexdigest() != SHA256:
    MODEL.parent.mkdir(exist_ok=True)
    part = MODEL.with_suffix('.part')
    try:
        urllib.request.urlretrieve('https://huggingface.co/mayocream/aot-inpainting/resolve/cffe2346ac2b5ebe1f2d61335d602d12cc144c6f/model.safetensors', part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('Checksum AOT không khớp')
        part.replace(MODEL)
    finally:
        part.unlink(missing_ok=True)
print('Sẵn sàng:', MODEL)
