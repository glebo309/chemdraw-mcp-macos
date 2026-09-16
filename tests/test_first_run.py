import asyncio
from contextlib import nullcontext
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def setup_run(tmp_path, monkeypatch):
    from chemdraw_macos import first_run as f
    environment = {'status': 'ready', 'app': '/Applications/Test.app',
                   'chemistry_validator_available': True, 'rasterizer_available': True,'cdxml_writer_available':True,
                   'version': 'test', 'native_connection': 'not tested'}
    monkeypatch.setattr(f, 'doctor', lambda connect=False: dict(environment))
    calls = []
    class Bridge:
        workspace = tmp_path / 'workspace'
        lock = nullcontext()
        def documents(self):
            calls.append('connect')
            return {'documents': []}
        def close(self, *args):
            pytest.fail('First-run wrapper must not close or retry uncertain native work')
    bridge = Bridge()
    def draw(b, structures, output_dir, **options):
        calls.append('draw')
        assert b is bridge
        assert [x['label'] for x in structures] == ['Caffeine', 'Aspirin']
        out = Path(output_dir)
        out.mkdir()
        artifacts = {}
        for fmt in ('cdxml', 'svg', 'png'):
            p = out / ('figure.' + fmt)
            p.write_text('test fixture')
            artifacts[fmt] = str(p)
        return {'document': {'document_id': 99},
                'output_dir': str(out), 'artifacts': artifacts,
                'audit': {'status': 'checks_passed', 'checks': {'preserved': True},
                          'visual_review': 'required'}}
    monkeypatch.setattr(f, 'draw_structures', draw)
    return f, environment, bridge, calls


def test_first_run_creates_unique_reviewable_result(setup_run):
    f, env, bridge, calls = setup_run
    stages = []
    results = [f.run_first_run(bridge_factory=lambda: bridge,
                             progress=lambda stage, label: stages.append(stage)) for _ in range(2)]
    assert results[0]['output_dir'] != results[1]['output_dir']
    assert calls == ['connect', 'draw', 'connect', 'draw']
    assert stages[:4] == ['installation', 'connection', 'drawing', 'exports']
    assert all(r['status'] == 'checks_passed' for r in results)
    assert results[0]['visual_review'] == 'required'
    assert json.loads(Path(results[0]['report']).read_text()) == results[0]
    assert 'review' not in results[0]
    assert not list(Path(results[0]['output_dir']).glob('*.html'))


@pytest.mark.parametrize('field,value', [('status', 'unavailable'),
    ('chemistry_validator_available', False), ('rasterizer_available', False),('cdxml_writer_available',False)])
def test_failed_installation_never_connects_or_creates_files(setup_run, field, value):
    f, env, bridge, calls = setup_run
    env[field] = value
    with pytest.raises(f.FirstRunError) as exc:
        f.run_first_run(bridge_factory=lambda: bridge)
    assert exc.value.report['stage'] == 'installation'
    assert exc.value.report['help']
    assert not calls and not bridge.workspace.exists()


def test_existing_destination_is_preserved_without_connecting(setup_run, tmp_path):
    f, env, bridge, calls = setup_run
    marker = tmp_path / 'keep.txt'; marker.write_text('untouched')
    with pytest.raises(f.FirstRunError):
        f.run_first_run(str(tmp_path), bridge_factory=lambda: bridge)
    assert marker.read_text() == 'untouched' and not calls


@pytest.mark.parametrize('failure,status', [('busy', 'busy'), ('uncertain', 'uncertain')])
def test_failures_are_not_retried_or_closed(setup_run, monkeypatch, failure, status):
    from chemdraw_macos.native_lock import NativeBusy
    from chemdraw_macos.batch import NativeUncertain
    f, env, bridge, calls = setup_run
    def fail(*args, **kwargs):
        calls.append('failed-once')
        raise (NativeBusy('busy') if failure == 'busy' else NativeUncertain('timeout'))
    monkeypatch.setattr(f, 'draw_structures', fail)
    with pytest.raises(f.FirstRunError) as exc:
        f.run_first_run(bridge_factory=lambda: bridge)
    assert exc.value.report['status'] == status
    assert calls.count('failed-once') == 1


def test_partial_exports_cannot_report_success(setup_run, monkeypatch):
    f, env, bridge, calls = setup_run
    original = f.draw_structures
    def partial(*args, **kwargs):
        result = original(*args, **kwargs)
        Path(result['artifacts']['png']).unlink()
        return result
    monkeypatch.setattr(f, 'draw_structures', partial)
    with pytest.raises(f.FirstRunError) as exc:
        f.run_first_run(bridge_factory=lambda: bridge)
    assert exc.value.report['stage'] == 'exports'


@pytest.mark.parametrize('verified', [True, False])
def test_first_run_accepts_only_verified_page_expansion(setup_run, monkeypatch, verified):
    f, env, bridge, calls = setup_run
    original = f.draw_structures
    def expanded(*args, **kwargs):
        result = original(*args, **kwargs)
        result['audit']['checks'].update(page_unchanged=False, page_expansion_verified=verified)
        return result
    monkeypatch.setattr(f, 'draw_structures', expanded)
    if verified:
        assert f.run_first_run(bridge_factory=lambda: bridge)['status'] == 'checks_passed'
    else:
        with pytest.raises(f.FirstRunError):
            f.run_first_run(bridge_factory=lambda: bridge)


def test_native_session_gate_covers_connection_and_draw(setup_run, monkeypatch):
    f, env, bridge, calls = setup_run
    class Gate:
        active = False
        def __enter__(self): self.active = True
        def __exit__(self, *args): self.active = False
    gate = Gate(); bridge.lock = gate
    original = f.draw_structures
    def checked(*a, **kw):
        assert gate.active
        return original(*a, **kw)
    monkeypatch.setattr(f, 'draw_structures', checked)
    f.run_first_run(bridge_factory=lambda: bridge)
    assert not gate.active


def test_ring_frames_are_ascii_and_move_one_marker():
    from chemdraw_macos.first_run import ring_frame
    frames = [ring_frame(i, 'Drawing') for i in range(6)]
    assert len(set(frames)) == 6
    assert all(x.isascii() and x.count('*') == 1 and len(x.splitlines()) == 5 for x in frames)


def test_noninteractive_progress_is_silent_and_thread_stops():
    from chemdraw_macos.first_run import TerminalProgress
    stream = io.StringIO()
    with TerminalProgress(stream, enabled=False) as progress:
        progress.update('drawing', 'Drawing')
    assert stream.getvalue() == ''
    with TerminalProgress(stream, enabled=True) as animated:
        animated.update('drawing', 'Drawing')
    assert not animated.thread.is_alive()
    assert '\x1b[' in stream.getvalue()


def test_cli_json_and_noninteractive_output_do_not_open_browser(setup_run, monkeypatch, capsys):
    from chemdraw_macos import cli
    f, env, bridge, calls = setup_run
    monkeypatch.setattr(f, 'Bridge', lambda **kw: bridge)
    monkeypatch.setattr(f.subprocess, 'run', lambda *a,**k: pytest.fail('Browser opened'))
    assert cli.main(['first-run', '--json']) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)['status'] == 'checks_passed'
    assert captured.err == ''
    assert cli.main(['first-run']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'checks_passed'


def test_cli_failure_is_structured_nonzero(setup_run, capsys):
    from chemdraw_macos import cli
    f, env, bridge, calls = setup_run
    env['chemistry_validator_available'] = False
    assert cli.main(['first-run', '--json']) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)['stage'] == 'installation'
    assert captured.err == ''


def test_interrupted_native_run_retains_phase_and_output_path(setup_run, monkeypatch):
    f, env, bridge, calls = setup_run
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(f, 'draw_structures', interrupted)
    with pytest.raises(f.FirstRunError) as exc:
        f.run_first_run(bridge_factory=lambda: bridge)
    assert exc.value.report['status'] == 'interrupted'
    assert exc.value.report['stage'] == 'drawing'
    assert exc.value.report['output_dir']


def test_cli_interactive_never_opens_browser_and_accepts_legacy_no_open(setup_run, monkeypatch, capsys):
    from chemdraw_macos import cli
    f, env, bridge, calls = setup_run
    monkeypatch.setattr(f, 'Bridge', lambda **kw: bridge)
    monkeypatch.setattr(f.sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(f.sys.stderr, 'isatty', lambda: True)
    monkeypatch.setattr(f.subprocess, 'run', lambda *a,**k: pytest.fail('Browser opened'))
    assert cli.main(['first-run', '--no-animation']) == 0
    captured = capsys.readouterr()
    assert 'Native smoke test passed' in captured.out
    assert 'Review:' not in captured.out
    assert '\x1b' not in captured.err
    assert cli.main(['first-run', '--no-animation', '--no-open']) == 0


def test_mcp_exposes_same_workflow_without_browser_or_animation(monkeypatch):
    from chemdraw_macos import server
    monkeypatch.setattr(server, 'run_first_run', lambda output_dir=None, **kw: {'output_dir': output_dir})
    assert server.chemdraw_first_run('/new/output') == {'output_dir': '/new/output'}
    tool = next(t for t in asyncio.run(server.mcp.list_tools()) if t.name == 'chemdraw_first_run')
    assert tool.annotations.readOnlyHint is False
    assert 'open' not in tool.inputSchema['properties']
