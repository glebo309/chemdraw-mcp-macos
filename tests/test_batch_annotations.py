"""Batch exports reuse the existing bounded annotation preservation contract."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import plan_annotations
from chemdraw_macos.batch import _supported, _verify, batch_export
from test_batch import BatchBridge
from test_annotations import HEAD_RENDER_ARROWS


ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / 'examples/sn2-annotation-input.cdxml').read_text()
RECIPE = json.loads((ROOT / 'examples/sn2-annotation-recipe.json').read_text())


def annotated(head='Full'):
    arrows = copy.deepcopy(RECIPE['arrows'])
    if head != 'Full':
        # Head-shape regression, not a proposed one-electron SN2 mechanism.
        # A negative-charge pair symbol must not be used as a one-electron source.
        arrows = copy.deepcopy(HEAD_RENDER_ARROWS)
        for arrow in arrows:
            arrow.update(electrons=1, fishhook_side='left' if head == 'HalfLeft' else 'right')
    return plan_annotations(SOURCE, arrows)[0]


@pytest.mark.parametrize('head', ['Full', 'HalfLeft', 'HalfRight'])
def test_supported_annotation_batch_exports_preserve_source_and_report_checks(tmp_path, head):
    source = tmp_path / 'mechanism.cdxml'
    text = annotated(head)
    source.write_text(text)
    bridge = BatchBridge(tmp_path / 'work')
    before = bridge.documents()
    result = batch_export(bridge, [{'key': 'mechanism', 'source': str(source)}], str(tmp_path / 'out'))
    assert result['status'] == 'completed'
    item = result['items'][0]
    assert item['status'] == 'exported'
    assert item['checks']['curve_geometry_preserved']
    assert item['checks']['existing_charge_symbols_preserved']
    assert item['checks']['source_file_unchanged']
    assert item['annotation_verification']['id_map']
    assert bridge.documents() == before
    assert not bridge.managed
    assert source.read_text() == text
    assert (tmp_path / 'out' / 'mechanism' / 'mechanism.cdxml').read_text() == text


def test_charge_only_native_input_and_plain_core_do_not_recurse_forever():
    root = _supported(SOURCE)
    assert len(root.findall('page/fragment/graphic')) == 2
    assert _verify(SOURCE, SOURCE)['checks']['existing_charge_symbols_preserved']


def test_batch_annotations_allow_native_id_remapping():
    before = annotated()
    root = ET.fromstring(before)
    mapping = {e.get('id'): str(int(e.get('id')) + 10000)
               for e in root.find('page').iter() if e.get('id')}
    for e in root.find('page').iter():
        for attr in ('id', 'B', 'E', 'SupersededBy', 'object'):
            if e.get(attr) in mapping:
                e.set(attr, mapping[e.get(attr)])
        for attr in list(e.attrib):
            if attr.startswith('ReactionStep'):
                e.set(attr, ' '.join(mapping.get(v, v) for v in e.get(attr).split()))
    result = _verify(before, ET.tostring(root, encoding='unicode'))
    assert result['checks']['curve_geometry_preserved']


@pytest.mark.parametrize('change', ['drop_curve', 'curve_point', 'curve_head', 'charge_position',
                                   'charge_owner', 'charge_width', 'atom_position', 'caption', 'reaction_arrow'])
def test_native_annotation_or_core_corruption_is_rejected(change):
    before = annotated()
    root = ET.fromstring(before)
    curve = root.find('page/curve')
    charge = root.find('page/fragment/graphic')
    if change == 'drop_curve':
        root.find('page').remove(curve)
    elif change == 'curve_point':
        values = curve.get('CurvePoints').split(); values[4] = str(float(values[4]) + 1)
        curve.set('CurvePoints', ' '.join(values))
    elif change == 'curve_head':
        curve.set('ArrowheadHead', 'HalfLeft'); curve.set('CurveType', '32')
    elif change == 'charge_position':
        charge.set('BoundingBox', '0 0 4 4')
    elif change == 'charge_owner':
        charge[0].set('object', '4114')
    elif change == 'charge_width':
        charge.set('LineWidth', '7')
    elif change == 'atom_position':
        root.find('page/fragment/n').set('p', '900 900')
    elif change == 'caption':
        root.find('page/t/s').text = 'Wrong caption'
    else:
        root.find('page/arrow').set('HeadSize', '999')
    with pytest.raises(ValueError):
        _verify(before, ET.tostring(root, encoding='unicode'))


@pytest.mark.parametrize('change', ['unsupported_symbol', 'invalid_charge_style', 'invalid_curve_style',
                                   'curve_nonfinite', 'atom_annotation'])
def test_unsupported_annotations_rejected_during_preflight(change):
    root = ET.fromstring(annotated())
    if change == 'unsupported_symbol':
        root.find('page/fragment/graphic').set('SymbolType', 'Electron')
    elif change == 'invalid_charge_style':
        root.find('page/fragment/graphic').set('LineType', 'Dashed')
    elif change == 'invalid_curve_style':
        root.find('page/curve').set('FillType', 'Solid')
    elif change == 'curve_nonfinite':
        root.find('page/curve').set('LineWidth', 'nan')
    else:
        ET.SubElement(root.find('page/fragment/n'), 'graphic', {'id': '9999'})
    with pytest.raises(ValueError):
        _supported(ET.tostring(root, encoding='unicode'))


def test_annotation_native_timeout_stops_batch_without_close_or_retry(tmp_path):
    source = tmp_path / 'mechanism.cdxml'; source.write_text(annotated())
    bridge = BatchBridge(tmp_path / 'work'); export = bridge.export
    def timeout(did, path, format, pixels=3200):
        if format == 'svg':
            raise RuntimeError('native annotation timeout')
        return export(did, path, format, pixels)
    bridge.export = timeout
    result = batch_export(bridge, [{'key': 'a', 'source': str(source)},
                                  {'key': 'b', 'source': str(source)}], str(tmp_path / 'out'))
    assert result['status'] == 'interrupted'
    assert [r['status'] for r in result['items']] == ['uncertain', 'not_run']
    assert len([e for e in bridge.events if e[0] == 'create']) == 1
    assert not any(e[0] == 'close' for e in bridge.events)
