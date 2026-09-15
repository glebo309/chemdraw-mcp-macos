"""Independent offline review regressions for native structure assembly."""
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.draw import prepare_structures, combine_native_structures


ETHANOL = '''<CDXML LabelFont="3" LabelSize="10"><fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable><page id="99" BoundingBox="0 0 540 720"><fragment id="101"><n id="102" p="40 40"/><n id="103" p="56 49"/><n id="104" p="72 40" Element="8" NumHydrogens="1"><t p="72 40"><s font="3" size="10" face="96">OH</s></t></n><b id="105" B="102" E="103"/><b id="106" B="103" E="104"/></fragment></page></CDXML>'''


def test_relabelled_native_atom_fails_instead_of_claiming_requested_structure():
    records = prepare_structures([{'compound_id': 'a', 'label': 'Ethanol', 'smiles': 'CCO'}])
    wrong_display = ETHANOL.replace('>OH<', '>NH<')
    with pytest.raises(ValueError, match='label'):
        combine_native_structures([wrong_display], records)


def test_native_id_remap_does_not_leave_stale_bond_circular_ordering():
    records = prepare_structures([{'compound_id': 'a', 'label': 'Ethanol', 'smiles': 'CCO'}])
    native = ETHANOL.replace('id="105" B=', 'id="105" BondCircularOrdering="105 106" B=')
    assembled, _ = combine_native_structures([native], records)
    root = ET.fromstring(assembled)
    bond_ids = {b.get('id') for b in root.findall('page/fragment/b')}
    for bond in root.findall('page/fragment/b'):
        assert set(bond.get('BondCircularOrdering', '').split()) <= bond_ids


def test_native_charge_graphic_is_rejected_not_dropped():
    records = prepare_structures([{'compound_id': 'a', 'label': 'Ethanol', 'smiles': 'CCO'}])
    annotated = ETHANOL.replace('</fragment>', '<graphic id="200" GraphicType="Symbol" SymbolType="CirclePlus" BoundingBox="0 0 3 3"/></fragment>')
    with pytest.raises(ValueError, match='graphic'):
        combine_native_structures([annotated], records)
