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
    local_tessdata = Path(__file__).resolve().parent.parent / "models" / "tessdata"
    if local_tessdata.is_dir() and "TESSDATA_PREFIX" not in os.environ:
        os.environ["TESSDATA_PREFIX"] = str(local_tessdata)

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
    missing_langs = [v for v in ("eng", "jpn", "jpn_vert", "chi_sim", "chi_tra", "kor", "vie") if v not in languages]
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
    if request.get("accel"):
        os.environ["MANGA_ACCEL"] = str(request["accel"]).lower()
    operation = request.get("operation")
    if isinstance(operation, str) and operation.startswith('translation_'):
        from .translation import service
        action = operation[len('translation_'):]
        if action == 'profile':
            return service.save_profile(request['project'], request['profile'])
        if action == 'preview_prompt':
            from .translation.prompts import compose, CORE
            return {'prompt': compose(request['profile']), 'core': CORE}
        if action == 'preset':
            from .translation.prompts import preset
            return preset(request['name'])
        if action == 'load':
            return service.load(request['project'])
        if action == 'index':
            return service.index_page(request['project'], request['manifest'], request['page_id'], request['ordinal'])
        if action == 'source':
            return service.edit_source(request['project'], request['segment_id'], request['text'], request.get('verified') is True, request.get('based_on','manual'))
        if action == 'ruby':
            return service.edit_ruby(request['project'],request['segment_id'],request['entries'],request.get('confirmed') is True)
        if action == 'exclude':
            return service.exclude_source(request['project'], request['segment_id'], request.get('excluded') is not False)
        if action == 'ocr_crop':
            return service.ocr_crop(request['project'], request['segment_id'], request.get('candidate') is True, request.get('cancel'))
        if action == 'ocr_suggest_batch':
            return service.ocr_suggest_batch(request['project'], request['segment_ids'], request.get('cancel'))
        if action == 'auto_ocr_page':
            return service.auto_ocr_page(request['project'],request['page_id'],request.get('cancel'))
        if action == 'visual_ocr_page':
            return service.visual_ocr_page(request['project'],request['page_id'],request.get('cancel'))
        if action == 'verify_page':
            return service.verify_page(request['manifest'], request['snapshot'])
        if action == 'prepare':
            return service.prepare(request['project'])
        if action == 'resume_or_prepare':
            return service.resume_or_prepare(request['project'])
        if action == 'preview_group':
            from .translation.grouping import payload_for_group, input_chars
            state=service.load(request['project'])
            run=next((r for r in state['runs'] if r['id']==request['run_id']),None)
            group=next((g for g in run['groups'] if g['id']==request['group_id']),None) if run else None
            if not group or not run.get('compiled_system'): raise ValueError('Không tìm thấy nhóm hoặc prompt snapshot')
            payload=payload_for_group(group)
            profile=next(p['values'] for p in state['profiles'] if p['revision']==run['profile_revision'])
            if profile.get('vision_mode','off')!='off':
                from .translation.vision import image_plan, public_plan
                payload['image_context']=public_plan(image_plan(state,group,profile['vision_mode']))
            import json
            return {'system':run['compiled_system'], 'payload':payload,
                    'input_chars':len(run['compiled_system'])+len(json.dumps(payload,ensure_ascii=False)),
                    'omitted_context_count':group.get('omitted_context_count',0)}
        if action == 'autopilot':
            from .translation import autopilot
            return autopilot.autopilot(request['project'], request.get('run_id'), max_attempts=int(request.get('max_attempts',3)),
                budget_seconds=request.get('budget_seconds'), auto_exclude=request.get('auto_exclude') is not False, cancel=request.get('cancel'),
                max_page_ordinal=request.get('max_page_ordinal'), max_groups=request.get('max_groups'),
                max_slice_attempts=request.get('max_slice_attempts'))
        if action == 'review_queue':
            from .report import review_queue
            return review_queue(request['project'], request['log'], request.get('state'))
        if action == 'review_mark':
            from .report import mark_reviewed
            return {'marked': mark_reviewed(request['state'], request['keys'], request.get('status', 'done'))}
        if action == 'env_check':
            from .environment import check_auto_flow
            return check_auto_flow(key_env=request.get('key_env','MANGA_TRANSLATION_API_KEY'))
        if action == 'key_status':
            from .translation.providers import key_status
            return key_status(request.get('key_env','MANGA_TRANSLATION_API_KEY'))
        if action == 'preflight_pick':
            from .preflight import pick_sample_pages
            return {'indices': pick_sample_pages(int(request['count']), int(request.get('k',3)))}
        if action == 'preflight_decide':
            from .preflight import decide, scorecard
            card = scorecard(request['pages'])
            return {'card': card, **decide(card, request['engine'], request.get('escalated') is True)}
        if action == 'report':
            from .report import build_report
            return build_report(request['project'], request['log'], request.get('out'), request.get('title','Báo cáo dịch truyện'))
        if action == 'cast_analyse':
            from .translation import cast
            result = cast.analyse(request['project'], int(request.get('page_limit', 6)), request.get('cancel'))
            cast.apply(request['project'])
            return result
        if action == 'cast_confirm':
            from .translation import cast
            return cast.set_status(request['project'], request['ids'], request.get('status', 'confirmed'))
        if action == 'cast_show':
            from .translation import cast
            state = service.load(request['project'])
            return {'cast': state.get('cast'), 'prompt': cast.render_prompt(state.get('cast'))}
        if action == 'auto_shorten':
            from .translation import shorten
            return shorten.auto_shorten(request['project'], request.get('run_id'), request.get('font_path'),
                budget_seconds=request.get('budget_seconds'), cancel=request.get('cancel'), page_ids=request.get('page_ids'),
                max_pages_per_call=request.get('max_pages_per_call'))
        if action == 'estimate':
            from .translation import autopilot
            return autopilot.estimate(request['project'], request.get('run_id'))
        if action == 'auto_exclude':
            from .translation import triage
            return triage.auto_exclude(request['project'], dry_run=request.get('dry_run') is True)
        if action == 'run_group':
            return service.run_group(request['project'], request['run_id'], request['group_id'], request.get('cancel'))
        if action == 'review_group':
            return service.review_group(request['project'], request['run_id'], request['group_id'], request.get('cancel'))
        if action == 'repair_quote':
            return service.repair_quote_group(request['project'],request['run_id'],request['group_id'],request.get('cancel'))
        if action == 'repair_slip':
            return service.repair_slip_group(request['project'],request['run_id'],request['group_id'],request.get('cancel'))
        if action == 'accept':
            return service.accept(request['project'], request['run_id'], request['edits'])
        if action == 'approve_lettering':
            return service.approve_lettering(request['project'],request['run_id'],request['segment_id'],request['text'])
        if action == 'mapping':
            return service.export_mapping(request['project'], request['run_id'])
        if action == 'draft_mapping':
            return service.export_mapping(request['project'], request['run_id'], draft=True, page_ids=request.get('page_ids'))
        raise ValueError('Thao tác dịch không được hỗ trợ: ' + action)
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
    parser.add_argument("--accel", choices=("auto", "cpu", "coreml", "cuda"), default=None,
                        help="Chế độ tăng tốc phần cứng: auto, cpu, coreml hoặc cuda")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    dl = sub.add_parser("download-models", help="Tải hoặc kiểm tra weights model theo profile")
    dl.add_argument("--profile", choices=["1107", "preview", "assist", "aot"], default="1107")
    dl.add_argument("--check-only", action="store_true", help="Chỉ kiểm tra offline mà không tải")
    clean = sub.add_parser("clean", help="Tạo overlay từ mapping đã duyệt trong manifest")
    clean.add_argument("manifest", type=Path)
    translate = sub.add_parser("translate", help="Dịch cả tập: tự thử lại, tiếp tục từ chỗ dừng, không giới hạn thời gian")
    translate.add_argument("--project", type=Path, required=True)
    translate.add_argument("--max-attempts", type=int, default=3)
    translate.add_argument("--no-exclude", action="store_true", help="Không tự loại banner, tựa, bản quyền, chữ ngoài bubble")
    translate.add_argument("--estimate-only", action="store_true")
    translate.add_argument("--no-shorten", action="store_true", help="Không tự rút gọn các dòng làm chữ bị bé")
    translate.add_argument("--no-cast", action="store_true", help="Không tự phân tích nhân vật và xưng hô trước khi dịch")
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
    if args.accel:
        os.environ["MANGA_ACCEL"] = args.accel
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
    if args.command == "translate":
        import json
        from .translation import autopilot, service as translation_service
        if args.estimate_only:
            print(json.dumps(autopilot.estimate(args.project), ensure_ascii=False, indent=2))
            return 0
        def show(info):
            print(json.dumps({'group': f"{info['index']}/{info['total']}", 'status': info['status'], 'attempts': info['attempts'],
                              'error': info['error']}, ensure_ascii=False), flush=True)
        # Automatic cast lookahead is disabled until facts can be retrieved
        # with a verified temporal boundary; --no-cast remains accepted.
        report = autopilot.autopilot(args.project, max_attempts=args.max_attempts, auto_exclude=not args.no_exclude, progress=show)
        if report['done'] and not args.no_shorten:
            from .translation import shorten
            report['shorten'] = shorten.auto_shorten(args.project, report['run_id'])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['done'] else 3
    if args.command == "doctor":
        import json
        report = doctor()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready"] else 2
    if args.command == "download-models":
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from scripts.download_models import main as dl_main
        dl_argv = ["--profile", args.profile]
        if not args.check_only:
            dl_argv.append("--download")
        return dl_main(dl_argv)
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
