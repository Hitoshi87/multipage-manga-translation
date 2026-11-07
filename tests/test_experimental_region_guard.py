import unittest,numpy as np
from manga_ai.experimental_region_guard import guard_mask
from manga_ai.experimental_region_preview import evaluate
class GuardTests(unittest.TestCase):
 def test_artwork_outside_text_is_excluded(self):
  im=np.full((100,100,3),255,np.uint8);base=np.zeros((100,100),np.uint8);base[20:30,20:30]=1;base[60:70,60:70]=1;ctd=base.copy()
  mask,t=guard_mask(im,base,ctd,[[15,15,20,20]],'日本語');self.assertTrue(mask[20:30,20:30].all());self.assertFalse(mask[60:70,60:70].any());self.assertEqual(t['removed_pixels'],100);self.assertFalse(t['authorized_to_clean'])
 def test_no_ocr_blocks_preview(self):
  im=np.full((30,30,3),255,np.uint8);m=np.zeros((30,30),np.uint8);m[10:15,10:15]=1
  _,mask,t=evaluate(im,m,m,[[0,0,30,30]],'',(255,255,255));self.assertFalse(mask.any());self.assertFalse(t['preview_applicable']);self.assertIn('NO_OCR_EVIDENCE',t['rule_ids'])
 def test_masked_changes_remain_in_mask(self):
  im=np.full((80,80,3),255,np.uint8);im[30:35,30:35]=0;m=np.zeros((80,80),np.uint8);m[30:35,30:35]=1
  clean,mask,t=evaluate(im,m,m,[[20,20,30,30]],'あ',(255,255,255));self.assertFalse(np.any(clean[~mask]!=im[~mask]));self.assertTrue(t['preview_applicable']);self.assertTrue(t['user_review_required'])
if __name__=='__main__':unittest.main()
