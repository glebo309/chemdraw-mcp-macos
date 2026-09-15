"""Native input-to-editable-drawing tests, using only owned private copies."""
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


@pytest.mark.asyncio
@pytest.mark.parametrize('aligned',[False,True])
async def test_native_smiles_creation_through_mcp(tmp_path,aligned):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
                                env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace')))
    records=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'},
             {'compound_id':'b','label':'Stereo/isotope test','smiles':'[13CH3][C@H](O)C(=O)O'},
             {'compound_id':'c','label':'Nitrobenzene','smiles':'O=[N+]([O-])c1ccccc1'}]
    options={}
    if aligned:
        records=[{'compound_id':'a','label':'Parent','smiles':'CC(=O)c1ccccc1'},
                 {'compound_id':'b','label':'2-Me','smiles':'CC(=O)c1ccccc1C'}]
        options={'scaffold_smiles':'CC(=O)c1ccccc1'}
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                r=await session.call_tool(name,args)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents')
            final=None
            try:
                result=await call('chemdraw_draw_structures',structures=records,output_dir=str(tmp_path/'draw'),columns=len(records),**options)
                final=result['document']['document_id']
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                assert [r['compound_id'] for r in result['audit']['structures']]==[r['compound_id'] for r in records]
                if aligned:
                    assert all(result['audit']['alignment']['checks'].values())
                    assert abs(result['audit']['alignment']['structures'][1]['rotation_degrees']-30)<.01
                assert Path(result['output_dir'],'figure','figure.svg').stat().st_size>100
                print('DRAW_REVIEW='+result['review'])
            finally:
                if final is not None:await call('chemdraw_close_working_document',document_id=final)
            assert await call('chemdraw_list_documents')==baseline


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['plain','circled'])
async def test_native_ionic_drawing_preserves_charge_owners(tmp_path,mode):
    import xml.etree.ElementTree as ET
    from chemdraw_macos.annotations import _core
    from chemdraw_macos.polish import chemical_signature
    from chemdraw_macos.draw import prepare_structures
    example='ions-circled.json' if mode=='circled' else 'molecules-circled.json'
    manifest=json.loads((Path(__file__).parents[1]/'examples'/example).read_text())
    records=manifest['structures']
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
                                env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace')))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                r=await session.call_tool(name,args)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents');final=None
            try:
                result=await call('chemdraw_draw_structures',structures=records,output_dir=str(tmp_path/'ions'),
                                  columns=2,charge_style=mode)
                final=result['document']['document_id']
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                text=Path(result['artifacts']['cdxml']).read_text();root=ET.fromstring(text)
                assert chemical_signature(_core(text))==sorted(r['canonical_smiles'] for r in prepare_structures(records))
                gs=root.findall('page/fragment/graphic')
                assert len(gs)==(3 if mode=='circled' else 0)
                if mode=='circled':
                    assert len({g.get('LineWidth') for g in gs})==1
                    for f in root.findall('page/fragment'):
                        for g in f.findall('graphic'):
                            owner=f.find(f'n[@id="{g[0].get("object")}"]')
                            assert owner is not None and int(owner.get('Charge'))==({'CirclePlus':1,'CircleMinus':-1}[g.get('SymbolType')])
                assert Path(result['artifacts']['png']).is_file()
                print('ION_REVIEW='+result['review'])
            finally:
                if final is not None:await call('chemdraw_close_working_document',document_id=final)
            assert await call('chemdraw_list_documents')==baseline
