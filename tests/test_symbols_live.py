"""Native symbol and electron-source endpoints, never editing originals."""
import copy
import json
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from test_annotations import SOURCE
from chemdraw_macos.annotations import verify_annotations

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['charge','positive_charge','lone_pair','electron','charge_arrow'])
async def test_native_symbol_creation_and_sources_mcp(tmp_path,kind):
    raw=SOURCE
    if kind in ('charge','positive_charge'):
        root=ET.fromstring(raw)
        for f in root.findall('page/fragment'):
            for g in f.findall('graphic'):f.remove(g)
            for n in f.findall('n'):
                if n.get('Charge')=='-1':
                    if kind=='positive_charge':
                        n.set('Element','7');n.set('Charge','1');n.set('NumHydrogens','4')
                        n.find('t/s').text='NH4+'
                    else:n.find('t/s').text+='-'
        raw=ET.tostring(root,encoding='unicode')
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'work')))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**kw):
                result=await session.call_tool(name,kw)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents');owned=[]
            try:
                created=await call('chemdraw_create_document',cdxml=raw)
                did=created['document']['document_id'];owned.append(did)
                report=await call('chemdraw_inspect_symbols',document_id=did)
                native=Path(report['snapshot']).read_text()
                mapping=verify_annotations(raw,native)['id_map']
                if kind!='charge_arrow':
                    requests=[{'key':'br','kind':'charge' if kind=='positive_charge' else kind,'atom_id':mapping['1100']}]
                    if kind=='charge':requests.append({'key':'i','kind':'charge','atom_id':mapping['4114']})
                    result=await call('chemdraw_add_symbols',document_id=did,output_dir=str(tmp_path/'symbols'),
                        symbols=requests,expected_source_token=report['source_token'])
                    owned.append(result['document']['document_id']);did=owned[-1]
                    assert result['audit']['status']=='checks_passed'
                    assert all(result['audit']['checks'].values())
                    # Capture fresh ownership after symbol creation and native renumbering.
                    report=await call('chemdraw_inspect_symbols',document_id=did)
                    native=Path(report['snapshot']).read_text()
                    from chemdraw_macos.symbols import _split
                    mapping=verify_annotations(_split(raw)[1],_split(native)[1])['id_map'] if kind not in ('charge','positive_charge') else None
                    print('SYMBOL_REVIEW='+result['review'])
                if kind in ('charge','positive_charge'):continue_arrow=False
                else:continue_arrow=True
                if continue_arrow:
                    typ={'charge_arrow':'CircleMinus','lone_pair':'LonePair','electron':'Electron'}[kind]
                    symbols=[s for s in report['symbols'] if s['kind']==typ]
                    symbol=symbols[0]
                    # The electron case is a rendering fixture, not an SN2 mechanism claim.
                    arrow={'key':'attack','electrons':1 if kind=='electron' else 2,
                        'source':{'kind':'symbol','id':symbol['id']},
                        'target':{'kind':'atom','id':mapping['2103'],'offset':[0,-14]},
                        'controls':[[0,-33],[0,-28]]}
                    result=await call('chemdraw_annotate_document',document_id=did,output_dir=str(tmp_path/'arrow'),
                        arrows=[arrow],expected_source_token=report['source_token'])
                    owned.append(result['document']['document_id'])
                    assert result['audit']['status']=='checks_passed'
                    assert all(result['audit']['checks'].values())
                    print('SYMBOL_ARROW_REVIEW='+result['review'])
            finally:
                for did in reversed(owned):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
