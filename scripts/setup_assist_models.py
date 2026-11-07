"""Install optional local face protection and OCR/alignment models."""
from pathlib import Path
import hashlib
import subprocess
import sys
import urllib.request

root=Path(__file__).resolve().parent.parent
if sys.prefix==sys.base_prefix:raise SystemExit('Dùng .venv/bin/python scripts/setup_assist_models.py')
subprocess.run([sys.executable,'-m','pip','install','-r',str(root/'requirements-assist.txt')],check=True)
files=[
 ('face/animeheadsv3.onnx','https://huggingface.co/tori29umai/AnimeHeads-ONNX/resolve/98c202184f35f55f85872c0affafd5361d20eb6d/weights/animeheadsv3.onnx','7f6ee8482dc12af94ebdd993ca6c21bb58668562714057c6948e6d639150b255'),
 ('baberu/onnx/vision_int4.onnx','https://huggingface.co/genshiai-daichi/baberu-ocr/resolve/b9868433dbda3ed9ba1357d008599ff4ada873d5/onnx/vision_int4.onnx','1967ecef502e4c1e1e7c512ea0a2e06396b39ded87a8a9cc77bd7db2e981a361'),
 ('baberu/onnx/decoder_prefill_int8.onnx','https://huggingface.co/genshiai-daichi/baberu-ocr/resolve/b9868433dbda3ed9ba1357d008599ff4ada873d5/onnx/decoder_prefill_int8.onnx','187a59cb61d3870f1f97c9eb027eb34ff19d023fba801cda113a13870be0b724'),
 ('baberu/onnx/decoder_step_int8.onnx','https://huggingface.co/genshiai-daichi/baberu-ocr/resolve/b9868433dbda3ed9ba1357d008599ff4ada873d5/onnx/decoder_step_int8.onnx','46640b0b3db77f0f0eef660bbe5dc9126a5e0fb49eb2786b2edba7b0371d9769'),
 ('baberu/tokenizer/vocab.json','https://huggingface.co/genshiai-daichi/baberu-ocr/resolve/b9868433dbda3ed9ba1357d008599ff4ada873d5/tokenizer/vocab.json','681de4eb83154a397af49e2ddae4705041b12a22e16fe00860b829e889e5f47c'),
 ('e5/model_qint8_avx512_vnni.onnx','https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx/model_qint8_avx512_vnni.onnx','dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'),
 ('e5/tokenizer.json','https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/tokenizer.json','0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39'),
]
for name,url,digest in files:
    target=root/'models'/name;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
        part=target.with_suffix(target.suffix+'.part')
        try:
            urllib.request.urlretrieve(url,part)
            if hashlib.sha256(part.read_bytes()).hexdigest()!=digest:raise RuntimeError('Sai checksum: '+name)
            part.replace(target)
        finally:part.unlink(missing_ok=True)
    print('Sẵn sàng:',target)
