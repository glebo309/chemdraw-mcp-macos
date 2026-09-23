"""Terminal onboarding uses the same setup protocol without launching its GUI."""
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


class Session:
    def __init__(self, *, ready=True, busy=False):
        self.calls = []
        self.closed = False
        self.ready = ready
        self.busy = busy

    def dispatch(self, request):
        self.calls.append(request)
        action = request['action']
        if action == 'check':
            return {'status': 'local_ready', 'details': {'cdxml_writer_available': True, 'rasterizer_available': True}}
        if action == 'prepare':
            return {'status': 'busy', 'message': 'Another assistant is connected'} if self.busy else {'status': 'prepared', 'existing_files': True}
        if action == 'export_installer':
            Path(request['path']).write_bytes(b'fixture')
            return {'status': 'exported', 'path': request['path']}
        if action == 'test':
            return {'status': 'ready' if self.ready else 'needs_document', 'ready': self.ready,
                    'message': 'Open a drawing'}
        raise AssertionError('Unexpected operation: ' + action)

    def close(self):
        self.closed = True


def arguments(**kwargs):
    return SimpleNamespace(app=None, client=[], no_animation=True, **kwargs)


def test_setup_exports_visible_private_installer_even_when_assets_exist(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    session = Session()
    out = io.StringIO()
    result = run_setup(arguments(), session=session, home=tmp_path,
                       input_fn=lambda prompt: '', stream=out)
    assert result == 0 and session.closed
    assert [x['action'] for x in session.calls] == ['check', 'prepare', 'export_installer', 'test']
    assert 'Add from file' in out.getvalue() and 'Downloads' in out.getvalue()
    assert 'Document read: PASS' in out.getvalue()
    assert not (tmp_path/'.codex').exists()
    assert not (tmp_path/'Library').exists()


def test_setup_never_overwrites_previous_download(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    downloads = tmp_path/'Downloads'
    downloads.mkdir()
    original = downloads/'ChemDraw MCP Native API.chemdrawaddin'
    original.write_text('keep me')
    session = Session()
    run_setup(arguments(), session=session, home=tmp_path, input_fn=lambda p: '', stream=io.StringIO())
    exported = next(x['path'] for x in session.calls if x['action'] == 'export_installer')
    assert Path(exported) != original and original.read_text() == 'keep me'


def test_download_uniqueness_does_not_change_chemdraw_installation_name(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    session = Session()
    run_setup(arguments(), session=session, home=tmp_path, input_fn=lambda p: '', stream=io.StringIO())
    exported = Path(next(x['path'] for x in session.calls if x['action'] == 'export_installer'))
    assert exported.name == 'ChemDraw MCP Native API.chemdrawaddin'
    assert exported.parent.parent == tmp_path/'Downloads'


def test_failed_connection_never_registers_clients_and_does_not_retry(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    session = Session(ready=False)
    out = io.StringIO()
    args = arguments()
    args.client = ['codex']
    assert run_setup(args, session=session, home=tmp_path, input_fn=lambda p: '', stream=out) == 1
    assert not (tmp_path/'.codex').exists()
    assert session.closed and sum(x['action'] == 'test' for x in session.calls) == 1
    assert 'PASS' not in out.getvalue()


def test_busy_stops_before_installer_export(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    session = Session(busy=True)
    assert run_setup(arguments(), session=session, home=tmp_path,
                     input_fn=lambda p: pytest.fail('Must not prompt'), stream=io.StringIO()) == 1
    assert session.closed and not (tmp_path/'Downloads').exists()


def test_interrupt_restores_terminal_and_closes_transport(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    session = Session()
    def interrupt(prompt): raise KeyboardInterrupt
    assert run_setup(arguments(), session=session, home=tmp_path,
                     input_fn=interrupt, stream=io.StringIO()) == 130
    assert session.closed


def test_selected_client_uses_stable_cli_server_without_desktop_launcher(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    import tomllib
    session = Session()
    args = arguments()
    args.client = ['codex']
    executable = tmp_path/'tools/bin/chemdraw-mcp-macos'
    executable.parent.mkdir(parents=True)
    executable.write_text('fixture')
    assert run_setup(args, session=session, home=tmp_path, input_fn=lambda p: '',
                     stream=io.StringIO(), executable=executable) == 0
    config = tomllib.loads((tmp_path/'.codex/config.toml').read_text())
    entry = config['mcp_servers']['glecko_chemdraw']
    assert entry['command'] == str(executable)
    assert entry['args'] == ['--profile', 'full']
    assert entry['tool_timeout_sec'] == 300
    assert session.closed


def test_setup_cli_is_reachable_and_noninteractive_requires_real_terminal(monkeypatch, capsys):
    from chemdraw_macos.cli import main
    monkeypatch.setattr('sys.stdin', io.StringIO())
    assert main(['setup', '--no-animation']) == 1
    assert 'interactive terminal' in capsys.readouterr().err


def test_checkout_completion_prints_runnable_first_run_command(tmp_path, monkeypatch):
    from chemdraw_macos.terminal_setup import run_setup
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    out = io.StringIO()
    assert run_setup(arguments(), session=Session(), home=tmp_path,
                     input_fn=lambda _: '', stream=out) == 0
    assert 'uv run --locked --extra chemistry chemdraw-mac first-run' in out.getvalue()


def test_bundled_setup_uses_shared_terminal_launchers(tmp_path, monkeypatch):
    import sys
    import shlex
    from chemdraw_macos.terminal_setup import run_setup
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    out = io.StringIO()
    assert run_setup(arguments(), session=Session(), home=tmp_path,
                     input_fn=lambda _: '', stream=out) == 0
    executable = tmp_path/'Library/Application Support/ChemDraw MCP/bin/chemdraw-mac'
    assert shlex.join([str(executable), 'first-run']) in out.getvalue()
    assert 'uv run' not in out.getvalue()


def test_terminal_failure_saves_private_shareable_report(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    class FailedRead(Session):
        def dispatch(self, request):
            if request['action'] == 'test':
                from chemdraw_macos.desktop_setup import present_diagnostic
                return present_diagnostic({'status': 'unavailable', 'native_connection': 'responding',
                    'error': 'Add-in response timed out; native state uncertain; no retry',
                    'documents': [{'name': 'SECRET DRAWING'}], 'secret': 'PRIVATE KEY'})
            return super().dispatch(request)
    out = io.StringIO()
    assert run_setup(arguments(), session=FailedRead(), home=tmp_path,
                     input_fn=lambda _: '', stream=out) == 1
    reports = list((tmp_path/'Library/Logs/ChemDraw MCP').glob('*.txt'))
    assert len(reports) == 1
    text = reports[0].read_text()
    assert 'addin_timeout' in text and 'timestamp' in text and 'terminal' in text
    assert 'SECRET DRAWING' not in text and 'PRIVATE KEY' not in text
    assert str(reports[0]) in out.getvalue()
    assert reports[0].stat().st_mode & 0o077 == 0


def test_terminal_report_write_failure_keeps_copyable_report(tmp_path):
    from chemdraw_macos.terminal_setup import run_setup
    # An existing non-directory makes the report destination unusable.
    (tmp_path/'Library').write_text('untouched')
    out = io.StringIO()
    assert run_setup(arguments(), session=Session(busy=True), home=tmp_path,
                     input_fn=lambda _: '', stream=out) == 1
    assert 'Could not save diagnostics' in out.getvalue()
    assert 'BEGIN CHEMDRAW DIAGNOSTICS' in out.getvalue()
    assert '"status": "busy"' in out.getvalue()
    assert (tmp_path/'Library').read_text() == 'untouched'
