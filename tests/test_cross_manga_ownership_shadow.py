import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('ownership_shadow',Path(__file__).resolve().parents[1]/'scripts/cross_manga_ownership_shadow.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class DuplicateOwnershipTests(unittest.TestCase):
    def test_polygon_iou_separates_duplicates_and_neighbors(self):
        a={'outline':[[0,0],[10,0],[10,10],[0,10]]}
        duplicate={'outline':[[0,0],[10,0],[10,10],[0,10]]}
        adjacent={'outline':[[10,0],[20,0],[20,10],[10,10]]}
        self.assertEqual(module.polygon_iou(a,duplicate),1.0)
        self.assertLess(module.polygon_iou(a,adjacent),.1)
        self.assertEqual(module.polygon_iou(a,{'outline':[]}),0.0)

    def test_partial_box_requires_polygon_ctd_and_unique_owner(self):
        bubble={'id':'A','box':[0,0,68,100], 'outline':[[0,0],[67,0],[67,99],[0,99]]}
        text=np.ones((100,100),dtype=np.uint8)
        owner,trace=module.partial_owner([0,0,100,100],.96,[bubble],text)
        self.assertEqual(owner,'A')
        self.assertEqual(trace['status'],'ASSIGNED_FOR_REVIEW')
        other={'id':'B','box':[68,0,32,100],'outline':[[68,0],[99,0],[99,99],[68,99]]}
        self.assertIsNone(module.partial_owner([0,0,100,100],.96,[bubble,other],text)[0])
        self.assertIsNone(module.partial_owner([0,0,100,100],.96,[bubble],np.zeros_like(text))[0])
        self.assertIsNone(module.partial_owner([0,0,100,100],.89,[bubble],text)[0])
        no_polygon=dict(bubble,outline=[])
        self.assertIsNone(module.partial_owner([0,0,100,100],.96,[no_polygon],text)[0])
