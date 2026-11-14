import tempfile
import unittest
from pathlib import Path
from manga_ai.cli import dispatch
from manga_ai.io import write_json


class ResumeInventoryTest(unittest.TestCase):
    def test_only_small_resume_metadata_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)/'project.json'
            write_json(project,{'schema_version':1,'pages':[{'ordinal':1,'page_id':'001.jpeg','segments':[{'jp':'private text'}]}],
                                'runs':[{'streaming':True,'groups':[{'results':[{'semantic_translation':'private translation'}]}]}],
                                'profiles':[]})
            result=dispatch({'operation':'translation_resume_inventory','project':str(project)})
            self.assertEqual(result,{'pages':[{'ordinal':1,'page_id':'001.jpeg'}],'streaming':True})


if __name__=='__main__':
    unittest.main()
