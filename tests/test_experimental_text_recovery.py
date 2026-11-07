import unittest
import numpy as np
from manga_ai.experimental_text_recovery import propose
class RecoveryTests(unittest.TestCase):
 def test_no_ocr_no_candidate(self):
  im=np.full((60,60,3),255,np.uint8);im[25:32,25:32]=0;m=np.zeros((60,60),np.uint8);ctd=m.copy();ctd[25:32,25:32]=1
  add,t=propose(im,m,ctd,[[0,0,60,60]],'');self.assertEqual(add.sum(),0);self.assertFalse(t['authorized_to_clean'])
 def test_border_component_never_candidate(self):
  im=np.full((60,60,3),255,np.uint8);im[0:10,0:10]=0;m=np.zeros((60,60),np.uint8);ctd=m.copy();ctd[0:10,0:10]=1
  add,t=propose(im,m,ctd,[[0,0,60,60]],'あ');self.assertFalse(add.any());self.assertIn('STRUCTURE_OR_CROP_EDGE',t['components'][0]['reason_codes'])
 def test_baseline_mask_not_modified(self):
  im=np.full((60,60,3),255,np.uint8);im[20:30,20:30]=0;m=np.zeros((60,60),np.uint8);m[21:25,21:25]=1;ctd=np.zeros_like(m);ctd[20:30,20:30]=1
  add,t=propose(im,m,ctd,[[0,0,60,60]],'あ');self.assertFalse(np.any((add>0)&(m>0)));self.assertFalse(t['authorized_to_clean'])
 def test_rejects_neighbor_outside_bubble_scope(self):
  im=np.full((60,60,3),255,np.uint8);im[25:32,10:17]=0;m=np.zeros((60,60),np.uint8);ctd=m.copy();ctd[25:32,10:17]=1;scope=np.zeros_like(m);scope[:,25:]=1
  add,t=propose(im,m,ctd,[[0,0,60,60]],'あ',scope_polygon=scope);self.assertFalse(add.any());self.assertIn('OUTSIDE_BUBBLE_SCOPE',t['components'][0]['reason_codes'])
if __name__=='__main__':unittest.main()
