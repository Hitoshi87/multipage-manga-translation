import unittest
from unittest.mock import patch
import numpy as np
from manga_ai.balloon_ai import recover_missed

class BalloonZoomTest(unittest.TestCase):
    def test_recovers_only_uncovered_text_and_projects_coordinates(self):
        image=np.full((600,600,3),255,np.uint8)
        text={'box':[250,250,40,60],'kind':'in_bubble','confidence':.98}
        candidate={'box':[60,60,100,120],'interior':np.ones((120,100),np.uint8)*255,'detector':'ai_balloon','detector_confidence':.97}
        with patch('manga_ai.balloon_ai.detect',return_value=[candidate]) as detect:
            result=recover_missed(image,[],[text,text])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['box'],[230,230,100,120])
        self.assertEqual(detect.call_count,1)
        self.assertEqual(result[0]['interior'].shape,(120,100))

    def test_rejects_crop_edge_and_keeps_existing_regions(self):
        image=np.zeros((600,600,3),np.uint8)
        text={'box':[250,250,40,60],'kind':'in_bubble','confidence':.98}
        candidate={'box':[0,0,180,180],'interior':np.ones((180,180),np.uint8)}
        with patch('manga_ai.balloon_ai.detect',return_value=[candidate]):
            self.assertEqual(recover_missed(image,[],[text]),[])
        old={'box':[230,230,100,120]}
        with patch('manga_ai.balloon_ai.detect') as detect:
            self.assertEqual(recover_missed(image,[old],[text]),[old]);detect.assert_not_called()
