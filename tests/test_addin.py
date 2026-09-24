import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from chemdraw_macos.addin import AddinChannel, source_token, prepare_payload


EMPTY='<CDXML BondLength="18"><page id="1" BoundingBox="0 0 540 720" WidthPages="1" HeightPages="1"/></CDXML>'
MOLECULE='''<CDXML BondLength="18"><page id="1" BoundingBox="0 0 540 720"><fragment id="2" BoundingBox="50 50 78 65"><n id="3" p="50 60"/><n id="4" p="68 60" Element="8" NumHydrogens="1"><t><s>OH</s></t></n><b id="5" B="3" E="4"/></fragment></page></CDXML>'''


def http(channel, path, data=None, token=True, origin='null', host=None):
    headers={} if origin is None else {'Origin':origin}
    if token:headers['Authorization']='Bearer '+channel.secret
    if host:headers['Host']=host
    if data is not None:headers['Content-Type']='application/json'
    req=Request(channel.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    with urlopen(req,timeout=2) as response:return json.load(response)


def test_only_authenticated_local_file_origin_can_claim_jobs():
    with AddinChannel() as c:
        for options in ({'token':False},{'origin':'https://evil.example'},{'host':'evil.example'}):
            with pytest.raises(HTTPError) as e:http(c,'/job',**options)
            assert e.value.code==403
        assert http(c,'/job')=={}


def test_job_is_delivered_once_and_result_is_correlated():
    with AddinChannel() as c:
        answers=[]
        worker=threading.Thread(target=lambda:answers.append(c.request('read',timeout=2)))
        worker.start()
        job=http(c,'/job')
        assert job['operation']=='read' and job['id']
        assert http(c,'/job')=={}
        with pytest.raises(HTTPError):http(c,'/result',{'id':'wrong','cdxml':EMPTY})
        assert http(c,'/result',{'id':job['id'],'cdxml':EMPTY})=={'ok':True}
        worker.join(2)
        assert answers==[{'id':job['id'],'cdxml':EMPTY}]
        with pytest.raises(HTTPError):http(c,'/result',{'id':job['id'],'cdxml':EMPTY})


def test_native_webview_without_origin_still_requires_private_bearer():
    # ChemDraw 23's local add-in webview omits Origin, including with Authorization.
    with AddinChannel() as c:
        with pytest.raises(HTTPError) as error:http(c,'/job',origin=None,token=False)
        assert error.value.code==403
        assert http(c,'/job',origin=None)=={}


def test_native_webview_file_origin_can_return_authenticated_result():
    with AddinChannel() as c:
        with pytest.raises(HTTPError):http(c,'/job',origin='file://',token=False)
        answers=[]
        worker=threading.Thread(target=lambda:answers.append(c.request('read',timeout=2)))
        worker.start()
        job=http(c,'/job',origin=None)
        try:
            assert http(c,'/result',{'id':job['id'],'cdxml':EMPTY},origin='file://')=={'ok':True}
        finally:
            worker.join(2)
        assert answers==[{'id':job['id'],'cdxml':EMPTY}]


def test_timed_out_job_cannot_execute_later_or_be_retried():
    with AddinChannel() as c:
        with pytest.raises(RuntimeError,match='uncertain'):
            c.request('append',expected=EMPTY,cdxml=MOLECULE,timeout=.01)
        assert http(c,'/job')=={}
        with pytest.raises(RuntimeError,match='uncertain'):c.request('read',timeout=.01)


def test_no_arbitrary_javascript_or_operation():
    with AddinChannel() as c:
        with pytest.raises(ValueError):c.request('eval',script='alert(1)')
        with pytest.raises(ValueError):c.request('append',cdxml=MOLECULE)


def test_snapshot_token_ignores_only_transient_page_handle():
    assert source_token(EMPTY)==source_token(EMPTY.replace('id="1"','id="99"'))
    assert source_token(EMPTY)!=source_token(EMPTY.replace('540','541'))
    assert source_token(EMPTY)!=source_token(MOLECULE)


def test_payload_uses_target_page_and_remaps_ids():
    import xml.etree.ElementTree as E
    payload=E.fromstring(prepare_payload(EMPTY,MOLECULE))
    assert payload.find('page').get('BoundingBox')=='0 0 540 720'
    assert payload.find('.//n').get('p')=='50 60'
    ids=[e.get('id') for e in payload.iter() if e.get('id')]
    assert len(ids)==len(set(ids))
    assert payload.get('BondLength')=='18'


@pytest.mark.parametrize('bad',[
    MOLECULE.replace('50 60','900 60'),
    MOLECULE.replace('50 50 78 65','500 500 800 800'),
    MOLECULE.replace('<fragment','<group><fragment').replace('</fragment>','</fragment></group>'),
    MOLECULE.replace('BondLength="18"','BondLength="30"'),
])
def test_bad_payload_fails_before_native_write(bad):
    with pytest.raises(ValueError):prepare_payload(EMPTY,bad)


def test_payload_refuses_overlap_with_existing_content():
    with pytest.raises(ValueError,match='overlap'):prepare_payload(MOLECULE,MOLECULE)


def test_read_is_id_bound_and_uses_api_without_native_export(tmp_path):
    from contextlib import nullcontext
    from chemdraw_macos.addin import read_document
    class Bridge:
        lock=nullcontext()
        def _id(self,n):return n
        def _run(self,operation):
            if operation=='active_document_state':return [42,'Test','',False,0]
            assert operation=='active_document';return 42
        def documents(self):return {'documents':[{'document_id':42,'file':'','molecule_count':0}]}
    class Channel:
        def request(self,operation):
            assert operation=='read';return {'cdxml':EMPTY,'selection':EMPTY,'version':'1.6'}
    result=read_document(Bridge(),Channel(),42)
    assert result['cdxml']==EMPTY and result['source_token']==source_token(EMPTY)
    with pytest.raises(ValueError,match='active'):read_document(Bridge(),Channel(),7)


@pytest.mark.parametrize('reply,code,stage', [
    ({'error':'PRIVATE', 'error_code':'no_open_document','error_stage':'active_document'}, 'no_open_document','active_document'),
    ({'error':'PRIVATE','error_code':'native_api_error','error_stage':'document_cdxml'}, 'native_api_error','document_cdxml'),
    ({'version':'1.6'}, 'invalid_read_response','document_cdxml'),
    ({'cdxml':'not XML'}, 'invalid_cdxml','cdxml_validation'),
])
def test_read_errors_keep_safe_protocol_context(reply, code, stage):
    from contextlib import nullcontext
    from chemdraw_macos.addin import read_document
    class Bridge:
        lock = nullcontext()
        def _id(self, n): return n
        def _run(self, op): return 42
    class Channel:
        def request(self, op): return reply
    with pytest.raises(RuntimeError) as error: read_document(Bridge(), Channel(), 42)
    assert error.value.code == code
    assert error.value.stage == stage
    assert 'PRIVATE' not in str(error.value)


def test_upgrade_refreshes_existing_suffixed_addin_and_retains_credentials(tmp_path):
    from zipfile import ZipFile
    from chemdraw_macos.addin import DesktopAddin
    root = tmp_path/'Add-ins/ChemDraw MCP Native API'
    installed = root.with_name(root.name+'-12345678')
    with DesktopAddin(None, directory=root, setup=True) as backend:
        with ZipFile(backend.package) as archive: archive.extractall(installed)
    credential = root.with_name(root.name+'.connection.json')
    before = credential.read_bytes()
    html = installed/'main.html'
    html.write_text(html.read_text().replace('Document sent to local MCP', 'OLD CLIENT'))
    for _ in range(2):
        with DesktopAddin(None, directory=root, setup=True) as backend:
            assert backend.directory == installed
            assert 'OLD CLIENT' not in html.read_text()
            assert 'Document sent to local MCP' in html.read_text()
            assert credential.read_bytes() == before
            assert not root.exists()


def test_stale_append_never_dispatches_write(tmp_path):
    from contextlib import nullcontext
    from chemdraw_macos.addin import append_document
    class Bridge:
        lock=nullcontext()
        def _id(self,n):return n
        def _run(self,operation):
            return [42,'Test','',False,0] if operation=='active_document_state' else 42
        def documents(self):return {'documents':[{'document_id':42,'file':''}]}
    class Channel:
        def request(self,operation):
            assert operation=='read';return {'cdxml':EMPTY,'version':'1.6'}
    with pytest.raises(ValueError,match='changed'):
        append_document(Bridge(),Channel(),42,MOLECULE,'stale')


def test_exact_api_verification_allows_native_bounds_and_id_changes_not_translation():
    from chemdraw_macos.shared import verify_append
    native=MOLECULE.replace('50 50 78 65','49 51 80 68').replace('id="2"','id="100"')
    native=native.replace('<page ','<page WidthPages="1" HeightPages="1" ')
    assert all(verify_append(EMPTY,native,MOLECULE,exact_coordinates=True).values())
    moved=native.replace('50 60','51 60').replace('68 60','69 60')
    with pytest.raises(ValueError):verify_append(EMPTY,moved,MOLECULE,exact_coordinates=True)


def test_addin_package_is_local_authenticated_and_has_no_gui_drawing_calls(tmp_path):
    from zipfile import ZipFile
    from chemdraw_macos.addin import prepare_addin
    with AddinChannel() as c:
        package=prepare_addin(c,tmp_path)
        with ZipFile(package) as z:
            html=z.read('main.html').decode()
            metadata=json.loads(z.read('chemdraw-addin-metadata.json'))
        assert c.secret in html and c.url in html
        assert 'addCDXML' in html and 'getCDXML' in html
        assert 'Authorization' in html
        assert 'clipboard' not in html.lower() and 'keystroke' not in html.lower()
        assert metadata['isModalDialog'] is False
        assert metadata['name']=='ChemDraw MCP Native API'
        assert package.name=='ChemDraw MCP Native API.chemdrawaddin'
        assert package.stat().st_mode & 0o077 == 0


def test_addin_installer_survives_destination_replacement(tmp_path):
    import shutil
    from zipfile import ZipFile
    from chemdraw_macos.addin import prepare_addin
    destination = tmp_path/'Add-ins/ChemDraw MCP Native API'
    with AddinChannel() as channel:
        package = prepare_addin(channel, destination)
        assert not package.is_relative_to(destination)
        # Model an installer's replacement of its destination directory.
        shutil.rmtree(destination)
        with ZipFile(package) as archive:
            assert archive.testzip() is None
            archive.extractall(destination)
        assert (destination/'main.html').is_file()


def test_gui_preparation_does_not_preinstall_a_duplicate_name(tmp_path):
    from zipfile import ZipFile
    from chemdraw_macos.addin import DesktopAddin
    destination = tmp_path/'Add-ins/ChemDraw MCP Native API'
    with DesktopAddin(None, directory=destination, setup=True) as backend:
        assert not destination.exists()
        with ZipFile(backend.package) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {'main.html', 'chemdraw-addin-metadata.json'}


def test_gui_preparation_preserves_existing_installation_identity(tmp_path):
    from chemdraw_macos.addin import DesktopAddin
    destination = tmp_path/'Add-ins/ChemDraw MCP Native API'
    with DesktopAddin(None, directory=destination):
        before = json.loads((destination/'chemdraw-addin-metadata.json').read_text())
    with DesktopAddin(None, directory=destination, setup=True) as backend:
        assert json.loads((destination/'chemdraw-addin-metadata.json').read_text()) == before
        assert backend.package.is_file()


def test_setup_discovers_filename_suffixed_install_before_and_after_import(tmp_path):
    from contextlib import nullcontext
    from zipfile import ZipFile
    from chemdraw_macos.addin import DesktopAddin
    root = tmp_path/'Add-ins/ChemDraw MCP Native API'
    installed = root.with_name(root.name + '-f9aa03bb')
    class Bridge:
        lock = nullcontext()
        def _run(self, operation, path):
            assert path == str(installed)
            return True
    with DesktopAddin(Bridge(), directory=root, setup=True) as backend:
        with ZipFile(backend.package) as archive: archive.extractall(installed)
        assert backend.connect()['status'] == 'connected'
        assert backend.directory == installed
    with DesktopAddin(None, directory=root, setup=True) as backend:
        assert backend.directory == installed
        assert not root.exists()
    assert not installed.with_name(installed.name + '.connection.json').exists()


def test_renamed_addin_discovery_does_not_adopt_another_connection(tmp_path):
    from chemdraw_macos.addin import DesktopAddin, installed_addin_directory, prepare_addin
    root = tmp_path/'ChemDraw MCP Native API'
    with DesktopAddin(None, directory=root, setup=True):
        with AddinChannel() as other:
            prepare_addin(other, root.with_name(root.name + '-12345678'))
        assert installed_addin_directory(root) == root


def test_session_setup_then_connect_does_not_create_documents(tmp_path):
    from contextlib import nullcontext
    from chemdraw_macos.addin import DesktopAddin
    calls=[]
    class Bridge:
        lock=nullcontext()
        installed=False
        def _run(self,op,*args):
            calls.append(op)
            if op=='addin_available':return self.installed
            assert op=='addin_open'
    b=Bridge()
    with DesktopAddin(b,directory=tmp_path) as session:
        setup=session.connect()
        assert setup['status']=='needs_setup'
        assert setup['code']=='addin_command_unavailable'
        assert 'Preferences > Directories' in setup['next_action']
        assert 'files are present' in setup['message']
        b.installed=True
        assert session.connect()['status']=='connected'
        assert session.connect()['status']=='connected'
    assert calls.count('addin_open')==1
    assert set(calls)=={'addin_available','addin_open'}


def test_mcp_tools_reach_the_addin_backend(monkeypatch):
    from chemdraw_macos import server
    calls=[]
    class Backend:
        def connect(self):calls.append('connect');return {'status':'connected'}
        def read(self,document_id):calls.append(('read',document_id));return {'cdxml':EMPTY}
        def append(self,*args):calls.append(('append',args));return {'status':'completed'}
    monkeypatch.setattr(server,'addin_backend',lambda:Backend())
    assert server.chemdraw_addin_connect()['status']=='connected'
    assert server.chemdraw_addin_read_document(42)['cdxml']==EMPTY
    assert server.chemdraw_addin_append_cdxml(42,MOLECULE,'token')['status']=='completed'
    assert calls==['connect',('read',42),('append',(42,MOLECULE,'token'))]


def test_cli_reaches_the_same_addin_backend(monkeypatch,tmp_path,capsys):
    from chemdraw_macos import cli,addin
    calls=[]
    class Backend:
        def __init__(self,bridge):pass
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('close')
        def connect(self):calls.append('connect');return {'status':'needs_setup'}
        def read(self,did):calls.append(('read',did));return {'cdxml':EMPTY}
        def append(self,*args):calls.append(('append',args));return {'status':'completed'}
    monkeypatch.setattr(addin,'DesktopAddin',Backend)
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    payload=tmp_path/'payload.cdxml';payload.write_text(MOLECULE)
    assert cli.main(['addin-connect'])==0
    assert cli.main(['addin-read','42'])==0
    assert cli.main(['addin-append','42','--input',str(payload),'--source-token','fresh'])==0
    assert calls==['connect','close',('read',42),'close',('append',(42,MOLECULE,'fresh')),'close']


def test_native_addin_dispatch_activates_only_when_opening_connection_panel():
    from pathlib import Path
    text=Path('chemdraw_macos/native.applescript').read_text()
    assert 'if operation is "active_document"' in text
    assert 'if operation is "addin_available"' in text
    assert 'if operation is "addin_open"' in text
    opening=text.split('if operation is "addin_open" then',1)[1].split('end if',1)[0]
    assert 'activate' in opening
    reading=text.split('if operation is "active_document" then',1)[1].split('end if',1)[0]
    assert 'activate' not in reading


def test_installed_addin_endpoint_survives_mcp_process_reconnect(tmp_path):
    from chemdraw_macos.addin import DesktopAddin
    with DesktopAddin(None,directory=tmp_path) as first:
        endpoint=first.channel.url;secret=first.channel.secret
        with pytest.raises(OSError):DesktopAddin(None,directory=tmp_path)
    with DesktopAddin(None,directory=tmp_path) as second:
        assert second.channel.url==endpoint and second.channel.secret==secret
