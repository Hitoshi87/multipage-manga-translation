"""Local AOT generator compatible with Koharu's pinned SafeTensors conversion.

Architecture: zyddnys/manga-image-translator AOTGenerator (MIT).
Weights: mayocream/aot-inpainting, see models/NOTICE.md. No remote code/pickle.
"""

from .runtime.resources import sha256_file
from functools import lru_cache
from pathlib import Path
import hashlib

import numpy as np

SHA256 = '1b4fea17a84a228c2097a42ab2f403357f07bb56ae022dc243b40817b7aa87d1'
MODEL = Path(__file__).resolve().parent.parent / 'models/aot_manga.safetensors'


@lru_cache(maxsize=1)
def session():
    if not MODEL.is_file() or sha256_file(MODEL) != SHA256:
        raise RuntimeError('Thiếu hoặc sai AOT Koharu. Chạy .venv/bin/python scripts/setup_aot.py')
    import torch
    from torch import nn
    from torch.nn import functional as F
    from safetensors.torch import load_file
    torch.set_num_threads(2)

    class StandardConv(nn.Conv2d):
        def __init__(self, ci, co, ks, stride):
            super().__init__(ci, co, ks, stride=stride)
            self.gain = nn.Parameter(torch.ones(co, 1, 1, 1))

        def forward(self, x):
            var, mean = torch.var_mean(self.weight, dim=(1, 2, 3), keepdim=True)
            scale = torch.rsqrt((var * np.prod(self.weight.shape[1:])).clamp_min(1e-4)) * self.gain
            return F.conv2d(x, (self.weight-mean)*scale, self.bias, self.stride)

    class StandardTranspose(nn.ConvTranspose2d):
        def __init__(self, ci, co):
            super().__init__(ci, co, 4, stride=2, padding=1)
            self.gain = nn.Parameter(torch.ones(ci, 1, 1, 1))

        def forward(self, x):
            var, mean = torch.var_mean(self.weight, dim=(1, 2, 3), keepdim=True)
            scale = torch.rsqrt((var * np.prod(self.weight.shape[1:])).clamp_min(1e-4)) * self.gain
            return F.conv_transpose2d(x, (self.weight-mean)*scale, self.bias, 2, 1)

    class Gated(nn.Module):
        def __init__(self, ci, co, ks=3, stride=1, transpose=False):
            super().__init__()
            self.padding = nn.Identity() if transpose else nn.ReflectionPad2d((ks-1)//2)
            self.conv = StandardTranspose(ci, co) if transpose else StandardConv(ci, co, ks, stride)
            self.conv_gate = StandardTranspose(ci, co) if transpose else StandardConv(ci, co, ks, stride)

        def forward(self, x):
            x = self.padding(x)
            return self.conv(x) * torch.sigmoid(self.conv_gate(x)) * 1.8

    class Relu(nn.Module):
        def forward(self, x):
            return F.relu(x) * 1.7139588594436646

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            for i, rate in enumerate((2, 4, 8, 16)):
                setattr(self, f'block{i:02d}', nn.Sequential(nn.ReflectionPad2d(rate),
                    nn.Conv2d(128, 32, 3, dilation=rate), nn.ReLU()))
            self.fuse = nn.Sequential(nn.ReflectionPad2d(1), nn.Conv2d(128, 128, 3))
            self.gate = nn.Sequential(nn.ReflectionPad2d(1), nn.Conv2d(128, 128, 3))

        def forward(self, x):
            out = self.fuse(torch.cat([getattr(self, f'block{i:02d}')(x) for i in range(4)], dim=1))
            gate = self.gate(x)
            gate = torch.sigmoid(5*(2*(gate-gate.mean((2, 3), keepdim=True))/(gate.std((2, 3), keepdim=True)+1e-9)-1))
            return x*(1-gate)+out*gate

    class Generator(nn.Module):
        def __init__(self):
            super().__init__()
            self.head = nn.Sequential(Gated(4, 32), Relu(), Gated(32, 64, 4, 2), Relu(), Gated(64, 128, 4, 2))
            self.body_conv = nn.Sequential(*[Block() for _ in range(10)])
            self.tail = nn.Sequential(Gated(128, 128), Relu(), Gated(128, 128), Relu(),
                Gated(128, 64, transpose=True), Relu(), Gated(64, 32, transpose=True), Relu(), Gated(32, 3))

        def forward(self, image, mask):
            return self.tail(self.body_conv(self.head(torch.cat([mask, image], dim=1)))).clamp(-1, 1)

    model = Generator().eval()
    model.load_state_dict(load_file(str(MODEL)), strict=True)
    return model


def infer(rgb, mask):
    """One padded RGB crop; normalization matches the upstream AOT runtime."""
    import torch
    from .hardware import get_torch_device
    device = get_torch_device()
    image = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1)[None])).float()/127.5-1
    tensor_mask = torch.from_numpy(np.ascontiguousarray(mask[None, None])).float()
    model = session()
    if device != 'cpu':
        if next(model.parameters()).device.type != device:
            model = model.to(device)  # move once, not per crop
        image = image.to(device)
        tensor_mask = tensor_mask.to(device)
    with torch.inference_mode():
        result = model(image*(1-tensor_mask), tensor_mask)[0].permute(1, 2, 0).cpu().numpy()
    return np.clip((result+1)*127.5, 0, 255).astype(np.uint8)
