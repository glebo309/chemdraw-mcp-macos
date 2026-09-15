import asyncio
import json
import pytest
from chemdraw_macos import cli, server


def test_identifier_and_scope_commands_do_not_construct_native_bridge(monkeypatch,capsys):
    def forbidden():raise AssertionError('Offline commands must not discover ChemDraw')
    monkeypatch.setattr(cli,'Bridge',forbidden)
    assert cli.main(['identify','--value','CCO'])==0
    assert json.loads(capsys.readouterr().out)['canonical_smiles']=='CCO'
    assert cli.main(['propose-scope','--parent','CC(=O)[c:1]1ccccc1','--handle-map','1'])==0
    proposal=json.loads(capsys.readouterr().out)
    assert len(proposal['candidates'])==14
    assert all(c['yield_percent'] is None for c in proposal['candidates'])


def test_mcp_new_workflows_callable_without_native(monkeypatch):
    def forbidden():raise AssertionError('Offline tools must not discover ChemDraw')
    monkeypatch.setattr(server,'bridge',forbidden)
    assert {'chemdraw_identify','chemdraw_propose_scope','chemdraw_draw_structures'} <= {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert server.chemdraw_identify('CCO')['canonical_smiles']=='CCO'
    assert len(server.chemdraw_propose_scope('CC(=O)[c:1]1ccccc1',1)['candidates'])==14


def test_draw_cli_dispatches_explicit_manifest(tmp_path,monkeypatch,capsys):
    manifest=tmp_path/'request.json'
    structures=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}]
    manifest.write_text(json.dumps({'schema_version':1,'structures':structures}))
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr(cli,'draw_structures',lambda b,**kw: calls.append(kw) or {'status':'test'})
    assert cli.main(['draw','--manifest',str(manifest),'--output',str(tmp_path/'out')])==0
    assert calls[0]['structures']==structures


def test_draw_accepts_explicit_scaffold_manifest(tmp_path,monkeypatch):
    path=tmp_path/'input.json'
    path.write_text(json.dumps({'structures':[{'compound_id':'a','label':'Parent','smiles':'CC(=O)c1ccccc1'}],
                               'scaffold_smiles':'CC(=O)c1ccccc1'}))
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr(cli,'draw_structures',lambda b,**kw: calls.append(kw) or {'status':'test'})
    assert cli.main(['draw','--manifest',str(path),'--output',str(tmp_path/'out')])==0
    assert calls[0]['scaffold_smiles']=='CC(=O)c1ccccc1'
