import unittest,numpy as np
from manga_ai.experimental_pair_ownership import arbitrate
class PairTests(unittest.TestCase):
 def test_tie_is_unresolved_without_unique_text_box(self):
  im=np.full((30,30,3),255,np.uint8);im[10:15,10:15]=0;b={k:np.zeros((30,30),np.uint8) for k in ['A','B']};e={k:np.zeros((30,30),np.uint8) for k in b}
  for m in e.values():m[10:15,10:15]=1
  result,t=arbitrate(im,b,e,{});self.assertFalse(result['A'].any());self.assertFalse(result['B'].any());self.assertFalse(t['authorized_to_clean']);self.assertEqual(t['components'][0]['reason'],'TIE_UNRESOLVED')
 def test_unique_text_box_breaks_tie(self):
  im=np.full((30,30,3),255,np.uint8);im[10:15,10:15]=0;b={k:np.zeros((30,30),np.uint8) for k in ['A','B']};e={k:np.zeros((30,30),np.uint8) for k in b}
  for m in e.values():m[10:15,10:15]=1
  result,t=arbitrate(im,b,e,{'A':[[0,0,20,20]],'B':[]});self.assertTrue(result['A'].any());self.assertFalse(result['B'].any());self.assertEqual(t['remaining_mask_conflict_pixels'],0)
if __name__=='__main__':unittest.main()
