import os
import json
import sys
from pathlib import Path

import pytest

from test_complexes import recipe

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires licensed running ChemDraw')


def test_native_coordination_keeps_explicit_xyz_and_direction(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.complexes import draw_complex
    bridge=Bridge(); baseline=bridge.documents(); final=None
    try:
        result=draw_complex(bridge,recipe(),str(tmp_path/'complex'))
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert result['audit']['checks']['supplied_xyz_preserved']
        assert result['audit']['checks']['dative_direction_preserved']
        assert Path(result['artifacts']['svg']).stat().st_size>100
        print('COMPLEX_REVIEW='+result['review'])
    finally:
        if final is not None: bridge.close(final)
    assert bridge.documents()==baseline


@pytest.mark.asyncio
@pytest.mark.parametrize('example',[None,'coordination-ruthenium-chelate.json'])
async def test_complex_over_actual_mcp_transport(tmp_path,example):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**arguments):
                result=await session.call_tool(name,arguments)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents'); final=None
            try:
                supplied=recipe() if example is None else json.loads((Path(__file__).parents[1]/'examples'/example).read_text())
                result=await call('chemdraw_draw_complex',recipe=supplied,output_dir=str(tmp_path/'mcp-complex'))
                final=result['document']['document_id']
                assert all(result['audit']['checks'].values())
            finally:
                if final is not None: await call('chemdraw_close_working_document',document_id=final)
            assert await call('chemdraw_list_documents')==baseline


def test_ferrocene_aromatic_import_loss_is_rejected_and_copy_closed(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.complexes import draw_complex
    bridge=Bridge(); baseline=bridge.documents()
    supplied=json.loads((Path(__file__).parents[1]/'examples/coordination-ferrocene.json').read_text())
    out=tmp_path/'ferrocene'
    with pytest.raises(ValueError,match='NumHydrogens|order'):
        draw_complex(bridge,supplied,str(out))
    assert json.loads((out/'audit.json').read_text())['status']=='failed'
    assert bridge.documents()==baseline
