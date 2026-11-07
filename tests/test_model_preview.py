import tempfile
import json
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from manga_ai.model_preview import preview, batch_clean


class PreviewTest(unittest.TestCase):
    def test_preview_preserves_source_and_only_changes_masked_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = np.full((80, 100, 3), 70, dtype=np.uint8)
            source = root / 'source.png'
            Image.fromarray(original).save(source)
            mask = np.zeros((80,100), np.uint8)
            mask[30:35,40:45] = 1
            with patch('manga_ai.model_preview.detailed_mask', return_value=(mask, [])), \
                 patch('manga_ai.model_preview.lama_clean', return_value=np.full_like(original, 200)):
                result = preview(source, root/'output', 'ctd', True)
            clean = np.asarray(Image.open(root/'output'/'clean.png'))
            self.assertTrue((np.asarray(Image.open(source)) == original).all())
            self.assertTrue((clean[0,0] == 70).all())
            self.assertTrue((clean[32,42] == 200).all())
            self.assertGreater(result['mask_pixels'], 0)
            self.assertTrue(all(Path(p).is_file() for p in result['images'].values()))

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            preview('unused', 'unused', 'invalid')

    def test_batch_overlay_matches_preview_and_retains_uncertainty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = np.full((80,100,3),70,np.uint8)
            Image.fromarray(source).save(root/'original.png')
            region={'id':'B001','box':[20,20,40,40],'safe':[20,20,40,40],
                    'auto_clean':False,'fill':[255,255,255]}
            (root/'manifest.json').write_text(json.dumps({'schema':1,'width':100,'height':80,'regions':[region]}))
            mask=np.zeros((80,100),np.uint8);mask[30:35,40:45]=1
            with patch('manga_ai.model_preview.detailed_mask', return_value=(mask, [])), \
                 patch('manga_ai.model_preview.lama_clean', return_value=np.full_like(source,200)):
                preview(root/'original.png', root/'preview', 'ctd', True)
                result=batch_clean(root/'manifest.json',[{'id':'B001','translation':'Xin chào','clean':True}], 'ctd',True)
            overlay=np.asarray(Image.open(result['overlay']))
            composite=source.copy(); composite[overlay[:,:,3]>0]=overlay[:,:,:3][overlay[:,:,3]>0]
            self.assertTrue(np.array_equal(composite,np.asarray(Image.open(root/'preview'/'clean.png'))))
            self.assertTrue(np.array_equal(np.asarray(Image.open(root/'original.png')),source))
            self.assertEqual(result['applied'],[])
            self.assertEqual(result['skipped'],['B001'])
            self.assertTrue(result['experimental'])

    def test_batch_rejects_mismatched_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            Image.fromarray(np.zeros((10,10,3),np.uint8)).save(root/'original.png')
            (root/'manifest.json').write_text(json.dumps({'schema':1,'width':100,'height':80,'regions':[]}))
            with self.assertRaises(ValueError): batch_clean(root/'manifest.json',[], 'ctd')

    def test_koharu_cache_used_only_for_matching_unchanged_pixels(self):
        from manga_ai.model_preview import MODELS
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); rgb=np.full((20,20,3),70,np.uint8)
            Image.fromarray(rgb).save(root/'original.png')
            (root/'manifest.json').write_text(json.dumps({'schema':1,'width':20,'height':20,'regions':[]}))
            mask=np.zeros((20,20),np.uint8);mask[5:8,5:8]=1
            np.savez_compressed(root/'koharu_mask_cache.npz',mask=mask,
                image_digest=hashlib.sha256(rgb.tobytes()).hexdigest(),
                mask_digest=hashlib.sha256(mask.tobytes()).hexdigest(),model_digest=MODELS['koharu'][1])
            fallback=np.zeros_like(mask);fallback[12:15,12:15]=1
            with patch('manga_ai.model_preview.model_path'), \
                 patch('manga_ai.comic_text_ai.detect_multiscale', return_value=[]), \
                 patch('manga_ai.model_preview.koharu_mask',return_value=fallback) as detect:
                result=batch_clean(root/'manifest.json',[],'koharu')
                self.assertEqual(detect.call_count,0)
                self.assertGreater(result['mask_pixels'],0)
                rgb[0,0]=0;Image.fromarray(rgb).save(root/'original.png')
                batch_clean(root/'manifest.json',[],'koharu')
                self.assertEqual(detect.call_count,1)


if __name__ == '__main__':
    unittest.main()
