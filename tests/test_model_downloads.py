import importlib.util,unittest,tempfile,hashlib,io
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('download_models',Path(__file__).resolve().parents[1]/'scripts/download_models.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ModelDownloadTests(unittest.TestCase):
 def item(self):return dict(id='demo',path='a.bin',url='https://example.org/model',sha256=hashlib.sha256(b'good').hexdigest(),size_bytes=4)
 def test_corrupt_download_does_not_replace_existing_and_temp_is_removed(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'a.bin').write_bytes(b'old')
   with patch.object(m.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
    with self.assertRaises(ValueError):m.install(self.item(),root,True)
   self.assertEqual((root/'a.bin').read_bytes(),b'old');self.assertEqual(len(list(root.iterdir())),1)
 def test_path_escape_and_valid_file_skip_network(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);item=self.item();item['path']='../outside'
   with self.assertRaises(ValueError):m.target_path(root,item)
   (root/'a.bin').write_bytes(b'good')
   with patch.object(m.urllib.request,'urlopen',side_effect=AssertionError('network')):self.assertEqual(m.install(self.item(),root,True),'verified')
