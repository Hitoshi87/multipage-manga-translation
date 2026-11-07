"""Optional heavyweight Magi + Qwen installation; downloads about 5 GB."""
from pathlib import Path
import hashlib
import subprocess
import sys
import urllib.request

root=Path(__file__).resolve().parent.parent
if sys.prefix==sys.base_prefix:raise SystemExit('Dùng .venv/bin/python scripts/setup_heavy_assist.py')
subprocess.run([sys.executable,'-m','pip','install','-r',str(root/'requirements-heavy-assist.txt')],check=True)
qenv=root/'.venv-qwen312'
if not (qenv/'bin/python').exists():subprocess.run([sys.executable,'-m','venv',str(qenv)],check=True)
subprocess.run([str(qenv/'bin/python'),'-m','pip','install','mlx-vlm==0.7.12'],check=True)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def fetch(target,url,expected=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and (expected is None or sha(target)==expected):return
    part=target.with_suffix(target.suffix+'.part')
    try:
        print('Đang tải:',target,flush=True);urllib.request.urlretrieve(url,part)
        if expected and sha(part)!=expected:raise RuntimeError('Checksum sai: '+str(target))
        part.replace(target)
    finally:part.unlink(missing_ok=True)

magi='https://huggingface.co/ragavsachdeva/magi/resolve/15ad498ad45093ad3b833d625728220c6309ad99/'
checks={'model.safetensors':'b4f77488ed0205e8b74b7373850d06ab7661752688c5e4f28f35095931e97c14',
 'config.json':'d2bba2e467f12843c29837b70a1adf8d9da249107990647764da6f487db18454',
 'conditional_detr_utils.py':'867b539a5eb0596670a9747fb340bb4f3f106e0a1034c2dc8f94fee1067b84c7',
 'configuration_magi.py':'a86301226fc88cdd4a50ee339551f2824d9bfbde7444954622babe13cd6512b7',
 'modelling_magi.py':'b90e7324ac9b7b70ae43a60243b37a9aea2d445e942a62ff9b20307d33566e8f',
 'processing_magi.py':'deaf43ed10be7f3a37272cb3561e7fb6cdeb5b7e7b285e81a660156578d1f8ea',
 'utils.py':'25313e9745f9e37779eb1e643c8c7c24d943a303d29babfa08109575b047a62f'}
for name,expected in checks.items():fetch(root/'models/magi'/name,magi+name,expected)
qwen='https://huggingface.co/mlx-community/Qwen2.5-VL-3B-Instruct-4bit/resolve/46d4cf06a06ffc1a766c214174f9cbed2f45bcab/'
for name in ('config.json','preprocessor_config.json','tokenizer_config.json','tokenizer.json','vocab.json','merges.txt','special_tokens_map.json','chat_template.json','model.safetensors.index.json','added_tokens.json'):
    fetch(root/'models/qwen_vl'/name,qwen+name)
fetch(root/'models/qwen_vl/model.safetensors',qwen+'model.safetensors','636982419c940321ac0f7793dc9dc3575a4ee4843a6b167b2e8c3d3cd25dacf4')
print('Đã chuẩn bị Magi và Qwen.')
