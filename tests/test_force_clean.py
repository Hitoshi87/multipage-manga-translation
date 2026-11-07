import tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from manga_ai.io import write_json,read_json
from manga_ai.engine import render_clean
class ForceCleanTests(unittest.TestCase):
 def test_only_explicit_force_overrides_confidence_and_retains_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'masks').mkdir();Image.new('RGB',(80,80),'black').save(root/'original.png');source=(root/'original.png').read_bytes()
   mask=np.zeros((40,40),dtype=np.uint8);mask[10:20,10:20]=255;Image.fromarray(mask).save(root/'masks/B001.png')
   write_json(root/'manifest.json',{'schema':1,'width':80,'height':80,'regions':[{'id':'B001','box':[10,10,40,40],'safe':[15,15,25,25],'auto_clean':False,'fill':[255,255,255]}]})
   item={'id':'B001','translation':'Thử clean','clean':True}
   self.assertEqual(render_clean(root/'manifest.json',[item])['applied'],[])
   item['force']='true';self.assertEqual(render_clean(root/'manifest.json',[item])['applied'],[])
   item['force']=True;result=render_clean(root/'manifest.json',[item]);self.assertEqual(result['applied'],['B001'])
   overlay=np.array(Image.open(result['overlay']));self.assertEqual(np.count_nonzero(overlay[:,:,3]),100)
   self.assertEqual((root/'original.png').read_bytes(),source);self.assertTrue(read_json(root/'manifest.json')['mapping'][0]['force'])
 def test_force_without_mask_skips_manual_region(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);Image.new('RGB',(80,80),'white').save(root/'original.png')
   write_json(root/'manifest.json',{'schema':1,'width':80,'height':80,'regions':[{'id':'B001','box':[10,10,40,40],'safe':[15,15,25,25],'auto_clean':False,'fill':[255,255,255]}]})
   self.assertEqual(render_clean(root/'manifest.json',[{'id':'B001','translation':'A','force':True}])['skipped'],['B001'])
