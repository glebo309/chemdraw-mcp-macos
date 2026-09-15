"""Native caption bearings must survive translation to the target ink centre."""
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import numbers
from chemdraw_macos.scope import arrange_scope, prepare_scope, verify_scope
from test_polish import SAMPLE
from test_scope import CELLS, measured


def with_native_bearings(text, bearings):
    root = ET.fromstring(measured(text))
    for tid, offset in bearings.items():
        caption = root.find(f'page/t[@id="{tid}"]')
        left, top, right, bottom = numbers(caption.get('BoundingBox'), 4)
        caption.set('BoundingBox', f'{left + offset} {top} {right + offset} {bottom}')
    return ET.tostring(root, encoding='unicode')


def test_grid_retains_native_bearing_when_centring_caption_ink():
    prepared, state = prepare_scope(SAMPLE, CELLS)
    name_id = state['cells'][0]['caption_id']
    metadata_id = state['cells'][0]['metadata_id']
    # Measured on the actual 14 pt Helvetica Neue Sharpless result: Parent
    # +0.34 pt, metadata 1 -0.785 pt relative to the native centred anchor.
    bearings = {name_id: .34, metadata_id: -.785}
    native = with_native_bearings(prepared, bearings)
    arranged, plan = arrange_scope(native, state['cells'], columns=2)
    root = ET.fromstring(arranged)
    cell = plan['cells'][0]
    for key, tid in [('name', name_id), ('metadata', metadata_id)]:
        caption = root.find(f'page/t[@id="{tid}"]')
        anchor = numbers(caption.get('p'), 2)[0]
        assert anchor == pytest.approx(cell['center_x'] - bearings[tid], abs=1e-5)
        assert cell[key + '_anchor_x'] == pytest.approx(anchor)
    saved = with_native_bearings(arranged, bearings)
    assert verify_scope(arranged, saved, plan)['checks']['caption_alignment'] is True


def test_corrected_grid_still_rejects_native_ink_shift():
    prepared, state = prepare_scope(SAMPLE, CELLS)
    tid = state['cells'][0]['metadata_id']
    bearings = {tid: -.785}
    arranged, plan = arrange_scope(with_native_bearings(prepared, bearings), state['cells'], columns=2)
    # Native font geometry changed after planning; a good anchor is insufficient.
    saved = with_native_bearings(arranged, {tid: bearings[tid] + 1.0})
    with pytest.raises(ValueError, match='ink'):
        verify_scope(arranged, saved, plan)


def test_grid_keeps_measured_justification_instead_of_reinterpreting_anchor():
    prepared, state = prepare_scope(SAMPLE, CELLS)
    root = ET.fromstring(measured(prepared))
    tid = state['cells'][0]['caption_id']
    caption = root.find(f'page/t[@id="{tid}"]')
    caption.set('Justification', 'Left')
    caption.set('CaptionJustification', 'Left')
    # A left-justified caption is still centred by translating its measured ink.
    arranged, _ = arrange_scope(ET.tostring(root, encoding='unicode'), state['cells'], columns=2)
    actual = ET.fromstring(arranged).find(f'page/t[@id="{tid}"]')
    assert actual.get('Justification') == 'Left'
    assert actual.get('CaptionJustification') == 'Left'
