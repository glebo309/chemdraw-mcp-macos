"""Actual stdio native naming, with independent graphs checked only in acceptance tests."""
import json
import os
from pathlib import Path
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw; allows native lookup for public fixture names')


@pytest.mark.asyncio
@pytest.mark.parametrize('name,expected,stereo',[
    ('6-amino-4-fluorononan-1-ol','OCCCC(F)CC(N)CCC',None),
    ('(2R)-butan-2-ol','CCC(C)O','R'),
])
async def test_native_name_drawing_via_core_mcp(tmp_path,name,expected,stereo):
    from rdkit import Chem
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','core'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(tool,**arguments):
                result=await session.call_tool(tool,arguments)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents')
            result=await call('chemdraw_draw_name',name=name,output_dir=str(tmp_path/'named'),allow_network=True)
            did=result['document']['document_id']
            # Only a returned successful copy is eligible for this test's cleanup.
            try:
                assert result['status']=='native_generated_review_required'
                assert result['audit']['rdkit_used'] is False
                mols=Chem.MolsFromCDXML(Path(result['artifacts']['cdxml']).read_text())
                assert len(mols)==1
                observed=Chem.MolToSmiles(mols[0],isomericSmiles=False)
                assert observed==Chem.MolToSmiles(Chem.MolFromSmiles(expected),isomericSmiles=False)
                if stereo:
                    Chem.AssignStereochemistry(mols[0],cleanIt=True,force=True)
                    assert [a.GetProp('_CIPCode') for a in mols[0].GetAtoms() if a.HasProp('_CIPCode')]==[stereo]
                assert all(Path(result['artifacts'][fmt]).stat().st_size>100 for fmt in ('cdxml','svg','png'))
                print('NATIVE_NAME_REVIEW='+result['review'])
            finally:
                await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
