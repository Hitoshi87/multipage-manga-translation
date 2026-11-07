import unittest
from manga_ai.engine import cjk_region_allowed
class EdgeDialogueTests(unittest.TestCase):
 def test_strong_japanese_at_panel_edge_retained(self):
  self.assertTrue(cjk_region_allowed('こんな山奥のスキー場で',94,True,.15,2,[255,255,255]))
 def test_edge_art_and_weak_ocr_rejected(self):
  for text,conf,ink,variation in [('ノ',95,.1,1),('//// Boom',95,.1,1),('こんな山奥',35,.1,1),('こんな山奥',90,.5,1),('こんな山奥',90,.1,20)]:
   self.assertFalse(cjk_region_allowed(text,conf,True,ink,variation,[255,255,255]))
 def test_short_clear_dialogue_retained(self):
  self.assertTrue(cjk_region_allowed('太',89,False,.1,1,[255,255,255]))
  self.assertFalse(cjk_region_allowed('と(',30,False,.1,1,[255,255,255]))
