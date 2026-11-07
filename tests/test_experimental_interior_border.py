import unittest
import numpy as np
from manga_ai.experimental_interior_border import review_components
class ReviewTest(unittest.TestCase):
 def test_never_authorizes_and_preserves_outside_components(self):
  src=np.full((80,80,3),255,np.uint8);base=np.zeros((80,80),np.uint8);ctd=base.copy();ctd[30:35,30:35]=1;ctd[5:10,5:10]=1;poly=base.copy();poly[10:70,10:70]=1
  candidate,trace=review_components(src,base,ctd,poly,[[0,0,80,80]],'あ')
  self.assertFalse(trace['authorized_to_clean']);self.assertEqual(candidate[5:10,5:10].sum(),0);self.assertTrue(any('OUTSIDE_DETECTOR_POLYGON' in x['reasons'] for x in trace['components']));self.assertTrue(all('ARTWORK_LABEL_UNAVAILABLE' in x['reasons'] for x in trace['components']))
 def test_ocr_alone_cannot_override_artwork_protection(self):
  img=np.full((30,30,3),255,np.uint8);m=np.zeros((30,30),np.uint8);ctd=m.copy();ctd[14:17,14:17]=1;poly=np.ones_like(m);protect=ctd.copy();candidate,t=review_components(img,m,ctd,poly,[[0,0,30,30]],'日本語',protected_artwork=protect);self.assertFalse(candidate.any());self.assertIn('PROTECTED_ARTWORK_OVERLAP',t['components'][0]['reasons'])
 def test_small_punctuation_kept_for_review(self):
  im=np.full((30,30,3),255,np.uint8);m=np.zeros((30,30),np.uint8);ctd=m.copy();ctd[14,14]=1;_,t=review_components(im,m,ctd,np.ones_like(m),[[0,0,30,30]],'。');self.assertIn('SMALL_COMPONENT_REVIEW_PUNCTUATION',t['components'][0]['reasons'])
if __name__=='__main__':unittest.main()
