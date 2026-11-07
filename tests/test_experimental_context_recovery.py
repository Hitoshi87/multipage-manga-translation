import unittest
import cv2
import numpy as np
from manga_ai.experimental_context_recovery import background_evidence,propose


class ContextRecoveryTests(unittest.TestCase):
    def setup_scene(self):
        src=np.full((80,80,3),255,np.uint8);src[35:40,35:40]=0
        used=np.zeros((80,80),np.uint8);support=np.zeros_like(used);support[28:50,28:50]=1
        ctd=np.zeros_like(used);ctd[35:40,35:40]=1;head=np.zeros_like(used)
        return src,used,support,ctd,head

    def test_does_not_use_box_without_ctd_or_residual(self):
        src,used,support,ctd,head=self.setup_scene()
        m,_=propose(src,src,used,support,np.zeros_like(ctd),head);self.assertFalse(m.any())
        clean=src.copy();clean[35:40,35:40]=255
        m,_=propose(src,clean,used,support,ctd,head);self.assertFalse(m.any())

    def test_head_box_is_warning_but_ink_must_be_separated(self):
        src,used,support,ctd,head=self.setup_scene();head[30:50,30:50]=1
        m,tr=propose(src,src,used,support,ctd,head);self.assertTrue(m[35:40,35:40].all());self.assertGreater(tr['head_box_mask_intersection'],0)
        src[34:42,42:45]=0
        m,_=propose(src,src,used,support,ctd,head);self.assertFalse(m.any())

    def test_structured_background_generates_review_evidence(self):
        gray=np.full((80,80),255,np.uint8);mask=np.zeros((80,80),np.uint8);mask[30:40,30:40]=1
        flat=background_evidence(gray,mask);gray[20:50:2,20:50]=0;complex_=background_evidence(gray,mask)
        self.assertFalse(flat['complex_for_review']);self.assertTrue(complex_['complex_for_review'])
