"""A drawing style chosen in setup becomes 'house' for every drawing; numbers only, never the file."""
import json
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos import core, desktop_setup as setup
from chemdraw_macos.scope import prepare_scope
from test_polish import SAMPLE
from test_scope import CELLS

BUILTIN = dict(core.PRESETS['house'])
CHOSEN = {'name': 'chemdraw template_Lab.cds', 'sha256': 'ab' * 32,
          'preset': {'BondLength': '18', 'LineWidth': '1.59', 'BoldWidth': '2.01', 'LabelSize': '14',
                     'CaptionSize': '14', 'font': 'Arial', 'CaptionFontName': 'Arial',
                     'LabelFace': '96', 'CaptionFace': '0'}}
TEMPLATE = ('<CDXML BondLength="18" LineWidth="1.59" BoldWidth="2.01" LabelSize="14" CaptionSize="14" '
            'LabelFont="3" CaptionFont="3" LabelFace="96" CaptionFace="0"><fonttable><font id="3" name="Arial"/>'
            '</fonttable><page/></CDXML>')


@pytest.fixture(autouse=True)
def builtin_house_afterwards(monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Arial'])
    yield
    core.use_default_style(None)


def test_style_chosen_in_setup_becomes_house_for_drawings():
    report = core.use_default_style(CHOSEN)
    assert report == {'status': 'applied', 'name': 'chemdraw template_Lab.cds', 'sha256': 'ab' * 32}
    house = core.preset_settings('house')
    assert house['LineWidth'] == '1.59' and house['CaptionSize'] == '14' and house['font'] == 'Arial'
    assert core.preset_settings('acs-1996')['font'] == 'Arial'  # other presets unchanged


def test_without_a_choice_house_stays_builtin():
    assert core.use_default_style(None) == {'status': 'built-in'}
    assert core.preset_settings('house') == BUILTIN


def test_missing_font_keeps_builtin_house_and_says_why(monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Calibri'])
    report = core.use_default_style(CHOSEN)
    assert report['status'] == 'not_applied' and 'Arial' in report['reason']
    assert core.preset_settings('house') == BUILTIN


@pytest.mark.parametrize('damaged', [{'name': 'x.cds', 'preset': {**CHOSEN['preset'], 'LineWidth': '99'}},
                                     {'name': 'x.cds'}, 'x.cds', ['x']])
def test_damaged_choice_keeps_builtin_house(damaged):
    assert core.use_default_style(damaged)['status'] == 'not_applied'
    assert core.preset_settings('house') == BUILTIN


def test_a_later_start_without_a_choice_restores_builtin_house():
    core.use_default_style(CHOSEN)
    core.use_default_style(None)
    assert core.preset_settings('house') == BUILTIN


def test_list_styles_reports_where_house_comes_from():
    from chemdraw_macos import server
    core.use_default_style(CHOSEN)
    listed = server.chemdraw_list_styles()
    assert listed['presets']['house']['LineWidth'] == '1.59'
    assert listed['default_style'] == {'status': 'applied', 'name': 'chemdraw template_Lab.cds', 'sha256': 'ab' * 32}


def test_scope_captions_follow_the_chosen_caption_face():
    def face(text, state):
        root = ET.fromstring(text)
        return root.find(f'.//t[@id="{state["cells"][0]["metadata_id"]}"]/s').get('face')
    assert face(*prepare_scope(SAMPLE, CELLS)) == '1'  # built-in house keeps bold metadata captions
    core.use_default_style(CHOSEN)
    assert face(*prepare_scope(SAMPLE, CELLS)) == '0'


def _session(tmp_path):
    return setup.SetupSession(settings_path=tmp_path / 'settings.json')


def test_setup_stores_the_chosen_style_by_name_without_its_path(tmp_path):
    source = tmp_path / 'private folder' / 'chemdraw template_Lab.cdxml'
    source.parent.mkdir()
    source.write_text(TEMPLATE, encoding='utf-8', newline='')
    session = _session(tmp_path)
    value = session.dispatch({'action': 'choose_style', 'path': str(source)})
    assert value['status'] == 'style_selected' and value['style']['name'] == 'chemdraw template_Lab.cdxml'
    chosen = session.settings['default_style']
    assert chosen['name'] == 'chemdraw template_Lab.cdxml' and len(chosen['sha256']) == 64
    assert chosen['preset']['LineWidth'] == '1.59' and chosen['preset']['font'] == 'Arial'
    assert 'private folder' not in json.dumps(session.settings) and 'private folder' not in json.dumps(value)


def test_setup_refuses_a_style_whose_fonts_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Calibri'])
    source = tmp_path / 'lab.cdxml'
    source.write_text(TEMPLATE, encoding='utf-8', newline='')
    session = _session(tmp_path)
    with pytest.raises(ValueError, match='Arial'):
        session.dispatch({'action': 'choose_style', 'path': str(source)})
    assert 'default_style' not in session.settings


def test_setup_can_return_to_the_builtin_style(tmp_path):
    session = _session(tmp_path)
    session.settings['default_style'] = CHOSEN
    assert session.dispatch({'action': 'clear_style'}) == {'status': 'style_cleared'}
    assert 'default_style' not in session.settings


def test_finish_keeps_the_chosen_style_for_later_runs(tmp_path):
    session = _session(tmp_path)
    session.settings['default_style'] = CHOSEN
    session.last_diagnostic = {'status': 'ready', 'shared_drawing_ready': True}
    assert session.dispatch({'action': 'finish'}) == {'status': 'finished'}
    saved = json.loads((tmp_path / 'settings.json').read_text(encoding='utf-8'))
    assert saved['default_style'] == CHOSEN and _session(tmp_path).settings['default_style'] == CHOSEN


@pytest.fixture
def windows_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, 'WINDOWS', True)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    monkeypatch.setenv('CHEMDRAW_DESKTOP_EXTENSION', 'unset-by-test')
    path = setup.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'setup_complete': True, 'default_style': CHOSEN}), encoding='utf-8')


def test_server_started_by_assistants_uses_the_chosen_style(windows_settings, monkeypatch):
    from chemdraw_macos import server
    seen = []
    monkeypatch.setattr(server, 'main', lambda argv: seen.append(core.preset_settings('house')['LineWidth']))
    assert setup.runtime_main(['--desktop-serve']) == 0
    assert seen == ['1.59']


def test_terminal_command_uses_the_chosen_style(windows_settings, monkeypatch):
    from chemdraw_macos import cli
    seen = []
    monkeypatch.setattr(cli, 'main', lambda argv: seen.append(core.preset_settings('house')['LineWidth']) or 0)
    setup.runtime_main(['--cli', 'doctor'])
    assert seen == ['1.59']
