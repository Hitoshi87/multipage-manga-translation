"""Optional Qwen VL advisory font classification on one crop."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

from PIL import Image

from .engine import read_image
from .io import read_json,validate_manifest

ROOT=Path(__file__).resolve().parent.parent


def suggest_font(manifest,region_id,text,cancel=None):
    path=Path(manifest).resolve();data=validate_manifest(read_json(path))
    region=next((r for r in data['regions'] if r['id']==region_id),None)
    if region is None:raise ValueError('Không tìm thấy vùng cần gợi ý font')
    python=ROOT/'.venv-qwen312/bin/python';weights=ROOT/'models/qwen_vl/model.safetensors'
    if not python.is_file() or not weights.is_file() or weights.stat().st_size!=3073720461:
        raise RuntimeError('Thiếu Qwen VL; chạy scripts/setup_heavy_assist.py')
    rgb=read_image(path.parent/'original.png');x,y,w,h=region['box'];pad=max(12,round(max(w,h)*.3))
    crop=rgb[max(0,y-pad):min(rgb.shape[0],y+h+pad),max(0,x-pad):min(rgb.shape[1],x+w+pad)]
    with tempfile.TemporaryDirectory(dir=path.parent,prefix='font_ai_') as tmp:
        folder=Path(tmp);image=folder/'crop.png';Image.fromarray(crop).save(image)
        request=folder/'request.json';response=folder/'response.json'
        request.write_text(json.dumps({'image':str(image),'text':str(text)},ensure_ascii=False),encoding='utf8')
        env=os.environ.copy();env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
        try:
            run=subprocess.run([str(python),str(ROOT/'scripts/qwen_font_helper.py'),str(request),str(response)],env=env,capture_output=True,text=True,timeout=150)
        except subprocess.TimeoutExpired as exc:raise RuntimeError('Qwen gợi ý font quá 150 giây') from exc
        if run.returncode or not response.exists():raise RuntimeError('Qwen chưa chạy được: '+run.stderr[-1200:])
        return json.loads(response.read_text(encoding='utf8'))
