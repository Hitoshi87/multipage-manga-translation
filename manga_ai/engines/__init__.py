"""Trusted built-in clean engine registry; no arbitrary plugin code loading."""
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from .contracts import normalize_result

ROOT=Path(__file__).resolve().parents[2]
API_VERSION=1

@dataclass(frozen=True)
class EngineDescriptor:
    id: str
    version: str
    label: str
    required_models: tuple
    review_required: bool
    module: str
    callable_name: str

_ENGINES={
    'baseline':EngineDescriptor('baseline','baseline-1','Baseline',(),False,'manga_ai.engine','render_clean'),
    '1107':EngineDescriptor('1107','1107-shadow-0.5','1107 — nền chữ liên tục, kiểm tra clean',('models/balloon.onnx','models/comic_ctd.onnx','models/comic_text_int8.onnx','models/face/animeheadsv3.onnx'),True,'manga_ai.engine_1107','render'),
    'art_draft':EngineDescriptor('art_draft','art-draft-0.1','AI phục hồi nền — NHÁP CẦN KIỂM TRA',('models/comic_ctd.onnx','models/comic_text_int8.onnx','models/lama_manga.onnx'),True,'manga_ai.engine_art_draft','render'),
}


def list_engines():
    rows=[]
    for d in _ENGINES.values():
        row=asdict(d);row['api_version']=API_VERSION;row['missing_models']=[p for p in d.required_models if not (ROOT/p).is_file()];row['ready']=not row['missing_models'];rows.append(row)
    from ..ui_capabilities import ui_features
    return {'api_version':API_VERSION,'engines':rows,'default':'baseline','ui_features':ui_features()}


def run_engine(engine_id, manifest, mapping, cancel=None, preview=False, version=None):
    if engine_id not in _ENGINES:raise ValueError('Engine không tồn tại: '+str(engine_id))
    d=_ENGINES[engine_id]
    if version is not None and version!=d.version:raise ValueError('Phiên bản engine không khớp: '+str(version)+'; cần '+d.version)
    missing=[p for p in d.required_models if not (ROOT/p).is_file()]
    if missing:raise RuntimeError('Engine thiếu weights: '+', '.join(missing))
    handler=getattr(import_module(d.module),d.callable_name)
    result=handler(manifest,mapping,cancel,preview)
    result=normalize_result(result,mapping)
    result.update(engine_id=d.id,version=d.version,engine_api_version=API_VERSION)
    if not preview:
        # One Photoshop layer per cleaned bubble instead of a single page-wide layer.
        from ..clean_layers import attach_from_manifest
        attach_from_manifest(result,manifest)
    if preview:
        from .preview import preview_images
        result['images']=preview_images(result,manifest)
    return result
