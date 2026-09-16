import asyncio
import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from chemdraw_macos import cli, server
from chemdraw_macos.core import Bridge


XML = '<CDXML><page id="1"><fragment id="2"><n id="3" p="10 20" Element="7"/></fragment></page></CDXML>'

def test_native_selection_is_read_directly_not_coerced_to_a_value():
    script=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=script.split('operation is "live_state" then',1)[1].split('else if',1)[0]
    assert 'count of atoms of selection of targetDoc' in branch
    assert 'bounds of selection of targetDoc' in branch
    assert 'set selectedObjects to selection' not in branch


class Fake:
    lock = nullcontext()
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.xml = XML
        self.calls = []
        self.index = 0
    _id = staticmethod(Bridge._id)
    def _new_path(self, suffix, category='scratch'):
        self.index += 1
        return self.tmp_path / (str(self.index) + suffix)
    def _run(self, operation, *args):
        self.calls.append((operation, *args))
        row = [12, 'drawing', '/drawing.cdxml', True, 1]
        if operation == 'live_state':
            return [row, True, [0, 0, 30, 30], [1, 0, 1, 0]]
        if operation == 'native_action':
            self.xml = self.xml.replace('10 20', '30 40')
            return [row, True]
        raise AssertionError(operation)
    def export(self, did, path, fmt):
        self.calls.append(('export', did, fmt))
        Path(path).write_text(self.xml)


def test_live_read_is_bound_to_document_and_reads_changed_content(tmp_path):
    from chemdraw_macos.live import read_live_document
    b = Fake(tmp_path)
    first = read_live_document(b, 12)
    assert first['document']['document_id'] == 12
    assert first['objects'][0]['id'] == '2'
    assert first['objects'][1]['attributes']['Element'] == '7'
    assert read_live_document(b, 12)['source_token'] == first['source_token']
    b.xml = b.xml.replace('10 20', '10 21')
    assert read_live_document(b, 12)['source_token'] != first['source_token']
    assert not any(c[0] in ('open', 'create', 'close') for c in b.calls)


def test_untitled_live_read_uses_no_save_snapshot(tmp_path, monkeypatch):
    from chemdraw_macos import shared
    from chemdraw_macos.live import read_live_document
    b=Fake(tmp_path); original=b._run
    def state(op,*args):
        result=original(op,*args)
        if op=='live_state':result[0][2]=''
        return result
    b._run=state
    monkeypatch.setattr(shared,'clipboard',lambda bridge,did:{'cdxml':b.xml,'clipboard_restored':True})
    first=read_live_document(b,12)
    assert first['document']['file']==''
    assert first['snapshot_method']=='clipboard'
    assert first['objects'][1]['attributes']['Element']=='7'
    assert not any(c[0]=='export' for c in b.calls)
    b.xml=b.xml.replace('page id="1"','page id="987"').replace('<CDXML>','<CDXML MacPrintInfo="updated">')
    assert read_live_document(b,12)['source_token']==first['source_token']
    b.xml=b.xml.replace('10 20','10 21')
    assert read_live_document(b,12)['source_token']!=first['source_token']


def test_untitled_analysis_uses_no_save_snapshot(tmp_path,monkeypatch):
    from chemdraw_macos import shared
    from chemdraw_macos.workflow import analyze_document
    b=Fake(tmp_path)
    b.inspect=lambda did:{'document':{'document_id':did,'file':''}}
    monkeypatch.setattr(shared,'clipboard',lambda bridge,did:{'cdxml':b.xml})
    result=analyze_document(b,12)
    assert result['document']['file']==''
    assert Path(result['snapshot']).read_text()==XML
    assert not any(c[0]=='export' for c in b.calls)


def test_live_action_edits_existing_unowned_document_without_import(tmp_path):
    from chemdraw_macos.live import read_live_document, live_action
    b = Fake(tmp_path)
    token = read_live_document(b, 12)['source_token']
    result = live_action(b, 12, 'align_left', token, 'all')
    assert result['document']['document_id'] == 12
    assert result['current']['source_token'] != token
    assert Path(result['backup']).is_file()
    assert b.calls.count(('native_action', 12, 'alignLeftEdges', 'all')) == 1


def test_live_stale_snapshot_never_dispatches_action(tmp_path):
    from chemdraw_macos.live import read_live_document, live_action
    b = Fake(tmp_path)
    token = read_live_document(b, 12)['source_token']
    b.xml = b.xml.replace('10 20', '40 50')
    with pytest.raises(ValueError, match='changed'):
        live_action(b, 12, 'align_left', token)
    assert not any(c[0] == 'native_action' for c in b.calls)


def test_live_invalid_action_never_contacts_native(tmp_path):
    from chemdraw_macos.live import live_action
    b = Fake(tmp_path)
    with pytest.raises(ValueError):live_action(b, 12, 'paste', 'token')
    assert b.calls == []


def test_live_action_never_uses_selection_replaced_by_snapshot(tmp_path,monkeypatch):
    from chemdraw_macos import live
    b=Fake(tmp_path)
    monkeypatch.setattr(live,'read_live_document',lambda *a:{'source_token':'a'*64,'selection_changed':True})
    with pytest.raises(ValueError,match='Selection changed'):
        live.live_action(b,12,'align_left','a'*64,'current')
    assert not any(c[0]=='native_action' for c in b.calls)


def test_live_uncertain_write_is_not_retried_or_followed_by_cleanup(tmp_path):
    from chemdraw_macos.live import read_live_document, live_action
    b = Fake(tmp_path); token = read_live_document(b, 12)['source_token']
    original = b._run
    def fail(op, *args):
        if op == 'native_action':
            b.calls.append((op, *args)); raise RuntimeError('uncertain')
        return original(op, *args)
    b._run = fail
    with pytest.raises(RuntimeError, match='uncertain'):live_action(b, 12, 'align_left', token)
    assert b.calls[-1][0] == 'native_action'
    assert sum(c[0] == 'native_action' for c in b.calls) == 1


def test_visibility_validates_and_uses_explicit_id(tmp_path, monkeypatch):
    b = Bridge(app_path=tmp_path, workspace=tmp_path)
    calls = []
    monkeypatch.setattr(b, '_run', lambda *a: calls.append(a) or [[12,'drawing','/drawing',False,1],False])
    result = b.set_visibility(12, False)
    assert calls == [('visibility', 12, 'false')]
    assert result['visible'] is False
    with pytest.raises(ValueError):b.set_visibility(12, 'false')
    assert len(calls) == 1


def test_background_create_validates_before_writing(tmp_path):
    b = Bridge(app_path=tmp_path, workspace=tmp_path/'work')
    with pytest.raises(ValueError):b.create(XML, visible='false')
    assert not (tmp_path/'work').exists()


def test_live_interfaces_are_callable_from_cli_and_both_mcp_profiles(tmp_path, monkeypatch, capsys):
    from chemdraw_macos import live
    calls=[]
    monkeypatch.setattr(live, 'read_live_document', lambda b,d: calls.append(d) or {'document_id':d})
    monkeypatch.setattr(cli, 'Bridge', lambda: object())
    monkeypatch.setattr(server, 'bridge', lambda: object())
    assert cli.main(['live-read', '12']) == 0
    assert json.loads(capsys.readouterr().out)['document_id'] == 12
    assert server.chemdraw_read_live_document(12)['document_id'] == 12
    assert calls == [12,12]
    for profile in ('core','full'):
        names={t.name for t in asyncio.run(server.get_server(profile).list_tools())}
        assert {'chemdraw_read_live_document','chemdraw_live_action','chemdraw_set_visibility','chemdraw_render_cdxml'} <= names


def test_background_renderer_only_closes_after_success(tmp_path):
    from chemdraw_macos.live import render_cdxml
    class Render(Fake):
        def create(self, text, visible=True):
            self.calls.append(('create', visible)); return {'document': {'document_id':12}}
        def close(self, did):self.calls.append(('close', did));return {}
        def set_visibility(self, did, visible):
            self.calls.append(('visibility',did,visible));return {'visible':visible}
    b=Render(tmp_path)
    result=render_cdxml(b,XML,str(tmp_path/'output'),background=True)
    assert ('create', False) in b.calls
    assert b.calls[-1] == ('close',12)
    assert result['document_closed'] is True
    assert result['chemical_preservation_verified'] is False
    assert not (tmp_path/'output/review.html').exists()
    b=Render(tmp_path)
    def fail(*args,**kw):raise RuntimeError('uncertain')
    b.export=fail
    with pytest.raises(RuntimeError):render_cdxml(b,XML,str(tmp_path/'failed'),background=True)
    assert not any(c[0]=='close' for c in b.calls)
