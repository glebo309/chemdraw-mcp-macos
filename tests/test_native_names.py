import asyncio
from contextlib import nullcontext
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos import cli, server
from chemdraw_macos.core import Bridge


def functions():
    from chemdraw_macos.native_names import caption_document, draw_name
    return caption_document, draw_name


@pytest.mark.parametrize('name', ['', '  ', 'x\ny', 'x\0y', 'a'*501, None])
def test_invalid_name_rejected(name):
    caption_document, _ = functions()
    with pytest.raises(ValueError):
        caption_document(name)


def test_caption_escapes_user_text_and_uses_native_style():
    caption_document, _ = functions()
    root = ET.fromstring(caption_document('A < B & "quoted"'))
    assert ''.join(root.find('page/t').itertext()) == 'A < B & "quoted"'
    assert not root.findall('.//fragment')
    assert root.get('LabelSize') == '14'
    assert root.get('BondLength') == '18'


def test_native_lookup_requires_optin_before_any_access(tmp_path):
    _, draw_name = functions()
    with pytest.raises(ValueError, match='allow_network'):
        draw_name(object(), 'caffeine', str(tmp_path/'out'))
    assert not (tmp_path/'out').exists()


def test_bridge_only_converts_owned_document(tmp_path, monkeypatch):
    b = Bridge(app_path=tmp_path, workspace=tmp_path/'work')
    calls = []
    monkeypatch.setattr(b, '_run', lambda *a: calls.append(a) or [12, 'copy', '/copy.cdxml', True, 1])
    with pytest.raises(ValueError, match='owned|session'):
        b.convert_name(12)
    assert not calls
    b.managed.add(12)
    assert b.convert_name(12)['document']['molecule_count'] == 1
    assert calls == [('convert_name', 12)]


class FakeBridge:
    lock = nullcontext()
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []
        self.created = False
    def documents(self):
        return {'documents': ([{'document_id': 12}] if self.created else [])}
    def create(self, source):
        self.calls.append('create'); self.created=True
        return {'document': {'document_id': 12}, 'working_copy': '/scratch.cdxml'}
    def convert_name(self, did):
        self.calls.append('convert')
        if self.fail == 'convert':
            raise RuntimeError('native timeout')
        return {'document': {'document_id': did, 'molecule_count': 1}}
    def export(self, did, path, fmt, **kw):
        self.calls.append(fmt)
        if fmt == 'cdxml':
            Path(path).write_text('<CDXML><page><fragment><n id="3" Element="6"/><n id="4" Element="8"/><b B="3" E="4"/></fragment></page></CDXML>')
        else:
            Path(path).write_bytes(b'fixture')
    def close(self, did):
        raise AssertionError('Do not automatically close after uncertain native operations')


def test_native_name_exports_and_reports_review_boundary(tmp_path):
    _, draw_name = functions()
    b=FakeBridge(); out=tmp_path/'out'
    result=draw_name(b,'methanol',str(out),allow_network=True)
    assert b.calls == ['create','convert','cdxml','svg','png']
    assert result['status'] == 'native_generated_review_required'
    assert result['audit']['chemical_identity_validation'] == 'not performed'
    assert result['audit']['rdkit_used'] is False
    assert result['audit']['native_lookup']['network_used'] == 'not observable'
    assert Path(result['review']).is_file()
    assert 'background:white' in Path(result['review']).read_text()
    assert json.loads((out/'request.json').read_text())['name'] == 'methanol'


def test_native_name_uncertainty_stops_without_retry_or_close(tmp_path):
    _, draw_name=functions()
    b=FakeBridge(fail='convert'); out=tmp_path/'out'
    with pytest.raises(RuntimeError, match='timeout'):
        draw_name(b,'methanol',str(out),allow_network=True)
    assert b.calls == ['create','convert']
    audit=json.loads((out/'audit.json').read_text())
    assert audit['status'] == 'uncertain'
    assert audit['owned_document_ids'] == [12]


def test_name_cli_and_mcp_use_the_same_workflow(tmp_path,monkeypatch):
    from chemdraw_macos import native_names
    calls=[]
    monkeypatch.setattr(native_names,'draw_name',lambda b,**kw: calls.append(kw) or {'status':'test'})
    monkeypatch.setattr(cli,'Bridge',object)
    assert cli.main(['draw-name','--name','alizarin','--output',str(tmp_path/'out'),'--allow-network']) == 0
    monkeypatch.setattr(server,'bridge',object)
    server.chemdraw_draw_name('alizarin',str(tmp_path/'out'),allow_network=True)
    assert calls[0] == calls[1]
    assert 'chemdraw_draw_name' in {t.name for t in asyncio.run(server.get_server('core').list_tools())}


def test_native_command_checks_front_document_and_caption_before_execution():
    script=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=script.split('else if operation is "convert_name" then',1)[1].split('else if operation',1)[0]
    assert branch.index('id of document 1') < branch.index('do command "selectAll"')
    assert branch.index('count of captions') < branch.index('do command "selectAll"')
    assert branch.index('enabled of command "convertNameToStructure"') < branch.index('do command "convertNameToStructure"')
    assert branch.count('do command "convertNameToStructure"') == 1
