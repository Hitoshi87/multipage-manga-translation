import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from manga_ai.io import validate_manifest, write_json, read_json
from manga_ai.engine import render_clean
from manga_ai.cli import main

class CleanCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.data = {'schema':1,'width':80,'height':80,'regions':[{'id':'B001','box':[10,10,50,50],'safe':[15,15,30,30],'fill':[255,255,255],'auto_clean':True}]}

    def test_reject_corrupt_geometry_and_ids(self):
        for field, value in [('safe',[float('nan'),0,20,20]),('safe',[0,0,90,90]),('id','../escape'),('fill',[256,0,0]),('auto_clean','true')]:
            data=copy.deepcopy(self.data);data['regions'][0][field]=value
            with self.assertRaises(ValueError): validate_manifest(data)
        data=copy.deepcopy(self.data);data['regions']*=2
        with self.assertRaises(ValueError): validate_manifest(data)

    def test_cli_clean_persists_selected_ids_and_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'masks').mkdir()
            Image.new('RGB',(80,80),'black').save(root/'original.png')
            Image.new('L',(50,50),255).save(root/'masks/B001.png')
            data=copy.deepcopy(self.data);data['mapping']=[{'id':'B001','translation':'Xin chào','clean':True}]
            write_json(root/'manifest.json',data)
            self.assertEqual(main(['clean',str(root/'manifest.json')]),0)
            self.assertEqual(read_json(root/'manifest.json')['clean_ids'],['B001'])
            result=render_clean(root/'manifest.json',[{'id':'B001','translation':'','clean':True}])
            self.assertEqual(result['applied'],[])
            self.assertFalse(np.any(np.array(Image.open(root/'clean_overlay.png'))[:,:,3]))

    def test_wrong_mask_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'masks').mkdir();write_json(root/'manifest.json',self.data)
            Image.new('RGB',(80,80),'white').save(root/'original.png')
            Image.new('L',(5,5),255).save(root/'masks/B001.png')
            with self.assertRaises(ValueError):render_clean(root/'manifest.json',[{'id':'B001','translation':'A'}])
