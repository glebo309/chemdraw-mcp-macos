"""Native batch exports through the actual MCP transport, on owned copies only."""
import json
import os
from pathlib import Path
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


@pytest.mark.asyncio
async def test_native_batch_with_rejection_and_all_export_formats(tmp_path):
    root=Path(__file__).parents[1]
    paths=[root/'examples/chlorobenzoic-acid.cdxml',root/'examples/messy-oxidation.cdxml']
    original=[p.read_bytes() for p in paths]
    items=[{'key':f'Figure-{i+1}','source':str(p),'formats':['pdf','cdx']} for i,p in enumerate(paths)]
    items.insert(1,{'key':'unsupported','source':str(tmp_path/'missing.cdxml')})
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'work')))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**kwargs):
                response=await session.call_tool(name,kwargs)
                assert not response.isError,response
                return response.structuredContent or json.loads(response.content[0].text)
            baseline=await call('chemdraw_list_documents')
            result=await call('chemdraw_batch_export',items=items,output_dir=str(tmp_path/'batch'),pixels=1200)
            assert result['status']=='partial_failure',result
            assert [r['status'] for r in result['items']]==['exported','rejected','exported'],result
            assert result['checks']['preexisting_documents_unchanged']
            for row in (result['items'][0],result['items'][2]):
                assert all(row['checks'].values())
                assert row['closed_working_document']
                for fmt in ('cdxml','svg','png','pdf','cdx'):
                    assert (tmp_path/'batch'/row['key']/f'{row["key"]}.{fmt}').stat().st_size>0
            assert await call('chemdraw_list_documents')==baseline
            assert [p.read_bytes() for p in paths]==original
            print('BATCH_REVIEW='+result['review'])
