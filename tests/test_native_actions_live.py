import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from chemdraw_macos.core import style_cdxml

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


def three_molecules():
    root=ET.Element('CDXML');page=ET.SubElement(root,'page',{'id':'1','BoundingBox':'0 0 600 750'})
    for i,(x,y) in enumerate([(80,100),(170,190),(380,140)]):
        fid=10+i*10;f=ET.SubElement(page,'fragment',{'id':str(fid)})
        ET.SubElement(f,'n',{'id':str(fid+1),'p':f'{x} {y}'})
        n=ET.SubElement(f,'n',{'id':str(fid+2),'Element':'8','NumHydrogens':'1','p':f'{x+24} {y+12}'})
        t=ET.SubElement(n,'t');ET.SubElement(t,'s',{'face':'96'}).text='OH'
        ET.SubElement(f,'b',{'id':str(fid+3),'B':str(fid+1),'E':str(fid+2)})
    return style_cdxml(ET.tostring(root,encoding='unicode'),'house')


def graphs(path):
    from rdkit import Chem
    return sorted(Chem.MolToSmiles(m) for m in Chem.MolsFromCDXML(Path(path).read_text()))


def single_step_reaction():
    # The manual requires a recognized single-step reaction with a straight arrow.
    # The original messy showcase is not recognized by native reaction cleanup.
    root=ET.parse(Path(__file__).parents[1]/'examples/messy-oxidation.cdxml').getroot()
    page=root.find('page')
    for t in list(page.findall('t')):page.remove(t)
    for e in page.find("fragment[@id='20']").iter():
        if e.get('p'):
            x,y=map(float,e.get('p').split());e.set('p',f'{x} {y-60}')
    arrow=page.find('arrow');arrow.set('Head3D','225 60 0');arrow.set('Tail3D','145 60 0')
    return ET.tostring(root,encoding='unicode')


@pytest.mark.asyncio
@pytest.mark.parametrize('action',[
    'align_left','align_right','align_top','align_bottom',
    'align_horizontal_centers','align_vertical_centers',
    'distribute_horizontal','distribute_vertical',
    'clean_structure','clean_reaction','unrecognized_reaction',
])
async def test_native_actions_through_mcp(tmp_path,action):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(tool,**arguments):
                r=await session.call_tool(tool,arguments)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents')
            source=(single_step_reaction() if action=='clean_reaction' else
                    (Path(__file__).parents[1]/'examples/messy-oxidation.cdxml').read_text() if action=='unrecognized_reaction' else three_molecules())
            created=await call('chemdraw_create_document',cdxml=source)
            did=created['document']['document_id']
            # No auto-close after an uncertain command. Once returned, this test
            # owns the known completed copy and can close it after verification.
            before=tmp_path/'before.cdxml';after=tmp_path/'after.cdxml'
            await call('chemdraw_export',document_id=did,path=str(before),format='cdxml')
            result=await call('chemdraw_native_action',document_id=did,action='clean_reaction' if action=='unrecognized_reaction' else action,selection='all')
            expected='unavailable_for_selection' if action=='unrecognized_reaction' else 'native_action_applied_review_required'
            assert result['status']==expected,result
            await call('chemdraw_export',document_id=did,path=str(after),format='cdxml')
            await call('chemdraw_export',document_id=did,path=str(tmp_path/'after.png'),format='png',pixels=1600)
            try:
                assert graphs(before)==graphs(after)
                bounds=[m['bounds_pt'] for m in (await call('chemdraw_inspect_document',document_id=did))['molecules']]
                if action.startswith('align_'):
                    components={'align_left':(0,), 'align_right':(2,), 'align_top':(1,), 'align_bottom':(3,),
                                'align_horizontal_centers':(0,2), 'align_vertical_centers':(1,3)}[action]
                    values=[sum(b[i] for i in components)/len(components) for b in bounds]
                    assert max(values)-min(values)<.1, bounds
                elif action.startswith('distribute_'):
                    axis=0 if action.endswith('horizontal') else 1
                    bounds.sort(key=lambda b:b[axis])
                    gaps=[bounds[i+1][axis]-bounds[i][axis+2] for i in range(len(bounds)-1)]
                    assert max(gaps)-min(gaps)<.1,bounds
                print('NATIVE_ACTION_PREVIEW='+str(tmp_path/'after.png'))
            finally:
                await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline
