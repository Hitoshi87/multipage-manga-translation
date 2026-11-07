import unittest
import cv2,numpy as np
from manga_ai.experimental_bubble_components import propose_components
class ComponentTests(unittest.TestCase):
 def test_small_near_glyph_candidate_is_recovered_but_not_authorized(self):
  image=np.full((90,100,3),255,np.uint8);polygon=np.zeros((90,100),np.uint8);polygon[5:85,5:90]=1
  image[25:45,80:84]=0;image[22:26,87:89]=0
  mask,trace=propose_components(image,polygon)
  self.assertTrue(mask[23,87]);self.assertEqual(len(trace['near_glyph_recovered']),1);self.assertFalse(trace['authorized_to_clean'])
 def test_large_boundary_line_is_not_selected(self):
  image=np.full((80,80,3),255,np.uint8);polygon=np.zeros((80,80),np.uint8);polygon[5:75,5:75]=1;image[5:75,5:8]=0
  mask,trace=propose_components(image,polygon)
  self.assertFalse(mask.any());self.assertTrue(trace['rejected'])
 def test_wrong_dimensions_fail(self):
  with self.assertRaises(ValueError):propose_components(np.zeros((4,5,3),np.uint8),np.zeros((4,4),np.uint8))
if __name__=='__main__':unittest.main()
