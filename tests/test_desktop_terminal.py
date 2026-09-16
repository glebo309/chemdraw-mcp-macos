"""The graphical installation also supplies a self-contained terminal entry point."""
import os
from pathlib import Path
import plistlib
import subprocess

import pytest

from chemdraw_macos import client_install, desktop_setup


def app_fixture(tmp_path):
    app = tmp_path/'download/ChemDraw MCP.app'
    runtime = app/'Contents/Resources/backend/chemdraw-runtime'
    runtime.parent.mkdir(parents=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'org.glebo309.chemdraw-mcp.setup', 'CFBundleVersion': '13'}))
    runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    runtime.chmod(0o700)
    return app


def test_finish_installs_terminal_commands_without_python_or_uv(tmp_path):
    app = app_fixture(tmp_path)
    home = tmp_path/'user space'
    home.mkdir()
    rc = home/'.zshrc'
    original = '# My settings\nexport KEEP_ME=retained\n'
    rc.write_text(original)
    result = client_install.install_and_connect(app, ['bundle'], home=home)
    assert rc.read_text().startswith(original)
    assert any(Path(p).read_text() == original for p in result['backups'])
    env = {**os.environ, 'ZDOTDIR': str(home), 'PATH': '/usr/bin:/bin'}
    cli = subprocess.run(['/bin/zsh', '-ic', 'chemdraw-mac identify --value "C C"'],
                         env=env, text=True, capture_output=True, check=True)
    assert cli.stdout.splitlines() == ['--cli', 'identify', '--value', 'C C']
    mcp = subprocess.run(['/bin/zsh', '-ic', 'chemdraw-mcp-macos --profile full'],
                         env=env, text=True, capture_output=True, check=True)
    assert mcp.stdout.splitlines() == ['--cli', 'serve', '--profile', 'full']
    before = rc.read_bytes()
    again = client_install.install_and_connect(app, ['bundle'], home=home)
    assert rc.read_bytes() == before
    assert again['backups'] == []


def test_failed_client_registration_rolls_back_terminal_changes(tmp_path):
    app = app_fixture(tmp_path)
    home = tmp_path/'user'
    codex = home/'.codex/config.toml'
    codex.parent.mkdir(parents=True)
    codex.write_text('[mcp_servers.glecko_chemdraw]\ncommand="other"\n')
    rc = home/'.zshrc'
    rc.write_text('# untouched\n')
    with pytest.raises(ValueError, match='already'):
        client_install.install_and_connect(app, ['codex'], home=home)
    assert rc.read_text() == '# untouched\n'
    assert not (home/'Library/Application Support/ChemDraw MCP/bin/chemdraw-mac').exists()


def test_symlink_shell_config_refused_before_client_writes(tmp_path):
    app = app_fixture(tmp_path)
    home = tmp_path/'user'
    home.mkdir()
    original = tmp_path/'my-shell-config'
    original.write_text('# untouched\n')
    (home/'.zshrc').symlink_to(original)
    with pytest.raises(ValueError, match='symbolic'):
        client_install.install_and_connect(app, ['codex'], home=home)
    assert original.read_text() == '# untouched\n'
    assert not (home/'.codex/config.toml').exists()


def test_bundled_cli_dispatch_preserves_arguments_and_selected_app(monkeypatch):
    from chemdraw_macos import cli
    monkeypatch.setattr(desktop_setup, 'read_settings', lambda: {'chemdraw_app': '/Applications/Selected.app'})
    monkeypatch.setattr(desktop_setup, 'validate_app', lambda path: path)
    # Register restoration even when the variable was initially absent: the
    # runtime sets it directly, outside monkeypatch's bookkeeping.
    monkeypatch.setenv('CHEMDRAW_APP', '/previous-selection')
    monkeypatch.setenv('CHEMDRAW_DESKTOP_EXTENSION', '1')
    def run(args):
        assert args == ['doctor', '--no-connect']
        assert os.environ['CHEMDRAW_APP'] == '/Applications/Selected.app'
        assert 'CHEMDRAW_DESKTOP_EXTENSION' not in os.environ
        return 7
    monkeypatch.setattr(cli, 'main', run)
    assert desktop_setup.runtime_main(['--cli', 'doctor', '--no-connect']) == 7


def test_full_profile_explains_electron_arrow_workflow():
    import asyncio
    from chemdraw_macos.server import get_server
    server = get_server('full')
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    required = {'chemdraw_inspect_annotations', 'chemdraw_annotate_document',
                'chemdraw_inspect_symbols', 'chemdraw_add_symbols',
                'chemdraw_suggest_routes', 'chemdraw_apply_route'}
    assert required <= names
    assert 'electron-pushing' in server.instructions
    assert 'chemdraw_annotate_document' in server.instructions
    assert 'mechanism' in server.instructions
