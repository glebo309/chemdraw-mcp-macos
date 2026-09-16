"""Opt-in real MCP test for the installed desktop add-in, not the legacy bridge."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST')!='1',reason='Requires installed local ChemDraw MCP add-in')


def panel(snapshot,count,y):
    from chemdraw_macos.polish import transform
    root=ET.fromstring(snapshot);page=root.find('page')
    for child in list(page):page.remove(child)
    seed=ET.parse(Path(__file__).parents[1]/'examples/chlorobenzoic-acid.cdxml').getroot().find('.//fragment')
    for i in range(count):
        f=copy.deepcopy(seed)
        mapping={e.get('id'):str(1000+100*i+int(e.get('id'))) for e in f.iter() if e.get('id')}
        for e in f.iter():
            for k in ('id','B','E'):
                if e.get(k) in mapping:e.set(k,mapping[e.get(k)])
        transform(f,dx=(i%3)*140,dy=y+(i//3)*170)
        points=[tuple(map(float,e.get('p').split())) for e in f.iter() if e.get('p')]
        f.set('BoundingBox',' '.join(map(str,(min(p[0] for p in points)-15,min(p[1] for p in points)-15,max(p[0] for p in points)+15,max(p[1] for p in points)+15))))
        page.append(f)
    return ET.tostring(root,encoding='unicode')


@pytest.mark.asyncio
async def test_native_api_untitled_batch_background_and_stale_guard(tmp_path):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            async def call(name,**arguments):
                response=await session.call_tool(name,arguments)
                assert not response.isError,response
                return response.structuredContent or json.loads(response.content[0].text)
            connected=await call('chemdraw_addin_connect')
            assert connected['status']=='connected',connected
            baseline=await call('chemdraw_list_documents')
            # This test owns the new untitled document. No user document is closed.
            created=subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True)
            did=int(created.strip())
            first=await call('chemdraw_addin_read_document',document_id=did)
            assert first['document']['file']==''
            supplied=panel(first['cdxml'],5,50)
            subprocess.run(['osascript','-e','tell application "Finder" to activate'],check=True)
            result=await call('chemdraw_addin_append_cdxml',document_id=did,cdxml=supplied,expected_source_token=first['source_token'])
            assert result['status']=='completed' and all(result['checks'].values())
            assert result['document']['file']=='' and result['document']['molecule_count']==5
            foreground=subprocess.check_output(['osascript','-e','tell application "System Events" to get name of first application process whose frontmost is true'],text=True).strip()
            assert foreground=='Finder'
            second=await call('chemdraw_addin_read_document',document_id=did)
            more=panel(second['cdxml'],1,450)
            stale=await session.call_tool('chemdraw_addin_append_cdxml',{'document_id':did,'cdxml':more,'expected_source_token':first['source_token']})
            assert stale.isError
            result2=await call('chemdraw_addin_append_cdxml',document_id=did,cdxml=more,expected_source_token=second['source_token'])
            assert result2['status']=='completed' and result2['document']['molecule_count']==6
            assert result2['document']['file']==''
            final=await call('chemdraw_list_documents')
            assert {d['document_id'] for d in final['documents']}=={did,*[d['document_id'] for d in baseline['documents']]}
            report={'initial':first,'first_append':result,'second_append':result2,'foreground':foreground,'baseline':baseline,'final':final}
            (tmp_path/'addin-native-report.json').write_text(json.dumps(report,indent=2))
            print('ADDIN_NATIVE_REPORT='+str(tmp_path/'addin-native-report.json'))
            # Both successful appends have recovery snapshots; close only our own test.
            from chemdraw_macos.core import Bridge
            Bridge()._run('close',did)


@pytest.mark.asyncio
async def test_ordinary_mcp_draw_and_eight_analogues_share_untitled_canvas(tmp_path):
    # Tables may use one hidden native measuring copy, never visible seed windows.
    bootstrap='from chemdraw_macos import server\noriginal=server.Bridge._open_working\ndef guarded(self,path,visible=True):\n if visible: raise RuntimeError("VISIBLE INTERMEDIATE DOCUMENT FORBIDDEN")\n return original(self,path,visible=False)\nserver.Bridge._open_working=guarded\nserver.main()'
    params=StdioServerParameters(command=sys.executable,args=['-c',bootstrap],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            async def call(name,**arguments):
                response=await session.call_tool(name,arguments)
                assert not response.isError,response
                return response.structuredContent or json.loads(response.content[0].text)
            baseline=await call('chemdraw_list_documents')
            did=int(subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True))
            report={'document_id':did,'baseline':baseline}
            (tmp_path/'owned-document.json').write_text(json.dumps(report))
            parent='CC1C=Cc2c1c(=O)n(C)c(=O)n2C'
            first=await call('chemdraw_draw',output_dir=str(tmp_path/'parent'),request={'molecules':[{'format':'smiles','value':parent,'label':'Caffeine'}],'panel':'plain'})
            report['first']=first
            (tmp_path/'ordinary-api-report.json').write_text(json.dumps(report,indent=2))
            assert first['status']=='completed',first
            assert first['document']['document_id']==did and first['document']['file']==''
            live=await call('chemdraw_read_live_document',document_id=did)
            assert live['snapshot_method']=='desktop_addin'
            from rdkit import Chem
            assert live['molecular_graphs'][0]['canonical_smiles']==Chem.MolToSmiles(Chem.MolFromSmiles(parent))
            subprocess.run(['osascript','-e','tell application "Finder" to activate'],check=True)
            records=[{'compound_id':str(i+2),'label':'R = '+label,'smiles':'CC1C('+r+')=Cc2c1c(=O)n(C)c(=O)n2C'} for i,(label,r) in enumerate([('Me','C'),('OMe','OC'),('NH2','N'),('F','F'),('Br','Br'),('CN','C#N'),('CF3','C(F)(F)F'),('Ph','c2ccccc2')])]
            second=await call('chemdraw_draw_structures',structures=records,output_dir=str(tmp_path/'analogues'),presentation='auto')
            report['second']=second
            (tmp_path/'ordinary-api-report.json').write_text(json.dumps(report,indent=2))
            assert second['status']=='completed',second
            assert second['document']['document_id']==did and second['document']['molecule_count']==9
            assert second['planning']['reference_source']=='live_document'
            assert second['checks']['new_object_style_verified']
            final=await call('chemdraw_list_documents')
            assert {d['document_id'] for d in final['documents']}=={did,*[d['document_id'] for d in baseline['documents']]}
            foreground=subprocess.check_output(['osascript','-e','tell application "System Events" to get name of first application process whose frontmost is true'],text=True).strip()
            assert foreground=='Finder'
            report.update(final=final,foreground=foreground,live=live)
            (tmp_path/'ordinary-api-report.json').write_text(json.dumps(report,indent=2))
            from chemdraw_macos.core import Bridge
            Bridge()._run('close',did)


@pytest.mark.asyncio
async def test_native_captions_remain_text_and_numbered_batch_keeps_count(tmp_path):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            did=int(subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True))
            (tmp_path/'owned-document.json').write_text(json.dumps({'document_id':did}))
            values=['CCO','CC(=O)Nc1ccccc1','c1ccccc1','CCCC','CCN(CC)CC','c1ccc2[nH]ccc2c1']
            molecules=[{'format':'smiles','value':sm} for sm in values]
            molecules[0]['label']='DMT'  # Intentionally misleading caption, never a second molecule.
            response=await session.call_tool('chemdraw_draw',{'document_id':did,'output_dir':str(tmp_path/'batch'),
                'request':{'panel':'plain','molecules':molecules}})
            result=response.structuredContent or json.loads(response.content[0].text)
            (tmp_path/'caption-grid-report.json').write_text(json.dumps(result,indent=2))
            assert result['status']=='completed',result
            root=ET.parse(result['artifacts']['cdxml']).getroot()
            assert result['document']['molecule_count']==6
            assert len(root.findall('page/t'))==6
            assert len(list(root.iter('fragment')))==6
            assert [''.join(t.itertext()).strip() for t in root.findall('page/t')]==['DMT','2','3','4','5','6']
            from chemdraw_macos.core import Bridge
            Bridge()._run('close',did)


@pytest.mark.asyncio
async def test_native_auto_replacement_scope_retains_live_orientation(tmp_path):
    from test_api_drawing import REPLACEMENT_SCOPE,assert_core_orientation
    bootstrap='from chemdraw_macos import server\noriginal=server.Bridge._open_working\ndef guarded(self,path,visible=True):\n if visible: raise RuntimeError("VISIBLE INTERMEDIATE DOCUMENT FORBIDDEN")\n return original(self,path,visible=False)\nserver.Bridge._open_working=guarded\nserver.main()'
    params=StdioServerParameters(command=sys.executable,args=['-c',bootstrap],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            async def call(name,**arguments):
                response=await session.call_tool(name,arguments)
                assert not response.isError,response
                return response.structuredContent or json.loads(response.content[0].text)
            baseline=await call('chemdraw_list_documents')
            did=int(subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True))
            (tmp_path/'owned-document.json').write_text(json.dumps({'document_id':did}))
            first=await call('chemdraw_draw',document_id=did,output_dir=str(tmp_path/'parent'),request={
                'molecules':[{'format':'smiles','value':'CC1C=Cc2c1c(=O)n(C)c(=O)n2C','label':'Parent'}]})
            assert first['status']=='completed',first
            before=Path(first['artifacts']['cdxml']).read_text()
            second=await call('chemdraw_draw',document_id=did,output_dir=str(tmp_path/'scope'),request={
                'panel':'auto','molecules':[{'format':'smiles','value':s,'label':'S'+str(i+1)} for i,s in enumerate(REPLACEMENT_SCOPE)]})
            (tmp_path/'replacement-scope-report.json').write_text(json.dumps(second,indent=2))
            assert second['status']=='completed',second
            assert second['document']['document_id']==did
            assert second['document']['molecule_count']==11
            assert second['document']['file']==''
            assert second['planning']['reference_source']=='live_document'
            assert second['checks']['new_object_style_verified']
            root=ET.parse(second['artifacts']['cdxml']).getroot()
            assert len(list(root.iter('fragment')))==11
            assert [''.join(t.itertext()).strip() for t in root.findall('page/t')]==['Parent']+['S'+str(i+1) for i in range(10)]
            root.find('page').remove(root.find('page/fragment'))
            assert_core_orientation(before,ET.tostring(root,encoding='unicode'),second['planning']['scaffold_smiles'])
            final=await call('chemdraw_list_documents')
            assert {d['document_id'] for d in final['documents']}=={did,*[d['document_id'] for d in baseline['documents']]}
            from chemdraw_macos.core import Bridge
            Bridge()._run('close',did)


@pytest.mark.asyncio
async def test_native_api_mixed_chemistry_batch(tmp_path):
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            did=int(subprocess.check_output(['osascript','-e','tell application "ChemDraw 23.0.1" to get id of (make new document)'],text=True))
            (tmp_path/'owned-document.json').write_text(json.dumps({'document_id':did}))
            smiles=['CC(=O)Nc1ccccc1','Cn1c(=O)c2c(ncn2C)n(C)c1=O','N[C@@H](C)C(=O)O','[13CH3]CO','O=[N+]([O-])c1ccccc1','C/C=C/C','c1ccc2[nH]ccc2c1','[H]OC']
            response=await session.call_tool('chemdraw_draw',{'document_id':did,'output_dir':str(tmp_path/'mixed'),
                'request':{'panel':'plain','molecules':[{'format':'smiles','value':sm,'label':'Test '+str(i+1)} for i,sm in enumerate(smiles)]}})
            result=response.structuredContent or json.loads(response.content[0].text)
            (tmp_path/'mixed-api-report.json').write_text(json.dumps(result,indent=2))
            assert result['status']=='completed',result
            assert result['document']['molecule_count']==len(smiles)
            from chemdraw_macos.core import Bridge
            Bridge()._run('close',did)
