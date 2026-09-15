"""Independent regression cases for the bounded analogue editor."""
import pytest

from chemdraw_macos.editing import plan_edit, verify_native_edit
from test_editing import ETHANOL


SYMMETRIC = '''<CDXML><page><fragment id="1">
<n id="2" p="0 0"/><n id="3" p="-18 10"/>
<n id="4" p="18 10"/><n id="5" p="0 -18" Element="9"/>
<b id="6" B="2" E="3"/><b id="7" B="2" E="4"/>
<b id="8" B="2" E="5"/></fragment></page></CDXML>'''


def test_edit_must_not_create_an_unspecified_tetrahedral_stereocentre():
    # The centre is initially achiral (two methyl groups). Replacing one
    # terminal carbon by NH2 creates a stereogenic centre without any wedge.
    with pytest.raises(ValueError, match='stereo'):
        plan_edit(SYMMETRIC,
                  [{'kind': 'atom', 'id': '4', 'element': 'N', 'hydrogens': 2}], {})


def test_edit_must_not_erase_an_unspecified_tetrahedral_stereocentre():
    source = SYMMETRIC.replace('id="4" p="18 10"',
                               'id="4" p="18 10" Element="7" NumHydrogens="2"')
    with pytest.raises(ValueError, match='stereo'):
        plan_edit(source,
                  [{'kind': 'atom', 'id': '4', 'element': 'C', 'hydrogens': 3}], {})


def test_native_atom_label_comparison_is_formula_aware_not_anagram_equality():
    planned, _ = plan_edit(ETHANOL,
                           [{'kind': 'atom', 'id': '4', 'element': 'N', 'hydrogens': 2}],
                           {'10': 'Ethylamine'})
    assert '>NH2<' in planned
    # Native graph attributes are unchanged, but this glyph corruption puts
    # the subscript on N instead of H. Sorting characters misses the error.
    corrupted = planned.replace('>NH2<', '>N2H<')
    with pytest.raises(ValueError, match='label'):
        verify_native_edit(planned, corrupted)
