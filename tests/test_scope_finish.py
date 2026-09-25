from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import Bridge


def test_finish_scope_refuses_unowned_document_before_read_or_write(tmp_path,monkeypatch):
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'_run',lambda *a:pytest.fail('Native call on unowned document'))
    with pytest.raises(ValueError,match='owned'):
        b.finish_scope(42,'bad','bad','bad',{})


def fixture(tmp_path,monkeypatch,problem=None):
    from test_scope_table_batch import RECORDS,GROUPS,PARENT
    from test_reaction import measured
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.core import style_cdxml
    from chemdraw_macos.reaction_batch import EMPTY,set_paper
    from chemdraw_macos.scope_table import _layout
    from chemdraw_macos.editing import source_token
    from chemdraw_macos import addin
    seed,_=plan_addition(style_cdxml(set_paper(EMPTY,'A3 landscape'),'house'),RECORDS,
        columns=3,scaffold_smiles=PARENT,allow_page_expansion=True)
    native=measured(seed)
    arranged,decorated,_,decoration,_=_layout(native,RECORDS,GROUPS,3,None,True,False,seed=seed)
    root=ET.fromstring(native);page=root.find('page')
    for e in list(page):page.remove(e)
    blank=ET.tostring(root,encoding='unicode')
    calls=[]
    b=Bridge(app_path=tmp_path,workspace=tmp_path);b.managed.add(42);b.lock=nullcontext()
    path=str(tmp_path/'owned.cdxml')
    doc={'document_id':42,'file':path,'modified':False}
    reads=[{'document':{**doc,'modified':problem=='edited'},'cdxml':native,
            'source_token':source_token(native)},
           {'document':doc,'cdxml':native if problem=='not_empty' else blank}]
    def read(did):calls.append('read');return reads.pop(0)
    def request(op,**kw):
        calls.append(op)
        if problem=='timeout':raise RuntimeError('lost append response')
        return {'cdxml':decorated}
    monkeypatch.setattr(addin,'get_backend',lambda bridge:SimpleNamespace(read=read,channel=SimpleNamespace(request=request)))
    def native_call(*args):
        calls.append(args[0])
        if args[0]=='active_document':return 99 if problem=='changed_target' else 42
        return [42,'owned.cdxml',path,True,15]
    monkeypatch.setattr(b,'_run',native_call)
    monkeypatch.setattr(b,'documents',lambda:{'documents':[doc]})
    return b,(42,native,arranged,decorated,decoration),calls


@pytest.mark.parametrize('problem',['edited','not_empty','changed_target','timeout'])
def test_finish_scope_stops_on_edits_identity_changes_or_uncertainty(tmp_path,monkeypatch,problem):
    from chemdraw_macos.batch import NativeUncertain
    b,args,calls=fixture(tmp_path,monkeypatch,problem)
    with pytest.raises((ValueError,NativeUncertain)):b.finish_scope(*args)
    assert calls.count('append')==(1 if problem=='timeout' else 0)
    assert calls.count('clear_owned_scope')<=1
    assert 'close' not in calls


def test_native_clear_checks_identity_file_and_edits_before_dispatch():
    text=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=text.split('else if operation is "clear_owned_scope" then')[1].split('else if operation')[0]
    before=branch.split('do command "selectAll"')[0]
    assert 'id of document 1' in before
    assert 'my pathOfFile(file of targetDoc)' in before
    assert 'modified of targetDoc' in before
    assert 'do command "clear"' in branch
