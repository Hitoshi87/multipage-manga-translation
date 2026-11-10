"""Read image headers to isolate unusually large pages in supervised runs."""
from pathlib import Path
import warnings

# Raw pixels are only a lower bound: layers, working copies and caches add more.
HEAVY_RAW_BYTES = 64 * 1024 * 1024


def inspect_inputs(paths, requested_channels=0, heavy_bytes=HEAVY_RAW_BYTES):
    from PIL import Image
    if not isinstance(paths, list) or len(paths) > 10000:
        raise ValueError('Danh sách ảnh quá lớn hoặc không hợp lệ')
    if requested_channels not in (0, 3, 4):
        raise ValueError('Chế độ màu không hợp lệ')
    result = []
    for name in paths:
        path = Path(name)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    width, height = image.size
                    mode = image.mode
                    channels = max(len(image.getbands()), requested_channels, 1)
                    bytes_per_channel = 4 if mode in ('I', 'F') else (2 if '16' in mode else 1)
                    if image.format == 'PNG':
                        # Pillow may expose a 16-bit RGB PNG as mode RGB, so
                        # inspect IHDR instead of assuming one byte/channel.
                        with path.open('rb') as source:
                            header = source.read(25)
                        if len(header) < 25 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
                            raise ValueError('PNG header không hợp lệ')
                        bytes_per_channel = max(bytes_per_channel, (header[24] + 7) // 8)
                    raw_bytes = width * height * channels * bytes_per_channel
                    heavy = raw_bytes >= heavy_bytes or path.suffix.lower() in ('.psd', '.psb')
                    result.append({'path':str(path), 'width':width, 'height':height, 'mode':mode,
                                   'raw_bytes':raw_bytes, 'heavy':heavy})
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            # A header we cannot assess should not be grouped with other pages.
            result.append({'path':str(path), 'heavy':True, 'unknown':True})
    return result
