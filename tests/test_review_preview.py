import unittest,tempfile,json
from pathlib import Path
from PIL import Image
from manga_ai.engine import preview_review,render_clean
from manga_ai.io import write_json
class ReviewPreviewTests(unittest.TestCase):
 def test_preview_does_not_commit_and_manual_region_never_cleans(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);Image.new('RGB',(100,100),'white').save(root/'original.png')
   data={'schema':1,'width':100,'height':100,'regions':[{'id':'B10001','box':[10,10,40,40],'safe':[15,15,20,20],'auto_clean':False,'fill':[255,255,255],'source':'Thủ công','warnings':['Manual']}],'mapping':[]}
   write_json(root/'manifest.json',data);before=(root/'manifest.json').read_bytes()
   result=preview_review(data,root)
   self.assertTrue(Path(result['preview']).exists());self.assertEqual(before,(root/'manifest.json').read_bytes())
   result=render_clean(root/'manifest.json',[{'id':'B10001','translation':'Tiếng Việt','clean':True}])
   self.assertEqual(result['applied'],[]);self.assertEqual(result['skipped'],['B10001'])
 def test_preview_rejects_out_of_page(self):
  with self.assertRaises(ValueError):preview_review({'schema':1,'width':10,'height':10,'regions':[{'id':'B1','box':[0,0,20,20],'safe':[0,0,10,10]}]},'.')

 def test_trial_clean_does_not_replace_approved_mapping(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'masks').mkdir();Image.new('RGB',(100,100),'black').save(root/'original.png')
   Image.new('L',(40,40),255).save(root/'masks/B001.png')
   data={'schema':1,'width':100,'height':100,'regions':[{'id':'B001','box':[10,10,40,40],'safe':[15,15,20,20],'auto_clean':True,'fill':[255,255,255]}],'mapping':[]}
   write_json(root/'manifest.json',data);before=(root/'manifest.json').read_bytes()
   result=render_clean(root/'manifest.json',[{'id':'B001','translation':'Xem thử','clean':True}],preview=True)
   self.assertEqual(result['applied'],['B001']);self.assertTrue(Path(result['preview']).exists())
   self.assertEqual(before,(root/'manifest.json').read_bytes());self.assertFalse((root/'clean.png').exists())
