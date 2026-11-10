import unittest
import cv2,numpy as np
from manga_ai.engine import bubble_shape
class BubbleShapeTests(unittest.TestCase):
 def test_contour_and_rows_follow_ellipse(self):
  mask=np.zeros((160,200),np.uint8);cv2.ellipse(mask,(100,80),(90,70),0,0,360,255,-1)
  outline,shape=bubble_shape({'box':[20,30,200,160],'safe':[65,70,100,70],'interior':mask})
  self.assertGreater(len(outline),8)
  for y,left,right in shape['rows']:
   self.assertTrue(np.all(mask[y-30,left-20:right-20]))
  widths=[r[2]-r[1] for r in shape['rows']];self.assertGreater(max(widths),min(widths)*2)
 def test_concavity_not_bridged(self):
  mask=np.zeros((120,140),np.uint8);mask[10:110,10:130]=255;mask[50:70,80:130]=0
  _,shape=bubble_shape({'box':[0,0,140,120],'safe':[20,20,40,80],'interior':mask})
  row=next(r for r in shape['rows'] if r[0]==60);self.assertLessEqual(row[2],80)
 def test_asymmetric_spiky_protrusion_is_clamped_around_safe_core(self):
  gray=np.full((240,260),255,np.uint8)
  mask=np.zeros((200,220),np.uint8);mask[10:190,10:205]=255
  for y in range(20,180,25):
   cv2.line(gray,(20+10,20+y),(20+85,20+y+12),0,3)
   cv2.line(gray,(20+85,20+y+12),(20+10,20+y+25),0,3)
  _,shape=bubble_shape({'box':[20,20,220,200],'safe':[110,45,100,150],'interior':mask,'detector':'ai_balloon'},gray)
  mid=next(r for r in shape['rows'] if r[0]==120)
  self.assertGreaterEqual(mid[1],95)
  self.assertLess(abs((mid[1]+mid[2])/2-160),8)
