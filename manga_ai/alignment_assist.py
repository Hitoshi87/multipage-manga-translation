"""Review-only multilingual matching; scores are not probabilities."""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path
import hashlib

import numpy as np

ROOT=Path(__file__).resolve().parent.parent/'models/e5'
FILES={'tokenizer.json':'0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39',
       'model_qint8_avx512_vnni.onnx':'dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'}


@lru_cache(maxsize=1)
def runtime():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    for name,digest in FILES.items():
        f=ROOT/name
        if not f.is_file() or sha256_file(f)!=digest:
            raise RuntimeError('Thiếu model đối chiếu E5; chạy scripts/setup_assist_models.py')
    tok=Tokenizer.from_file(str(ROOT/'tokenizer.json'));tok.enable_truncation(max_length=256);tok.enable_padding()
    opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
    opts.enable_cpu_mem_arena=False;opts.enable_mem_pattern=False
    net=ort.InferenceSession(str(ROOT/'model_qint8_avx512_vnni.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
    return tok,net


def encode(texts):
    tok,net=runtime();all_vectors=[]
    for offset in range(0,len(texts),16):
        batch=tok.encode_batch(['query: '+t for t in texts[offset:offset+16]])
        feeds={'input_ids':np.asarray([x.ids for x in batch],np.int64),
               'attention_mask':np.asarray([x.attention_mask for x in batch],np.int64),
               'token_type_ids':np.asarray([x.type_ids for x in batch],np.int64)}
        hidden=net.run(None,feeds)[0];mask=feeds['attention_mask'][:,:,None]
        vec=(hidden*mask).sum(axis=1)/np.maximum(mask.sum(axis=1),1)
        vec/=np.maximum(np.linalg.norm(vec,axis=1,keepdims=True),1e-12)
        all_vectors.extend(vec)
    return np.asarray(all_vectors)


def suggest(manifest_path, translations, cancel=None):
    from .io import read_json,validate_manifest
    from .engine import read_image,check_cancel
    from .baberu_ocr import read
    if not isinstance(translations,list) or any(not isinstance(x,str) for x in translations):
        raise ValueError('Danh sách bản dịch không hợp lệ')
    path=Path(manifest_path).resolve();data=validate_manifest(read_json(path));image=read_image(path.parent/'original.png')
    if image.shape[:2]!=(data['height'],data['width']):raise ValueError('Ảnh gốc không khớp manifest')
    regions=data['regions'];texts=[]
    for region in regions:
        check_cancel(cancel)
        x,y,w,h=region['box'];texts.append(read(image[y:y+h,x:x+w]))
    check_cancel(cancel)
    if not regions or not translations:return {'regions':[],'translations':translations}
    vectors=encode(texts+translations);scores=vectors[:len(texts)]@vectors[len(texts):].T
    results=[]
    for i,(region,ocr) in enumerate(zip(regions,texts)):
        candidates=sorted(range(len(translations)),key=lambda j:float(scores[i,j]),reverse=True)[:3]
        results.append({'id':region['id'],'ocr':ocr,'candidates':[{'index':j,'score':round(float(scores[i,j]),4)} for j in candidates]})
    return {'regions':results,'translations':translations}
