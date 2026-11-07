"""Optional Magi panel ordering; the pinned model is loaded locally on CPU."""
from functools import lru_cache
from pathlib import Path
import hashlib
import importlib
import os
import sys
import tempfile
import types

import numpy as np

ROOT=Path(__file__).resolve().parent.parent/'models/magi'
PANEL_WEIGHTS_SHA256='368bdc4363b8daecb29b524dbd607ab31546a92e4b0b25c819ad65594ffb540f'
PANEL_PREFIXES=('detection_transformer.','bbox_predictor.','class_labels_classifier.')
CHECKS={
 'model.safetensors':'b4f77488ed0205e8b74b7373850d06ab7661752688c5e4f28f35095931e97c14',
 'config.json':'d2bba2e467f12843c29837b70a1adf8d9da249107990647764da6f487db18454',
 'conditional_detr_utils.py':'867b539a5eb0596670a9747fb340bb4f3f106e0a1034c2dc8f94fee1067b84c7',
 'configuration_magi.py':'a86301226fc88cdd4a50ee339551f2824d9bfbde7444954622babe13cd6512b7',
 'modelling_magi.py':'b90e7324ac9b7b70ae43a60243b37a9aea2d445e942a62ff9b20307d33566e8f',
 'processing_magi.py':'deaf43ed10be7f3a37272cb3561e7fb6cdeb5b7e7b285e81a660156578d1f8ea',
 'utils.py':'25313e9745f9e37779eb1e643c8c7c24d943a303d29babfa08109575b047a62f',
}


def digest_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def panel_weights():
    """Build a verified detector-only checkpoint once, then reuse it."""
    target=ROOT/'panels_only.safetensors'
    if target.is_file() and digest_file(target)==PANEL_WEIGHTS_SHA256:
        return target
    source=ROOT/'model.safetensors'
    if not source.is_file() or digest_file(source)!=CHECKS['model.safetensors']:
        raise RuntimeError('Thiếu/sai model Magi; chạy scripts/setup_heavy_assist.py')
    from safetensors import safe_open
    from safetensors.numpy import save_file
    with safe_open(source,framework='np') as f:
        tensors={name:f.get_tensor(name) for name in f.keys() if name.startswith(PANEL_PREFIXES)}
    fd,name=tempfile.mkstemp(prefix='.magi-panels-',suffix='.safetensors',dir=ROOT)
    os.close(fd)
    try:
        save_file(tensors,name)
        if digest_file(Path(name))!=PANEL_WEIGHTS_SHA256:
            raise RuntimeError('Không xác minh được trọng số Magi rút gọn')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
    return target


@lru_cache(maxsize=1)
def model():
    for filename,expected in CHECKS.items():
        if filename=='model.safetensors':continue
        path=ROOT/filename
        if not path.is_file() or digest_file(path)!=expected:
            raise RuntimeError('Thiếu/sai model Magi; chạy scripts/setup_heavy_assist.py')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from transformers import AutoConfig,AutoModel,logging
    import torch
    import matplotlib
    # Magi imports pyplot solely for visualization, not detection. Avoid
    # scanning all Photoshop fonts during a background inference worker.
    old={name:sys.modules.get(name) for name in ('matplotlib.pyplot','matplotlib.patches')}
    for name in old:sys.modules[name]=types.ModuleType(name)
    try:
        logging.set_verbosity_error();torch.set_num_threads(2)
        config=AutoConfig.from_pretrained(str(ROOT),trust_remote_code=True,local_files_only=True)
        config.disable_ocr=True;config.disable_crop_embeddings=True
        config.detection_model_config.use_pretrained_backbone=False
        # Panel detection only needs the detector, box head and classifier.
        # The 2 GB checkpoint also contains OCR and crop-embedding weights;
        # never materialize those unused tensors for each scanned page.
        from safetensors import safe_open
        net=AutoModel.from_config(config,trust_remote_code=True)
        required=PANEL_PREFIXES
        with safe_open(panel_weights(),framework='np') as source:
            state={name:torch.from_numpy(np.array(source.get_tensor(name),copy=True))
                   for name in source.keys() if name.startswith(required)}
        info=net.load_state_dict(state,strict=False)
        missing=[name for name in info.missing_keys if name.startswith(required)]
        if missing or info.unexpected_keys:
            raise RuntimeError('Thiếu trọng số nhận diện Magi: '+str(missing[:3]))
        return net.eval()
    finally:
        for name,value in old.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value


def panels(rgb):
    import torch
    from transformers.image_transforms import center_to_corners_format
    h,w=rgb.shape[:2]
    with torch.inference_mode():
        net=model()
        inputs=net.move_to_device(net.processor.preprocess_inputs_for_detection([rgb]))
        output=net._get_detection_transformer_output(**inputs)
        scores, boxes=net._get_predicted_bboxes_and_classes(output)
        scores,labels=scores.max(-1);scores=scores.sigmoid();labels=labels.long()
        boxes=center_to_corners_format(boxes)*torch.tensor([w,h,w,h],device=boxes.device)[None,None,:]
        indices=net.processor._get_indices_of_panels_to_keep(scores,labels,boxes,.2)[0]
        panel_boxes=boxes[0][indices]
        utils=importlib.import_module(net.processor.__class__.__module__.rsplit('.',1)[0]+'.utils')
        panel_boxes=panel_boxes[utils.sort_panels(panel_boxes)]
    boxes=[]
    for x1,y1,x2,y2 in panel_boxes.tolist():
        left=max(0,min(w,round(x1)));top=max(0,min(h,round(y1)))
        right=max(0,min(w,round(x2)));bottom=max(0,min(h,round(y2)))
        if right>left and bottom>top:boxes.append([left,top,right-left,bottom-top])
    return boxes
