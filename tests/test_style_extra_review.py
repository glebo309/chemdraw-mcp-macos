"""Independent custom-style preservation regressions; no native application."""
import struct
import threading
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import style_cdxml
from chemdraw_macos.styles import inspect_style_file
from chemdraw_macos.workflow import polish_document
from test_polish import SAMPLE
from test_style_import import binary_style, prop
from test_workflow import FakeBridge


SPEC = {'BondLength': '18', 'LineWidth': '1.2', 'BoldWidth': '2',
        'LabelSize': '13', 'CaptionSize': '12', 'font': 'Arial',
        'CaptionFontName': 'Arial', 'BondSpacing': '15',
        'LabelFace': '97', 'CaptionFace': '2'}


def test_custom_spacing_replaces_explicit_local_bond_override():
    root = ET.fromstring(SAMPLE)
    bond = root.find('.//b')
    bond.set('BondSpacing', '35')
    result = ET.fromstring(style_cdxml(ET.tostring(root, encoding='unicode'), SPEC))
    actual = result.find('.//b').get('BondSpacing', result.get('BondSpacing'))
    assert float(actual) == 15


def test_custom_typography_replaces_explicit_node_overrides():
    root = ET.fromstring(SAMPLE)
    node = root.find('.//n')
    node.attrib.update(LabelFont='2', LabelSize='24', LabelFace='98')
    result = ET.fromstring(style_cdxml(ET.tostring(root, encoding='unicode'), SPEC))
    node = result.find('.//n')
    assert node.get('LabelFont', result.get('LabelFont')) == result.get('LabelFont')
    assert float(node.get('LabelSize', result.get('LabelSize'))) == 13
    assert int(node.get('LabelFace', result.get('LabelFace'))) & 3 == 1


@pytest.mark.parametrize('corruption', ['stroke', 'font'])
def test_native_custom_style_loss_does_not_return_success(tmp_path, monkeypatch, corruption):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Arial'])
    bridge = FakeBridge(tmp_path / 'work')
    original_create = bridge.create

    def changed(text):
        root = ET.fromstring(text)
        if corruption == 'stroke':
            root.set('LineWidth', '0.5')
            for bond in root.iter('b'):
                bond.set('LineWidth', '0.5')
        else:
            for font in root.findall('fonttable/font'):
                if font.get('name') == 'Arial':
                    font.set('name', 'Courier')
        return original_create(ET.tostring(root, encoding='unicode'))

    bridge.create = changed
    with pytest.raises(ValueError, match='[Ss]tyle|[Ww]idth|[Ff]ont|typography'):
        polish_document(bridge, 1, str(tmp_path / 'out'), preset=SPEC)


def test_binary_missing_caption_font_is_rejected_or_reports_fallback(tmp_path):
    # Leave explicit caption size while removing its font/face compound setting.
    data = binary_style().replace(prop(0x80b, struct.pack('<HHHH', 3, 0, 240, 0)),
                                  prop(0x81d, struct.pack('<H', 240)))
    source = tmp_path / 'incomplete.cds'
    source.write_bytes(data)
    try:
        report = inspect_style_file(source)
    except ValueError:
        return
    assert 'CaptionFontName' in report['defaults_used']


def test_custom_face_preserves_chemical_script_bits():
    root = ET.fromstring(SAMPLE)
    run = root.find('.//n/t/s')
    run.set('face', '66')
    result = ET.fromstring(style_cdxml(ET.tostring(root, encoding='unicode'), SPEC))
    assert result.find('.//n/t/s').get('face') == '65'


def test_custom_caption_face_reaches_new_scope_metadata():
    from chemdraw_macos.scope import prepare_scope
    from test_scope import CELLS
    text, state = prepare_scope(SAMPLE, CELLS, SPEC)
    root = ET.fromstring(text)
    for cell in state['cells']:
        run = root.find(f'page/t[@id="{cell["metadata_id"]}"]/s')
        assert int(run.get('face')) & 3 == 2


def test_style_verification_accepts_font_id_remapping_and_run_splits():
    from chemdraw_macos.styles import verify_custom_style
    expected = style_cdxml(SAMPLE, SPEC)
    root = ET.fromstring(expected)
    oldid = root.get('LabelFont')
    for entry in root.findall('fonttable/font'):
        if entry.get('id') == oldid:
            entry.set('id', '240')
    for element in root.iter():
        for attr in ('LabelFont', 'CaptionFont', 'font'):
            if element.get(attr) == oldid:
                element.set(attr, '240')
    report = verify_custom_style(expected, ET.tostring(root, encoding='unicode'), SPEC)
    assert report['verified'] is True
    assert report['scope'] == 'supported numerical settings, font families, sizes and bold/italic faces'


def low_level_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts', lambda: ['Arial'])
    bridge = FakeBridge(tmp_path / 'work')
    bridge.lock = threading.RLock()
    return bridge


def test_low_level_custom_style_exports_and_verifies_created_copy(tmp_path, monkeypatch):
    from pathlib import Path
    from chemdraw_macos.core import Bridge
    bridge = low_level_bridge(tmp_path, monkeypatch)
    result = Bridge.apply_style(bridge, 1, SPEC)
    assert result['custom_style_verification']['verified'] is True
    assert Path(result['styled_snapshot']).is_file()
    assert bridge.docs[1] == SAMPLE
    assert result['document']['document_id'] in bridge.managed
    assert len([event for event in bridge.events if event[0] == 'create']) == 1


def test_low_level_custom_style_rejects_native_stroke_loss(tmp_path, monkeypatch):
    from chemdraw_macos.core import Bridge
    bridge = low_level_bridge(tmp_path, monkeypatch)
    original_create = bridge.create
    def changed(text):
        root = ET.fromstring(text)
        root.set('LineWidth', '0.5')
        return original_create(ET.tostring(root, encoding='unicode'))
    bridge.create = changed
    with pytest.raises(ValueError, match='style'):
        Bridge.apply_style(bridge, 1, SPEC)
    assert bridge.docs[1] == SAMPLE
    assert not any(event[0] == 'close' for event in bridge.events)


def test_low_level_uncertain_verification_export_stops_without_retry_or_close(tmp_path, monkeypatch):
    from chemdraw_macos.core import Bridge
    bridge = low_level_bridge(tmp_path, monkeypatch)
    original_export = bridge.export
    attempts = []
    def uncertain(did, *args):
        attempts.append(did)
        if did != 1:
            raise TimeoutError('native export outcome uncertain')
        return original_export(did, *args)
    bridge.export = uncertain
    with pytest.raises(TimeoutError, match='uncertain'):
        Bridge.apply_style(bridge, 1, SPEC)
    assert len(attempts) == 2
    assert len(bridge.managed) == 1
    assert bridge.docs[1] == SAMPLE
    assert not any(event[0] == 'close' for event in bridge.events)


def test_low_level_style_verifier_checks_grouped_caption_runs():
    from chemdraw_macos.styles import verify_custom_style
    root = ET.fromstring(style_cdxml(SAMPLE, SPEC))
    page = root.find('page')
    caption = page.find('t')
    page.remove(caption)
    group = ET.SubElement(page, 'group', {'id': '999'})
    group.append(caption)
    expected = ET.tostring(root, encoding='unicode')
    caption.find('s').set('size', '30')
    with pytest.raises(ValueError, match='style'):
        verify_custom_style(expected, ET.tostring(root, encoding='unicode'), SPEC)
