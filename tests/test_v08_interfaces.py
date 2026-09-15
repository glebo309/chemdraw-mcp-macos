import asyncio
import json
import pytest
from chemdraw_macos.cli import main

def test_import_style_cli_is_offline_and_can_save_report(tmp_path,monkeypatch,capsys):
    from test_style_import import binary_style
    src=tmp_path/'style.cds';src.write_bytes(binary_style());out=tmp_path/'style.json'
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:pytest.fail('Native bridge created'))
    assert main(['import-style','--input',str(src),'--output',str(out)])==0
    assert json.loads(capsys.readouterr().out)['preset']['LabelSize']=='14'
    assert json.loads(out.read_text())['preset']['font']=='Arial'
    assert main(['import-style','--input',str(src),'--output',str(out)])==1

def test_draw_accepts_template_path(tmp_path,monkeypatch,capsys):
    from test_style_import import binary_style
    src=tmp_path/'style.cds';src.write_bytes(binary_style())
    manifest=tmp_path/'in.json';manifest.write_text(json.dumps({'structures':[{'compound_id':'1','label':'Ethanol','smiles':'CCO'}]}))
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr('chemdraw_macos.cli.draw_structures',lambda *a,**kw:calls.append(kw) or {'ok':True})
    assert main(['draw','--manifest',str(manifest),'--style',str(src),'--output',str(tmp_path/'out')])==0
    assert calls[0]['preset']['CaptionSize']=='12'

def test_custom_style_is_exposed_over_mcp():
    from chemdraw_macos.server import mcp
    tools={t.name:t for t in asyncio.run(mcp.list_tools())}
    assert 'chemdraw_import_style' in tools
    schema=tools['chemdraw_draw_structures'].inputSchema['properties']['preset']
    assert any(x.get('type')=='object' for x in schema['anyOf'])

def test_new_workflow_interfaces(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:object())
    manifest=tmp_path/'scope.json';manifest.write_text(json.dumps({'parent_smiles':'n1[cH:2]c[cH:4]cc1','site_atom_maps':[2,4],'substituents':['Me','Cl']}))
    assert main(['scan-scope','--manifest',str(manifest)])==0
    assert len(json.loads(capsys.readouterr().out)['candidates'])==5
    assert main(['resolve','--query','caffeine'])==1
    assert 'allow_network=True' in json.loads(capsys.readouterr().err)['error']
    records=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}]
    manifest.write_text(json.dumps({'reactants':records,'products':[{'compound_id':'b','label':'Ethanal','smiles':'CC=O'}]}))
    calls=[]
    monkeypatch.setattr('chemdraw_macos.cli.build_reaction',lambda *a,**kw:calls.append(kw) or {'ok':True},raising=False)
    assert main(['reaction','--manifest',str(manifest),'--output',str(tmp_path/'out')])==0
    assert calls[0]['reactants']==records

def test_v08_tools_exposed():
    from chemdraw_macos.server import mcp
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert {'chemdraw_resolve','chemdraw_scan_scope','chemdraw_build_reaction'}<=names

def test_symbol_interfaces(tmp_path,monkeypatch,capsys):
    from chemdraw_macos.server import mcp
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert {'chemdraw_inspect_symbols','chemdraw_add_symbols'}<=names
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr('chemdraw_macos.cli.symbols_file',lambda *a,**kw:calls.append((a,kw)) or {'ok':True},raising=False)
    recipe=tmp_path/'symbols.json';recipe.write_text(json.dumps({'symbols':[{'key':'br','kind':'charge','atom_id':'1'}]}))
    assert main(['symbols','--input',str(tmp_path/'input.cdxml'),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert calls[0][1]['symbols'][0]['atom_id']=='1'

def test_scope_decoration_interfaces(tmp_path,monkeypatch,capsys):
    from chemdraw_macos.server import mcp
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert 'chemdraw_decorate_scope' in names
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:object())
    calls=[]
    monkeypatch.setattr('chemdraw_macos.cli.decorate_scope_file',lambda *a,**kw:calls.append((a,kw)) or {'ok':True},raising=False)
    recipe=tmp_path/'groups.json'
    groups=[{'label':'','fragment_ids':['1'],'caption_ids':['2','3']}]
    recipe.write_text(json.dumps({'groups':groups,'frame':True,'separators':False}))
    assert main(['decorate-scope','--input',str(tmp_path/'input.cdxml'),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert calls[0][1]=={'groups':groups,'frame':True,'separators':False}
