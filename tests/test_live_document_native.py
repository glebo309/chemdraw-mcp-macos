"""Native integration: same-document writes, external changes, hidden exports."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from chemdraw_macos.core import Bridge


pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed ChemDraw desktop')
SOURCE=Path(__file__).parents[1]/'examples/chlorobenzoic-acid.cdxml'


@pytest.mark.asyncio
async def test_existing_document_and_external_changes_through_mcp(tmp_path):
    owner=Bridge(); baseline=owner.documents()
    did=owner.create(SOURCE.read_text())['document']['document_id']
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','core'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(tool,**args):
                result=await session.call_tool(tool,args)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            first=await call('chemdraw_read_live_document',document_id=did)
            same=await call('chemdraw_read_live_document',document_id=did)
            assert same['source_token']==first['source_token']
            inventory=owner.documents()
            result=await call('chemdraw_live_action',document_id=did,action='clean_structure',
                              expected_source_token=first['source_token'],selection='all')
            assert result['document']['document_id']==did
            assert result['current']['document']['file']==first['document']['file']
            assert {d['document_id'] for d in owner.documents()['documents']}=={d['document_id'] for d in inventory['documents']}
            # A separate native client mutates this test document, standing in
            # for a human changing its style while the MCP server remains alive.
            script=f'''tell application "{owner.app}"
repeat with d in documents
if (id of d) as integer is {did} then
set line width of d to 45
end if
end repeat
end tell'''
            subprocess.run(['osascript','-'],input=script,text=True,capture_output=True,check=True,timeout=20)
            changed=await call('chemdraw_read_live_document',document_id=did)
            assert changed['source_token']!=result['current']['source_token']
            stale=await session.call_tool('chemdraw_live_action',dict(document_id=did,action='clean_structure',
                expected_source_token=result['current']['source_token'],selection='all'))
            assert stale.isError
            assert 'changed' in str(stale)
            hidden=await call('chemdraw_set_visibility',document_id=did,visible=False)
            assert hidden['visible'] is False
            await call('chemdraw_export',document_id=did,path=str(tmp_path/'hidden.svg'),format='svg')
            assert (await call('chemdraw_read_live_document',document_id=did))['visible'] is False
            await call('chemdraw_set_visibility',document_id=did,visible=True)
            denied=await session.call_tool('chemdraw_close_working_document',dict(document_id=did))
            assert denied.isError  # Live use does not promote user documents to owned copies.
    owner.close(did)
    assert owner.documents()==baseline


def test_background_renderer_actual_cli(tmp_path):
    b=Bridge();baseline=b.documents()
    run=subprocess.run([sys.executable,'-m','chemdraw_macos.cli','render','--input',str(SOURCE),
                        '--output',str(tmp_path/'render')],capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stderr+run.stdout
    result=json.loads(run.stdout)
    assert result['document_closed'] is True
    assert result['background'] is True
    for fmt in ('cdxml','svg','png','pdf'):
        assert Path(result['artifacts'][fmt]).stat().st_size>0
    assert not (tmp_path/'render/review.html').exists()
    assert b.documents()==baseline
