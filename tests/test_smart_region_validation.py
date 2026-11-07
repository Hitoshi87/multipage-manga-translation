import unittest
import numpy as np
from manga_ai.smart_region_validation import RegionConfig,group_regions,decide,rollback_region,fill_candidate_flat

class TestSmartRegion(unittest.TestCase):
 def test_groups_nearby_glyphs_without_changing_mask(self):
  m=np.zeros((80,80),np.uint8);m[10:15,10:15]=1;m[20:25,10:15]=1;m[60:65,60:65]=1
  labels,regions=group_regions(m,15);self.assertEqual(len(regions),2);self.assertEqual(sum(r['mask_pixels'] for r in regions),int(m.sum()))
 def test_requires_multiple_evidence_and_refuses_protected(self):
  c=RegionConfig();e=dict(ocr_ran=True,japanese_chars=2,bubble_overlap=1,flat_fraction=1,mask_agreement=.8,protected_overlap=0,too_large=False,mask_pixels=30)
  self.assertEqual(decide(e,c)[0],'candidate_auto');e['protected_overlap']=.1;self.assertEqual(decide(e,c)[0],'review')
  e['protected_overlap']=0;e['ocr_ran']=False;self.assertEqual(decide(e,c)[0],'review')
 def test_rollback_touches_only_region(self):
  original=np.zeros((5,5,3),np.uint8);image=np.ones_like(original);mask=np.zeros((5,5),np.uint8);mask[2,2]=1
  out=rollback_region(image,original,mask);self.assertTrue((out[mask>0]==0).all());self.assertTrue((out[mask==0]==1).all())
 def test_flat_fill_is_mask_local(self):
  image=np.full((20,20,3),248,np.uint8);mask=np.zeros((20,20),np.uint8);mask[8:12,8:12]=1;image[mask>0]=0
  out,applied=fill_candidate_flat(image,mask,235)
  self.assertTrue(np.array_equal(applied,mask));self.assertTrue((out[mask>0]==248).all());self.assertTrue(np.array_equal(out[mask==0],image[mask==0]))

class TestRouting(unittest.TestCase):
 def test_fallback_and_review_routing(self):
  from manga_ai.smart_region_validation import route_for_review
  self.assertEqual(route_for_review('review',['ocr_not_run'],'flat'),'fallback')
  self.assertEqual(route_for_review('review',['ocr_not_run'],'structural_lines'),'review')
  self.assertEqual(route_for_review('review',['ocr_not_run','protected_art_or_head_overlap'],'flat'),'review')
  self.assertEqual(route_for_review('candidate_auto',[],'flat'),'candidate_auto')
