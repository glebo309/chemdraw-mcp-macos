import json
from pathlib import Path

import pytest
from test_scope import MeasuredBridge, SAMPLE, CELLS
from chemdraw_macos.scope import grid_document
from chemdraw_macos.editing import source_token


def test_grid_native_timeout_does_not_close_or_retry(tmp_path):
    b=MeasuredBridge(tmp_path/'work')
    b.docs[1]=SAMPLE
    export=b.export
    def uncertain(did,path,format,pixels=3200):
        if Path(path).name=='figure.svg':raise RuntimeError('native timeout')
        return export(did,path,format,pixels)
    b.export=uncertain
    with pytest.raises(RuntimeError,match='native timeout'):
        grid_document(b,1,str(tmp_path/'out'),CELLS,source_token(SAMPLE),columns=2)
    assert not any(event[0]=='close' for event in b.events)
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='uncertain'
