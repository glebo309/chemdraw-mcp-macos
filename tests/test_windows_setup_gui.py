"""Windows graphical setup: flow, private diagnostics, animation data and a window smoke test."""
import json
import sys

import pytest

from chemdraw_macos import windows_setup_gui as gui
from chemdraw_macos.private_files import is_private


def test_braille_sprites_decode_like_the_mac_animation():
    full = chr(0x28FF)  # all eight dots
    assert sorted(gui.sprite_dots({'rows': [full]})) == sorted(
        [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)])
    assert gui.sprite_dots({'rows': [' ' + chr(0x2801)]}) == [(2, 0)]


def test_layout_fits_the_canvas_with_margins():
    points, scale, left, top = gui.sprite_layout([(0, 0), (10, 4)], 200, 100)
    assert scale > 0 and left >= 12 and top >= 12
    assert points == [(0, 0), (10, 4)]


def test_flow_has_no_addin_step_on_windows():
    flow = gui.Flow()
    assert flow.step == 0
    assert flow.receive({'status': 'local_ready', 'ready': False}) is None and flow.step == 1
    flow.receive({'status': 'needs_document', 'ready': False})
    assert flow.step == 1 and flow.show_diagnostics
    flow.receive({'status': 'ready', 'ready': True})
    assert flow.step == 2 and flow.connected
    assert flow.receive({'status': 'finished'}) == 'finished' and flow.finished
    flow.receive({'status': 'selected'})
    assert flow.step == 0 and not flow.connected


def test_choosing_a_drawing_style_keeps_the_connection():
    flow = gui.Flow()
    flow.receive({'status': 'ready', 'ready': True})
    for status in ('style_selected', 'style_cleared'):
        assert flow.receive({'status': status}) is None
        assert flow.step == 2 and flow.connected and not flow.show_diagnostics


def test_diagnostics_autosave_is_private_and_free_of_raw_errors(tmp_path):
    record = gui.Diagnostics(session='abc-123')
    record.record('test', 'unavailable', {'failure': {'kind': 'chemdraw_not_running'}})
    path = record.autosave(tmp_path / 'Logs')
    assert path.name == 'setup-abc-123.txt' and is_private(path)
    text = path.read_text(encoding='utf-8')
    assert text.startswith('ChemDraw MCP setup diagnostics')
    body = json.loads(text.split('\n\n', 1)[1])
    assert body['events'][0]['details'] == {'failure': {'kind': 'chemdraw_not_running'}}
    with pytest.raises(ValueError):
        gui.Diagnostics(session='../x').autosave(tmp_path / 'Logs')


class FakeSession:
    def __init__(self):
        self.requests = []
        self.settings = {}

    def dispatch(self, request):
        self.requests.append(request)
        if request['action'] == 'welcome':
            from chemdraw_macos.welcome import load_molecules
            return {'status': 'welcome', 'molecules': load_molecules()}
        return {'status': 'local_ready', 'ready': False, 'title': 'Software checked', 'message': 'ok', 'details': {}}

    def close(self):
        pass


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk window smoke test on the Windows desktop')
def test_window_builds_animates_and_runs_a_check(tmp_path, monkeypatch):
    tk = pytest.importorskip('tkinter')
    session = FakeSession()
    try:
        app = gui.SetupWindow(session, logs=tmp_path / 'Logs', detect_app=lambda: None)
    except tk.TclError as exc:
        pytest.skip(f'No interactive desktop for Tk: {exc}')
    try:
        app.root.withdraw()
        for _ in range(5):
            app.animate_once(0.3)
        assert app.dot_items
        app.run_action({'action': 'check'})
        import time
        deadline = time.monotonic() + 5
        while app.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(.01)
        assert session.requests[-1] == {'action': 'check'}
        assert app.flow.step == 1
        assert (tmp_path / 'Logs').glob('setup-*.txt')
    finally:
        app.root.destroy()


def test_animation_runs_unless_explicitly_reduced():
    # Windows "Animation effects" is off on many machines and must not freeze the installer's sprite;
    # only an explicit opt-out does.
    from chemdraw_macos import windows_setup_gui as gui
    assert gui.reduced_motion({}) is False
    assert gui.reduced_motion({'CHEMDRAW_MCP_REDUCE_MOTION': '0'}) is False
    assert gui.reduced_motion({'CHEMDRAW_MCP_REDUCE_MOTION': '1'}) is True


def _window(tmp_path, session):
    tk = pytest.importorskip('tkinter')
    try:
        app = gui.SetupWindow(session, logs=tmp_path / 'Logs', detect_app=lambda: None)
    except tk.TclError as exc:
        pytest.skip(f'No interactive desktop for Tk: {exc}')
    app.root.withdraw()
    return app


def _texts(widget):
    found = []
    for child in widget.winfo_children():
        try:
            found.append(str(child.cget('text')))
        except Exception:
            pass
        found += _texts(child)
    return found


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk window on the Windows desktop')
def test_finish_sends_every_ticked_assistant_including_terminal_clis(tmp_path):
    app = _window(tmp_path, FakeSession())
    try:
        labels = ' | '.join(_texts(app.content))
        for name in ('Claude Desktop', 'Claude Code', 'Codex', 'Gemini CLI'):
            assert name in labels
        for variable in (app.claude, app.claude_code, app.codex, app.gemini):
            variable.set(True)
        sent = []
        app.run_action = sent.append
        app.flow.step = 2
        app.primary_action()
        assert sent == [{'action': 'finish', 'clients': ['claude', 'claude-code', 'codex', 'gemini']}]
    finally:
        app.root.destroy()


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk window on the Windows desktop')
def test_gemini_is_not_preselected_by_another_google_tool_folder(tmp_path, monkeypatch):
    # Antigravity creates ~/.gemini too; only Gemini CLI itself or its settings file counts.
    monkeypatch.setenv('USERPROFILE', str(tmp_path / 'home'))
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'home' / '.gemini' / 'antigravity').mkdir(parents=True)
    monkeypatch.setattr(gui.shutil, 'which', lambda name: None)
    app = _window(tmp_path, FakeSession())
    try:
        assert app.gemini.get() is False
    finally:
        app.root.destroy()
    (tmp_path / 'home' / '.gemini' / 'settings.json').write_text('{}', encoding='utf-8')
    app = _window(tmp_path, FakeSession())
    try:
        assert app.gemini.get() is True
    finally:
        app.root.destroy()


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk window on the Windows desktop')
def test_connected_step_offers_a_default_drawing_style(tmp_path):
    session = FakeSession()
    app = _window(tmp_path, session)
    try:
        app.flow.step = 2
        app.refresh()
        text = ' | '.join(_texts(app.content))
        assert 'Built-in house style' in text and 'Choose a ChemDraw style' in text
        session.settings['default_style'] = {'name': 'chemdraw template_Lab.cds', 'sha256': 'ab' * 32, 'preset': {
            'BondLength': '18', 'LineWidth': '1.587387085', 'BoldWidth': '2', 'LabelSize': '14', 'CaptionSize': '14',
            'font': '@MS Gothic'}}
        app.handle({'action': 'choose_style', 'path': 'x'}, {'status': 'style_selected'})
        text = ' | '.join(_texts(app.content))
        assert 'chemdraw template_Lab.cds' in text and '@MS Gothic, 14 pt labels, 1.59 pt bonds' in text
        assert 'Use built-in' in text and app.flow.step == 2
        sent = []
        app.run_action = sent.append
        app.use_builtin_style()
        assert sent == [{'action': 'clear_style'}]
    finally:
        app.root.destroy()


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk window on the Windows desktop')
def test_done_screen_shows_manual_claude_code_command_and_any_client_command(tmp_path):
    session = FakeSession()
    runtime = r'C:\Users\u\AppData\Local\ChemDraw MCP\current\chemdraw-runtime.exe'
    session.settings = {'installed_runtime': r'C:\x', 'runtime_command': runtime,
                        'claude_code': {'status': 'manual', 'message': 'Claude Code was not found on PATH.',
                                        'command': 'claude mcp add --scope user glecko_chemdraw -- "x" --desktop-serve'}}
    app = _window(tmp_path, session)
    try:
        app.flow.finished = True
        app.refresh()
        text = ' | '.join(_texts(app.content))
        assert 'claude mcp add --scope user glecko_chemdraw -- "x" --desktop-serve' in text
        assert f'"{runtime}" --desktop-serve' in text  # stdio command for any other MCP client
    finally:
        app.root.destroy()
