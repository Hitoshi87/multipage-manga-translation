"""Everything the automatic (unattended) flow needs, checked up front.

A long run must not discover a missing dependency halfway through (for example Baberu OCR,
which is only touched at the OCR step). `check_auto_flow` reports every requirement at once,
with the exact command that fixes each one, and says which engine and models will actually run.
"""
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = (('numpy', 'numpy'), ('cv2', 'opencv-python-headless'), ('PIL', 'Pillow'),
            ('onnxruntime', 'onnxruntime'), ('pytesseract', 'pytesseract'))
DETECTOR = ('models/balloon.onnx', 'models/comic_text_int8.onnx')
AI_CLEAN = ('models/comic_ctd.onnx', 'models/comic_text_int8.onnx', 'models/lama_manga.onnx')
DL = 'python manga_typesetter.py download-models --profile '


def _item(item_id, label, missing, fix, required=True):
    return {'id': item_id, 'label': label, 'ok': not missing, 'missing': missing, 'fix': fix, 'required': required}


def baberu_files():
    from .baberu_ocr import FILES
    return ['models/baberu/' + name for name in FILES]


def check_auto_flow(root=None, doctor_fn=None, key_fn=None, package_fn=None, key_env='MANGA_TRANSLATION_API_KEY'):
    root = Path(root) if root is not None else ROOT
    package_fn = package_fn or (lambda name: find_spec(name) is not None)
    if doctor_fn is None:
        from .cli import doctor as doctor_fn
    if key_fn is None:
        from .translation.providers import key_status as key_fn
    absent = lambda paths: [p for p in paths if not (root / p).is_file()]
    items = [
        _item('packages', 'Thư viện Python', [pip for mod, pip in PACKAGES if not package_fn(mod)],
              'Cài lại môi trường: pip install -r requirements.txt (trong .venv)'),
    ]
    try:
        info = doctor_fn()
    except Exception as exc:                        # a broken Tesseract must not hide the other findings
        info = {'tesseract': None, 'languages': [], 'error': str(exc)}
    tess_missing = []
    if not info.get('tesseract'):
        tess_missing.append('Tesseract')
    elif 'jpn_vert' not in (info.get('languages') or []):
        tess_missing.append('ngôn ngữ jpn_vert')
    items.append(_item('tesseract', 'Tesseract OCR (jpn_vert)', tess_missing,
                       'macOS: ./setup_macos.command --install. Windows/Linux: cài Tesseract và gói ngôn ngữ jpn_vert'))
    items.append(_item('detector', 'Nhận diện bong bóng và chữ (AI)', absent(DETECTOR), DL + '1107'))
    items.append(_item('baberu', 'Baberu OCR (đọc chữ Nhật)', absent(baberu_files()), DL + 'assist'))
    ai_missing = absent(AI_CLEAN)
    items.append(_item('ai_clean', 'AI vẽ lại nền (CTD + LaMa)', ai_missing, DL + 'preview', required=False))
    key = key_fn(key_env)
    items.append(_item('api_key', 'API key dịch', [] if key.get('present') else ['API key'],
                       'Dán API key vào ô API key trong tab Tự động', required=True))
    engine = 'art_draft' if not ai_missing else 'baseline'
    plan = ['Nhận diện: AI (balloon.onnx) + chữ (comic_text_int8)', 'Đọc chữ Nhật: Baberu OCR (chạy trên máy)',
            'Xoá chữ: ' + ('engine AI vẽ lại nền art_draft (CTD + LaMa)' if engine == 'art_draft'
                           else 'engine thường baseline (thiếu model AI vẽ lại nền, nhiều bong bóng có thể không được xoá)')]
    return {'ready': all(i['ok'] for i in items if i['required']), 'engine': engine, 'items': items, 'plan': plan}
