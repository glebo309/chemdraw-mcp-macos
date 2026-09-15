"""Actual stdio MCP onboarding with native artifact and ownership checks."""
import json
import os
from pathlib import Path
import sys

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
            final = None
            try:
                result = await call('chemdraw_first_run', output_dir=str(tmp_path / 'first-run'))
                final = result['document']['document_id']
                assert result['status'] == 'checks_passed'
                assert all(result['checks'].values())
                assert result['visual_review'] == 'required'
                assert result['environment']['native_connection'] == 'responding'
                expected = sorted(x['canonical_smiles'] for x in prepare_structures(list(DEMO_STRUCTURES)))
                assert chemical_signature(Path(result['artifacts']['cdxml']).read_text()) == expected
                assert json.loads(Path(result['report']).read_text()) == result
                for path in result['artifacts'].values():
                    assert Path(path).stat().st_size > 100
                print('FIRST_RUN_REVIEW=' + result['review'])
            finally:
                if final is not None:
                    await call('chemdraw_close_working_document', document_id=final)
            assert await call('chemdraw_list_documents') == baseline
