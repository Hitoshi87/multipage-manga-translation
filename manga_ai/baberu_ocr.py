"""Local Baberu ONNX inference, based on upstream Apache-2.0 onnx_infer.py."""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import unicodedata

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent.parent/'models/baberu'
FILES={
 'onnx/vision_int4.onnx':'1967ecef502e4c1e1e7c512ea0a2e06396b39ded87a8a9cc77bd7db2e981a361',
 'onnx/decoder_prefill_int8.onnx':'187a59cb61d3870f1f97c9eb027eb34ff19d023fba801cda113a13870be0b724',
 'onnx/decoder_step_int8.onnx':'46640b0b3db77f0f0eef660bbe5dc9126a5e0fb49eb2786b2edba7b0371d9769',
 'tokenizer/vocab.json':'681de4eb83154a397af49e2ddae4705041b12a22e16fe00860b829e889e5f47c',
}


@lru_cache(maxsize=1)
def sessions():
    import onnxruntime as ort
    for name,checksum in FILES.items():
        f=ROOT/name
        if not f.is_file() or sha256_file(f)!=checksum:
            raise RuntimeError('Thiếu Baberu OCR; chạy scripts/setup_assist_models.py')
    opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
    opts.enable_cpu_mem_arena=False;opts.enable_mem_pattern=False
    def load(name):return ort.InferenceSession(str(ROOT/name),sess_options=opts,providers=['CPUExecutionProvider'])
    chars=json.loads((ROOT/'tokenizer/vocab.json').read_text(encoding='utf8'))
    return load('onnx/vision_int4.onnx'),load('onnx/decoder_prefill_int8.onnx'),load('onnx/decoder_step_int8.onnx'),chars


def read(rgb,max_tokens=160):
    vis,pre,step,chars=sessions()
    image=Image.fromarray(rgb).convert('RGB').resize((224,224),Image.Resampling.BICUBIC)
    x=np.asarray(image,dtype=np.float32)/255
    x=(x-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    emb=vis.run(['vision_embeds'],{'pixel_values':np.ascontiguousarray(x.transpose(2,0,1)[None])})[0]
    out=pre.run(None,{'vision_embeds':emb,'input_ids':np.array([[1]],np.int64)})
    logits,past=out[0][0,-1].astype(np.float64),out[1:];seq=[1];tokens=[];pos=emb.shape[1]+1
    names=['past_k'+str(i) for i in range(6)]+['past_v'+str(i) for i in range(6)]
    for _ in range(max_tokens):
        for tid in set(seq):logits[tid]=logits[tid]*1.2 if logits[tid]<0 else logits[tid]/1.2
        if tokens:
            last=tokens[-1];ch=chars[last-4] if 4<=last<len(chars)+4 else ''
            cap=12 if ch and ch not in 'ーｰ〜~' and unicodedata.category(ch)[0] in 'LN' else 16
            if len(tokens)>=cap and all(t==last for t in tokens[-cap:]):logits[last]=-np.inf
        token=int(np.argmax(logits))
        if token==2:break
        tokens.append(token);seq.append(token)
        if len(tokens)>=max_tokens:break
        feed={'input_ids':np.array([[token]],np.int64),'position_ids':np.array([[pos]],np.int64)}
        feed.update(dict(zip(names,past)))
        out=step.run(None,feed);logits,past=out[0][0,-1].astype(np.float64),out[1:];pos+=1
    return ''.join(chars[t-4] for t in tokens if 4<=t<len(chars)+4)
