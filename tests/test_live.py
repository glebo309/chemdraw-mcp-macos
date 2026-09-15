"""Opt-in live scratch test through the real MCP stdio transport."""
import json,os,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires running, licensed ChemDraw on macOS')
SOURCE='''<CDXML BondLength="18" LineWidth="0.6" LabelFont="3" LabelSize="10" InterpretChemically="no"><fonttable><font id="3" charset="Unicode" name="Helvetica Neue"/></fonttable><page id="100" BoundingBox="0 0 540 720"><fragment id="1"><n id="2" p="80 100"/><n id="3" Element="8" NumHydrogens="1" p="110 115"><t p="105 119"><s font="3" size="10" face="96">OH</s></t></n><b id="4" B="2" E="3"/></fragment></page></CDXML>'''

@pytest.mark.asyncio
async def test_real_mcp_scratch(tmp_path):
    env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace'))
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=env)
    results={};created=[]
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(name,**args):
                result=await session.call_tool(name,args)
                assert not result.isError, result
                return result.structuredContent or json.loads(result.content[0].text)
            baseline=await call('chemdraw_list_documents')
            try:
                result=await call('chemdraw_create_document',cdxml=SOURCE)
                did=result['document']['document_id'];created.append(did)
                imported=await call('chemdraw_import_file',path=result['working_copy'])
                iid=imported['document']['document_id'];created.append(iid)
                assert iid!=did
                assert imported['working_copy']!=result['working_copy']
                initial=await call('chemdraw_inspect_document',document_id=did)
                assert initial['document']['molecule_count']==1
                cleaned=await call('chemdraw_clean',document_id=did,molecule_index=initial['molecules'][0]['molecule_index'])
                assert Path(cleaned['backup']).is_file()
                whole_cleaned=await call('chemdraw_clean',document_id=did)
                assert Path(whole_cleaned['backup']).is_file()
                styled=await call('chemdraw_apply_style',document_id=did,preset='house')
                sid=styled['document']['document_id'];created.append(sid)
                final=await call('chemdraw_inspect_document',document_id=sid)
                assert final['settings']['label_size_twentieth_pt']==280
                out=tmp_path/'export';out.mkdir()
                for fmt in ('cdxml','svg','pdf','png','cdx'):
                    result=await call('chemdraw_export',document_id=sid,path=str(out/('methanol.'+fmt)),format=fmt)
                    assert result['bytes']>0
                native=ET.parse(out/'methanol.cdxml').getroot()
                assert len(list(native.iter('n')))==2
                assert len(list(native.iter('b')))==1
                assert native.find('.//n[@Element="8"]') is not None
                after=await call('chemdraw_list_documents')
                byid={d['document_id']:d for d in after['documents']}
                for d in baseline['documents']:assert byid[d['document_id']]==d
                results.update(baseline=baseline,initial=initial,cleaned=cleaned,styled=styled,final=final,exports=str(out))
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            after=await call('chemdraw_list_documents')
            assert after==baseline
            results['status']='pass'
            (tmp_path/'live-report.json').write_text(json.dumps(results,indent=2))
            print('LIVE_REPORT='+str(tmp_path/'live-report.json'))


@pytest.mark.asyncio
async def test_live_polish_through_mcp(tmp_path):
    from test_polish import SAMPLE
    env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace'))
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=env)
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
                source=await call('chemdraw_create_document',cdxml=SAMPLE)
                did=source['document']['document_id'];created.append(did)
                analyzed=await call('chemdraw_analyze_document',document_id=did)
                molecules=analyzed['molecules'];texts=analyzed['texts']
                captions={m['id']:t['id'] for m,t in zip(molecules,texts)}
                result=await call('chemdraw_polish_document',document_id=did,
                                  output_dir=str(tmp_path/'polish'),layout='row',caption_map=captions)
                created.append(result['document']['document_id'])
                assert result['audit']['status']=='checks_passed'
                assert all(result['audit']['checks'].values())
                assert (tmp_path/'polish'/'review.html').is_file()
                print('POLISH_REVIEW='+result['review'])
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline


@pytest.mark.asyncio
@pytest.mark.parametrize('target,smiles', [('S','CCS'),('N','CCN'),('carbonyl','CC=O'),('chiral',None)])
async def test_live_analogue_through_mcp(tmp_path,target,smiles):
    from test_editing import ETHANOL,CHIRAL
    env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace'))
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=env)
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
                result=await call('chemdraw_create_document',cdxml=CHIRAL if target=='chiral' else ETHANOL)
                did=result['document']['document_id'];created.append(did)
                report=await call('chemdraw_analyze_document',document_id=did)
                edit=report['editing'];assert 'unsupported' not in edit,edit
                oxygen=next(a for a in edit['atoms'] if a['element']=='O')['id']
                captions={edit['captions'][0]['id']:{'S':'Ethanethiol','N':'Ethylamine','carbonyl':'Ethanal'}[target]} if target!='chiral' else {}
                if target=='chiral':
                    chloride=next(a for a in edit['atoms'] if a['element']=='Cl')['id']
                    ops=[{'kind':'atom','id':chloride,'element':'Br','hydrogens':0}]
                    smiles=edit['smiles'][0].replace('Cl','Br')
                    assert '@' in smiles
                elif target=='carbonyl':
                    bond=next(b for b in edit['bonds'] if oxygen in (b['begin'],b['end']))
                    ops=[{'kind':'bond','id':bond['id'],'order':2},{'kind':'atom','id':oxygen,'hydrogens':0}]
                else:ops=[{'kind':'atom','id':oxygen,'element':target,'hydrogens':2 if target=='N' else 1}]
                result=await call('chemdraw_edit_document',document_id=did,output_dir=str(tmp_path/'analogue'),
                                  operations=ops,captions=captions,
                                  expected_source_token=edit['source_token'])
                created.append(result['document']['document_id'])
                assert result['audit']['chemical_diff']['after_smiles']==[smiles]
                assert all(result['audit']['checks'].values())
                print('ANALOGUE_REVIEW='+result['review'])
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline


def test_live_aromatic_file_edit_renders_left_hydroxyl_correctly(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.editing import edit_file
    bridge=Bridge(workspace=tmp_path/'workspace');baseline=bridge.documents()
    source=Path(__file__).parents[1]/'examples/chlorobenzoic-acid.cdxml'
    original=source.read_bytes();result=None
    try:
        result=edit_file(bridge,source,str(tmp_path/'bromo'),
                         [{'kind':'atom','id':'8','element':'Br','hydrogens':0}],{'30':'4-Bromobenzoic acid'})
        root=ET.parse(tmp_path/'bromo'/'figure.svg').getroot()
        labels=[''.join(t.itertext()).strip() for t in root.findall('{http://www.w3.org/2000/svg}text')]
        assert 'HO' in labels and 'OH' not in labels
        assert result['audit']['native_verification']['maximum_displacement_pt']<.03
        assert source.read_bytes()==original
    finally:
        if result:bridge.close(result['document']['document_id'])
    assert bridge.documents()==baseline
