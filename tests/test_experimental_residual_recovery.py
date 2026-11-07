import unittest
import numpy as np
from manga_ai.experimental_residual_recovery import propose


class ResidualRecoveryTests(unittest.TestCase):
    def fixture(self):
        source=np.full((50,50,3),255,np.uint8);source[20:25,20:25]=0
        poly=np.ones((50,50),np.uint8);support=np.zeros((50,50),np.uint8);support[15:30,15:30]=1
        ctd=np.zeros((50,50),np.uint8);ctd[20:25,20:25]=1
        empty=np.zeros((50,50),np.uint8)
        return source,poly,support,ctd,empty

    def test_residual_requires_ctd_and_text_box(self):
        s,p,t,c,e=self.fixture();mask,trace=propose(s,s,e,p,t,c,e)
        self.assertTrue(mask[20:25,20:25].all());self.assertEqual(trace['accepted'],1)
        mask,_=propose(s,s,e,p,e,c,e);self.assertFalse(mask.any())
        mask,_=propose(s,s,e,p,t,e,e);self.assertFalse(mask.any())

    def test_head_overlap_and_existing_output_are_protected(self):
        s,p,t,c,e=self.fixture();head=e.copy();head[20:25,20:25]=1
        mask,trace=propose(s,s,e,p,t,c,head)
        self.assertFalse(mask.any());self.assertIn('HEAD_BOX_OVERLAP',trace['components'][0]['reasons'])
        clean=s.copy();clean[20:25,20:25]=255
        mask,_=propose(s,clean,e,p,t,c,e);self.assertFalse(mask.any())

    def test_ambiguous_polygon_boundary_is_not_cleaned(self):
        s,p,t,c,e=self.fixture();p[:,23:]=0
        mask,trace=propose(s,s,e,p,t,c,e)
        self.assertFalse(mask.any());self.assertIn('NEAR_OR_OUTSIDE_POLYGON',trace['components'][0]['reasons'])
