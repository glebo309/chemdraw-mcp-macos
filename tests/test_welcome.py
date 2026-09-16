import io
import json
from importlib.resources import files

import pytest


def test_bundled_native_sprites_are_portable_and_include_alizarin():
    data = json.loads(files('chemdraw_macos').joinpath('data/welcome.json').read_text())
    assert data['renderer'] == 'native ChemDraw'
    assert len(data['molecules']) == 9
    names = {m['name'] for m in data['molecules']}
    assert {'Caffeine', '5-MeO-DMT', 'Alizarin'} <= names
    assert not {'Ethanol', 'Uric acid'} & names
    for molecule in data['molecules']:
        assert len(molecule['native_svg_sha256']) == 64
        for sprite in molecule['sprites']:
            assert len(sprite['rows']) <= sprite['height']
            assert all(len(row) <= sprite['width'] for row in sprite['rows'])
            assert all(c == ' ' or 0x2800 <= ord(c) <= 0x28ff
                       for row in sprite['rows'] for c in row)
    assert '/Users/' not in json.dumps(data)


def test_welcome_progress_waits_for_verified_completion():
    from chemdraw_macos.welcome import phase_progress, progress_bar
    assert phase_progress('drawing', 10000) < 1
    assert phase_progress('exports', 10000) < 1
    assert phase_progress('complete', 0) == 1
    assert phase_progress('drawing', 2) > phase_progress('drawing', 0)
    assert progress_bar(0, 40) == '░' * 40
    assert progress_bar(1, 40) == '█' * 40
    assert progress_bar(.501, 40) != progress_bar(.52, 40)


def test_welcome_frames_keep_names_hidden_and_fit_small_terminals():
    from chemdraw_macos.welcome import frame, load_molecules
    import re
    for width, height in [(80, 29), (72, 22), (40, 12)]:
        result = frame(width, height, 3, 'drawing', 'Drawing', .4)
        assert all(m['name'] not in result for m in load_molecules())
        assert '\x1b[38;2' not in result
        lines = re.sub(r'\x1b\[[0-9;]*m', '', result).splitlines()
        assert len(lines) == height
        assert all(len(line) <= width for line in lines)
    assert 'Natural language → ChemDraw' in frame(80, 29, 4, 'complete', 'Ready', 1)


def test_animation_restores_terminal_even_on_failure():
    from chemdraw_macos.first_run import TerminalProgress
    stream = io.StringIO()
    with pytest.raises(RuntimeError):
        with TerminalProgress(stream, enabled=True) as progress:
            progress.update('drawing', 'Drawing')
            raise RuntimeError('native failure')
    assert not progress.thread.is_alive()
    output = stream.getvalue()
    assert '\x1b[?25l' in output and '\x1b[?25h' in output
    assert '\x1b[?1049h' in output and '\x1b[?1049l' in output


def test_terminal_theme_matches_pink_lavender_graphical_setup():
    from chemdraw_macos.welcome import frame
    result = frame(80, 29, .2, 'connection', 'Testing connection', .2)
    assert '\x1b[38;5;218m' in result
    assert '\x1b[38;5;183m' in result
    assert '\x1b[96m' not in result and '\x1b[36m' not in result
