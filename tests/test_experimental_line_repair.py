import unittest
import numpy as np
from manga_ai.experimental_line_repair import repair_confirmed_lines


class TestRepair(unittest.TestCase):
    def test_approval_and_edit_mask_are_both_required(self):
        original=np.full((40,80,3),255,np.uint8);original[20,10:70]=10
        edit=np.zeros((40,80),np.uint8);edit[20,35:45]=1
        clean=original.copy();clean[edit>0]=255
        restored,mask,decisions=repair_confirmed_lines(original,clean,edit,edit,[(10,20,69,20)])
        self.assertEqual(decisions[0]['reason'],'repaired_approved_line');self.assertEqual(int(mask.sum()),10)
        self.assertTrue(np.array_equal(restored[edit==0],clean[edit==0]))
        refused,m,reason=repair_confirmed_lines(original,clean,edit,np.zeros_like(edit),[(10,20,69,20)])
        self.assertEqual(reason[0]['reason'],'gap_unapproved_or_too_long');self.assertFalse(m.any());self.assertTrue(np.array_equal(refused,clean))

    def test_requires_both_dark_anchors(self):
        original=np.full((40,80,3),255,np.uint8);original[20,10:30]=0
        edit=np.zeros((40,80),np.uint8);edit[20,35:45]=1
        out,mask,decisions=repair_confirmed_lines(original,original,edit,edit,[(10,20,69,20)])
        self.assertEqual(decisions[0]['reason'],'anchors_not_verified');self.assertFalse(mask.any())

if __name__=='__main__':unittest.main()
