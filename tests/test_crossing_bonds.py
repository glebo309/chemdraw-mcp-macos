import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import chemical_signature, supported_root
from chemdraw_macos.editing import verify_native_edit


RAW = '''<CDXML><page id="1" BoundingBox="0 0 300 300"><fragment id="2">
<n id="3" p="50 50"/><n id="4" p="80 80"/>
<n id="5" p="50 80"/><n id="6" p="80 50"/>
<b id="10" B="3" E="4" Z="1" CrossingBonds="12"/>
<b id="11" B="4" E="5" Z="2"/>
<b id="12" B="5" E="6" Z="3" CrossingBonds="10"/>
<b id="13" B="6" E="3" Z="4"/>
</fragment></page></CDXML>'''


def test_crossing_cache_is_supported_without_changing_chemistry():
    assert chemical_signature(RAW) == ['C1CCC1']
    assert verify_native_edit(RAW, RAW)['crossing_order_verified']


@pytest.mark.parametrize('refs', ['99', '3', '10', '12 12'])
def test_bad_crossing_references_fail_closed(refs):
    with pytest.raises(ValueError, match='crossing'):
        supported_root(RAW.replace('CrossingBonds="12"', f'CrossingBonds="{refs}"'))


def test_native_over_under_change_is_rejected():
    changed = RAW.replace('Z="1"', 'Z="5"')
    with pytest.raises(ValueError, match='crossing'):
        verify_native_edit(RAW, changed)


def test_relative_z_preserved_when_absolute_z_values_change():
    changed = RAW.replace('Z="1"', 'Z="11"').replace('Z="3"', 'Z="13"')
    assert verify_native_edit(RAW, changed)['crossing_order_verified']


def test_native_may_recompute_crossing_cache_with_same_coordinates_and_order():
    # Cached lists describe ink crossings too, not only centreline intersections.
    source = RAW.replace('CrossingBonds="12"', '').replace('CrossingBonds="10"', '')
    source = source.replace('80 80', '80 52').replace('50 80', '50 54')
    source = source.replace('id="6" p="80 50"', 'id="6" p="80 56"')
    native = source.replace('Z="1"', 'Z="1" CrossingBonds="12"')
    assert verify_native_edit(source, native)['crossing_order_verified']


def test_crossing_refs_are_remapped_during_native_assembly():
    from chemdraw_macos.draw import combine_native_structures
    root = ET.fromstring(RAW)
    root.find('page/fragment').set('BoundingBox', '50 50 80 80')
    text, _ = combine_native_structures([ET.tostring(root, encoding='unicode')],
        [{'compound_id': 'cage', 'label': 'Crossing fixture', 'canonical_smiles': 'C1CCC1'}])
    result = supported_root(text)
    bonds = {b.get('id') for b in result.findall('page/fragment/b')}
    assert all(set(b.get('CrossingBonds', '').split()) <= bonds
               for b in result.findall('page/fragment/b'))


def test_polish_rejects_changed_crossing_order(tmp_path):
    from test_workflow import FakeBridge
    from chemdraw_macos.workflow import polish_document
    bridge = FakeBridge(tmp_path / 'work')
    bridge.docs[1] = RAW
    create = bridge.create
    bridge.create = lambda text: create(text.replace('Z="1"', 'Z="5"'))
    with pytest.raises(ValueError, match='crossing'):
        polish_document(bridge, 1, str(tmp_path / 'out'))
