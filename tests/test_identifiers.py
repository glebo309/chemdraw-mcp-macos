"""Offline identifier checks: strict input, preserved graph, explicit limits."""
import json

import pytest
from rdkit import Chem

from chemdraw_macos.identifiers import inspect_identifier


def test_ethanol_smiles_returns_offline_identifiers():
    result = inspect_identifier('OCC')
    assert result['canonical_smiles'] == 'CCO'
    assert result['formula'] == 'C2H6O'
    assert result['formal_charge'] == 0
    assert result['component_count'] == 1
    assert result['inchi']['status'] == 'available'
    assert result['inchi']['value'].startswith('InChI=1S/')
    assert len(result['inchi']['key']) == 27
    assert result['inchi']['graph_roundtrip_equivalent'] is True
    assert result['normalization']['salt_neutralization'] is False
    assert result['normalization']['tautomer_canonicalization'] is False
    json.dumps(result, allow_nan=False)


def test_standard_inchi_input_roundtrip():
    original = inspect_identifier('F[C@](Cl)(Br)I')
    result = inspect_identifier(original['inchi']['value'], input_format='inchi')
    assert result['canonical_smiles'] == original['canonical_smiles']
    assert len(result['stereo']['tetrahedral']) == 1


def test_isotopic_chiral_salt_retains_components_charge_and_stereo():
    value = '[13CH3][C@H](O)C(=O)[O-].[Na+]'
    result = inspect_identifier(value)
    assert result['component_count'] == 2
    assert result['formal_charge'] == 0
    assert result['isotopes'] == [{'atom_index': 0, 'element': 'C', 'mass_number': 13}]
    assert len(result['stereo']['tetrahedral']) == 1
    assert result['stereo']['tetrahedral'][0]['cip'] in ('R', 'S')
    mol = Chem.MolFromSmiles(result['canonical_smiles'])
    assert sorted(a.GetFormalCharge() for a in mol.GetAtoms() if a.GetFormalCharge()) == [-1, 1]
    assert result['inchi']['warnings']


def test_explicit_isotopic_and_ordinary_hydrogens_are_not_stripped():
    result = inspect_identifier('[2H]O[H]')
    assert result['atom_count'] == 3
    assert '[2H]' in result['canonical_smiles'] and '[H]' in result['canonical_smiles']
    assert result['isotopes'][0]['mass_number'] == 2


def test_enantiomers_and_alkene_stereo_remain_distinct():
    assert inspect_identifier('F[C@](Cl)(Br)I')['canonical_smiles'] != inspect_identifier('F[C@@](Cl)(Br)I')['canonical_smiles']
    e = inspect_identifier('F/C=C/F')
    z = inspect_identifier('F/C=C\\F')
    assert e['canonical_smiles'] != z['canonical_smiles']
    assert e['stereo']['double_bonds'][0]['configuration'] == 'STEREOE'
    assert z['stereo']['double_bonds'][0]['configuration'] == 'STEREOZ'


def test_unspecified_stereo_is_reported_not_invented():
    result = inspect_identifier('CC(O)C(=O)O')
    assert not result['stereo']['tetrahedral']
    assert result['stereo']['unspecified']
    assert '@' not in result['canonical_smiles']


@pytest.mark.parametrize('value', ['', 'CCO ethanol', ' CCO', 'CCO\n', 'CCO\tname',
    'CCO |atomProp:0.foo.bar|', '*CC', '[#6]C', '[C,N]', '[CH3:1]O',
    'C~C', 'N->[Cu]', '[Pt@SP1](Cl)(Br)(I)F', 'C1CC', 'C(C)(C)(C)(C)C',
    'C/C', 'C[C@H](C)O'])
def test_invalid_unsupported_or_silently_discarded_smiles_rejected(value):
    with pytest.raises(ValueError):
        inspect_identifier(value)


@pytest.mark.parametrize('value', ['InChI=1S/', 'InChI=1S/CH4/h1H4 trailing',
    'InChI=1S/CH4/h1H4/garbage', 'InChI=1S/CH4/h1H4/s1', 'InChI=1/CH4/h1H4'])
def test_invalid_or_noncanonical_standard_inchi_rejected(value):
    with pytest.raises(ValueError):
        inspect_identifier(value, 'inchi')


@pytest.mark.parametrize('value, fmt', [(None, 'smiles'), ('CCO', None), ('CCO', 'name'),
    ('64-17-5', 'cas'), ('C' * 10001, 'smiles')])
def test_input_contract_rejected(value, fmt):
    with pytest.raises(ValueError):
        inspect_identifier(value, fmt)


def test_missing_inchi_backend_is_explicit_without_losing_smiles(monkeypatch):
    import chemdraw_macos.identifiers as module
    monkeypatch.setattr(module, '_inchi_backend', lambda: None)
    result = inspect_identifier('CCO')
    assert result['canonical_smiles'] == 'CCO'
    assert result['inchi']['status'] == 'unavailable'
    assert result['inchi']['value'] is None and result['inchi']['key'] is None
    assert result['inchi']['reason']
    with pytest.raises(RuntimeError, match='InChI'):
        inspect_identifier('InChI=1S/CH4/h1H4', 'inchi')


def test_tautomers_are_not_merged_by_smiles_canonicalization():
    keto = inspect_identifier('O=C1CCCCN1')
    enol = inspect_identifier('OC1=CCCCN1')
    assert keto['canonical_smiles'] != enol['canonical_smiles']
    assert keto['normalization']['tautomer_canonicalization'] is False


def test_inchi_normalization_is_reported_separately_from_input_graph():
    result = inspect_identifier('O=C1CCCCN1')
    assert result['canonical_smiles'] == 'O=C1CCCCN1'
    assert result['inchi']['status'] == 'available'
    assert result['inchi']['graph_roundtrip_equivalent'] is False
    assert any('changes this graph' in text for text in result['inchi']['warnings'])


def test_failed_inchi_generation_is_explicit_without_fabricated_key(monkeypatch):
    import chemdraw_macos.identifiers as module
    class FailingBackend:
        def MolToInchi(self, mol):
            return '', 2, 'unsupported test graph', '', ''
    monkeypatch.setattr(module, '_inchi_backend', lambda: FailingBackend())
    result = inspect_identifier('CCO')
    assert result['inchi']['status'] == 'unavailable'
    assert result['inchi']['value'] is None and result['inchi']['key'] is None
    assert result['inchi']['graph_roundtrip_equivalent'] is None
    assert 'unsupported test graph' in result['inchi']['reason']
