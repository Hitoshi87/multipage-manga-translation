import tempfile
import unittest
import struct
import zlib
from pathlib import Path

from PIL import Image
from manga_ai.input_memory import inspect_inputs


class InputMemoryTest(unittest.TestCase):
    def test_16_bit_rgb_png_uses_two_bytes_per_channel(self):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rgb16.png'
            ihdr = struct.pack('>IIBBBBB', 10, 20, 16, 2, 0, 0, 0)
            pixels = (b'\0' + b'\0' * (10 * 3 * 2)) * 20
            path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
                             chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))
            row = inspect_inputs([str(path)], heavy_bytes=1000)[0]
            self.assertEqual(row['raw_bytes'], 1200)
            self.assertTrue(row['heavy'])

    def test_header_estimate_and_requested_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'gray.png'
            Image.new('L', (10, 20)).save(path)
            ordinary = inspect_inputs([str(path)], heavy_bytes=500)[0]
            converted = inspect_inputs([str(path)], requested_channels=3, heavy_bytes=500)[0]
            self.assertEqual(ordinary['raw_bytes'], 200)
            self.assertFalse(ordinary['heavy'])
            self.assertEqual(converted['raw_bytes'], 600)
            self.assertTrue(converted['heavy'])

    def test_layered_or_unreadable_file_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            psd = Path(tmp) / 'page.psd'
            Image.new('L', (10, 20)).save(psd, format='PNG')
            bad = Path(tmp) / 'broken.png'
            bad.write_bytes(b'not-an-image')
            rows = inspect_inputs([str(psd), str(bad)])
            self.assertTrue(rows[0]['heavy'])
            self.assertTrue(rows[1]['heavy'])
            self.assertTrue(rows[1]['unknown'])


if __name__ == '__main__':
    unittest.main()
