import asyncio
import json
import pytest
from chemdraw_macos import cli, server
from chemdraw_macos.lab_style import make_package, save_package

STYLE={'BondLength':18,'LineWidth':1.58,'BoldWidth':2,'LabelSize':14,'CaptionSize':12,'font':'Arial'}

def test_v09_tools_exposed():
    names={t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {'chemdraw_plan_scope_job','chemdraw_build_scope_job','chemdraw_build_reaction_series',
            'chemdraw_build_ownership','chemdraw_move_owned','chemdraw_suggest_routes',
            'chemdraw_apply_route','chemdraw_create_lab_style','chemdraw_inspect_lab_style',
            'chemdraw_run_styled_job'} <= names

def test_lab_style_cli_offline(tmp_path,monkeypatch,capsys):
    from test_style_import import binary_style
    monkeypatch.setattr(cli,'Bridge',lambda:pytest.fail('Unexpected native access'))
    style=tmp_path/'style.cds';style.write_bytes(binary_style())
    output=tmp_path/'lab.json'
    assert cli.main(['make-lab-style','--name','test-lab','--version','1.0.0','--style',str(style),'--output',str(output)])==0
    assert output.exists()
    assert cli.main(['inspect-lab-style','--input',str(output)])==0

def test_scope_plan_cli_does_not_connect(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(cli,'Bridge',lambda:pytest.fail('Unexpected native access'))
    monkeypatch.setattr(cli,'plan_scope_job',lambda job:{'selection_required':True},raising=False)
    manifest=tmp_path/'job.json';manifest.write_text('{}')
    assert cli.main(['scope-job','--manifest',str(manifest),'--plan-only'])==0
    assert json.loads(capsys.readouterr().out)['selection_required']

@pytest.mark.parametrize('command,function,manifest',[
    ('scope-job','build_scope_job',{'accept_all':True}),
    ('reaction-series','build_reaction_series',{'schema_version':1,'steps':[]}),
])
def test_new_native_cli_dispatch(command,function,manifest,tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr(cli,function,lambda *a,**kw:calls.append((a,kw)) or {'ok':True},raising=False)
    path=tmp_path/'job.json';path.write_text(json.dumps(manifest))
    assert cli.main([command,'--manifest',str(path),'--output',str(tmp_path/'out')])==0
    assert len(calls)==1

def test_styled_cli_dispatch(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr(cli,'run_styled_job',lambda *a,**kw:calls.append((a,kw)) or {'ok':True},raising=False)
    style=tmp_path/'style.json';save_package(make_package('lab','1.0.0',STYLE),style)
    recipe=tmp_path/'recipe.json';recipe.write_text('{"structures":[]}')
    assert cli.main(['styled-job','--lab-style',str(style),'--workflow','draw','--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert len(calls)==1

def test_move_cli_dispatch(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr(cli,'move_file',lambda *a,**kw:calls.append((a,kw)) or {'ok':True},raising=False)
    recipe=tmp_path/'recipe.json';recipe.write_text('{"ownership":{},"moves":[]}')
    assert cli.main(['move-owned','--input',str(tmp_path/'figure.cdxml'),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert len(calls)==1

def test_ownership_mcp_uses_annotation_capable_snapshot(tmp_path,monkeypatch):
    from test_annotations import SOURCE
    source=tmp_path/'source.cdxml';source.write_text(SOURCE)
    monkeypatch.setattr(server,'bridge',lambda:object())
    monkeypatch.setattr(server,'analyze_document',lambda *a:pytest.fail('Plain analyzer rejects supported native symbols'))
    monkeypatch.setattr(server,'inspect_annotations_document',lambda *a:{'snapshot':str(source)})
    owners=[{'key':key,'fragment_ids':[fid],'caption_ids':[tid]} for key,fid,tid in
        [('a','1001','970'),('b','2002','971'),('c','3003','972'),('d','4004','973')]]
    result=server.chemdraw_build_ownership(1,owners)
    assert result['owners']==owners
