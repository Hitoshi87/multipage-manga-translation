import importlib.util
import unicodedata
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FONTS=('itim/Itim-Regular.ttf','patrickhand/PatrickHand-Regular.ttf','bangers/Bangers-Regular.ttf')

class FontSamplesTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('fontTools'), 'fontTools not installed')
    def test_vietnamese_precomposed_characters(self):
        from fontTools.ttLib import TTFont
        # Unicode compositions used for the Vietnamese alphabet, both cases.
        bases='aăâeêioôơuưyAĂÂEÊIOÔƠUƯY'
        characters=set(bases+'đĐ')
        for base in bases:
            for accent in '\u0300\u0301\u0303\u0309\u0323':
                composed=unicodedata.normalize('NFC',base+accent)
                if len(composed)==1:characters.add(composed)
        for name in FONTS:
            path=ROOT/'assets/fonts'/name
            with self.subTest(font=name):
                self.assertTrue((path.parent/'OFL.txt').is_file())
                font=TTFont(path)
                try:
                    cmap=font.getBestCmap()
                    self.assertEqual([c for c in sorted(characters) if ord(c) not in cmap],[])
                finally:font.close()
