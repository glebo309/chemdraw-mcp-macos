import copy
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from test_annotations import SOURCE,ARROWS,HEAD_RENDER_ARROWS

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires running licensed ChemDraw')


@pytest.mark.asyncio
@pytest.mark.parametrize('head',['Full','HalfLeft','HalfRight'])
async def test_native_curved_arrow_heads_through_mcp(tmp_path,head):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'work')))
    created=[]
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                result=await session.call_tool(name,args)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents')
            try:
                source=await call('chemdraw_create_document',cdxml=SOURCE)
                did=source['document']['document_id'];created.append(did)
                report=await call('chemdraw_inspect_annotations',document_id=did)
                from chemdraw_macos.annotations import verify_annotations
                mapping=verify_annotations(SOURCE,Path(report['snapshot']).read_text())['id_map']
                arrows=copy.deepcopy(ARROWS if head=='Full' else HEAD_RENDER_ARROWS)
                for arrow in arrows:
                    for side in ('source','target'):arrow[side]['id']=mapping[arrow[side]['id']]
                    if head!='Full':arrow.update(electrons=1,fishhook_side='left' if head=='HalfLeft' else 'right')
                # Half-head variants are rendering regressions, not alternative SN2 mechanisms.
                result=await call('chemdraw_annotate_document',document_id=did,output_dir=str(tmp_path/'annotation'),
                                  arrows=arrows,expected_source_token=report['source_token'],pixels=1800)
                created.append(result['document']['document_id'])
                assert all(result['audit']['checks'].values())
                root=ET.parse(tmp_path/'annotation'/'figure.cdxml')
                curves=root.findall('page/curve')
                assert len(curves)==2 and all(c.get('ArrowheadHead')==head for c in curves)
                assert all(c.get('CurveType')==('8' if head=='Full' else '32') for c in curves)
                assert len(root.findall('.//graphic[@SymbolType="CircleMinus"]'))==2
                print('ANNOTATION_REVIEW='+result['review'])
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
