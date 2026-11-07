import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import cv2
import numpy as np
from manga_ai.bubble_refinement import split_text_groups
from manga_ai.balloon_clean import supported_mask
from manga_ai.engine import bubble_font_style


class DialogueRepairTest(unittest.TestCase):
    def test_separate_text_groups_preserve_whole_parent_mask(self):
        rgb=np.full((100,200,3),255,np.uint8)
        interior=np.zeros((80,180),np.uint8)
        for x in (45,135):cv2.ellipse(interior,(x,40),(50,38),0,0,360,255,-1)
        parent={'box':[10,10,180,80],'interior':interior,
                'detector':'ai_balloon','detector_confidence':.99}
        ds=[{'box':[25,25,40,40],'kind':'in_bubble','confidence':.95},
            {'box':[120,25,40,40],'kind':'in_bubble','confidence':.95}]
        children=split_text_groups(rgb,[parent],ds)
        self.assertEqual(len(children),2)
        self.assertEqual(sum(cv2.countNonZero(c['interior']) for c in children),cv2.countNonZero(interior))
        # A band of ink across the gap prevents the split.
        rgb[40:45,65:120]=0
        self.assertEqual(len(split_text_groups(rgb,[parent],ds)),1)
        rgb[:]=255
        parent['interior'][:]=255
        self.assertEqual(len(split_text_groups(rgb,[parent],ds)),1)

    def test_single_multicolumn_text_group_stays_whole(self):
        rgb=np.full((100,200,3),255,np.uint8)
        p={'box':[10,10,180,80],'interior':np.ones((80,180),np.uint8)*255}
        ds=[{'box':[25,25,140,40],'kind':'in_bubble','confidence':.99}]
        self.assertEqual(split_text_groups(rgb,[p],ds),[p])

    def test_supported_clean_excludes_faces_and_requires_models_to_agree(self):
        rgb=np.full((200,200,3),255,np.uint8);rgb[35:45,35:45]=0
        region={'box':[20,20,50,50],'outline':[[20,20],[69,20],[69,69],[20,69]],
                'detector':'ai_balloon','detector_confidence':.99}
        mask=np.zeros((200,200),np.uint8);mask[35:45,35:45]=1
        ds=[{'box':[30,30,20,20],'kind':'in_bubble','confidence':.99}]
        proof=supported_mask(rgb,region,mask,ds,[])
        self.assertIsNotNone(proof);self.assertEqual(proof[20,20],255)
        self.assertIsNone(supported_mask(rgb,region,mask,ds,[[30,30,20,20]]))
        self.assertIsNone(supported_mask(rgb,region,mask,[],[]))

    def test_smooth_connected_lobes_are_not_shouting(self):
        mask=np.zeros((220,320),np.uint8)
        for x in (65,155,245):cv2.ellipse(mask,(x,110),(60,85),0,0,360,255,-1)
        contour=max(cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea)
        self.assertEqual(bubble_font_style({'outline':contour[:,0].tolist(),'detector':'ai_balloon'}),'dialogue')

    def test_renderer_rejects_modified_mask_even_if_manifest_claims_safe(self):
        from manga_ai.engine import render_clean
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'masks').mkdir()
            rgb=np.full((200,200,3),255,np.uint8);rgb[35:45,35:45]=0
            region={'id':'B001','box':[20,20,50,50],'safe':[25,25,40,40],
                'outline':[[20,20],[69,20],[69,69],[20,69]],'detector':'ai_balloon',
                'detector_confidence':.99,'auto_clean':True,'clean_method':'model_supported_text','fill':[255,255,255]}
            tm=np.zeros((200,200),np.uint8);tm[35:45,35:45]=1
            ds=[{'box':[30,30,20,20],'kind':'in_bubble','confidence':.99}]
            Image.fromarray(rgb).save(root/'original.png')
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'schema':1,'lang':'jpn_vert','width':200,'height':200,'regions':[region]}))
            proof=supported_mask(rgb,region,tm,ds,[]);Image.fromarray(proof).save(root/'masks/B001.png')
            mapping=[{'id':'B001','translation':'Test','clean':True}]
            with patch('manga_ai.model_preview.ctd_mask',return_value=tm),patch('manga_ai.comic_text_ai.detect',return_value=ds),patch('manga_ai.head_protection.detect',return_value=[]):
                self.assertEqual(render_clean(manifest,mapping)['applied'],['B001'])
                proof[0,0]=255;Image.fromarray(proof).save(root/'masks/B001.png')
                result=render_clean(manifest,mapping)
                self.assertEqual(result['applied'],[]);self.assertIn('B001',result['blocked'])


if __name__=='__main__':unittest.main()
