"""Independent grid review: native success must cover the entire output."""
import copy
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import numbers
from chemdraw_macos.scope import prepare_scope, arrange_scope, verify_scope
from test_scope import CELLS, measured
from test_polish import SAMPLE


def planned_grid():
    prepared, state = prepare_scope(SAMPLE, CELLS)
    return arrange_scope(measured(prepared), state['cells'], columns=2)


@pytest.mark.parametrize('extra_kind', ['molecule', 'caption'])
def test_native_output_cannot_gain_unowned_objects(extra_kind):
    expected, plan = planned_grid()
    root = ET.fromstring(measured(expected))
    page = root.find('page')
    # Well inside the page and far from the intended grid. An overlap/page-fit
    # check alone cannot establish that all native output belongs to a cell.
    if extra_kind == 'molecule':
        fragment = ET.SubElement(page, 'fragment', {
            'id': '900', 'BoundingBox': '399 599 419 601'})
        ET.SubElement(fragment, 'n', {'id': '901', 'p': '400 600'})
        ET.SubElement(fragment, 'n', {'id': '902', 'p': '418 600'})
        ET.SubElement(fragment, 'b', {'id': '903', 'B': '901', 'E': '902'})
    else:
        caption = ET.SubElement(page, 't', {
            'id': '900', 'p': '410 600', 'BoundingBox': '400 592 420 602'})
        ET.SubElement(caption, 's', {'font': '3', 'size': '10'}).text = 'unowned'
    with pytest.raises(ValueError):
        verify_scope(expected, ET.tostring(root, encoding='unicode'), plan)


@pytest.mark.parametrize('label_key', ['caption_id', 'metadata_id'])
def test_native_caption_alignment_uses_ink_not_only_anchor(label_key):
    expected, plan = planned_grid()
    root = ET.fromstring(measured(expected))
    tid = plan['cells'][0][label_key]
    text = root.find(f'page/t[@id="{tid}"]')
    left, top, right, bottom = numbers(text.get('BoundingBox'), 4)
    # Text content and baseline anchor stay unchanged, but the visible ink is
    # no longer centred. There is still no overlap or page overflow.
    text.set('BoundingBox', f'{left + 6} {top} {right + 6} {bottom}')
    with pytest.raises(ValueError):
        verify_scope(expected, ET.tostring(root, encoding='unicode'), plan)


def test_native_reordering_and_renumbering_keep_duplicate_molecule_ownership():
    root = ET.fromstring(SAMPLE)
    page = root.find('page')
    original = page.find('fragment[@id="1"]')
    replacement = copy.deepcopy(original)
    for element in replacement.iter():
        for key in ('id', 'B', 'E'):
            if element.get(key):
                element.set(key, str(int(element.get(key)) + 200))
        if element.get('p'):
            x, y = numbers(element.get('p'), 2)
            element.set('p', f'{x + 200} {y + 100}')
    page.remove(page.find('fragment[@id="20"]'))
    page.append(replacement)
    cells = copy.deepcopy(CELLS)
    cells[1]['fragment_ids'] = ['201']
    cells[1]['yield_percent'] = 91
    prepared, state = prepare_scope(ET.tostring(root, encoding='unicode'), cells)
    expected, plan = arrange_scope(measured(prepared), state['cells'], columns=2)
    native = ET.fromstring(measured(expected))
    page = native.find('page')
    for element in page.iter():
        for key in ('id', 'B', 'E'):
            if element.get(key):
                element.set(key, str(int(element.get(key)) + 1000))
    page[:] = reversed(list(page))
    result = verify_scope(expected, ET.tostring(native, encoding='unicode'), plan)
    assert [cell['compound_id'] for cell in result['cells']] == ['3a', '3b']
    assert [cell['yield_percent'] for cell in result['cells']] == [0, 91]
    assert result['cells'][0]['fragment_ids'] == ['1001']
    assert result['cells'][1]['fragment_ids'] == ['1201']
