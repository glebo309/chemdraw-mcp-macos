"""Opt-in, serial acceptance of the complete framed-table workflow."""
import os
from pathlib import Path

import pytest

pytestmark=pytest.mark.skipif(
    os.environ.get('CHEMDRAW_LIVE_TEST')!='1' or os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST')!='1',
    reason='Requires a licensed desktop and exclusive native/add-in acceptance session')


@pytest.fixture
def native_bridge(tmp_path):
    from chemdraw_macos.core import Bridge
    b=Bridge(workspace=tmp_path/'native')
    try:yield b
    finally:
        backend=getattr(b,'_desktop_addin',None)
        if backend is not None:backend.close()


@pytest.mark.parametrize('exports',['full','canvas'])
def test_complete_scope_with_existing_documents_preserved(tmp_path,exports,native_bridge):
    from chemdraw_macos.draw import draw_structures
    from test_scope_table_batch import RECORDS,GROUPS,PARENT
    b=native_bridge
    before=b.documents()['documents']
    result=draw_structures(b,RECORDS,str(tmp_path/'result'),groups=GROUPS,
        columns=3,scaffold_smiles=PARENT,separators=False,presentation='background',exports=exports)
    assert result['status']=='completed' and result['document_closed'] is True
    assert all(result['checks'].values())
    assert sorted(b.documents()['documents'],key=lambda d:d['document_id'])==sorted(before,key=lambda d:d['document_id'])
    assert not b.managed
    assert ('svg' in result['artifacts'])==(exports=='full')
    for path in result['artifacts'].values():assert Path(path).is_file()
