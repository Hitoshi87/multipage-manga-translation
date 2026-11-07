"""1107 reviewable clean from a freshly scanned manifest.

The selected mapping is respected and unselected regions are protected. The
experimental recovery stages are the same ones used in the approved 1107 run.
"""

from .runtime.resources import sha256_file, read_rgb, read_gray
import contextlib
import io
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .io import checked_mapping, read_json, validate_manifest, write_json
from .engine import check_cancel, read_image, render_clean, save_image
from .coordinates import analysis_image

VERSION='1107-shadow-0.4'


def render(manifest_path, mapping, cancel=None, preview=False):
    from .model_preview import ctd_mask
    from .comic_text_ai import detect
    from .head_protection import detect as detect_heads
    started=time.monotonic();manifest_path=Path(manifest_path).resolve();root=manifest_path.parent
    manifest=validate_manifest(read_json(manifest_path));mapping=checked_mapping(manifest,mapping)
    selected={m['id'] for m in mapping if m['clean']}
    original=read_image(root/'original.png')
    if original.shape[:2] != (manifest['height'],manifest['width']):raise ValueError('Ảnh gốc không khớp manifest')
    check_cancel(cancel)
    # Temporary copies keep preview and mapping modifications away from the user's manifest.
    with tempfile.TemporaryDirectory(prefix='engine1107_', dir=root) as tmp:
        home=Path(tmp)/'input';p=home/'case/p04/pages/page';scan=p/'scan';scan.mkdir(parents=True)
        shutil.copy2(root/'original.png',scan/'original.png');shutil.copy2(manifest_path,scan/'manifest.json')
        shutil.copytree(root/'masks',scan/'masks',dirs_exist_ok=True)
        base=render_clean(scan/'manifest.json',mapping,cancel,True);check_cancel(cancel)
        source_hash=sha256_file(root/'original.png')
        write_json(p/'baseline_complete.json',{'source_sha256':source_hash,'applied':base['applied'], 'skipped':base['skipped'], 'blocked':base['blocked']})
        small=analysis_image(original,'ai');ah,aw=small.shape[:2]
        ctd=ctd_mask(small);check_cancel(cancel);detections=detect(small);check_cancel(cancel);heads=detect_heads(small);check_cancel(cancel)
        Image.fromarray(ctd*255).save(p/'ctd_full_page_analysis.png')
        write_json(p/'independent_text_detections.json',{'original':detections,'resolution':[aw,ah],'source':'comic_text_int8 ONNX'})
        write_json(p/'audit_heads.json',{'boxes_analysis':heads,'model':'animeheadsv3.onnx'})
        del small,ctd
        # No stage mutates the source image; release the outer full-page copy.
        del original
        from .engines import core_1107
        from .engines.stages import general
        from .engines.stages import border
        from .engines.stages import ownership as owner
        with contextlib.redirect_stdout(io.StringIO()):core_1107.run(p.parent,home/'no_case_specific_masks',home/'case/core','page',make_previews=False)
        core=home/'case/core/pages/page';trace_path=core/'trace.json'
        if not trace_path.exists():raise RuntimeError('1107 core failed: '+(core/'error.json').read_text() if (core/'error.json').exists() else '1107 core trace missing')
        for a,b in [('shadow_lossless.png','shadow.png'),('compositing_mask.png','mask.png')]:shutil.copy2(core/a,core/b)
        check_cancel(cancel)
        gt=general.process('page',p04=p.parent,prior=core.parent,out=home/'case/general',selected_ids=selected,make_previews=False);check_cancel(cancel)
        bt=border.run('page',p04=p.parent,base=home/'case/general/pages',out=home/'case/border',make_previews=False);check_cancel(cancel)
        ot=owner.process('case','page',source_root=home,output_root=home/'output',selected_ids=selected,make_previews=False);check_cancel(cancel)
        dest=home/'output/case/pages/page';clean=read_rgb(dest/'shadow.png');mask=read_gray(dest/'mask.png')>0
        original=read_image(root/'original.png')
        from .engines.flat_finish import finish_page
        prefix='trial_' if preview else ''
        finish_artifacts=root/(prefix+'1107_flat_finish');finish_artifacts.mkdir(exist_ok=True)
        for stale in finish_artifacts.iterdir():
            if stale.is_file() and stale.suffix in ('.png','.json'):stale.unlink()
        clean,mask,finish=finish_page(original,clean,mask,manifest['regions'],selected,ot,heads,[aw,ah],cancel,finish_artifacts)
        outside=int((np.any(original!=clean,axis=2)&~mask).sum())
        del original
        if outside:raise RuntimeError('1107 thay đổi pixel ngoài mask')
        overlay=np.zeros((*mask.shape,4),np.uint8);overlay[:,:,:3]=clean;overlay[:,:,3]=mask.astype('uint8')*255
        overlay_path=root/(prefix+'1107_overlay.png');clean_path=root/(prefix+'1107_clean.png');mask_path=root/(prefix+'1107_mask.png');trace_out=root/(prefix+'1107_trace.json')
        save_image(overlay_path,overlay);save_image(clean_path,clean);save_image(mask_path,(mask*255).astype('uint8'))
        events=ot['events'];reasons={r['id']:[] for r in manifest['regions'] if r['id'] in selected}
        for event in events:
            if event['region'] in reasons:reasons[event['region']].append({'decision':event['decision'],'reason':event['reason']})
        for event in finish['events']:
            if event.get('changed_pixels',0):reasons[event['region_id']].append({'decision':'SHADOW_FINISH_REVIEW','reason':'FLAT_TEXT_BACKGROUND_FIELD'})
        artifacts=root/(prefix+'1107_region_masks');artifacts.mkdir(exist_ok=True)
        for stale in artifacts.glob('*.png'):stale.unlink()
        for stage,directory,pattern in [('core',core/'regions','*_mask.png'),('core',core/'regions','*_skip_preview_mask.png'),('general',home/'case/general/pages/page','B*_added_mask.png'),('border',home/'case/border/pages/page','B*_mask.png'),('ownership',dest,'B*_mask.png')]:
            for path in directory.glob(pattern):shutil.copy2(path,artifacts/(stage+'_'+path.name))
        from .hardware import runtime_info, SESSION_REPORTS
        write_json(trace_out,{'version':VERSION,'selected_ids':sorted(selected),'baseline':base,'core':read_json(trace_path),'general':gt,'border':bt,'ownership':ot,'flat_finish':finish,'flat_finish_artifacts':str(finish_artifacts),'region_reasons':reasons,'region_masks':str(artifacts),'outside_mask_changed':outside,'source_sha256':source_hash,'seconds':round(time.monotonic()-started,2),'hardware':{'profile':runtime_info(),'sessions':dict(SESSION_REPORTS)}})
        # Experimental pixels remain review-required even if some were changed.
        applied=[];skipped=sorted(selected);codes={};blocked={}
        for k in skipped:
            last=reasons[k][-1] if reasons[k] else {'decision':'REVIEW','reason':'NO_REGION_TRACE'}
            reason=last.get('reason') or 'UNSPECIFIED';codes[k]='1107_REVIEW_'+str(reason)
            baseline_status='baseline đã tạo mask' if k in base['applied'] else 'baseline bỏ qua'
            blocked[k]='1107: '+baseline_status+'; recovery: '+str(reason)+' — kiểm tra output trước khi dùng'
        return {'overlay':str(overlay_path),'preview':str(clean_path),'mask':str(mask_path),'trace':str(trace_out),'manifest':str(manifest_path),'applied':applied,'skipped':skipped,'review_ids':skipped.copy(),'blocked':blocked,'skip_reason_codes':codes,'experimental':True,'full_page':True,'mask_pixels':int(mask.sum()),'version':VERSION,'hardware':{'profile':runtime_info(),'sessions':dict(SESSION_REPORTS)}}
