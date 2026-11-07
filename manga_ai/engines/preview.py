"""Small presentation images from an engine overlay; no new cleaning pass."""
from pathlib import Path

from PIL import Image


def preview_images(result, manifest_path):
    root = Path(manifest_path).resolve().parent
    with Image.open(root / 'original.png') as image:
        original = image.convert('RGB')
    cleaned = original.copy()
    mask = Image.new('L', original.size, 0)
    if result.get('overlay'):
        with Image.open(result['overlay']) as image:
            overlay = image.convert('RGBA')
        if overlay.size != original.size:
            raise ValueError('Engine preview overlay không khớp ảnh gốc')
        mask = overlay.getchannel('A')
        cleaned.paste(overlay, (0, 0), mask)
        overlay.close()
    images = {}
    # Shrink before building the red visualization to bound extra memory.
    size = (540, 600)
    original.thumbnail(size)
    cleaned.thumbnail(size)
    small_mask = mask.resize(original.size, Image.Resampling.NEAREST)
    mask.close()
    red = Image.blend(original, Image.new('RGB', original.size, (255, 0, 0)), .65)
    marked = Image.composite(red, original, small_mask)
    for name, image in (('original', original), ('clean', cleaned), ('mask', marked)):
        target = root / ('ui_engine_' + name + '_small.png')
        image.save(target)
        images[name] = str(target)
    return images
