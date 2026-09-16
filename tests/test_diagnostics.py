from contextlib import nullcontext
from pathlib import Path
import plistlib

import pytest


@pytest.fixture
def environment(tmp_path,monkeypatch):
    from chemdraw_macos import diagnostics as d
    app=tmp_path/'Test.app';(app/'Contents').mkdir(parents=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString':'23.test'}))
    monkeypatch.setattr(d.platform,'system',lambda:'Darwin')
    monkeypatch.setattr(d,'app_location',lambda:app)
    class Bridge:
        lock=nullcontext()
        def documents(self):return {'documents':[{'document_id':7,'file':''}]}
        def _run(self,op,*args):
            if op=='active_document':return 7
            if op=='addin_available':return True
            pytest.fail('Unexpected native call: '+op)
    return d,Bridge()


def test_offline_doctor_checks_actual_writer_but_never_claims_live_ready(environment,monkeypatch):
    d,b=environment
    monkeypatch.setattr(d,'Bridge',lambda **k:pytest.fail('Offline check contacted ChemDraw'))
    report=d.doctor(connect=False)
    assert report['status']=='local_ready'
    assert report['cdxml_writer_available'] is True
    assert report['shared_drawing_ready'] is False
    assert report['desktop_api']['status']=='not_tested'
    assert report['architecture'] and report['package_version'] and report['rdkit_version']


def test_missing_writer_is_not_ready(environment,monkeypatch):
    from rdkit import Chem
    d,b=environment
    monkeypatch.setattr(Chem,'HasChemDrawCDXSupport',lambda:False)
    report=d.doctor(connect=False)
    assert report['cdxml_writer_available'] is False
    assert report['status']=='basic_only'
    assert report['shared_drawing_ready'] is False


def test_connected_doctor_reuses_backend_and_reads_without_drawing(environment):
    d,b=environment
    class Backend:
        closed=False
        def read(self,did):
            assert did==7
            return {'api_version':'1.6','cdxml':'SECRET DRAWING MUST NOT BE REPORTED'}
    b._desktop_addin=Backend()
    report=d.doctor(bridge=b)
    assert report['status']=='ready'
    assert report['shared_drawing_ready'] is True
    assert report['desktop_api']['api_version']=='1.6'
    assert 'SECRET' not in str(report)


def test_endpoint_owned_by_other_client_is_busy_not_missing_installation(environment,monkeypatch):
    import errno
    d,b=environment
    monkeypatch.setattr(Path,'is_file',lambda self:True)
    def busy(*a):raise OSError(errno.EADDRINUSE,'Address already in use')
    monkeypatch.setattr('chemdraw_macos.addin.get_backend',busy)
    report=d.doctor(bridge=b)
    assert report['status']=='busy'
    assert report['desktop_api']['code']=='endpoint_in_use'
    assert report['shared_drawing_ready'] is False


def test_missing_addin_reports_setup_without_installing(environment,monkeypatch):
    d,b=environment
    monkeypatch.setattr(Path,'is_file',lambda self:False)
    monkeypatch.setattr('chemdraw_macos.addin.get_backend',lambda *a:pytest.fail('Doctor installed an add-in'))
    report=d.doctor(bridge=b)
    assert report['status']=='needs_setup'
    assert report['desktop_api']['code']=='addin_files_missing'


def test_no_canvas_reports_unverified_read_not_success(environment):
    d,b=environment
    b.documents=lambda:{'documents':[]}
    report=d.doctor(bridge=b)
    assert report['status']=='needs_document'
    assert report['shared_drawing_ready'] is False


def test_mcp_doctor_uses_its_existing_bridge(monkeypatch):
    from chemdraw_macos import server
    sentinel=object()
    monkeypatch.setattr(server,'bridge',lambda:sentinel)
    monkeypatch.setattr(server,'doctor',lambda **kw:kw)
    assert server.chemdraw_doctor()=={'bridge':sentinel}


def test_prepared_but_unregistered_addin_is_not_a_licence_or_permission_error(environment):
    d, b = environment
    class Backend:
        closed = False
        def connect(self):
            return {'status': 'needs_setup', 'code': 'addin_command_unavailable',
                    'next_action': 'Enable the add-in in Add-in Manager.'}
        def read(self, did): pytest.fail('Must not read an unregistered add-in')
    b._desktop_addin = Backend()
    report = d.doctor(bridge=b)
    assert report['status'] == 'needs_setup'
    assert report['native_connection'] == 'responding'
    assert 'Add-in Manager' in report['help']
