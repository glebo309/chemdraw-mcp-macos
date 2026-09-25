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


def test_interactive_scope_uses_one_visible_working_document(tmp_path,native_bridge,monkeypatch):
    from chemdraw_macos.draw import draw_structures
    from test_scope_table_batch import RECORDS,GROUPS,PARENT
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.reaction_batch import EMPTY
    from chemdraw_macos.core import style_cdxml
    b=native_bridge
    original,_=plan_addition(style_cdxml(EMPTY,'house'),RECORDS[:1])
    originals=[b.create(original,visible=True)['document']['document_id'] for _ in range(2)]
    before=b.documents()['documents'];events=[]
    create,close=b.create,b.close
    def record_create(*args,**kw):
        result=create(*args,**kw);events.append(('create',result['document']['document_id'],kw['visible']))
        return result
    def record_close(did):events.append(('close',did));return close(did)
    monkeypatch.setattr(b,'create',record_create);monkeypatch.setattr(b,'close',record_close)
    result=draw_structures(b,RECORDS,str(tmp_path/'interactive'),groups=GROUPS,
        columns=3,scaffold_smiles=PARENT,separators=False,presentation='interactive',exports='preview')
    did=result['document']['document_id']
    assert events==[('create',did,True)]
    assert result['status']=='completed' and all(result['checks'].values())
    after=[d for d in b.documents()['documents'] if d['document_id']!=did]
    assert sorted(after,key=lambda d:d['document_id'])==sorted(before,key=lambda d:d['document_id'])
    close(did)
    for oid in originals:close(oid)


def test_acyclic_scope_native_backbone_alignment(tmp_path,native_bridge):
    import xml.etree.ElementTree as ET
    from chemdraw_macos.draw import draw_structures
    from chemdraw_macos.api_drawing import _isolated
    from test_api_drawing import LYSINE_SCOPE,assert_core_orientation
    b=native_bridge
    before=b.documents()['documents']
    records=[{'compound_id':str(i),'label':str(i),'smiles':s} for i,s in enumerate(LYSINE_SCOPE)]
    groups=[{'label':'Parent','compound_ids':['0']},
            {'label':'Analogues','compound_ids':[str(i) for i in range(1,9)]}]
    result=draw_structures(b,records,str(tmp_path/'acyclic'),groups=groups,
        separators=False,presentation='interactive',exports='preview')
    assert result['status']=='completed' and all(result['checks'].values())
    text=Path(result['artifacts']['cdxml']).read_text();root=ET.fromstring(text)
    assert_core_orientation(_isolated(root,root.find('page/fragment')),text,LYSINE_SCOPE[0])
    did=result['document']['document_id']
    assert sorted([d for d in b.documents()['documents'] if d['document_id']!=did],key=lambda d:d['document_id'])==sorted(before,key=lambda d:d['document_id'])
    b.close(did)
