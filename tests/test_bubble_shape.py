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
