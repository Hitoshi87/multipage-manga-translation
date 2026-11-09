import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from manga_ai.runtime.resources import sha256_file
from manga_ai.translation.vision import focused_plan, image_parts, image_plan, public_plan


class VisionDetailTests(unittest.TestCase):
    def test_numbered_detail_sheet_is_mapped_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);image=folder/'original.png'
            picture=Image.new('RGB',(300,240),'white');draw=ImageDraw.Draw(picture)
            draw.rectangle((20,30,80,100),fill='black');draw.rectangle((190,100,250,200),fill='black')
            picture.save(image)
            segments=[{'id':'first','page_id':'p','box':[20,30,60,70]},
                      {'id':'second','page_id':'p','box':[190,100,60,100]}]
            state={'pages':[{'page_id':'p','manifest':str(folder/'manifest.json'),
                             'image_digest':sha256_file(image),'segments':segments}]}
            plan=focused_plan(state,segments)
            self.assertEqual([p['mode'] for p in plan],['detail_sheet','detail_sheet'])
            self.assertEqual([(p['cells'][0]['label'],p['cells'][0]['target_id']) for p in public_plan(plan)],
                             [('1','first'),('2','second')])
            self.assertNotIn('image_path',public_plan(plan)[1])
            parts=image_parts(plan);self.assertEqual(len(parts),2)
            encoded=parts[1]['image_url']['url'].split(',',1)[1]
            sheet=Image.open(io.BytesIO(base64.b64decode(encoded)))
            self.assertEqual(sheet.size,(600,400))
            self.assertLess(sheet.convert('L').getextrema()[0],20)

    def test_single_crop_does_not_duplicate_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);image=folder/'original.png';Image.new('RGB',(40,40),'white').save(image)
            seg={'id':'s','page_id':'p','box':[5,5,20,20]}
            state={'pages':[{'page_id':'p','manifest':str(folder/'manifest.json'),
                             'image_digest':sha256_file(image),'segments':[seg]}]}
            self.assertEqual(len(image_parts(image_plan(state,{'targets':[seg]},'target_crop'))),1)
