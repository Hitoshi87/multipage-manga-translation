import unittest
import numpy as np
from manga_ai.shadow_small_bubble import ShadowConfig,adaptive_roi_mask,shadow_decision,provenance_from_trace
class TestShadow(unittest.TestCase):
 def test_partial_component_is_flagged_not_clipped(self):
  image=np.zeros((60,60,3),np.uint8);mask=np.zeros((60,60),np.uint8);mask[20:25,10:40]=1;polygon=np.ones((60,60),np.uint8)
  roi,chosen,dil,diag=adaptive_roi_mask(image,mask,[{'box':[15,18,8,10]}],polygon,ShadowConfig());self.assertEqual(diag['partial_roi_components'],1);self.assertEqual(int(chosen.sum()),int(mask.sum()));self.assertGreater(diag['dilated_pixels'],diag['selected_pixels'])
 def test_high_ocr_alone_never_authorizes_clean(self):
  words=[{'text':'ああ','confidence':99,'box':[10,10,10,20]}];diag={'selected_pixels':5,'partial_roi_components':0,'crop_edge_components':0,'outside_polygon_pixels':1,'min_border_distance_px':0}
  result=shadow_decision({'detector_confidence':.99},words,.99,diag,ShadowConfig());self.assertEqual(result['decision'],'review');self.assertFalse(result['authorized_to_clean']);self.assertIn('MASK_OUTSIDE_BUBBLE',result['reason_codes'])
 def test_fragmented_mask_fails_ink_coverage_even_with_high_confidence(self):
  image=np.full((80,80,3),255,np.uint8);image[20:60,35:40]=0;mask=np.zeros((80,80),np.uint8);mask[25:28,35:40]=1
  words=[{'text':'あ','confidence':99,'box':[30,15,15,50]}];_,_,_,diag=adaptive_roi_mask(image,mask,words,np.ones((80,80),np.uint8),ShadowConfig())
  decision=shadow_decision({'detector_confidence':.99},words,.99,diag,ShadowConfig());self.assertIn('OCR_ROI_INK_COVERAGE_INSUFFICIENT',decision['reason_codes']);self.assertEqual(decision['decision'],'review')
 def test_provenance_preserves_measured_ocr_without_changing_decision(self):
  region={'id':'B005','source':'あ あ','ocr_status':'unconfirmed','confidence':0};gate={'group':[{'text':'あ','confidence':91},{'text':'あ','confidence':84}],'touches_edge':True,'confidence':87.5};fallback={'rule_id':'MODEL_MASK_AREA_MAX','observed':.268}
  out=provenance_from_trace(region,gate,fallback);self.assertEqual(out['ocr_confidence_model_mean'],87.5);self.assertEqual(out['legacy_manifest_confidence'],0);self.assertEqual(out['clean_decision'],'review');self.assertIn('CJK_NEAR_BORDER_REQUIRES_3_CHARS',out['reason_codes'])
