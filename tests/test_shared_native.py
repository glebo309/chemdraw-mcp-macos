"""Actual native clipboard insertion. Only mutate owned test documents."""
import os
import json
import sys
import subprocess
from pathlib import Path
import pytest
from chemdraw_macos.core import Bridge

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_SHARED_TEST')!='1',reason='Explicit shared-document native acceptance')
SOURCE=Path(__file__).parents[1]/'examples/chlorobenzoic-acid.cdxml'


def test_untitled_read_and_analysis_do_not_assign_filename(tmp_path):
    from chemdraw_macos.harness import run_drawing
    from chemdraw_macos.live import read_live_document
    from chemdraw_macos.workflow import analyze_document
    b=Bridge();baseline=b.documents()
    with b.lock:
        script=f'tell application "{b.app}"\nset d to make new document\nreturn id of d\nend tell'
        created=subprocess.run(['osascript','-'],input=script,text=True,capture_output=True,check=True,timeout=20)
        did=int(created.stdout.strip())
    result=run_drawing(b,{'molecules':[{'format':'smiles','value':'c1ccncc1'}],'panel':'plain'},str(tmp_path/'addition'),presentation='shared',document_id=did)
    assert result['status']=='completed',result
    first=read_live_document(b,did)
    assert first['document']['file']==''
    assert first['snapshot_method']=='clipboard'
    assert read_live_document(b,did)['source_token']==first['source_token']
    report=analyze_document(b,did)
    assert report['document']['file']==''
    assert report['editing']['smiles']
    assert {d['document_id'] for d in b.documents()['documents']}=={did,*[d['document_id'] for d in baseline['documents']]}
    # Only this test-created untitled document is closed. Snapshots retain content.
    with b.lock:
        script=f'tell application "{b.app}"\nrepeat with d in documents\nif (id of d) as integer is {did} then\nclose d saving no\nexit repeat\nend if\nend repeat\nend tell'
        subprocess.run(['osascript','-'],input=script,text=True,capture_output=True,check=True,timeout=20)
    assert b.documents()==baseline


def test_native_cdx_append_moves_only_new_objects_and_undo_restores(tmp_path):
    from chemdraw_macos.shared import clipboard, plan_append, verify_append
    b=Bridge(); baseline=b.documents()
    target=b.create(SOURCE.read_text())['document']['document_id']
    cdx=tmp_path/'payload.cdx';b.export(target,str(cdx),'cdx')
    # Native CDX export normalizes print metadata. Capture the actual pre-paste
    # baseline after export so Undo is tested independently of that save effect.
    before=clipboard(b,target)['cdxml']
    (tmp_path/'before.cdxml').write_text(before)
    plan=plan_append(before,before)
    result=clipboard(b,target,cdx=str(cdx),placement=plan,expected=before)
    (tmp_path/'after.cdxml').write_text(result['cdxml'])
    assert result['clipboard_restored']
    assert result['document_id']==target
    assert verify_append(before,result['cdxml'],before)['existing_content_preserved']
    from chemdraw_macos.core import validate_cdxml
    from chemdraw_macos.workflow import remap_ids
    from chemdraw_macos.shared import _union
    from chemdraw_macos.polish import bounds
    old=set(remap_ids(before,result['cdxml']).values())
    added=_union([bounds(e) for e in validate_cdxml(result['cdxml']).find('page') if e.get('id') not in old])
    assert abs(added.left-plan['left'])<=1 and abs(added.top-plan['top'])<=1
    restored=clipboard(b,target,undo_steps=result['undo_steps'])
    (tmp_path/'restored.cdxml').write_text(restored['cdxml'])
    from chemdraw_macos.shared import fingerprint
    assert fingerprint(before)==fingerprint(restored['cdxml'])
    b.close(target)
    assert b.documents()==baseline


@pytest.mark.asyncio
async def test_actual_mcp_adds_to_same_document_twice(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from chemdraw_macos.shared import clipboard, verify_append
    b=Bridge(); baseline=b.documents()
    target=b.create(SOURCE.read_text())['document']['document_id']
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','drawing'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            for i,smiles in enumerate(['c1ccncc1','C[C@H](O)C(=O)O']):
                before=clipboard(b,target)['cdxml']
                result=await session.call_tool('chemdraw_draw',{
                    'request':{'molecules':[{'value':smiles,'format':'smiles'}],'panel':'plain'},
                    'output_dir':str(tmp_path/f'addition-{i}'),'presentation':'shared','document_id':target})
                assert not result.isError,result
                data=result.structuredContent or json.loads(result.content[0].text)
                assert data['status']=='completed',data
                assert data['document']['document_id']==target
                after=clipboard(b,target)['cdxml']
                assert verify_append(before,after,Path(data['artifacts']['cdxml']).read_text())['existing_content_preserved']
                for fmt in ('cdxml','svg','png'):assert Path(data['artifacts'][fmt]).stat().st_size>100
                assert {d['document_id'] for d in b.documents()['documents']}=={target,*[d['document_id'] for d in baseline['documents']]}
    b.close(target)


@pytest.mark.asyncio
async def test_actual_advanced_mcp_scope_keeps_target_and_closes_generated_final(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from chemdraw_macos.shared import clipboard,verify_append
    b=Bridge();baseline=b.documents()
    target=b.create(SOURCE.read_text())['document']['document_id']
    before=clipboard(b,target)['cdxml']
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server','--profile','full'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=await session.call_tool('chemdraw_draw_structures',{
                'structures':[{'compound_id':str(i+1),'label':label,'smiles':s} for i,(label,s) in enumerate([
                    ('Parent','c1ccncc1'),('Nitrile','N#Cc1ccncc1'),('Fluoro','Fc1ccncc1')])],
                'frame':False,'columns':3,'document_id':target,'presentation':'shared',
                'output_dir':str(tmp_path/'scope')})
            assert not result.isError,result
            data=result.structuredContent or json.loads(result.content[0].text)
            assert data['status']=='completed',data
            assert data['document']['document_id']==target
            after=clipboard(b,target)['cdxml']
            assert verify_append(before,after,Path(data['artifacts']['cdxml']).read_text())['existing_content_preserved']
            assert {d['document_id'] for d in b.documents()['documents']}=={target,*[d['document_id'] for d in baseline['documents']]}
    b.close(target)
