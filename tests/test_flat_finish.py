import unittest

import numpy as np

from manga_ai.engines.flat_finish import finish_crop, finish_page


class FlatFinishTests(unittest.TestCase):
    def fixture(self):
        src = np.full((120, 120, 3), 252, 'uint8')
        src[45:75, 45:75] = 228  # light AA outside the old mask
        src[48:72, 48:72] = 0
        used = np.zeros((120, 120), bool)
        used[48:72, 48:72] = True
        current = src.copy()
        current[used] = 248  # old donor contamination
        inside = np.zeros_like(used)
        inside[8:112, 8:112] = True
        text = np.zeros_like(used)
        text[40:80, 40:80] = True
        return src, current, used, inside, text, np.zeros_like(used)

    def test_completes_light_rim_and_refills_from_uncontaminated_donors(self):
        src, current, used, inside, text, protected = self.fixture()
        out, final, added, trace = finish_crop(src, current, used, inside, text, protected)
        self.assertTrue(added.any())
        self.assertTrue((out[45:75, 45:75] == 252).all())
        self.assertFalse((np.any(out != current, axis=2) & ~final).any())
        self.assertTrue((final[used]).all())
        self.assertTrue(trace['review_required'])

    def test_protected_artwork_and_unknown_dark_lines_are_not_overwritten(self):
        src, current, used, inside, text, protected = self.fixture()
        src[35:85, 75:77] = 0
        current[35:85, 75:77] = 0
        protected[45:60, 45:75] = True
        out, final, added, trace = finish_crop(src, current, used, inside, text, protected)
        np.testing.assert_array_equal(out[protected], current[protected])
        np.testing.assert_array_equal(out[:, 75:77], current[:, 75:77])
        self.assertFalse(added[:, 71:].any())
        self.assertFalse((added & ~inside).any())

    def test_no_mask_or_text_or_dark_background_cannot_gain_authority(self):
        a = self.fixture()
        for index in (2, 3, 4):
            b = list(a)
            b[index] = np.zeros_like(b[index])
            out, mask, extra, trace = finish_crop(*b)
            np.testing.assert_array_equal(out, b[1])
            self.assertFalse(extra.any())
        b = list(a)
        b[0] = np.minimum(b[0], 210)
        out, _, extra, trace = finish_crop(*b)
        np.testing.assert_array_equal(out, a[1])
        self.assertFalse(extra.any())
        self.assertEqual(trace['reason'], 'BACKGROUND_NOT_FLAT_OR_INSUFFICIENT_DONORS')

    def test_page_respects_selection_ownership_gates_and_heads(self):
        src, current, used, _, _, _ = self.fixture()
        region = {'id': 'B001', 'box': [0, 0, 120, 120], 'outline': [[8,8],[112,8],[112,112],[8,112]]}
        owner = {'text_boxes_by_region': {'B001': [[40,40,40,40]]}, 'events': []}
        for selected, gates in ((set(), []), ({'B001'}, [{'region':'B001','reason':'COMPLEX_BACKGROUND'}])):
            own = dict(owner, events=gates)
            out, mask, trace = finish_page(src, current, used, [region], selected, own, [], [120,120])
            np.testing.assert_array_equal(out, current)
            np.testing.assert_array_equal(mask, used)
        out, mask, trace = finish_page(src, current, used, [region], {'B001'}, owner, [[35,35,50,50]], [120,120])
        np.testing.assert_array_equal(out[35:85,35:85], current[35:85,35:85])

    def test_conflicting_other_region_blocks_the_finish(self):
        src, current, used, _, _, _ = self.fixture()
        regions = [{'id': 'B001', 'box': [0,0,120,120], 'outline': [[8,8],[112,8],[112,112],[8,112]]},
                   {'id': 'B002', 'box': [35,35,50,50], 'outline': []}]
        owner = {'text_boxes_by_region': {'B001': [[40,40,40,40]]}, 'events': []}
        out, mask, trace = finish_page(src, current, used, regions, {'B001'}, owner, [], [120,120])
        np.testing.assert_array_equal(out, current)
        np.testing.assert_array_equal(mask, used)


class BackgroundFieldRegressionTests(unittest.TestCase):
    def test_compression_halo_and_letter_counter_do_not_remain_as_negative_glyph(self):
        # Ground truth paper gradient is independent of the glyph-shaped mask.
        from manga_ai.engines.flat_finish import FinishConfig
        h, w = 160, 180
        yy, xx = np.indices((h,w))
        paper = np.repeat(np.rint(250+xx[:,:,None]/90), 3, axis=2).astype('uint8')
        used = np.zeros((h,w), bool)
        used[45:115,60:68] = True
        used[45:115,105:113] = True
        used[45:53,60:113] = True
        used[107:115,60:113] = True
        text = np.zeros_like(used);text[25:135,40:135] = True
        src = paper.copy()
        # A broad, pale compression ghost and contaminated counter survive a
        # stroke-only refill even when all dark strokes have been removed.
        src[38:122,53:120] = 246
        src[used] = 0
        old = src.copy();old[used] = 253
        out, final, added, trace = finish_crop(src,old,used,np.ones_like(used),text,np.zeros_like(used))
        self.assertEqual(trace['decision'], 'shadow_finish_review')
        error = np.abs(out[38:122,53:120].astype(int)-paper[38:122,53:120].astype(int))
        self.assertLessEqual(error.max(), 1)
        self.assertFalse((np.any(out != old,axis=2) & ~final).any())
        self.assertTrue((added & ~used).any())
        self.assertEqual(trace['protected_pixels_changed'], 0)

    def test_disconnected_unmasked_text_does_not_gain_authority(self):
        src=np.full((100,160,3),252,'uint8');used=np.zeros((100,160),bool);used[40:60,25:35]=True
        src[used]=0;old=src.copy();old[used]=249
        text=np.zeros_like(used);text[20:80,15:45]=True;text[20:80,100:140]=True
        old[35:65,110:130]=248;src[35:65,110:130]=248
        out,mask,added,trace=finish_crop(src,old,used,np.ones_like(used),text,np.zeros_like(used))
        np.testing.assert_array_equal(out[:,100:],old[:,100:])
        self.assertFalse(added[:,100:].any())

    def test_no_text_free_donors_keeps_previous_output_and_reason(self):
        src=np.full((100,100,3),252,'uint8');used=np.zeros((100,100),bool);used[45:55,45:55]=True
        src[used]=0;old=src.copy();old[used]=250
        out,mask,added,trace=finish_crop(src,old,used,np.ones_like(used),np.ones_like(used),np.zeros_like(used))
        np.testing.assert_array_equal(out,old)
        self.assertFalse(added.any())
        self.assertEqual(trace['reason'],'INSUFFICIENT_TEXT_FREE_DONORS')


class UndercoveredPolygonTests(unittest.TestCase):
    def test_finishes_already_masked_text_outside_polygon_without_touching_unknown_ink(self):
        src=np.full((160,200,3),252,'uint8');used=np.zeros((160,200),bool)
        used[45:110,103:111]=True;used[45:110,130:138]=True
        used[45:53,103:138]=True;used[102:110,103:138]=True
        src[38:118,96:146]=247;src[used]=0
        # A real line inside the owned box must remain protected.
        src[30:125,147:149]=0
        old=src.copy();old[used]=254
        r={'id':'B001','box':[20,20,75,110],'outline':[[20,20],[95,20],[95,130],[20,130]]}
        own={'text_boxes_by_region':{'B001':[[85,30,70,95]]},'events':[]}
        out,mask,t=finish_page(src,old,used,[r],{'B001'},own,[],[200,160])
        self.assertEqual(t['events'][0]['decision'],'shadow_finish_review')
        self.assertTrue((out[55:100,112:129]==252).all())
        np.testing.assert_array_equal(out[:,147:149],old[:,147:149])
        self.assertFalse((np.any(out!=old,axis=2)&~mask).any())
        self.assertGreater(t['events'][0]['reconstructed_envelope_outside_polygon_pixels'],0)
