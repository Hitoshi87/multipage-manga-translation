import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, PngImagePlugin

spec=importlib.util.spec_from_file_location('compact_png_cache',Path(__file__).resolve().parents[1]/'scripts/compact_png_cache.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PngCacheCompactionTest(unittest.TestCase):
    def test_lossless_pixels_metadata_and_mtime_and_safe_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input.png';info=PngImagePlugin.PngInfo();info.add_text('Description','Tiếng Việt — cache')
            Image.new('RGBA',(320,240),(240,230,220,200)).save(path,compress_level=0,pnginfo=info,dpi=(300,300))
            original=path.read_bytes();before=path.stat();parts=module.chunks(original)
            self.assertGreater(module.recompress(path)['saved'],0);self.assertEqual(path.read_bytes(),original)
            result=module.recompress(path,True);self.assertTrue(result['applied'])
            after=module.chunks(path.read_bytes());self.assertEqual(module.raw_rows(parts),module.raw_rows(after))
            self.assertEqual([x[2] for x in parts if x[0]!=b'IDAT'],[x[2] for x in after if x[0]!=b'IDAT'])
            self.assertEqual(path.stat().st_mtime_ns,before.st_mtime_ns)
            with Image.open(path) as image:
                self.assertEqual(image.getpixel((100,100)),(240,230,220,200))
                self.assertEqual(image.info['Description'],'Tiếng Việt — cache')
            self.assertEqual(module.recompress(path,True)['saved'],0)

    def test_corrupt_input_is_never_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input.png';Image.new('RGB',(20,20)).save(path)
            raw=bytearray(path.read_bytes());raw[20]^=1;path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'CRC'):module.recompress(path,True)
            self.assertEqual(path.read_bytes(),raw)

    def test_symlinks_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original.png';Image.new('RGB',(20,20)).save(path)
            link=Path(temp)/'input.png';link.symlink_to(path)
            with self.assertRaises(ValueError):module.recompress(link,True)
            self.assertTrue(link.is_symlink())
