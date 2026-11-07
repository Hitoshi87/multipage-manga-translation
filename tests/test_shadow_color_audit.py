import unittest
import numpy as np
from manga_ai.shadow_color_audit import audit_fill
class ColorAuditTest(unittest.TestCase):
 def test_detects_too_bright_fill_and_limits_preview_to_mask(self):
  source=np.full((80,80,3),245,np.uint8);mask=np.zeros((80,80),np.uint8);mask[37:43,37:43]=1;source[mask>0]=0
  output=source.copy();output[mask>0]=255
  preview,heat,report=audit_fill(source,output,mask)
  self.assertEqual(report['baseline_delta_mean'],10);self.assertEqual(report['configuration']['bright_floor'],245);self.assertEqual(report['warning_pixels'],36);self.assertFalse(report['authorized_to_clean']);self.assertTrue(np.all(preview[mask>0]==245));self.assertTrue(np.array_equal(preview[mask==0],output[mask==0]));self.assertTrue(np.all(heat[mask==0]==0))
 def test_background_below_245_is_not_overwritten_without_samples(self):
  src=np.full((50,50,3),240,np.uint8);mask=np.zeros((50,50),np.uint8);mask[20:30,20:30]=1;out=src.copy();out[mask>0]=251
  preview,_,report=audit_fill(src,out,mask)
  self.assertEqual(report['unsupported_pixels'],100);self.assertTrue(np.array_equal(preview,out))
 def test_no_background_never_guesses_or_changes_output(self):
  src=np.zeros((20,20,3),np.uint8);m=np.ones((20,20),np.uint8);output=src.copy();preview,_,r=audit_fill(src,output,m);self.assertIsNone(r['baseline_delta_mean']);self.assertEqual(r['unsupported_pixels'],400);self.assertTrue(np.array_equal(preview,output))
 def test_bad_geometry_is_rejected(self):
  with self.assertRaises(ValueError):audit_fill(np.zeros((2,2,3)),np.zeros((2,3,3)),np.zeros((2,2)))
if __name__=='__main__':unittest.main()
