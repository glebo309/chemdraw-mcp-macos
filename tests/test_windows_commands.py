"""Windows named commands, dialogs and settings.

The helpers are pure and run on every platform. The COM operations run only on
Windows, against fakes; they are not a substitute for the native checklist in
docs/WINDOWS_NATIVE_COMMANDS_CHECKLIST.md.
"""
import sys
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos import windows_commands as wc
from chemdraw_macos.commands import command_policy


def test_captions_normalize_accelerators_shortcuts_ellipses_and_superscripts():
    assert wc.normalize('&Clean Up Structure\tCtrl+Shift+K') == 'clean up structure'
    assert wc.normalize('Sc&ale...') == 'scale'
    assert wc.normalize('Predict ¹H-NMR Shifts') == wc.normalize('Predict 1H NMR Shifts')
    assert wc.caption_matches('Undo*', '&Undo Clean Up Structure\tCtrl+Z')
    assert not wc.caption_matches('Undo*', 'Redo')
    assert wc.caption_matches('Group', '&Group') and not wc.caption_matches('Group', 'Ungroup')


def test_aliases_and_explicit_menu_names_resolve():
    assert wc.resolve('undo') == ('Edit', 'Undo*')
    assert wc.resolve('Structure > Clean Up Structure') == ('Structure', 'Clean Up Structure')
    with pytest.raises(ValueError, match='Menu > Item'):
        wc.resolve('toggleKekulization')


@pytest.mark.parametrize('name,allowed', [
    ('Object > Flip Horizontal', True), ('Structure > Clean Up Structure', True),
    ('File > Save', False), ('File > Close', False), ('Edit > Copy As', False), ('Edit > Paste', False),
    ('Edit > Preferences...', False), ('Help > About ChemDraw', False),
    ('Structure > Predict 1H-NMR Shifts', False), ('Structure > Check Structure', False),
    ('Structure > Convert Name to Structure', False)])
def test_menu_names_follow_the_same_refusal_policy(name, allowed):
    assert command_policy(name)[0] is allowed


def test_button_styles_classify_controls():
    assert [wc.button_kind(s) for s in (0, 1, 2, 3, 4, 9, 7, 0x50010001)] == [
        'button', 'button', 'checkbox', 'checkbox', 'radio', 'radio', 'group', 'button']


def test_dialog_record_from_controls_matches_the_macos_shape():
    record = wc.describe_controls('Scale', [
        ('Static', 0, 'Scale the selected objects:', False),
        ('Button', 9, 'Scale &by', True), ('Edit', 0, '100', False), ('Static', 0, '%', False),
        ('Button', 3, 'Scale atom labels', False), ('Button', 1, 'OK', False), ('Button', 0, 'Cancel', False),
        ('Button', 7, 'Group', False)])
    assert record == {'kind': 'dialog', 'window': 'Scale', 'text': ['Scale the selected objects:', '%'],
                      'buttons': ['OK', 'Cancel'], 'fields': [{'index': 1, 'value': '100'}],
                      'radio_buttons': [{'name': 'Scale by', 'selected': True}],
                      'checkboxes': [{'name': 'Scale atom labels', 'checked': False}]}


class Settings:
    BondLength, LineWidth, BoldWidth, LabelSize, CaptionSize = 14.4, .6, 2.0, 10.0, 10.0
    LabelFont, CaptionFont, BondSpacing, ChainAngle, MarginWidth, HashSpacing = 'Arial', 'Arial', 18, 120, 1.6, 2.5


def test_settings_use_the_shared_twentieth_point_order():
    s = Settings()
    assert wc.read_settings(s) == [288, 12, 40, 200, 200, 'Arial', 'Arial', 18, 120, 32, 50, None]
    wc.write_settings(s, [('fixed length', '340'), ('label font', 'Helvetica'), ('chain angle', '120')])
    assert (s.BondLength, s.LabelFont, s.ChainAngle) == (17.0, 'Helvetica', 120)
    with pytest.raises(RuntimeError, match='Magnification'):
        wc.write_settings(s, [('magnification', '150')])


def test_object_counts_match_the_macos_meaning():
    root = ET.fromstring('<CDXML><page><fragment id="1"><n id="2"/><n id="3"/><b id="4"/></fragment>'
                         '<t id="5"/><arrow id="6"/></page></CDXML>')
    tops = lambda r: [f for p in r.findall('page') for f in p if f.tag == 'fragment']
    assert wc.object_counts(root, tops) == [2, 1, 1, 1, 1]


class Item:
    def __init__(self, caption, enabled=True, command_id=1):
        self.caption, self.Enabled, self.CommandID = caption, enabled, command_id


class Menu:
    def __init__(self, caption, items):
        self.caption, self.MenuItems = caption, items


class App:
    def __init__(self, menus):
        self.MenuBars = [type('Bar', (), {'Menus': menus})()]


APP = App([Menu('&Edit', [Item('&Undo Flip\tCtrl+Z'), Item('&Redo', False), Item('-', command_id=0)]),
           Menu('&Object', [Item('Flip &Horizontal'), Item('Sc&ale...')])])


def test_menu_listing_gives_aliases_then_every_item():
    names, enabled, descriptions = wc.list_menu_commands(APP)
    assert names[:4] == ['undo', 'redo', 'flipObjectsHorizontal', 'showScaleDialog']
    assert descriptions[0] == 'Edit > Undo Flip' and enabled[1] is False
    assert 'Object > Scale...' in names and '-' not in ' '.join(names)


def test_missing_menu_item_lists_what_exists():
    with pytest.raises(ValueError, match="Flip Horizontal"):
        wc.find_menu_item(APP, 'Object', 'Rotate')


def test_windows_stationery_is_found_beside_chemdraw_exe(tmp_path):
    from chemdraw_macos.styles import stationery_styles
    exe = tmp_path / 'ChemDraw' / 'ChemDraw.exe'
    (tmp_path / 'ChemDraw' / 'ChemDraw Items' / 'Stationery').mkdir(parents=True)
    exe.write_bytes(b'')
    (tmp_path / 'ChemDraw' / 'ChemDraw Items' / 'Stationery' / 'Wiley Document.cds').write_bytes(b'x')
    assert [s['name'] for s in stationery_styles(exe)] == ['Wiley Document']


# ---------------------------------------------------------------- COM operations (Windows only)

windows = pytest.mark.skipif(sys.platform != 'win32', reason='Windows COM adapter (pywin32)')


@windows
def test_dispatch_reports_a_dialog_without_touching_com_while_it_is_open(monkeypatch):
    from chemdraw_macos import windows_native as wn

    class Doc:
        Name = 'mine.cdxml'
        Objects = type('O', (), {'Select': lambda self: None})()
        def Activate(self): pass
    doc = Doc()
    monkeypatch.setattr(wn, '_find', lambda app, did, pid=None: doc)
    monkeypatch.setattr(wn, '_require_active', lambda *a: None)
    monkeypatch.setattr(wc, 'find_menu_item', lambda app, m, p: Item('Scale...'))
    state = [[1, 'mine.cdxml', '', True, 1], [6, 6, 1, 0, 0], [1], ['mine.cdxml']]
    monkeypatch.setattr(wn, '_command_state', lambda app, did: state)
    pending = wc._Pending()
    monkeypatch.setattr(wc, 'start_command', lambda m, p: pending)
    monkeypatch.setattr(wc, 'dialog_count', lambda: 1)
    monkeypatch.setattr(wc, '_pending', pending)
    reply = wn._op_dispatch_command(object(), 1, 'showScaleDialog', 'all')
    assert reply[5] == 'busy' and reply[6] == 1
    assert wn._op_command_state(object(), 1) == ['busy', 1]
    pending.done.set()
    assert wn._op_command_state(object(), 1) == [state, 1]


@windows
def test_second_command_is_refused_while_the_first_waits_for_its_dialog(monkeypatch):
    from chemdraw_macos import windows_native as wn
    pending = wc._Pending()
    monkeypatch.setattr(wc, '_pending', pending)
    with pytest.raises(wn.NativeError, match='still running'):
        wn._op_dispatch_command(object(), 1, 'undo', 'current')
