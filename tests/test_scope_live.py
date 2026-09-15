"""Native scope tests; never touch pre-existing documents."""
import json
import os
from pathlib import Path
import sys

import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

from test_polish import SAMPLE

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


def test_native_grid_file_freezes_input_and_preserves_original(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.scope import grid_file
    import hashlib
    root=Path(__file__).parents[1]
    source=root/'examples/scope-input.cdxml'
    before=source.read_bytes()
    recipe=json.loads((root/'examples/scope-recipe.json').read_text());recipe.pop('schema_version')
    bridge=Bridge(workspace=tmp_path/'workspace');baseline=bridge.documents()
    final=None
    try:
        result=grid_file(bridge,source,str(tmp_path/'file-grid'),**recipe)
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert result['audit']['checks']['source_file_unchanged']
        assert result['audit']['source_file_sha256']==hashlib.sha256(before).hexdigest()
        assert (tmp_path/'file-grid/source-input.cdxml').read_bytes()==before
        assert source.read_bytes()==before
        print('FILE_GRID_REVIEW='+result['review'])
    finally:
        if final is not None:bridge.close(final)
    assert bridge.documents()==baseline

SALT='''<CDXML LabelFont="3" LabelSize="10"><fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable><page id="100" BoundingBox="0 0 540 720">
<fragment id="1"><n id="2" p="50 60" Element="11" Charge="1" NumHydrogens="0"><t p="46 64"><s font="3" size="10" face="96">Na</s><s font="3" size="10" face="64">+</s></t></n></fragment>
<fragment id="3"><n id="4" p="100 60" Element="17" Charge="-1" NumHydrogens="0"><t p="96 64"><s font="3" size="10" face="96">Cl</s><s font="3" size="10" face="64">-</s></t></n></fragment>
<t id="10" p="75 110" Justification="Center"><s font="3" size="10">Sodium chloride</s></t></page></CDXML>'''


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['basic','salt'])
async def test_native_scope_via_mcp(tmp_path,kind):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace')))
    created=[]
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                r=await session.call_tool(name,args)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents')
            try:
                result=await call('chemdraw_create_document',cdxml=SALT if kind=='salt' else SAMPLE)
                did=result['document']['document_id'];created.append(did)
                report=await call('chemdraw_analyze_document',document_id=did)
                if kind=='salt':
                    cells=[{'compound_id':'salt','fragment_ids':[m['id'] for m in report['molecules']],
                            'caption_id':report['texts'][0]['id'],'yield_percent':None}]
                else:
                    cells=[{'compound_id':f'3{chr(97+i)}','fragment_ids':[m['id']],
                            'caption_id':t['id'],'yield_percent':0 if i==0 else None}
                           for i,(m,t) in enumerate(zip(report['molecules'],report['texts']))]
                result=await call('chemdraw_grid_document',document_id=did,output_dir=str(tmp_path/'scope'),
                                  cells=cells,expected_source_token=report['source_token'],columns=len(cells))
                created.append(result['document']['document_id'])
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                assert [c['compound_id'] for c in result['audit']['verification']['cells']]==[c['compound_id'] for c in cells]
                print('SCOPE_REVIEW='+result['review'])
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
