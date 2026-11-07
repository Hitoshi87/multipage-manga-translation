"""Cheap local readiness checks for optional UI tools; never load/download weights."""
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ui_features(root=None, available=None):
    root = Path(root) if root is not None else ROOT
    available = available or (lambda name: find_spec(name) is not None)
    features = {}

    def feature(name, files=(), packages=()):
        missing = [p for p in files if not (root / p).is_file()]
        missing += ['package:' + p for p in packages if not available(p)]
        features[name] = {'ready': not missing, 'missing': missing}

    ctd = 'models/comic_ctd.onnx'
    text = 'models/comic_text_int8.onnx'
    koharu = 'models/koharu_layout.onnx'
    head = 'models/face/animeheadsv3.onnx'
    feature('scan_ai', ('models/balloon.onnx', text), ('onnxruntime',))
    feature('koharu', (koharu,), ('onnxruntime',))
    feature('magi', tuple('models/magi/' + p for p in (
        'model.safetensors', 'config.json', 'conditional_detr_utils.py',
        'configuration_magi.py', 'modelling_magi.py', 'processing_magi.py', 'utils.py')),
        ('torch', 'transformers', 'safetensors', 'matplotlib'))
    feature('alignment', tuple('models/baberu/' + p for p in (
        'onnx/vision_int4.onnx', 'onnx/decoder_prefill_int8.onnx',
        'onnx/decoder_step_int8.onnx', 'tokenizer/vocab.json')) + (
        'models/e5/tokenizer.json', 'models/e5/model_qint8_avx512_vnni.onnx'),
        ('onnxruntime', 'tokenizers'))
    feature('font_qwen', ('.venv-qwen312/bin/python', 'models/qwen_vl/model.safetensors'))
    feature('mask_ctd', (ctd, text), ('onnxruntime',))
    feature('mask_mask', (ctd, text, 'models/comic_text_mask.pt'), ('onnxruntime', 'torch'))
    feature('mask_koharu', (ctd, text, koharu), ('onnxruntime',))
    feature('mask_hybrid', (ctd, text, koharu), ('onnxruntime',))
    feature('inpaint_lama', ('models/lama_manga.onnx',), ('onnxruntime',))
    feature('inpaint_aot', ('models/aot_manga.safetensors',), ('torch', 'safetensors'))
    feature('inpaint_white')
    feature('head_guard', (head,), ('onnxruntime',))
    return features
