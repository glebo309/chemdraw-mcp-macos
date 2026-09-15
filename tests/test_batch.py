import asyncio
import json
from pathlib import Path

import pytest

from chemdraw_macos.batch import batch_export
from test_workflow import FakeBridge
from test_polish import SAMPLE


class BatchBridge(FakeBridge):
    def documents(self):
        return {'documents':[self.inspect(d)['document'] for d in [1]+sorted(self.managed)]}


def entries(tmp_path, count=2):
    result=[]
    for i in range(count):
        p=tmp_path/f'source{i}.cdxml';p.write_text(SAMPLE)
        result.append({'key':f'fig-{i+1}','source':str(p),'formats':['pdf','cdx']})
    return result


def test_batch_native_exports_and_contact_sheet(tmp_path):
    items=entries(tmp_path);b=BatchBridge(tmp_path/'work');baseline=b.documents()
    r=batch_export(b,items,str(tmp_path/'out'),pixels=1200)
    assert r['status']=='completed'
    assert [v['status'] for v in r['items']]==['exported','exported']
    assert b.documents()==baseline
    assert r['checks']['preexisting_documents_unchanged']
    for item in items:
        folder=tmp_path/'out'/item['key']
        for fmt in ('cdxml','svg','png','pdf','cdx'):
            assert (folder/f'{item["key"]}.{fmt}').is_file()
        audit=json.loads((folder/'audit.json').read_text())
        assert audit['checks']['mapped_chemistry_preserved']
        assert audit['checks']['source_file_unchanged']
        assert Path(item['source']).read_text()==SAMPLE
    page=(tmp_path/'out'/'review.html').read_text()
    assert 'fig-1/fig-1.png' in page and 'Visual review' in page
    assert len([e for e in b.events if e[0]=='create'])==2
    assert not b.managed


@pytest.mark.parametrize('key',['../bad','/bad','bad/name','.','', 'A'*65])
def test_invalid_keys_rejected_before_output_or_native(tmp_path,key):
    items=entries(tmp_path,1);items[0]['key']=key;b=BatchBridge(tmp_path/'work')
    with pytest.raises(ValueError):batch_export(b,items,str(tmp_path/'out'))
    assert not b.events and not (tmp_path/'out').exists()


def test_case_insensitive_duplicate_keys_and_existing_destination(tmp_path):
    items=entries(tmp_path);items[1]['key']='FIG-1';b=BatchBridge(tmp_path/'work')
    with pytest.raises(ValueError,match='Duplicate'):batch_export(b,items,str(tmp_path/'out'))
    items[1]['key']='fig-2'
    with pytest.raises(FileExistsError):batch_export(b,items,str(tmp_path))
    assert not b.events


def test_unsupported_and_missing_inputs_reported_while_valid_items_export(tmp_path):
    items=entries(tmp_path,3)
    Path(items[1]['source']).write_text('<CDXML><page><group/></page></CDXML>')
    items[2]['source']=str(tmp_path/'missing.cdxml')
    b=BatchBridge(tmp_path/'work');r=batch_export(b,items,str(tmp_path/'out'))
    assert r['status']=='partial_failure'
    assert [v['status'] for v in r['items']]==['exported','rejected','rejected']
    assert len([e for e in b.events if e[0]=='create'])==1


def test_uncertain_native_write_stops_batch_without_retry_or_cleanup(tmp_path):
    items=entries(tmp_path,3);b=BatchBridge(tmp_path/'work');original=b.export
    def fail(did,path,format,pixels=3200):
        if format=='pdf':raise RuntimeError('native timeout')
        return original(did,path,format,pixels)
    b.export=fail
    r=batch_export(b,items,str(tmp_path/'out'))
    assert r['status']=='interrupted'
    assert [v['status'] for v in r['items']]==['uncertain','not_run','not_run']
    assert len(b.managed)==1
    assert not any(e[0]=='close' for e in b.events)
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='interrupted'
    assert r['checks']['preexisting_documents_unchanged'] is None


def test_import_changes_chemistry_reports_failed_item_not_success(tmp_path):
    items=entries(tmp_path,1);b=BatchBridge(tmp_path/'work');create=b.create
    b.create=lambda text:create(text.replace('Element="8"','Element="7"'))
    r=batch_export(b,items,str(tmp_path/'out'))
    assert r['items'][0]['status']=='failed' and r['status']=='partial_failure'
    assert not b.managed


def test_source_file_modified_during_export_not_claimed_preserved(tmp_path):
    items=entries(tmp_path,1);b=BatchBridge(tmp_path/'work');export=b.export
    def change(did,path,format,pixels=3200):
        if format=='png':Path(items[0]['source']).write_text(SAMPLE+'\n')
        return export(did,path,format,pixels)
    b.export=change
    r=batch_export(b,items,str(tmp_path/'out'))
    assert r['items'][0]['status']=='failed'
    assert 'source' in r['items'][0]['error'].lower()


def test_batch_cli_and_mcp_exposed(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import cli
    from chemdraw_macos.server import mcp
    assert 'chemdraw_batch_export' in {t.name for t in asyncio.run(mcp.list_tools())}
    items=entries(tmp_path);manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'schema_version':1,'items':items,'pixels':1200}))
    monkeypatch.setattr(cli,'Bridge',lambda:BatchBridge(tmp_path/'work'))
    assert cli.main(['batch','--manifest',str(manifest),'--output',str(tmp_path/'out')])==0
    assert json.loads(capsys.readouterr().out)['status']=='completed'


def test_batch_cli_partial_failure_is_nonzero(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import cli
    items=entries(tmp_path,1);items[0]['source']=str(tmp_path/'absent.cdxml')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'items':items}))
    monkeypatch.setattr(cli,'Bridge',lambda:BatchBridge(tmp_path/'work'))
    assert cli.main(['batch','--manifest',str(manifest),'--output',str(tmp_path/'out')])==1
    assert json.loads(capsys.readouterr().out)['status']=='partial_failure'
