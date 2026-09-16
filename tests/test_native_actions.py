import asyncio
from pathlib import Path

import pytest

from chemdraw_macos import cli, server
from chemdraw_macos.core import Bridge


ACTIONS = {
    'clean_structure':'cleanStructure', 'clean_reaction':'cleanReaction',
    'align_left':'alignLeftEdges', 'align_right':'alignRightEdges',
    'align_top':'alignTopEdges', 'align_bottom':'alignBottomEdges',
    'align_horizontal_centers':'alignLeftRightCenters',
    'align_vertical_centers':'alignTopBottomCenters',
    'distribute_horizontal':'distributeObjectsHorizontally',
    'distribute_vertical':'distributeObjectsVertically',
    'expand_labels':'expandLabel', 'contract_labels':'contractLabel',
}


@pytest.mark.parametrize('action,command', ACTIONS.items())
def test_native_action_dispatches_one_command_after_backup(tmp_path,monkeypatch,action,command):
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'work'); b.managed.add(12)
    calls=[]
    monkeypatch.setattr(b,'export',lambda *a,**kw:calls.append(('backup',a)))
    monkeypatch.setattr(b,'_run',lambda *a: calls.append(a) or [[12,'copy','/copy',False,3],True])
    result=b.native_action(12,action,selection='all')
    assert calls[0][0]=='backup'
    assert calls[1]==('native_action',12,command,'all')
    assert len(calls)==2
    assert result['native_command']==command
    assert result['status']=='native_action_applied_review_required'
    assert result['chemical_preservation_verified'] is False


@pytest.mark.parametrize('action,selection,owned', [('quit','all',True),('align_left','guess',True),('align_left','all',False)])
def test_native_action_rejects_before_backup(tmp_path,monkeypatch,action,selection,owned):
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'work')
    if owned:b.managed.add(12)
    monkeypatch.setattr(b,'export',lambda *a:pytest.fail('Must fail before backup'))
    with pytest.raises(ValueError):b.native_action(12,action,selection)


def test_disabled_native_command_is_not_reported_as_applied(tmp_path,monkeypatch):
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'work'); b.managed.add(12)
    monkeypatch.setattr(b,'export',lambda *a:None)
    monkeypatch.setattr(b,'_run',lambda *a:[[12,'copy','/copy',False,1],False])
    assert b.native_action(12,'align_left')['status']=='unavailable_for_selection'


def test_native_action_is_exposed_to_both_profiles_and_cli(tmp_path,monkeypatch):
    calls=[]
    class Native:
        lock=None
        def import_file(self,path):
            calls.append(('import',path));return {'document':{'document_id':12}}
        def native_action(self,*a,**kw):
            calls.append((a,kw));return {'status':'test'}
    monkeypatch.setattr(cli,'Bridge',Native)
    monkeypatch.setattr(server,'bridge',Native)
    server.chemdraw_native_action(12,'align_left',selection='all')
    assert cli.main(['native-action','--input',str(tmp_path/'input.cdxml'),'--action','align_left'])==0
    assert calls[0]==calls[-1]
    for profile in ('core','full'):
        tools={t.name:t for t in asyncio.run(server.get_server(profile).list_tools())}
        schema=tools['chemdraw_native_action'].inputSchema
        assert set(schema['properties']['action']['enum'])==set(ACTIONS)
        assert tools['chemdraw_native_action'].annotations.destructiveHint


def test_native_action_script_checks_front_and_allowlist():
    script=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=script.split('else if operation is "native_action" then',1)[1].split('else if operation',1)[0]
    assert branch.index('id of document 1') < branch.index('do command')
    assert 'supportedCommands' in branch and 'not in supportedCommands' in branch
    assert 'enabled of command nativeCommand' in branch
