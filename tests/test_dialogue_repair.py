import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import cv2
import numpy as np
from manga_ai.bubble_refinement import split_text_groups, split_vertical_text_groups
from manga_ai.balloon_clean import supported_mask
from manga_ai.engine import bubble_font_style
from manga_ai.engine_art_draft import _local_glyph_mask


class DialogueRepairTest(unittest.TestCase):
    def test_art_draft_mask_requires_evidence_and_stays_inside_outline(self):
        rgb=np.full((120,120,3),255,np.uint8);rgb[45:55,45:55]=0
        region={'box':[20,20,80,80], 'outline':[[20,20],[99,20],[99,99],[20,99]],'detector':'ai_balloon'}
        evidence=np.zeros((120,120),np.uint8);evidence[45:55,45:55]=1
        boxes=[{'box':[35,35,30,30],'kind':'in_bubble','confidence':.99}]
        mask=_local_glyph_mask(rgb,region,evidence,boxes)
        self.assertIsNotNone(mask);self.assertTrue(mask[50,50]);self.assertEqual(int(mask[:20].sum()+mask[:, :20].sum()),0)
        self.assertIsNone(_local_glyph_mask(rgb,region,evidence,[]))
        # A glyph mostly inside `interior` whose edge touches the 7x7 erosion band is still fully covered.
        rgb2=np.full((120,120,3),255,np.uint8);rgb2[45:58,82:95]=0
        ev2=np.zeros((120,120),np.uint8);ev2[45:58,82:95]=1
        b2=[{'box':[78,40,20,22],'kind':'in_bubble','confidence':.83}]
        m2=_local_glyph_mask(rgb2,region,ev2,b2)
        self.assertIsNotNone(m2);self.assertTrue(np.all(m2[45:58,82:95]>0));self.assertEqual(int(m2[:,98:].sum()),0)
        self.assertIsNone(_local_glyph_mask(rgb2,region,ev2,[{'box':[78,40,20,22],'kind':'in_bubble','confidence':.75}]))
    def test_split_offset_vertical_lobes_only_at_ink_free_band(self):
        rgb=np.full((220,220,3),255,np.uint8);rgb[45:75,125:145]=0;rgb[140:170,65:85]=0
        parent={'box':[20,20,180,180],'interior':np.ones((180,180),np.uint8)*255,'detector':'ai_balloon'}
        boxes=[{'box':[115,40,40,40],'kind':'in_bubble','confidence':.99},
               {'box':[55,135,40,40],'kind':'in_bubble','confidence':.99}]
        split=split_vertical_text_groups(rgb,[parent],boxes)
        self.assertEqual(len(split),2)
        self.assertEqual(sum(cv2.countNonZero(c['interior']) for c in split),cv2.countNonZero(parent['interior']))
        aligned=[boxes[0],{**boxes[1],'box':[115,135,40,40]}]
        self.assertEqual(split_vertical_text_groups(rgb,[parent],aligned),[parent])
        rgb[60:155,20:200]=0
        self.assertEqual(split_vertical_text_groups(rgb,[parent],boxes),[parent])
    def test_large_balloon_requires_independent_text_proof(self):
        rgb=np.full((200,200,3),255,np.uint8);rgb[60:70,60:70]=0
        region={'box':[20,20,90,80], 'outline':[[20,20],[109,20],[109,99],[20,99]],
                'detector':'ai_balloon','detector_confidence':.99}
        text=np.zeros((200,200),np.uint8);text[60:70,60:70]=1
        boxes=[{'box':[55,55,25,25],'kind':'in_bubble','confidence':.99}]
        self.assertIsNotNone(supported_mask(rgb,region,text,boxes,[]))
        self.assertIsNone(supported_mask(rgb,region,text,[],[]))
        rgb[45:90,45:90]=0
        self.assertIsNone(supported_mask(rgb,region,text,boxes,[]))
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
