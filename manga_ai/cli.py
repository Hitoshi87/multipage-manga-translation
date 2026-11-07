from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import platform
import os
import re
import shutil
import subprocess
import sys
import traceback
import uuid
from pathlib import Path

from .io import import_text, parse_translations, read_json, write_json, import_translation_folder


def doctor():
    packages = {name: importlib.util.find_spec(module) is not None for name, module in
                (("numpy", "numpy"), ("opencv-python-headless", "cv2"),
                 ("Pillow", "PIL"), ("pytesseract", "pytesseract"))}
    executable = next((p for p in [shutil.which("tesseract"), "/opt/homebrew/bin/tesseract",
                                   "/usr/local/bin/tesseract"] if p and Path(p).is_file()), None)
    languages = []
    if executable:
        result = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            languages = result.stdout.splitlines()[1:]
    missing_langs = [v for v in ("eng", "jpn", "jpn_vert", "chi_sim", "chi_tra", "kor") if v not in languages]
    try:
        from .hardware import runtime_info
        hardware=runtime_info()
    except Exception as exc:
        hardware={'error':str(exc)}
    return {"platform": platform.platform(), "cpu": platform.machine(), "python": sys.version.split()[0], 'hardware':hardware,
            'ai': {'runtime': importlib.util.find_spec('onnxruntime') is not None,
                   'model': (Path(__file__).resolve().parent.parent/'models'/'balloon.onnx').is_file()},
            "executable": sys.executable, "venv": sys.prefix != sys.base_prefix,
            "packages": packages, "tesseract": executable, "languages": languages,
            "missing_languages": missing_langs, "unicode": "Tiếng Việt: Truyện tranh — Đường dẫn có dấu",
            "ready": all(packages.values()) and not missing_langs and sys.prefix != sys.base_prefix
                     and sys.version_info >= (3, 12)}


def dispatch(request):
    operation = request.get("operation")
    if operation == "doctor":
        return doctor()
    if operation == "import":
        if Path(request['path']).is_dir():
            return import_translation_folder(request['path'])
        text = import_text(request["path"])
        return {"text": text, **parse_translations(text)}
    if operation == "translations":
        return parse_translations(request.get("text", ""))
    if operation == "preview":
        from .engine import preview_review
        return preview_review(request["data"], request["folder"], request.get("selected"))
    if operation == "model_preview":
        from .model_preview import preview
        return preview(request['input'], request['out'], request['method'], bool(request.get('lama')), request.get('cancel'), bool(request.get('protect_faces')), request.get('inpaint'))
    if operation == "model_batch_clean":
        from .model_preview import batch_clean
        return batch_clean(request['manifest'], request['mapping'], request['method'], bool(request.get('lama')), request.get('cancel'), bool(request.get('protect_faces')), request.get('inpaint'))
    if operation == 'region_shadow_preview':
        from .experimental_region_preview import preview_region
        return preview_region(request['manifest'], request['region_id'])
    if operation == "alignment_suggest":
        from .alignment_assist import suggest
        return suggest(request['manifest'], request['translations'], request.get('cancel'))
    if operation == "font_suggest":
        from .font_assist import suggest_font
        return suggest_font(request['manifest'],request['region_id'],request.get('text',''),request.get('cancel'))
    if operation == "scan":
        from .engine import analyse
        return analyse(request["input"], request["out"], request.get("lang", "eng"),
                       request.get("rtl", True), int(request.get("psm", 11)), request.get("cancel"), request.get('detector', 'opencv'), request.get('layout','opencv'), request.get('detail','standard'))
    if operation == 'list_engines':
        from .engines import list_engines
        return list_engines()
    if operation == 'run_engine':
        from .engines import run_engine
        return run_engine(request['engine_id'],request['manifest'],request['mapping'],request.get('cancel'),request.get('preview',False),request.get('engine_version'))
    if operation == "clean":
        from .engine import render_clean
        return render_clean(request["manifest"], request["mapping"], request.get("cancel"), request.get("preview", False))
    if operation == "clean_1107":
        from .engine_1107 import render
        return render(request['manifest'], request['mapping'], request.get('cancel'), request.get('preview', False))
    raise ValueError("Thao tác không được hỗ trợ: " + str(operation))


def natural_key(path):
    return [int(s) if s.isdigit() else s.casefold() for s in re.split(r"(\d+)", path.name)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manga Typesetter AI — macOS local worker")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--response", type=Path)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    clean = sub.add_parser("clean", help="Tạo overlay từ mapping đã duyệt trong manifest")
    clean.add_argument("manifest", type=Path)
    scan = sub.add_parser("scan", help="Tiền xử lý độc lập; JSX nhập manifest.json")
    scan.add_argument("input", type=Path)
    scan.add_argument("--out", type=Path, required=True)
    scan.add_argument("--lang", default="eng")
    scan.add_argument("--order", choices=("rtl", "ltr"), default="rtl")
    scan.add_argument("--psm", type=int, default=11)
    scan.add_argument('--detector', choices=('opencv', 'ai'), default='opencv')
    scan.add_argument("--translations", type=Path)
    scan.add_argument("--min-conf", type=float, help=argparse.SUPPRESS)  # legacy CLI compatibility
    args = parser.parse_args(argv)
    if args.request:
        if not args.response:
            parser.error("--response bắt buộc với --request")
        try:
            result = dispatch(read_json(args.request))
            response = {"ok": True, "result": result}
            code = 0
        except Exception as exc:
            traceback.print_exc()
            if os.name=='nt':
                with (args.request.parent/'worker.log').open('a',encoding='utf-8') as log:
                    log.write(traceback.format_exc())
            response = {"ok": False, "error": str(exc), "type": type(exc).__name__}
            code = 1
        write_json(args.response, response)
        return code
    if args.command == "doctor":
        import json
        report = doctor()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready"] else 2
    if args.command == "clean":
        from .engine import render_clean
        manifest = read_json(args.manifest)
        result = render_clean(args.manifest, manifest.get("mapping", []))
        print(result["overlay"])
        print("Clean:", result["applied"], "Thủ công:", result["skipped"])
        return 0
    if args.command == "scan":
        from .engine import analyse, render_clean
        if not args.input.exists():
            parser.error("Đầu vào không tồn tại")
        supported = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}
        sources = sorted((p for p in args.input.iterdir() if p.suffix.lower() in supported and not re.search(r'_(clean|typeset)(?:_\d+)?\.[^.]+$',p.name,re.I)), key=natural_key) if args.input.is_dir() else [args.input]
        if not sources:
            parser.error("Không tìm thấy ảnh; PSD cần xuất ảnh tổng hợp từ JSX")
        run = args.out.resolve() / ("run_" + uuid.uuid4().hex[:12])
        run.mkdir(parents=True)
        translations = (import_translation_folder(args.translations) if args.translations.is_dir()
                        else parse_translations(import_text(args.translations))) if args.translations else None
        if translations and len(sources) > 1 and not translations["marked"]:
            parser.error("Nhiều trang cần marker [PAGE 1], [PAGE 2] để tránh ghép lệch")
        results = []
        for index, source in enumerate(sources, 1):
            try:
                target = run / f"{index:03d}_{source.stem}"
                result = analyse(source, target, args.lang, args.order == "rtl", args.psm, detector=args.detector)
                if translations:
                    number = re.search(r'(\d+)$', source.stem)
                    key = str(int(number[1])) if number and (translations.get('filename_pages') or str(int(number[1])) in translations['pages']) else str(index)
                    lines = translations["pages"].get(key, [])
                    mapping = [{"id": region["id"], "translation": line, "clean": True}
                               for region, line in zip(result["regions"], lines)]
                    if len(lines) != len(result["regions"]):
                        write_json(target / "translation_review.json", {"translations": lines, "mapping": mapping,
                                   "warning": "Số dòng khác số vùng: sửa mapping trong JSX trước khi clean"})
                    else:
                        render_clean(target / "manifest.json", mapping)
                results.append({"page": index, "source": str(source), "ok": True, "manifest": result["manifest"]})
                print(f"[{index}/{len(sources)}] {source.name}: {len(result['regions'])} vùng", flush=True)
            except Exception as exc:
                results.append({"page": index, "source": str(source), "ok": False, "error": str(exc)})
                print(f"LỖI {source.name}: {exc}", file=sys.stderr, flush=True)
            write_json(run / "batch.json", results)
        print("Kết quả:", run)
        return 1 if any(not item["ok"] for item in results) else 0
    parser.print_help()
    return 2
