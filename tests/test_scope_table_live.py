"""Opt-in, serial acceptance of the complete framed-table workflow."""
import os
from pathlib import Path

import pytest

pytestmark=pytest.mark.skipif(
    os.environ.get('CHEMDRAW_LIVE_TEST')!='1' or os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST')!='1',
    reason='Requires a licensed desktop and exclusive native/add-in acceptance session')


def test_complete_scope_with_existing_documents_preserved(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.draw import draw_structures
    from test_scope_table_batch import RECORDS,GROUPS,PARENT
    b=Bridge(workspace=tmp_path/'native')
    before=b.documents()['documents']
    result=draw_structures(b,RECORDS,str(tmp_path/'result'),groups=GROUPS,
        columns=3,scaffold_smiles=PARENT,separators=False,presentation='background')
    assert result['status']=='completed' and result['document_closed'] is True
    assert all(result['checks'].values())
    assert sorted(b.documents()['documents'],key=lambda d:d['document_id'])==sorted(before,key=lambda d:d['document_id'])
    assert not b.managed
    for path in result['artifacts'].values():assert Path(path).is_file()
