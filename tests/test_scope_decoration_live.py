"""Native editable frame/divider roundtrip through the actual MCP endpoint."""
import json
import os
import sys
from pathlib import Path
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from test_scope_decoration import source,GROUPS
from chemdraw_macos.workflow import remap_ids

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')

@pytest.mark.asyncio
@pytest.mark.parametrize('labels',[False,True])
async def test_native_scope_decoration_mcp(tmp_path,labels):
    raw=source()
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
                report=await call('chemdraw_analyze_document',document_id=did)
                mapping=remap_ids(raw,Path(report['snapshot']).read_text())
                groups=[{'label':('Group '+str(i+1)) if labels else '',
                    'fragment_ids':[mapping[k] for k in g['fragment_ids']],
                    'caption_ids':[mapping[k] for k in g['caption_ids']]} for i,g in enumerate(GROUPS)]
                result=await call('chemdraw_decorate_scope',document_id=did,output_dir=str(tmp_path/'decorated'),
                    groups=groups,expected_source_token=report['source_token'])
                owned.append(result['document']['document_id'])
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                print('DECORATION_REVIEW='+result['review'])
            finally:
                for did in reversed(owned):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
