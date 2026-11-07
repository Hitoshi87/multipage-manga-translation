import unittest
import numpy as np
from manga_ai.experimental_flat_bubble import shadow_clean, ShadowConfig

class ExperimentalFlatBubbleTest(unittest.TestCase):
 def setUp(self):
  self.image=np.full((60,60,3),255,np.uint8);self.image[29:32,29:32]=0
  self.mask=np.zeros((60,60),np.uint8);self.mask[29:32,29:32]=1
  self.bubble=np.zeros((60,60),np.uint8);self.bubble[4:56,4:56]=1
  self.evidence={'japanese_characters':2,'has_text_proposal':True,'bubble_confidence_model':.999,'ocr_confidence_model':99}
 def run_trial(self,**kw):return shadow_clean(self.image,(0,0,60,60),self.mask,self.bubble,self.evidence,**kw)
 def test_no_labels_no_authorization_and_no_outside_changes(self):
  out,trace=self.run_trial();self.assertFalse(trace['authorized_to_clean']);self.assertIn('INDEPENDENT_PIXEL_LABELS_MISSING',trace['reasons'])
  for clean,m,_ in out.values():self.assertFalse(np.any(clean[~m]!=self.image[~m]))
 def test_artwork_intersection_blocks_even_high_confidence(self):
  protected=np.zeros_like(self.mask);protected[28,28]=1
  _,trace=self.run_trial(protected=protected,text_label=self.mask,labels_independent=True)
  self.assertIn('PROTECTED_ARTWORK_OVERLAP',trace['reasons']);self.assertFalse(trace['preview_eligible'])
 def test_border_collision_not_clipped(self):
  self.bubble[:,:29]=0
  out,trace=self.run_trial();self.assertIn('BUBBLE_BORDER_RISK',trace['reasons']);self.assertFalse(trace['preview_eligible']);self.assertEqual(out['dilated'][1].sum(),25)
 def test_no_text_blocks(self):
  self.evidence['japanese_characters']=0
  _,trace=self.run_trial();self.assertIn('TEXT_EVIDENCE_INSUFFICIENT',trace['reasons'])
 def test_missing_labeled_text_blocks(self):
  text=self.mask.copy();text[20,20]=1
  _,trace=self.run_trial(protected=np.zeros_like(text),text_label=text,labels_independent=True)
  self.assertIn('LABELED_TEXT_NOT_FULLY_COVERED',trace['reasons']);self.assertFalse(trace['preview_eligible']);self.assertFalse(trace['authorized_to_clean'])
 def test_no_dilation_preserves_original(self):
  out,_=self.run_trial(config=ShadowConfig(dilation_px=0));self.assertTrue(np.array_equal(out['original'][1],out['dilated'][1]))
 def test_no_ground_truth_even_when_only_one_label_is_missing(self):
  _,trace=self.run_trial(protected=np.zeros_like(self.mask),labels_independent=True);self.assertIn('INDEPENDENT_PIXEL_LABELS_MISSING',trace['reasons'])
if __name__=='__main__':unittest.main()
