import unittest
import cv2
import numpy as np
from manga_ai.engine import japanese_bubble_ink
class JapaneseInkTests(unittest.TestCase):
 def test_missed_long_dash_and_small_marks_inside_outline(self):
  gray=np.full((150,120),255,np.uint8);inside=np.zeros_like(gray)
  cv2.ellipse(inside,(60,75),(50,65),0,0,360,255,-1)
  gray[inside==0]=0
  gray[35:90,79:82]=0  # long vertical dash absent from OCR
  gray[95:98,80:83]=0  # tiny punctuation
  mask=japanese_bubble_ink(gray,inside)
  self.assertTrue(np.all(mask[35:90,79:82]==255));self.assertTrue(mask[96,81])
  self.assertFalse(np.any(mask[inside==0]));self.assertFalse(mask[75,10])
 def test_component_connected_to_border_not_erased(self):
  gray=np.full((100,100),255,np.uint8);inside=np.zeros_like(gray);inside[10:90,10:90]=255
  gray[inside==0]=0;gray[45:48,0:40]=0
  mask=japanese_bubble_ink(gray,inside)
  self.assertFalse(np.any(mask[45:48,:40]))
