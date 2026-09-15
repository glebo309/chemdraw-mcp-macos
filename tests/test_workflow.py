import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.workflow import polish_document, remap_ids
from chemdraw_macos.cli import main
from test_polish import SAMPLE


class FakeBridge:
    def __init__(self,workspace):
        self.workspace=workspace;self.docs={1:SAMPLE};self.managed=set();self.counter=1
        self.events=[]
    def inspect(self,did):
        return {'document':{'document_id':did,'name':'original','modified':False}}
    def _new_path(self,suffix,category='scratch'):
        self.counter+=1;p=self.workspace/category/f'{self.counter}{suffix}';p.parent.mkdir(parents=True,exist_ok=True);return p
    def export(self,did,path,format,pixels=3200):
        self.events.append(('export',did,format))
        Path(path).write_text(self.docs[did] if format=='cdxml' else '<svg/>' if format=='svg' else 'image')
        return {'path':str(path)}
    def create(self,cdxml):
        self.counter+=1;self.docs[self.counter]=cdxml;self.managed.add(self.counter)
        self.events.append(('create',self.counter))
        return {'document':{'document_id':self.counter}}
    def close(self,did):
        assert did in self.managed;self.events.append(('close',did));self.managed.remove(did)


def test_polish_outputs_review_and_audit_without_editing_original(tmp_path):
    b=FakeBridge(tmp_path/'work')
    result=polish_document(b,1,str(tmp_path/'deliverable'),layout='row',caption_map={'1':'10','20':'30'})
    assert b.docs[1]==SAMPLE
    assert result['audit']['checks']['source_document_unchanged']
    assert result['audit']['checks']['native_roundtrip_chemistry_preserved']
    assert result['audit']['visual_review']=='required'
    for name in ('before.cdxml','before.svg','before.png','figure.cdxml','figure.svg','figure.png','review.html','audit.json','recipe.json'):
        assert (tmp_path/'deliverable'/name).is_file()
    assert result['document']['document_id'] in b.managed
    assert len(b.managed)==1


def test_existing_output_directory_is_rejected_before_native_calls(tmp_path):
    b=FakeBridge(tmp_path/'work')
    with pytest.raises(FileExistsError):polish_document(b,1,str(tmp_path))
    assert b.events==[]


def test_native_chemistry_change_fails_without_a_success_result(tmp_path):
    b=FakeBridge(tmp_path/'work');original=b.create
    def corrupt(cdxml):return original(cdxml.replace('Element="8"','Element="7"'))
    b.create=corrupt
    with pytest.raises(ValueError,match='chemistry'):
        polish_document(b,1,str(tmp_path/'out'))
    assert b.docs[1]==SAMPLE
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='failed'


def test_object_ids_can_change_on_native_import():
    r=ET.fromstring(SAMPLE)
    for e in r.find('page').iter():
        for k in ('id','B','E'):
            if e.get(k):e.set(k,str(int(e.get(k))+1000))
    mapping=remap_ids(SAMPLE,ET.tostring(r,encoding='unicode'))
    assert mapping['1']=='1001' and mapping['10']=='1010'


def test_native_id_mapping_tolerates_rounding_across_decimal_boundaries():
    before=SAMPLE.replace('30 45','30.049 45')
    after=SAMPLE.replace('30 45','30.05 45')
    assert remap_ids(before,after)['1']=='1'


def test_cli_has_doctor_and_usable_polish_command(capsys):
    with pytest.raises(SystemExit) as exc:main(['polish','--help'])
    assert exc.value.code==0
    assert '--input' in capsys.readouterr().out


def test_cli_doctor_returns_json_even_without_chemdraw(monkeypatch,capsys):
    monkeypatch.setattr('chemdraw_macos.cli.doctor',lambda **kw:{'status':'unavailable'})
    assert main(['doctor'])==1
    assert json.loads(capsys.readouterr().out)['status']=='unavailable'


def test_mcp_exposes_workflow_and_diagnostic_tools():
    import asyncio
    from chemdraw_macos.server import mcp
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert {'chemdraw_polish_document','chemdraw_analyze_document','chemdraw_doctor'} <= names


def test_cli_input_recipe_uses_original_file_ids_after_native_renumbering(tmp_path,monkeypatch,capsys):
    source=tmp_path/'source.cdxml';source.write_text(SAMPLE)
    recipe=tmp_path/'recipe.json';recipe.write_text(json.dumps({'layout':'row','caption_map':{'1':'10','20':'30'}}))
    b=FakeBridge(tmp_path/'work')
    def imported(path):
        r=ET.fromstring(Path(path).read_text())
        for e in r.find('page').iter():
            for k in ('id','B','E'):
                if e.get(k):e.set(k,str(int(e.get(k))+1000))
        return b.create(ET.tostring(r,encoding='unicode'))
    b.import_file=imported
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:b)
    assert main(['polish','--input',str(source),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert json.loads(capsys.readouterr().out)['audit']['checks']['native_roundtrip_chemistry_preserved']


def test_cli_validates_cdxml_before_native_import_can_drop_unsupported_features(tmp_path,monkeypatch):
    source=tmp_path/'query.cdxml';source.write_text(SAMPLE.replace('id="2"','id="2" RingBondCount="2"'))
    b=FakeBridge(tmp_path/'work');calls=[]
    def imported(path):
        calls.append(path)
        return b.create(SAMPLE)
    b.import_file=imported
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:b)
    assert main(['polish','--input',str(source),'--output',str(tmp_path/'out')])==1
    assert calls==[]
