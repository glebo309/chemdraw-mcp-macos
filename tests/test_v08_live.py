"""Native v0.8 interfaces; serial private documents only."""
import json
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')

@pytest.mark.asyncio
@pytest.mark.parametrize('operation',['style','reaction'])
async def test_native_custom_style_and_reaction_mcp(tmp_path,operation):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace')))
    preset={'BondLength':'18','LineWidth':'1.58','BoldWidth':'2','LabelSize':'14','CaptionSize':'12',
            'font':'Arial','CaptionFontName':'Arial','LabelFace':'96','CaptionFace':'0',
            'BondSpacing':'18','ChainAngle':'120','MarginWidth':'1.6','HashSpacing':'2.5'}
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                r=await session.call_tool(name,args)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents');final=None
            try:
                if operation=='style':
                    result=await call('chemdraw_draw_structures',structures=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],
                        output_dir=str(tmp_path/'style'),preset=preset)
                    cdxml=Path(result['output_dir'],'figure','figure.cdxml')
                else:
                    result=await call('chemdraw_build_reaction',
                        reactants=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],
                        products=[{'compound_id':'b','label':'Ethanal','smiles':'CC=O'}],
                        conditions_above='oxidation',conditions_below='layout test',
                        output_dir=str(tmp_path/'reaction'),preset=preset)
                    cdxml=Path(result['output_dir'],'figure.cdxml')
                final=result['document']['document_id']
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                root=ET.parse(cdxml).getroot()
                assert float(root.get('LineWidth'))==pytest.approx(1.58,abs=.001)
                for b in root.iter('b'):
                    assert float(b.get('LineWidth',root.get('LineWidth')))==pytest.approx(1.58,abs=.001)
                print('V08_REVIEW='+result['review'])
            finally:
                if final is not None:await call('chemdraw_close_working_document',document_id=final)
            assert await call('chemdraw_list_documents')==baseline
