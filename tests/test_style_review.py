"""Independent fail-closed stylesheet review regressions."""

from pathlib import Path

import pytest

from chemdraw_macos.styles import inspect_style_file, require_style_fonts
from test_style_import import binary_style


def xml_style(fonttables):
    return ('<CDXML BondLength="18" LineWidth="1" BoldWidth="2" '
            'LabelSize="14" CaptionSize="12" LabelFont="3" CaptionFont="3">'
            + fonttables + '<page/></CDXML>')


@pytest.mark.parametrize('fonttables', [
    '<fonttable><font id="3" name="Arial"/><font id="3" name="Helvetica"/></fonttable>',
    '<fonttable><font id="3" name="Arial"/></fonttable>'
    '<fonttable><font id="3" name="Helvetica"/></fonttable>',
])
def test_ambiguous_xml_font_ownership_is_rejected(tmp_path, fonttables):
    source = tmp_path / 'ambiguous.cdxml'
    source.write_text(xml_style(fonttables))
    with pytest.raises(ValueError, match='font'):
        inspect_style_file(str(source))


def test_source_change_during_style_inspection_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / 'style.cds'
    source.write_bytes(binary_style())
    original = Path.read_bytes
    calls = 0

    def changing(path):
        nonlocal calls
        data = original(path)
        if path == source:
            calls += 1
            if calls == 2:
                return data + b'changed'
        return data

    monkeypatch.setattr(Path, 'read_bytes', changing)
    with pytest.raises(ValueError, match='changed'):
        inspect_style_file(str(source))


def test_separate_caption_font_is_checked_on_rendering_mac(monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Arial'])
    spec = {'BondLength': '18', 'LineWidth': '1', 'BoldWidth': '2',
            'LabelSize': '14', 'CaptionSize': '12', 'font': 'Arial',
            'CaptionFontName': 'Missing Caption Font'}
    with pytest.raises(ValueError, match='Missing Caption Font'):
        require_style_fonts(spec)
