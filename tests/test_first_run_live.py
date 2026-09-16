"""Actual stdio MCP onboarding with native artifact and ownership checks."""
import json
import os
from pathlib import Path
import sys
import subprocess

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1',
                                reason='Requires licensed running ChemDraw')


@pytest.mark.asyncio
async def test_first_run_over_mcp_preserves_existing_documents(tmp_path):
    from chemdraw_macos.first_run import DEMO_STRUCTURES
    from chemdraw_macos.draw import prepare_structures
    from chemdraw_macos.polish import chemical_signature
    params = StdioServerParameters(command=sys.executable, args=['-m', 'chemdraw_macos.server'],
        env=dict(os.environ, CHEMDRAW_MCP_WORKSPACE=str(tmp_path / 'workspace')))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            async def call(name, **arguments):
                result = await session.call_tool(name, arguments)
                assert not result.isError, result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline = await call('chemdraw_list_documents')
            final = int(subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True))
            (tmp_path/'owned-document.json').write_text(json.dumps({'document_id':final}))
            succeeded = False
            try:
                diagnostic=await call('chemdraw_doctor')
                assert diagnostic['status']=='ready',diagnostic
                assert diagnostic['shared_drawing_ready'] is True
                result = await call('chemdraw_first_run', output_dir=str(tmp_path / 'first-run'))
                assert result['document']['document_id']==final
                assert result['status'] == 'checks_passed'
                assert all(result['checks'].values())
                assert result['visual_review'] == 'required'
                assert result['environment']['native_connection'] == 'responding'
                expected = sorted(x['canonical_smiles'] for x in prepare_structures(list(DEMO_STRUCTURES)))
                assert chemical_signature(Path(result['artifacts']['cdxml']).read_text()) == expected
                assert json.loads(Path(result['report']).read_text()) == result
                for path in result['artifacts'].values():
                    assert Path(path).stat().st_size > 100
                assert 'review' not in result
                assert not list((tmp_path/'first-run').rglob('*.html'))
                print('FIRST_RUN_REPORT=' + result['report'])
                succeeded = True
            finally:
                if succeeded:
                    from chemdraw_macos.core import Bridge
                    Bridge()._run('close',final)
            assert await call('chemdraw_list_documents') == baseline
