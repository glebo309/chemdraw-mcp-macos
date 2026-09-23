import io
import json
import plistlib
from pathlib import Path

import pytest

from chemdraw_macos import desktop_setup as setup


def test_welcome_reuses_native_animation_and_small_author_credit():
    data = setup.welcome_data()
    assert data['credit'] == 'Created by Glenn Bojanov'
    assert len(data['molecules']) == 9
    assert all(m['sprites'] for m in data['molecules'])
    assert data['renderer'] == 'native ChemDraw'


def test_readiness_never_confuses_local_dependencies_with_live_connection():
    assert setup.present_diagnostic({'status': 'local_ready'})['ready'] is False
    assert setup.present_diagnostic({'status': 'ready', 'shared_drawing_ready': False})['ready'] is False
    result = setup.present_diagnostic({'status': 'ready', 'shared_drawing_ready': True})
    assert result['ready'] is True
    assert 'drawing' not in result['title'].lower()


@pytest.mark.parametrize('status', ['needs_setup', 'needs_document', 'busy', 'unavailable', 'basic_only'])
def test_all_failure_states_have_graphical_next_step(status):
    value = setup.present_diagnostic({'status': status, 'error': 'internal detail'})
    assert not value['ready']
    assert value['message']
    assert 'uv ' not in value['message']
    assert 'Terminal' not in value['message']


def test_setup_cannot_finish_without_successful_live_check(tmp_path):
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    with pytest.raises(ValueError, match='connection'):
        session.dispatch({'action': 'finish'})
    assert not (tmp_path/'settings.json').exists()


def test_prepare_occupied_endpoint_is_recoverable_not_raw_error(monkeypatch, tmp_path):
    import errno
    from chemdraw_macos import addin
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    session.bridge = object()
    session.last_diagnostic = {'status': 'ready', 'shared_drawing_ready': True}
    def occupied(*args, **kwargs):
        raise OSError(errno.EADDRINUSE, 'Address already in use')
    monkeypatch.setattr(addin, 'get_backend', occupied)
    value = session.dispatch({'action': 'prepare'})
    assert value['status'] == 'busy' and not value['ready']
    assert 'Errno' not in value['message']
    assert 'Nothing needs reinstalling' in value['message']
    assert session.last_diagnostic['status'] == 'busy'
    with pytest.raises(ValueError, match='connection'):
        session.dispatch({'action': 'finish'})


def test_prepare_does_not_misdiagnose_other_os_errors(monkeypatch, tmp_path):
    import errno
    from chemdraw_macos import addin
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    session.bridge = object()
    def denied(*args, **kwargs):
        raise OSError(errno.EACCES, 'Permission denied')
    monkeypatch.setattr(addin, 'get_backend', denied)
    with pytest.raises(OSError) as error:
        session.dispatch({'action': 'prepare'})
    assert error.value.errno == errno.EACCES


def test_choose_app_rejects_non_chemdraw_and_stores_valid_choice(tmp_path):
    app = tmp_path/'ChemDraw Test.app'
    (app/'Contents').mkdir(parents=True)
    plist = app/'Contents/Info.plist'
    plist.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'example.unrelated'}))
    with pytest.raises(ValueError, match='ChemDraw'):
        setup.validate_app(str(app))
    plist.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.revvity.ChemDraw'}))
    assert setup.validate_app(str(app)) == app.resolve()


def test_finish_releases_endpoint_before_saving_setup_state(tmp_path):
    events = []
    class Backend:
        def close(self): events.append('closed')
    class Bridge:
        _desktop_addin = Backend()
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    session.bridge = Bridge()
    session.last_diagnostic = {'status': 'ready', 'shared_drawing_ready': True}
    result = session.dispatch({'action': 'finish'})
    assert events == ['closed']
    assert result['status'] == 'finished'
    saved = json.loads((tmp_path/'settings.json').read_text())
    assert saved['setup_complete'] is True
    assert (tmp_path/'settings.json').stat().st_mode & 0o077 == 0


def test_protocol_is_json_only_and_unknown_commands_do_not_run(tmp_path):
    out = io.StringIO()
    setup.serve_setup(io.StringIO('{"action":"shell"}\n{"action":"welcome"}\n'), out,
                      session=setup.SetupSession(settings_path=tmp_path/'settings.json'))
    responses = [json.loads(line) for line in out.getvalue().splitlines()]
    assert responses[0]['status'] == 'error'
    assert responses[1]['credit'] == 'Created by Glenn Bojanov'
    assert '\x1b' not in out.getvalue()


def test_manifest_is_self_contained_macos_full_profile():
    data = setup.extension_manifest('0.10.0-rc.4', 'arm64')
    assert data['server']['type'] == 'binary'
    assert '${__dirname}/' in data['server']['mcp_config']['command']
    assert data['server']['mcp_config']['args'] == ['--desktop-serve']
    assert data['compatibility']['platforms'] == ['darwin']
    assert data['author']['name'] == 'Glenn Bojanov'
    assert 'Apple Silicon' in data['description']


def test_extension_waits_for_setup_and_reloads_app_choice(monkeypatch, tmp_path):
    from chemdraw_macos.core import app_location
    monkeypatch.setenv('CHEMDRAW_DESKTOP_EXTENSION', '1')
    monkeypatch.delenv('CHEMDRAW_APP', raising=False)
    monkeypatch.setattr(setup, 'settings_path', lambda: tmp_path/'settings.json')
    with pytest.raises(RuntimeError, match='setup window'):
        app_location()
    app = tmp_path/'ChemDraw.app'
    (app/'Contents').mkdir(parents=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.revvity.ChemDraw'}))
    (tmp_path/'settings.json').write_text(json.dumps({'setup_complete': True, 'chemdraw_app': str(app)}))
    assert app_location() == app


def test_failed_bundle_check_does_not_blame_mac_or_recommend_same_download():
    result = setup.present_diagnostic({'status': 'basic_only', 'cdxml_writer_available': False})
    assert 'incompatible' not in result['message']
    assert 'again' not in result['message']
    assert 'Save diagnostics' in result['message']


def test_selection_returns_validated_app_and_clears_previous_readiness(tmp_path):
    app = tmp_path/'ChemDraw.app'
    (app/'Contents').mkdir(parents=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.revvity.ChemDraw'}))
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    session.last_diagnostic = {'status': 'ready', 'shared_drawing_ready': True}
    value = session.dispatch({'action': 'choose_app', 'path': str(app)})
    assert value == {'status': 'selected', 'app': str(app)}
    assert not session.last_diagnostic


def test_export_installer_checks_zip_and_keeps_credentials_private(tmp_path):
    from zipfile import ZipFile
    package = tmp_path/'source.chemdrawaddin'
    with ZipFile(package, 'w') as archive:
        archive.writestr('main.html', 'private local connection')
        archive.writestr('chemdraw-addin-metadata.json', '{}')
    target = tmp_path/'Downloads/Connect ChemDraw.chemdrawaddin'
    target.parent.mkdir()
    setup.export_installer(package, target, tmp_path/'Add-ins/Native')
    assert target.read_bytes() == package.read_bytes()
    assert target.stat().st_mode & 0o077 == 0
    package.write_bytes(b'broken zip')
    with pytest.raises(ValueError, match='package'):
        setup.export_installer(package, target, tmp_path/'Add-ins/Native')
    assert target.read_bytes().startswith(b'PK')


def test_export_cannot_write_into_install_destination(tmp_path):
    with pytest.raises(ValueError, match='installation folder'):
        setup.export_installer(tmp_path/'source', tmp_path/'Native/pkg.chemdrawaddin', tmp_path/'Native')


@pytest.mark.parametrize('error,kind,code', [
    ('ChemDraw automation failed: Not authorized to send Apple events. (-1743)', 'automation_denied', -1743),
    ('Add-in response timed out; native state uncertain; no retry', 'addin_timeout', None),
    ('ChemDraw automation timed out, possibly due to a dialog.', 'automation_timeout', None),
    ('ChemDraw automation failed: event failed (-2700)', 'native_error', -2700),
    ('unexpected private information', 'unclassified_error', None),
])
def test_exported_diagnostics_keep_failure_category_without_private_text(error, kind, code):
    report = {'status': 'unavailable', 'error': error + ' /Users/secret/private.cdxml token=PRIVATE',
              'documents': [{'name': 'SECRET DRAWING'}], 'cdxml': '<CDXML>PRIVATE</CDXML>',
              'native_connection': 'responding',
              'desktop_api': {'status': 'not_tested', 'secret': 'PRIVATE'}}
    details = setup.present_diagnostic(report)['details']
    assert details['failure']['kind'] == kind
    assert details['failure']['native_error_code'] == code
    assert details['native_connection'] == 'responding'
    assert details['desktop_api'] == {'status': 'not_tested'}
    assert not any(word in json.dumps(details) for word in ('PRIVATE', '/Users/', 'SECRET DRAWING'))


def test_protocol_errors_also_include_shareable_diagnostics(tmp_path):
    class FailedSession:
        def dispatch(self, request):
            raise PermissionError(13, 'denied', '/Users/secret/key.connection.json')
        def close(self): pass
    output = io.StringIO()
    setup.serve_setup(io.StringIO('{"action":"prepare"}\n'), output, session=FailedSession())
    result = json.loads(output.getvalue())
    assert result['details']['failure']['exception_type'] == 'PermissionError'
    assert result['details']['failure']['os_error_code'] == 13
    assert '/Users/' not in json.dumps(result['details'])


def test_timeout_guidance_does_not_claim_missing_automation_authorization():
    value = setup.present_diagnostic({'status': 'unavailable', 'error':
        'Add-in response timed out; native state uncertain; no retry'})
    assert 'Automation' not in value['message']
    assert 'Save diagnostics' in value['message']
    denied = setup.present_diagnostic({'status': 'unavailable', 'error':
        'ChemDraw automation failed: Not authorized to send Apple events. (-1743)'})
    assert 'Automation' in denied['message']
