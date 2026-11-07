import unittest
import numpy as np
from manga_ai.experimental_text_ownership import ownership_graph
class OwnershipTests(unittest.TestCase):
 def setUp(self):
  self.img=np.full((80,80,3),255,np.uint8);self.img[30:35,30:35]=0;self.ctd=np.zeros((80,80),np.uint8);self.ctd[30:35,30:35]=1
 def test_competing_bubbles_unresolved(self):
  b=[{'id':'A','box':[10,10,60,60],'polygon':[[10,10],[70,10],[70,70],[10,70]]},{'id':'B','box':[10,10,60,60],'polygon':[[10,10],[70,10],[70,70],[10,70]]}];g,_=ownership_graph(self.img,self.ctd,b,[[0,0,80,80]]);self.assertEqual(g['components'][0]['ownership_status'],'ambiguous');self.assertIsNone(g['components'][0]['owner']);self.assertFalse(g['authorized_to_clean'])
 def test_outside_all_bubbles_unassigned(self):
  g,_=ownership_graph(self.img,self.ctd,[],[[0,0,80,80]]);self.assertEqual(g['components'][0]['ownership_status'],'unassigned')
 def test_single_owner_is_still_not_clean_authority(self):
  b=[{'id':'A','box':[10,10,60,60],'polygon':[[10,10],[70,10],[70,70],[10,70]]}];g,_=ownership_graph(self.img,self.ctd,b,[[0,0,80,80]]);self.assertEqual(g['components'][0]['owner'],'A');self.assertFalse(g['authorized_to_clean'])
if __name__=='__main__':unittest.main()
