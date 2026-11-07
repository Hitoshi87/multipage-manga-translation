import unittest
import numpy as np
from manga_ai.experimental_selective_color import selective_color_preview
from manga_ai.shadow_color_audit import ColorAuditConfig

class SelectiveColorTests(unittest.TestCase):
 def test_unsupported_stays_original_and_no_outside_change(self):
  source=np.full((80,80,3),200,dtype=np.uint8);source[:,:20]=250;source[35:45,55:65]=0
  mask=np.zeros((80,80),bool);mask[35:45,55:65]=True
  out,used,trace=selective_color_preview(source,mask,ColorAuditConfig(sigma_px=2,bright_floor=245,minimum_weight=.02))
  self.assertEqual(trace['unsupported_pixels'],100);self.assertFalse(used.any());np.testing.assert_array_equal(out,source)
 def test_supported_changes_only_selected_pixels(self):
  source=np.full((30,30,3),250,dtype=np.uint8);source[14:16,14:16]=0;mask=np.zeros((30,30),bool);mask[14:16,14:16]=True
  out,used,trace=selective_color_preview(source,mask)
  self.assertTrue(used.all(where=mask));self.assertEqual(trace['unsupported_pixels'],0);self.assertFalse(np.any((out!=source).any(axis=2)&~mask));self.assertFalse(trace['authorized_to_clean'])
if __name__=='__main__':unittest.main()
