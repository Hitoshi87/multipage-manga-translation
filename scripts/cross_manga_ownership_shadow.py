"""Compatibility entry point; runtime implementation lives in manga_ai.engines.stages."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from manga_ai.engines.stages import ownership as _impl
from manga_ai.engines.stages.ownership import *

def process(dataset,page,source_root=None,output_root=None,selected_ids=None,make_previews=True):
    return _impl.process(dataset,page,source_root=S if source_root is None else source_root,output_root=O if output_root is None else output_root,selected_ids=SELECTED_IDS if selected_ids is None else selected_ids,make_previews=make_previews)

if __name__=='__main__':
    _impl.main()
