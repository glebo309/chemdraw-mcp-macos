import io
import os
import re
import time

import pytest

from test_terminal_setup import Session, arguments


class TTY(io.StringIO):
    def isatty(self): return True


def animated(monkeypatch):
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.setattr('shutil.get_terminal_size', lambda *a: os.terminal_size((110, 34)))
    args = arguments()
    args.no_animation = False
    return args


def test_one_themed_session_animates_while_waiting_and_holds_success(tmp_path, monkeypatch):
    from chemdraw_macos.terminal_setup import run_setup
    out = TTY()
    prompts = []
    def waiting(prompt):
        prompts.append(prompt)
        before = out.getvalue().count('\x1b[H')
        time.sleep(.2)
        assert out.getvalue().count('\x1b[H') > before
        if len(prompts) == 1:
            assert 'Add from file' in out.getvalue()
        else:
            assert 'Document read: PASS' in out.getvalue()
        return ''
    assert run_setup(animated(monkeypatch), session=Session(), home=tmp_path,
                     stream=out, input_fn=waiting) == 0
    value = out.getvalue()
    assert len(prompts) == 2
    assert value.count('\x1b[?1049h') == value.count('\x1b[?1049l') == 1
    assert '\x1b[?25h' in value
    assert '38;5;218' in value
    assert 'local connection key' in value


@pytest.mark.parametrize('failure', [KeyboardInterrupt, RuntimeError])
def test_animated_exit_always_restores_screen(tmp_path, monkeypatch, failure):
    from chemdraw_macos.terminal_setup import run_setup
    out = TTY()
    session = Session()
    def stop(prompt): raise failure('stop')
    code = run_setup(animated(monkeypatch), session=session, home=tmp_path,
                     stream=out, input_fn=stop)
    assert code == (130 if failure is KeyboardInterrupt else 1)
    assert session.closed
    assert out.getvalue().count('\x1b[?1049l') == 1


def test_frame_keeps_content_inside_viewport_and_molecules_move():
    from chemdraw_macos.terminal_screen import setup_frame
    clean = lambda value: re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', value)
    first = setup_frame(109, 33, .5, 'Connect ChemDraw', ['Install the add-in.'], 'Return to continue')
    later = setup_frame(109, 33, 4.5, 'Connect ChemDraw', ['Install the add-in.'], 'Return to continue')
    assert first != later
    lines = clean(first).splitlines()
    assert len(lines) == 33 and all(len(line) <= 109 for line in lines)
    assert 'Install the add-in.' in clean(first)
    assert 'Created by Glenn Bojanov' in clean(first)


def test_theme_starts_before_setup_session_initializes(tmp_path, monkeypatch):
    from chemdraw_macos.terminal_setup import run_setup
    out = TTY()
    def create():
        assert '\x1b[?1049h' in out.getvalue()
        return Session()
    monkeypatch.setattr('chemdraw_macos.terminal_setup.SetupSession', create)
    assert run_setup(animated(monkeypatch), home=tmp_path, stream=out, input_fn=lambda _: '') == 0


def test_short_window_pages_instructions_before_running_next_step(monkeypatch):
    from chemdraw_macos.terminal_screen import SetupScreen
    monkeypatch.setattr('shutil.get_terminal_size', lambda *a: os.terminal_size((80, 24)))
    out = TTY()
    calls = []
    with SetupScreen(out, enabled=True) as screen:
        screen.show('Read steps', [f'Instruction {i}' for i in range(24)])
        screen.wait(lambda prompt: calls.append(prompt), 'Return to test')
    assert len(calls) == 2
    assert 'Instruction 23' in out.getvalue()
    assert 'Return for more' in out.getvalue()


def test_animation_centers_actual_braille_ink_not_padded_sprite_metadata(monkeypatch):
    from chemdraw_macos.terminal_screen import setup_frame
    monkeypatch.setattr('chemdraw_macos.terminal_screen.load_molecules', lambda: [
        {'sprites': [{'width': 60, 'height': 18, 'rows': ['  ⠀  ', '  ⣿⣿ ', '  ⣿⣿ ']}]}])
    plain = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', setup_frame(119, 37, 2, 'Title', [], 'Return'))
    points = [(x, y) for y, row in enumerate(plain.splitlines()) for x, c in enumerate(row) if c == '⣿']
    assert len(points) == 4
    assert abs(sum(p[0] for p in points)/len(points) - 19) <= .5


def test_theme_uses_indexed_dark_background_and_resets_inherited_attributes():
    from chemdraw_macos.terminal_screen import setup_frame, SetupScreen
    frame = setup_frame(107, 30, 1, 'Connect ChemDraw', ['Read these steps'], 'Return')
    assert frame.startswith('\x1b[0m\x1b[48;5;235m')
    assert '\x1b[48;2;' not in frame
    out = TTY()
    with SetupScreen(out, enabled=True):
        pass
    assert '\x1b[0m\x1b[48;5;235m\x1b[2J' in out.getvalue()
    assert '\x1b[48;2;' not in out.getvalue()
