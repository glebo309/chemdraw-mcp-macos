import json
import os
import sys
import xml.etree.ElementTree as ET

import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from chemdraw_macos.core import style_cdxml
from test_targeted import sheet

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


@pytest.mark.asyncio
@pytest.mark.parametrize('case',['atom','charge','bond','fragment','removal','methyl'])
async def test_expanded_edit_native_mcp(tmp_path,case):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**kw):
                r=await session.call_tool(name,kw)
                assert not r.isError,r
                return r.structuredContent or json.loads(r.content[0].text)
            baseline=await call('chemdraw_list_documents')
            created=await call('chemdraw_create_document',cdxml=sheet())
            did=created['document']['document_id'];owned=[did]
            info=await call('chemdraw_inspect_targets',document_id=did)
            n=next(a['id'] for a in info['atoms'] if a['element']=='N')
            kind='atom';oid=n
            if case=='atom':op={'kind':'set_atom','element':'O','hydrogens':1,'charge':0};wanted='CO'
            elif case=='charge':op={'kind':'set_atom','element':'N','hydrogens':3,'charge':1};wanted='C[NH3+]'
            elif case=='bond':
                oxygen=next(a['id'] for a in info['atoms'] if a['element']=='O')
                bond=next(b for b in info['bonds'] if oxygen in (b['begin'],b['end']))
                kind='bond';oid=bond['id'];carbon=next(a for a in (bond['begin'],bond['end']) if a!=oxygen)
                op={'kind':'set_bond_order','order':2,'hydrogens':{oxygen:0,carbon:2}};wanted='C=O'
            else:
                fragment=style_cdxml('<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/><n id="4" Element="8" NumHydrogens="1" p="18 0"><t><s>OH</s></t></n><b id="5" B="3" E="4"/></fragment></page></CDXML>','house')
                if case=='methyl':fragment=style_cdxml('<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/></fragment></page></CDXML>','house')
                op={'kind':'attach_fragment','fragment_cdxml':fragment,'attachment_atom_id':'3','angle_degrees':'auto'};wanted='CNCO'
                if case=='methyl':wanted='CNC'
            selection=await call('chemdraw_prepare_selection',document_id=did,kind=kind,ids=[oid],expected_source_token=info['source_token'])
            result=await call('chemdraw_edit_targets',document_id=did,selection=selection,operation=op,output_dir=str(tmp_path/'edit'))
            final=result['document']['document_id'];owned.append(final)
            assert wanted in result['audit']['changes']['after_smiles']
            assert result['audit']['verification']['placement']['new_collisions']==0
            if case=='removal':
                info=await call('chemdraw_inspect_targets',document_id=final)
                n=next(a['id'] for a in info['atoms'] if a['element']=='N')
                # Select the bond to the newly attached right-hand carbon.
                right=next(a['id'] for a in info['atoms'] if a['element']=='C' and 130<a['position_pt'][0]<150)
                bond=next(b['id'] for b in info['bonds'] if {b['begin'],b['end']}=={n,right})
                selection=await call('chemdraw_prepare_selection',document_id=final,kind='bond',ids=[bond],expected_source_token=info['source_token'])
                result=await call('chemdraw_edit_targets',document_id=final,selection=selection,operation={'kind':'remove_substituent','keep_atom_id':n,'hydrogens':2},output_dir=str(tmp_path/'remove'))
                owned.append(result['document']['document_id'])
                assert result['audit']['changes']['after_smiles']==['CN','CO']
            print('EXPANDED_REVIEW='+result['review'])
            for doc in reversed(owned):await call('chemdraw_close_working_document',document_id=doc)
            assert await call('chemdraw_list_documents')==baseline
