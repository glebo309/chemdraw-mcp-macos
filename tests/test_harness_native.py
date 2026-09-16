"""Front-door acceptance, deliberately using chemically different inputs."""
import json
import os
from pathlib import Path
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from chemdraw_macos.core import Bridge

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed native ChemDraw')

CASES=[
    {'molecules':[
        {'value':'C[C@H](O)C(=O)O','format':'smiles','label':'Tetrahedral stereo'},
        {'value':'[13CH3]CO','format':'smiles','label':'Isotope'},
        {'value':'C/C=C/C','format':'smiles','label':'Alkene stereo'},
        {'value':'c1ccc2[nH]ccc2c1','format':'smiles','label':'Fused heterocycle'},
        {'value':'O=[N+]([O-])c1ccccc1','format':'smiles','label':'Formal charges'},
    ]},
    {'molecules':[{'value':s,'format':'smiles','label':label} for s,label in [
        ('CC(=O)c1ccccc1','Parent'),('CC(=O)c1ccc(C)cc1','Alkyl'),
        ('CC(=O)c1ccc(C#N)cc1','Nitrile'),('CC(=O)c1ccc(F)cc1','Halogen')]]},
    {'molecules':[{'value':'CCO','format':'smiles','label':'Reactant'}],
     'products':[{'value':'CC=O','format':'smiles','label':'Product'}], 'conditions_above':'[O]'},
]


@pytest.mark.asyncio
@pytest.mark.parametrize('payload',CASES,ids=['diverse-chemistry','automatic-panel','explicit-reaction'])
async def test_guarded_drawing_profile_end_to_end(tmp_path,payload):
    owner=Bridge();baseline=owner.documents()
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','drawing'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=await session.call_tool('chemdraw_draw',{'request':payload,'output_dir':str(tmp_path/'job'),'presentation':'background'})
            assert not result.isError,result
            data=result.structuredContent or json.loads(result.content[0].text)
            assert data['status']=='completed',data
            assert data['document_closed'] is True
            assert data['presentation']['mode']=='background'
            assert len(data['gates'])==5
            for fmt in ('cdxml','svg','png'):assert Path(data['artifacts'][fmt]).stat().st_size>100
            assert json.loads((tmp_path/'job/result.json').read_text())['document_closed'] is True
            assert owner.documents()==baseline
            print('HARNESS_ACCEPTANCE='+json.dumps({'case':payload['molecules'][0]['label'],'artifacts':data['artifacts']}))


@pytest.mark.asyncio
async def test_untitled_preflight_over_actual_mcp_is_read_only(tmp_path):
    owner=Bridge();baseline=owner.documents()
    if not any(not d['file'] for d in baseline['documents']):
        pytest.skip('This guard test requires a pre-existing untitled document; never create one in the user session')
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','drawing'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            # Test the separate-output save guard, never auto/shared against a
            # pre-existing human document: auto is now an in-place operation.
            result=await session.call_tool('chemdraw_draw',{'request':CASES[0],'output_dir':str(tmp_path/'job'),'presentation':'background'})
            assert not result.isError,result
            data=result.structuredContent or json.loads(result.content[0].text)
            assert data['status']=='needs_input' and data['code']=='unsaved_user_document'
            assert not (tmp_path/'job').exists()
            assert owner.documents()==baseline
