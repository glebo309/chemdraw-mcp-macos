from contextlib import nullcontext
from pathlib import Path
import json
import xml.etree.ElementTree as ET

import pytest

from test_api_drawing import EMPTY
from test_scope_decoration import source, GROUPS
from test_batch import BatchBridge


def caption_parent():
    from chemdraw_macos.api_drawing import plan_addition
    text, _ = plan_addition(EMPTY, [{'compound_id':'parent','label':'caffein',
        'smiles':'CC1C=Cc2c1c(=O)n(C)c(=O)n2C'}])
    root = ET.fromstring(text);page = root.find('page')
    ET.SubElement(page, 'chemicalproperty', id='9000', ChemicalPropertyType='1',
        ChemicalPropertyDisplayID=page.find('t').get('id'),
        BasisObjects=' '.join(e.get('id') for e in page.find('fragment').iter() if e.get('id')))
    return ET.tostring(root, encoding='unicode')


def test_shared_append_retains_linked_name_property_without_using_it_as_chemistry():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.shared import verify_append
    before = caption_parent()
    payload, report = plan_addition(before, [{'compound_id':'new','label':'new','smiles':'CCO'}])
    root = ET.fromstring(before);root.find('page').extend(ET.fromstring(payload).find('page'))
    after = ET.tostring(root, encoding='unicode')
    assert verify_append(before, after, payload, exact_coordinates=True)['existing_content_preserved']
    root.find('page/chemicalproperty').set('ChemicalPropertyType','2')
    with pytest.raises(ValueError):verify_append(before, ET.tostring(root,encoding='unicode'), payload)


def test_unknown_caption_property_rejected_before_planning():
    from chemdraw_macos.api_drawing import plan_addition
    before = caption_parent().replace('ChemicalPropertyType="1"', 'ChemicalPropertyType="999"')
    with pytest.raises(ValueError):plan_addition(before,[{'compound_id':'new','label':'new','smiles':'CCO'}])


def test_export_verifies_linked_caption_metadata_independently():
    from chemdraw_macos.api_drawing import verify_export_snapshot
    before=caption_parent()
    verify_export_snapshot(before,before)
    with pytest.raises(ValueError):
        verify_export_snapshot(before,before.replace('ChemicalPropertyType="1"','ChemicalPropertyType="2"'))


def test_full_append_and_export_retains_stale_linked_name(tmp_path,monkeypatch):
    from chemdraw_macos import api_drawing
    from chemdraw_macos.addin import source_token
    from chemdraw_macos.shared import verify_append
    class Backend:
        current=caption_parent()
        def read(self,did):return {'cdxml':self.current,'source_token':source_token(self.current)}
        def append(self,did,text,token,**kwargs):
            root=ET.fromstring(self.current);root.find('page').extend(ET.fromstring(text).find('page'))
            after=ET.tostring(root,encoding='unicode')
            checks=verify_append(self.current,after,text,exact_coordinates=True)
            self.current=after
            path=tmp_path/'native.cdxml';path.write_text(after)
            return {'document':{'document_id':42},'after_snapshot':str(path),'checks':checks,'status':'completed'}
    class Bridge:
        def _id(self,did):return did
        def documents(self):return {'documents':[{'document_id':42}]}
        def export(self,did,path,fmt):
            Path(path).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>')
    backend=Backend();monkeypatch.setattr(api_drawing,'get_backend',lambda bridge:backend)
    result=api_drawing.run_api_drawing(Bridge(),{'exports':'full','structures':[{'compound_id':'new','label':'New','smiles':'CCO'}]},tmp_path/'out',42)
    assert result['status']=='completed'
    assert ET.fromstring(backend.current).find('page/chemicalproperty') is not None
    assert result['checks']['native_svg_export'] is True


def test_preservation_read_selects_exact_untitled_document_and_restores_active(monkeypatch,tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.batch import _document_content
    from chemdraw_macos import addin
    b = object.__new__(Bridge);b.lock = nullcontext();b.active = 2;b.calls = []
    b._new_path = lambda *a: tmp_path/'snapshot.cdxml'
    b.inspect = lambda did: {'document':{'document_id':did,'file':''}}
    def run(op,*args):
        b.calls.append((op,*args))
        if op == 'active_document':return b.active
        if op == 'select_document':
            assert b.active == args[1]
            b.active = args[0];return True
        raise AssertionError(op)
    b._run = run
    class Backend:
        def read(self,did):
            assert b.active == did, 'Preservation must not read a different active document'
            return {'cdxml':EMPTY}
    monkeypatch.setattr(addin,'get_backend',lambda bridge:Backend())
    _document_content(b,1)
    assert b.active == 2
    assert [c for c in b.calls if c[0]=='select_document'] == [('select_document',1,2),('select_document',2,1)]


def test_decoration_mcp_returns_retained_result_when_postcheck_fails(tmp_path,monkeypatch):
    from chemdraw_macos import server
    from chemdraw_macos.editing import source_token
    b=BatchBridge(tmp_path/'work');b.docs[1]=source()
    monkeypatch.setattr(server,'bridge',lambda:b)
    from chemdraw_macos import scope_decoration
    original=scope_decoration._document_content
    def read(bridge,did):
        if b.managed:raise scope_decoration.NativeUncertain('read failed after drawing')
        return original(bridge,did)
    monkeypatch.setattr(scope_decoration,'_document_content',read)
    result=server.chemdraw_decorate_scope(1,str(tmp_path/'out'),GROUPS,source_token(source()))
    assert result['status']=='uncertain'
    assert result['retry_safe'] is False
    assert result['document']['document_id'] in b.managed
    assert Path(result['artifacts']['cdxml']).exists()
    assert result['checks']['decoration_geometry_preserved']
    assert 'Do not' in result['next_action']
    assert len([e for e in b.events if e[0]=='create'])==1


def test_front_door_uncertainty_includes_retained_document_and_artifacts(tmp_path,monkeypatch):
    from chemdraw_macos import harness,reaction_batch
    from chemdraw_macos.batch import NativeUncertain
    out=tmp_path/'out'
    def failed(*a,**kw):
        out.mkdir();(out/'figure').mkdir()
        (out/'figure/figure.cdxml').write_text(EMPTY)
        (out/'audit.json').write_text(json.dumps({'working_document_id':456,'checks':{'native_layout':True}}))
        raise NativeUncertain('preservation read failed')
    monkeypatch.setattr(reaction_batch,'run_reaction_batch',failed)
    result=harness.run_drawing(object(),{'molecules':[{'format':'smiles','value':'CCO'}],
        'products':[{'format':'smiles','value':'CC=O'}]},str(out),presentation='background')
    assert result['status']=='uncertain' and result['retry_safe'] is False
    assert result['document']['document_id']==456
    assert Path(result['artifacts']['cdxml']).is_file()


def test_cli_draw_returns_same_uncertain_recovery_evidence(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import cli
    from chemdraw_macos.batch import NativeUncertain
    out=tmp_path/'out';out.mkdir()
    (out/'audit.json').write_text(json.dumps({'working_document_id':456}))
    manifest=tmp_path/'request.json';manifest.write_text(json.dumps({'structures':[]}))
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    def failed(*a,**kw):raise NativeUncertain('read failed')
    monkeypatch.setattr(cli,'draw_structures',failed)
    assert cli.main(['draw','--manifest',str(manifest),'--output',str(out)])!=0
    result=json.loads(capsys.readouterr().err)
    assert result['status']=='uncertain' and result['document']['document_id']==456
    assert result['retry_safe'] is False


def test_untitled_preservation_ignores_fresh_page_handle_but_checks_content(monkeypatch,tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.batch import _document_content
    from chemdraw_macos import addin
    b=object.__new__(Bridge)
    b.inspect=lambda did:{'document':{'file':''}}
    b._new_path=lambda *a:tmp_path/'snapshot.cdxml'
    text=caption_parent();state={'text':text}
    monkeypatch.setattr(addin,'read_preserving_active',lambda *a:{'cdxml':state['text']})
    before=_document_content(b,42)
    root=ET.fromstring(text);root.find('page').set('id','99999')
    state['text']=ET.tostring(root,encoding='unicode')
    assert _document_content(b,42)==before
    root.find('page/t/s').text='Changed caption'
    state['text']=ET.tostring(root,encoding='unicode')
    assert _document_content(b,42)!=before


def test_named_modified_original_is_read_without_native_save(monkeypatch,tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.batch import _document_content
    from chemdraw_macos import addin
    b=object.__new__(Bridge)
    b.inspect=lambda did:{'document':{'file':'/private/source.cdxml','modified':True}}
    b._new_path=lambda *a:tmp_path/'snapshot.cdxml'
    b.export=lambda *a:pytest.fail('A modified original must not be native-saved during preservation')
    calls=[]
    monkeypatch.setattr(addin,'read_preserving_active',lambda b,did:calls.append(did) or {'cdxml':EMPTY})
    _document_content(b,42)
    assert calls==[42]
