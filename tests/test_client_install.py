"""One shared installation; explicit, recoverable per-client registration."""
import json
import tomllib
from pathlib import Path

import pytest

from chemdraw_macos import desktop_setup as setup


def test_neutral_bundle_branding():
    manifest = setup.extension_manifest('0.10.0-rc.8', 'arm64')
    assert manifest['display_name'] == 'ChemDraw MCP'
    assert setup.APP_NAME == 'ChemDraw MCP.app'
    assert 'Claude' not in manifest['long_description']


def test_selected_clients_share_runtime_and_preserve_other_settings(tmp_path):
    from chemdraw_macos.client_install import connect_clients, SERVER_NAME
    runtime = tmp_path/'Applications/ChemDraw MCP.app/Contents/Resources/backend/chemdraw-runtime'
    claude = tmp_path/'Library/Application Support/Claude/claude_desktop_config.json'
    codex = tmp_path/'.codex/config.toml'
    claude.parent.mkdir(parents=True)
    codex.parent.mkdir()
    original_json = '{"preferences":{"theme":"dark"},"mcpServers":{"other":{"command":"other"}}}'
    original_toml = '# Keep my comments\nmodel = "my-model"\n[mcp_servers.other]\ncommand = "other"\n'
    claude.write_text(original_json)
    codex.write_text(original_toml)
    result = connect_clients(['claude', 'codex'], runtime, home=tmp_path)
    a = json.loads(claude.read_text())
    b = tomllib.loads(codex.read_text())
    assert a['preferences'] == {'theme': 'dark'}
    assert a['mcpServers']['other'] == b['mcp_servers']['other'] == {'command': 'other'}
    assert a['mcpServers'][SERVER_NAME]['command'] == b['mcp_servers'][SERVER_NAME]['command'] == str(runtime)
    assert b['mcp_servers'][SERVER_NAME]['tool_timeout_sec'] == 300
    assert a['mcpServers'][SERVER_NAME]['args'] == ['--desktop-serve']
    assert original_toml in codex.read_text()
    assert [Path(p).read_text() for p in result['backups']] == [original_json, original_toml]
    assert all(Path(p).stat().st_mode & 0o077 == 0 for p in result['backups'])
    assert connect_clients(['claude', 'codex'], runtime, home=tmp_path)['backups'] == []


def test_registration_is_opt_in_and_all_configs_preflight_before_writing(tmp_path):
    from chemdraw_macos.client_install import connect_clients, SERVER_NAME
    runtime = tmp_path/'runtime'
    codex = tmp_path/'.codex/config.toml'
    codex.parent.mkdir()
    codex.write_text(f'[mcp_servers.{SERVER_NAME}]\ncommand="someone-else"\n')
    before = codex.read_bytes()
    with pytest.raises(ValueError, match='already'):
        connect_clients(['claude', 'codex'], runtime, home=tmp_path)
    assert codex.read_bytes() == before
    assert not (tmp_path/'Library/Application Support/Claude/claude_desktop_config.json').exists()
    with pytest.raises(ValueError, match='Select'):
        connect_clients([], runtime, home=tmp_path)
    with pytest.raises(ValueError, match='Unsupported'):
        connect_clients(['grok'], runtime, home=tmp_path)


def test_codex_only_does_not_require_or_configure_claude(tmp_path):
    from chemdraw_macos.client_install import connect_clients
    connect_clients(['codex'], tmp_path/'runtime', home=tmp_path)
    assert (tmp_path/'.codex/config.toml').exists()
    assert not (tmp_path/'Library/Application Support/Claude').exists()


def test_symlink_config_refused(tmp_path):
    from chemdraw_macos.client_install import connect_clients
    codex = tmp_path/'.codex'
    codex.mkdir()
    original = tmp_path/'other.toml'
    original.write_text('model="do not touch"')
    (codex/'config.toml').symlink_to(original)
    with pytest.raises(ValueError, match='symbolic'):
        connect_clients(['codex'], tmp_path/'runtime', home=tmp_path)
    assert original.read_text() == 'model="do not touch"'


def test_shared_app_install_is_stable_and_versioned_without_deleting_old(tmp_path):
    import plistlib
    from chemdraw_macos.client_install import install_shared_app
    source = tmp_path/'download/ChemDraw MCP.app'
    (source/'Contents/Resources/backend').mkdir(parents=True)
    (source/'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'org.glebo309.chemdraw-mcp.setup', 'CFBundleVersion': '8'}))
    (source/'Contents/Resources/backend/chemdraw-runtime').write_text('fixture')
    installed = install_shared_app(source, home=tmp_path/'user')
    assert 'download' not in str(installed)
    assert installed.name == 'ChemDraw MCP.app'
    assert installed.exists()
    assert install_shared_app(source, home=tmp_path/'user') == installed
    assert source.exists()


def test_no_registration_until_finish_and_finish_failure_does_not_mark_complete(tmp_path, monkeypatch):
    session = setup.SetupSession(settings_path=tmp_path/'settings.json')
    with pytest.raises(ValueError, match='connection'):
        session.dispatch({'action': 'finish', 'clients': ['codex']})
    session.last_diagnostic = {'status': 'ready', 'shared_drawing_ready': True}
    def fail(clients):
        assert clients == ['codex']
        raise ValueError('registration failed')
    monkeypatch.setattr(session, 'install_clients', fail)
    with pytest.raises(ValueError, match='registration failed'):
        session.dispatch({'action': 'finish', 'clients': ['codex']})
    assert not session.path.exists()


def test_existing_claude_bundle_is_not_registered_twice(tmp_path):
    from chemdraw_macos.client_install import connect_clients
    extension = tmp_path/'Library/Application Support/Claude/Claude Extensions/local.mcpb.glenn-bojanov.chemdraw-macos'
    extension.mkdir(parents=True)
    (extension/'manifest.json').write_text(json.dumps({'name': 'chemdraw-macos'}))
    result = connect_clients(['claude', 'codex'], tmp_path/'runtime', home=tmp_path)
    assert result['bundle_clients'] == ['claude']
    assert not (tmp_path/'Library/Application Support/Claude/claude_desktop_config.json').exists()
    assert (tmp_path/'.codex/config.toml').exists()


def test_generic_mcpb_host_needs_no_vendor_config(tmp_path):
    from chemdraw_macos.client_install import connect_clients
    result = connect_clients(['bundle'], tmp_path/'runtime', home=tmp_path)
    assert result['clients'] == ['bundle']
    assert list(tmp_path.iterdir()) == []


def test_bundle_server_hands_off_to_shared_runtime_after_setup(tmp_path, monkeypatch):
    import sys
    from chemdraw_macos import server
    def unexpected(args):
        raise AssertionError('Bundle started its own runtime instead of handing off')
    monkeypatch.setattr(server, 'main', unexpected)
    app = tmp_path/'Library/Application Support/ChemDraw MCP/versions/8/ChemDraw MCP.app'
    runtime = app/'Contents/Resources/backend/chemdraw-runtime'
    runtime.parent.mkdir(parents=True)
    runtime.write_text('fixture')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(setup, 'read_settings', lambda: {'setup_complete': True, 'installed_app': str(app)})
    monkeypatch.setattr(sys, 'executable', str(tmp_path/'download/runtime'))
    class HandedOff(Exception): pass
    def execv(command, args):
        assert command == str(runtime)
        assert args == [str(runtime), '--desktop-serve']
        raise HandedOff()
    monkeypatch.setattr(setup.os, 'execv', execv)
    with pytest.raises(HandedOff):
        setup.runtime_main(['--desktop-serve'])
