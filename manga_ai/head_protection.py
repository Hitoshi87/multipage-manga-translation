"""Optional conservative exclusion of learned manga/anime head boxes."""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

MODEL=Path(__file__).resolve().parent.parent/'models/face/animeheadsv3.onnx'
SHA256='7f6ee8482dc12af94ebdd993ca6c21bb58668562714057c6948e6d639150b255'


@lru_cache(maxsize=1)
def session():
    if not MODEL.is_file() or sha256_file(MODEL)!=SHA256:
        raise RuntimeError('Thiếu model bảo vệ đầu/mặt. Chạy scripts/setup_assist_models.py')
    import onnxruntime as ort
    opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
    opts.enable_cpu_mem_arena=False;opts.enable_mem_pattern=False
    from .hardware import create_session
    return create_session(ort, MODEL, opts, 'head')


def detect(rgb,threshold=.25):
    h,w=rgb.shape[:2];scale=min(640/w,640/h);nw,nh=round(w*scale),round(h*scale)
    left,top=(640-nw)//2,(640-nh)//2
    square=np.full((640,640,3),114,np.uint8);square[top:top+nh,left:left+nw]=cv2.resize(rgb,(nw,nh))
    tensor=np.ascontiguousarray(square.transpose(2,0,1)[None],dtype=np.float32)/255
    runner=session();out=runner.run(None,{runner.get_inputs()[0].name:tensor})[0][0]
    if out.shape[0]==5:out=out.T
    boxes=[];scores=[]
    for cx,cy,bw,bh,score in out:
        if score<threshold:continue
        x1=max(0,int((cx-bw/2-left)/scale));y1=max(0,int((cy-bh/2-top)/scale))
        x2=min(w,int(np.ceil((cx+bw/2-left)/scale)));y2=min(h,int(np.ceil((cy+bh/2-top)/scale)))
        if x2>x1 and y2>y1:boxes.append([x1,y1,x2-x1,y2-y1]);scores.append(float(score))
    if not boxes:return []
    keep=np.asarray(cv2.dnn.NMSBoxes(boxes,scores,threshold,.45)).reshape(-1)
    return [boxes[i] for i in keep]


def protect(mask, boxes, padding=.08):
    """Remove all clean pixels within head boxes. Text there requires manual work."""
    result=mask.copy();h,w=mask.shape
    for x,y,bw,bh in boxes:
        dx=round(bw*padding);dy=round(bh*padding)
        result[max(0,y-dy):min(h,y+bh+dy),max(0,x-dx):min(w,x+bw+dx)]=0
    return result
