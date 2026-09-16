import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from test_targeted import sheet,chiral_sheet

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


def four_molecules():
    root=ET.fromstring(sheet());page=root.find('page')
    for fid,x,y in [(40,190,250),(50,360,310)]:
        f=ET.SubElement(page,'fragment',{'id':str(fid)})
        ET.SubElement(f,'n',{'id':str(fid+1),'p':f'{x} {y}'})
        ET.SubElement(f,'n',{'id':str(fid+2),'p':f'{x+18} {y}'})
        ET.SubElement(f,'b',{'id':str(fid+3),'B':str(fid+1),'E':str(fid+2)})
    return ET.tostring(root,encoding='unicode')


@pytest.mark.asyncio
@pytest.mark.parametrize('case',['ring','wedge','align'])
async def test_targeted_edit_through_mcp(tmp_path,case):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(tool,**args):
                result=await session.call_tool(tool,args)
                assert not result.isError,result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents')
            text=chiral_sheet() if case=='wedge' else four_molecules() if case=='align' else sheet()
            original=await call('chemdraw_create_document',cdxml=text);did=original['document']['document_id']
            info=await call('chemdraw_inspect_targets',document_id=did)
            if case=='ring':
                kind='atom';ids=[a['id'] for a in info['atoms'] if a['element']=='N']
                operation={'kind':'attach_ring','size':6,'angle_degrees':0}
            elif case=='wedge':
                carbon=next(a['id'] for a in info['atoms'] if a['element']=='C')
                fluorine=next(a['id'] for a in info['atoms'] if a['element']=='F')
                kind='bond';ids=[b['id'] for b in info['bonds'] if {b['begin'],b['end']}=={carbon,fluorine}]
                operation={'kind':'bond_display','display':'hashed_wedge','from_atom_id':carbon,'allow_stereo_change':True}
            else:
                # Native order is not promised: choose by original X position.
                byx=sorted(info['molecules'],key=lambda m:min(a['position_pt'][0] for a in info['atoms'] if a['molecule_id']==m['id']))
                kind='molecule';ids=[m['id'] for m in byx[:3]]
                untouched=[a for a in info['atoms'] if a['molecule_id']==byx[3]['id']]
                operation={'kind':'native_align','action':'align_top'}
            selection=await call('chemdraw_prepare_selection',document_id=did,kind=kind,ids=ids,expected_source_token=info['source_token'])
            result=await call('chemdraw_edit_targets',document_id=did,output_dir=str(tmp_path/'result'),selection=selection,operation=operation)
            final=result['document']['document_id']
            try:
                assert result['audit']['status']=='checks_passed'
                assert result['audit']['source_unchanged']
                assert result['audit']['verification']['bond_displays_verified']
                finalinfo=await call('chemdraw_inspect_targets',document_id=final)
                if case=='align':
                    native=await call('chemdraw_inspect_document',document_id=final)
                    tops=sorted(m['bounds_pt'][1] for m in native['molecules'])
                    assert tops[2]-tops[0]<.1
                    for old in untouched:
                        assert any(sum((a-b)**2 for a,b in zip(old['position_pt'],new['position_pt']))<.001 for new in finalinfo['atoms'])
                elif case=='ring':
                    assert 'CNC1CCCCC1' in result['audit']['changes']['after_smiles']
                else:
                    assert any('@' in s for m in finalinfo['molecules'] for s in m['smiles'])
                print('TARGETED_REVIEW='+result['review'])
            finally:
                await call('chemdraw_close_working_document',document_id=final)
                await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
