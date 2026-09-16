import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import validate_cdxml


def drawing(x=30, y=40):
    return f'<CDXML><page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"><fragment id="2" BoundingBox="{x} {y} {x+25} {y+20}"><n id="3" p="{x} {y}"/><n id="4" p="{x+18} {y}"/><b id="5" B="3" E="4" Order="1"/></fragment></page></CDXML>'


def test_shared_placement_uses_free_space_without_scaling_or_page_expansion():
    from chemdraw_macos.shared import plan_append
    plan=plan_append(drawing(), drawing())
    assert plan['left'] >= 24 and plan['top'] >= 24
    assert plan['left'] >= 79 or plan['top'] >= 84
    assert plan['width']==25 and plan['height']==20


def test_shared_placement_refuses_full_or_unknown_page_before_paste():
    from chemdraw_macos.shared import plan_append
    large=drawing().replace('30 40 55 60','0 0 523 770')
    with pytest.raises(ValueError,match='space'):plan_append(large,drawing())
    with pytest.raises(ValueError):plan_append(drawing().replace('HeightPages="1"','HeightPages="39"'),drawing())
    with pytest.raises(ValueError):plan_append(drawing().replace('</page>','<embeddedobject id="9"/></page>'),drawing())


def test_append_verifier_preserves_original_objects_and_checks_new_chemistry():
    from chemdraw_macos.shared import verify_append
    before=drawing(); addition=drawing(100,100)
    root=validate_cdxml(before)
    added=validate_cdxml(addition).find('page/fragment')
    for e in added.iter():
        for key in ('id','B','E'):
            if key in e.attrib:e.set(key,str(int(e.get(key))+10))
    root.find('page').append(added)
    after=ET.tostring(root,encoding='unicode')
    assert verify_append(before,after,addition)['existing_content_preserved']
    with pytest.raises(ValueError,match='planned'):
        verify_append(before,after,addition,placement={'left':200,'top':200})
    with pytest.raises(ValueError,match='Existing'):
        verify_append(before,after.replace('p="30 40"','p="31 40"'),addition)
    with pytest.raises(ValueError):
        verify_append(before,after.replace('HeightPages="1"','HeightPages="39"'),addition)
    with pytest.raises(ValueError):
        verify_append(before,after.replace('id="14" p=', 'id="14" Element="8" p='),addition)


def test_shared_parameter_reaches_harness_through_mcp_and_cli(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import server,cli,harness
    calls=[]
    def run(*a,**kw):calls.append((a,kw));return {'status':'completed'}
    monkeypatch.setattr(server,'run_drawing',run)
    monkeypatch.setattr(server,'bridge',lambda:object())
    request=harness.DrawingRequest(molecules=[{'value':'CCO','format':'smiles'}])
    assert server.chemdraw_draw(request,str(tmp_path/'out'),presentation='shared',document_id=42)['status']=='completed'
    assert calls[-1][1]['document_id']==42
    monkeypatch.setattr(harness,'run_drawing',run)
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    path=tmp_path/'request.json';path.write_text(request.model_dump_json())
    assert cli.main(['produce','--request',str(path),'--output',str(tmp_path/'out'),'--presentation','shared','--document','42'])==0
    assert calls[-1][1]['document_id']==42


def test_advanced_mcp_preserves_explicit_shared_target(tmp_path,monkeypatch):
    from chemdraw_macos import server
    calls=[]
    monkeypatch.setattr(server,'bridge',lambda:object())
    monkeypatch.setattr(server,'draw_structures',lambda *a,**kw:calls.append(kw) or {'status':'completed'})
    result=server.chemdraw_draw_structures([{'compound_id':'1','label':'A','smiles':'CCO'}],str(tmp_path/'out'),
        presentation='shared',document_id=42)
    assert result['status']=='completed'
    assert calls[0]['document_id']==42 and calls[0]['presentation']=='shared'


def test_shared_harness_bypasses_untitled_save_guard_and_uses_checked_delivery(tmp_path,monkeypatch):
    from chemdraw_macos import harness,shared
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    calls=[]
    monkeypatch.setattr(shared,'run_shared',lambda bridge,plan,out,did: calls.append(did) or {'status':'completed'})
    result=harness.run_drawing(b,{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'),
                               presentation='shared',document_id=42)
    assert result['status']=='completed' and calls==[42]


def test_native_shared_preservation_read_never_saves_target(tmp_path,monkeypatch):
    from chemdraw_macos import shared
    from chemdraw_macos.batch import _document_content
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path);b._shared_document_id=42
    monkeypatch.setattr(shared,'clipboard',lambda bridge,did:{'cdxml':drawing()})
    monkeypatch.setattr(b,'export',lambda *a:pytest.fail('Do not save the shared document'))
    assert _document_content(b,42)


def test_clipboard_fingerprint_ignores_regenerated_page_handle_and_printer_record():
    from chemdraw_macos.shared import fingerprint
    a=drawing().replace('<CDXML>', '<CDXML MacPrintInfo="A">')
    b=a.replace('MacPrintInfo="A"','MacPrintInfo="B"').replace('page id="1"','page id="99"')
    assert fingerprint(a)==fingerprint(b)
    assert fingerprint(a)!=fingerprint(b.replace('p="30 40"','p="31 40"'))


def test_shared_route_checks_target_before_generation(tmp_path,monkeypatch):
    from chemdraw_macos.shared import run_shared
    class NoCalls:
        from contextlib import nullcontext
        lock=nullcontext()
        def documents(self):return {'documents':[]}
        def _id(self,did):return did
        def __getattr__(self,name):pytest.fail('Must gate before any native call')
    with pytest.raises(ValueError,match='absent'):
        run_shared(NoCalls(),{},tmp_path/'out',42)


def test_auto_reuses_visible_working_document(tmp_path,monkeypatch):
    from chemdraw_macos import harness,shared
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'automatic_presentation',lambda:'interactive')
    monkeypatch.setattr(b,'documents',lambda:pytest.fail('Old save guard must not run'))
    calls=[]
    monkeypatch.setattr(shared,'run_shared',lambda *a:calls.append(a) or {'status':'completed'})
    result=harness.run_drawing(b,{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'))
    assert result['status']=='completed' and len(calls)==1


def test_empty_working_document_is_supported_without_save():
    from chemdraw_macos.shared import plan_append,verify_append
    empty='<CDXML><page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"/></CDXML>'
    assert plan_append(empty,drawing())['left']==24
    assert verify_append(empty,drawing(),drawing())['existing_content_preserved']


def test_generated_final_is_closed_before_shared_paste_can_fail(tmp_path,monkeypatch):
    from contextlib import nullcontext
    from chemdraw_macos import shared,harness
    from chemdraw_macos.batch import NativeUncertain
    calls=[]
    class Backend:
        lock=nullcontext()
        _id=staticmethod(int)
        def documents(self):return {'documents':[{'document_id':42,'file':'/user.cdxml'}]}
        def export(self,*a):calls.append('export')
        def close(self,did):assert did==99;calls.append('close_generated')
    def generate(b,plan,out):
        out.mkdir();p=out/'figure.cdxml';p.write_text(drawing())
        return {'document':{'document_id':99},'artifacts':{'cdxml':str(p)}}
    def clipboard(b,did,**kw):
        assert did==42
        if kw.get('cdx'):
            calls.append('paste')
            assert calls.index('close_generated')<calls.index('paste')
            raise NativeUncertain('Focus lost after paste')
        return {'cdxml':drawing()}
    monkeypatch.setattr(harness,'_execute',generate)
    monkeypatch.setattr(shared,'clipboard',clipboard)
    with pytest.raises(NativeUncertain):shared.run_shared_legacy(Backend(),{},tmp_path/'out',42)
    assert calls==['export','close_generated','paste']
@pytest.mark.parametrize('plan',[{'workflow':'reaction'}, {'workflow':'molecules','groups':[{'label':'EWG','compound_ids':['1']}]}])
def test_unsupported_shared_request_stops_before_native_generation(plan,tmp_path):
    from contextlib import nullcontext
    from chemdraw_macos.shared import run_shared
    from chemdraw_macos.harness import NeedsInput
    class Backend:
        lock=nullcontext()
        def documents(self):pytest.fail('Unsupported shared request must not contact native app')
    with pytest.raises(NeedsInput,match='separate'):
        run_shared(Backend(),plan,tmp_path/'out',42)
