"""Native rounding regressions found during aligned-drawing integration."""
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.workflow import remap_ids
from chemdraw_macos.scope import verify_molecules


# Minimal coordinates reproduce the native 2-Me alignment failure: the bottom
# atom has a slightly smaller x before save, but equal x after rounding, so a
# lexicographic sort reverses its order relative to the top oxygen.
NEAR_VERTICAL = '''<CDXML BondLength="18"><page id="1"><fragment id="22"><n id="23" p="201.673710 71.177372"/><n id="24" p="192.674010 55.588741"/><n id="25" p="201.674310 40.000000" Element="8" NumHydrogens="1"/><b id="33" B="23" E="24"/><b id="34" B="24" E="25"/></fragment></page></CDXML>'''


def rounded_native(text):
    root = ET.fromstring(text)
    for node in root.findall('.//n'):
        node.set('p', ' '.join(f'{float(v):.2f}' for v in node.get('p').split()))
    for e in root.find('page').iter():
        for key in ('id', 'B', 'E'):
            if e.get(key):
                e.set(key, str(int(e.get(key)) + 1000))
    return ET.tostring(root, encoding='unicode')


def test_nearly_equal_x_coordinate_order_may_change_after_native_rounding():
    native = rounded_native(NEAR_VERTICAL)
    assert remap_ids(NEAR_VERTICAL, native)['22'] == '1022'
    mapping, checks = verify_molecules(NEAR_VERTICAL, native)
    assert mapping['22'] == '1022'
    assert checks['22']['mapped_chemistry_verified']


def test_coordinate_bijection_does_not_accept_a_missing_point_reused_twice():
    root = ET.fromstring(rounded_native(NEAR_VERTICAL))
    root.find('.//n[@id="1025"]').set('p', '201.67 71.18')
    with pytest.raises(ValueError):
        remap_ids(NEAR_VERTICAL, ET.tostring(root, encoding='unicode'))


def test_fragment_match_retains_point_distance_tolerance():
    root = ET.fromstring(rounded_native(NEAR_VERTICAL))
    root.find('.//n[@id="1025"]').set('p', '201.71 40')
    with pytest.raises(ValueError):
        remap_ids(NEAR_VERTICAL, ET.tostring(root, encoding='unicode'))


def test_reaction_arrow_head_and_tail_are_not_an_unordered_point_set():
    before = NEAR_VERTICAL.replace('</page>', '<arrow id="50" Head3D="300 60 0" Tail3D="260 60 0"/></page>')
    root = ET.fromstring(before)
    arrow = root.find('page/arrow')
    arrow.set('Head3D', '260 60 0'); arrow.set('Tail3D', '300 60 0')
    with pytest.raises(ValueError):
        remap_ids(before, ET.tostring(root, encoding='unicode'))
