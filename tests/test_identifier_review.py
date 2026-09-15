"""Bounded independent review of identifier and scope input preservation."""
import pytest

from chemdraw_macos.identifiers import inspect_identifier
from chemdraw_macos.scope_design import propose_scope


@pytest.mark.parametrize('suffix', ['\x00', '\x01'])
def test_scope_parent_control_suffix_is_not_silently_discarded(suffix):
    with pytest.raises(ValueError):
        propose_scope('O=[CH][c:1]1ccccc1' + suffix, 1)


@pytest.mark.parametrize('smiles', ['[Na+].[Na+].[O-]C(=O)CC(=O)[O-]', '[Fe+2].[Cl-].[Cl-]'])
def test_generated_standard_inchi_stoichiometry_can_be_read_without_losing_components(smiles):
    source = inspect_identifier(smiles)
    assert source['inchi']['status'] == 'available'
    assert source['inchi']['graph_roundtrip_equivalent'] is True
    restored = inspect_identifier(source['inchi']['value'], 'inchi')
    assert restored['component_count'] == source['component_count']
    assert restored['formal_charge'] == source['formal_charge']
    assert restored['canonical_smiles'] == source['canonical_smiles']
