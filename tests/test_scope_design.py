import json

import pytest

Chem = pytest.importorskip('rdkit.Chem')

from chemdraw_macos.scope_design import propose_scope


PARENT = 'CC(=O)[c:1]1ccccc1'


def test_standard_coverage_and_no_results():
    result = propose_scope(PARENT, 1)
    assert result['status'] == 'proposal'
    assert len(result['candidates']) == 14
    labels = {c['display_label'] for c in result['candidates']}
    assert labels == {'Parent reference', '2-Me relative to parent', '3-Me relative to parent',
                      '4-Me relative to parent', '4-OMe relative to parent',
                      '4-CF3 relative to parent', '4-CN relative to parent',
                      '4-NO2 relative to parent', '4-F relative to parent',
                      '4-Cl relative to parent', '4-Br relative to parent',
                      '2-iPr relative to parent', '2-tBu relative to parent',
                      '2,6-Me2 relative to parent'}
    for candidate in result['candidates']:
        assert candidate['yield_percent'] is None
        assert candidate['checks']['parent_heavy_atom_graph_preserved'] is True
        assert candidate['checks']['existing_stereochemistry_preserved'] is True
        assert candidate['checks']['smiles_roundtrip_verified'] is True
        assert Chem.MolFromSmiles(candidate['canonical_smiles']) is not None
        assert all(not a.GetAtomMapNum() for a in Chem.MolFromSmiles(candidate['canonical_smiles']).GetAtoms())
        assert sum(a.GetAtomMapNum() == 1 for a in Chem.MolFromSmiles(candidate['mapped_smiles']).GetAtoms()) == 1
        assert candidate['compatibility_questions']
    json.dumps(result, allow_nan=False)


def test_deduplication_merges_coverage_and_ids_ignore_map_tags():
    first = propose_scope(PARENT, 1)['candidates']
    other = propose_scope('O=C(C)[c:42]1ccccc1', 42)
    assert {x['candidate_id'] for x in first} == {x['candidate_id'] for x in other['candidates']}
    assert len({x['canonical_smiles'] for x in first}) == len(first)
    para_me = next(x for x in first if x['display_label'] == '4-Me relative to parent')
    assert set(para_me['categories']) == {'electron_donating', 'positional'}
    ortho_me = next(x for x in first if x['display_label'] == '2-Me relative to parent')
    assert set(ortho_me['categories']) == {'positional', 'steric'}


def test_handle_graph_and_remote_tetrahedral_configuration_retained():
    parent = 'C[C@H](O)[c:7]1ccccc1'
    source = Chem.MolFromSmiles(parent)
    signature = Chem.MolToSmiles(source, isomericSmiles=True)
    result = propose_scope(parent, 7)
    for candidate in result['candidates']:
        product = Chem.MolFromSmiles(candidate['mapped_smiles'])
        assert product.HasSubstructMatch(source, useChirality=True)
        stereo = [a for a in product.GetAtoms() if a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED]
        assert len(stereo) == 1
    assert Chem.MolToSmiles(source, isomericSmiles=True) == signature


def test_explicit_aromatic_h_counts_are_replaced_at_attachment_sites():
    result = propose_scope('O=[CH][c:1]1[cH][cH][cH][cH][cH]1', 1)
    assert len(result['candidates']) == 14
    assert all(Chem.MolFromSmiles(c['canonical_smiles']) for c in result['candidates'])


@pytest.mark.parametrize('smiles,anchor', [
    ('CC(=O)c1ccccc1', 1),
    ('[cH:1]1ccccc1', 1),
    ('CC(=O)[c:1]1cc(C)ccc1', 1),
    ('CC(=O)[c:1]1cccc2ccccc12', 1),
    ('CC(=O)[c:1]1ccccn1', 1),
    ('C[CH:1](O)c1ccccc1', 1),
    ('CC(=O)[c:1]1ccccc1.[Na+]', 1),
    ('C[CH:1](O)[c:1]1ccccc1', 1),
    ('CC(=O)[c:1]1cc[13cH]cc1', 1),
    ('CC(O)[c:1]1ccccc1', 1),
    ('C/C=C/[c:1]1ccccc1', 1),
    ('*[c:1]1ccccc1', 1),
    ('CC(=O)[c:1]1ccccc1 test', 1),
    ('CC(=O)[c:1]1ccccc1 |atomProp:0.x.y|', 1),
    ('not smiles', 1),
])
def test_unsupported_or_ambiguous_parents_fail_closed(smiles, anchor):
    with pytest.raises(ValueError):
        propose_scope(smiles, anchor)


@pytest.mark.parametrize('anchor', [0, -1, True, '1', 1.0, None])
def test_anchor_requires_positive_integer(anchor):
    with pytest.raises(ValueError):
        propose_scope(PARENT, anchor)


def test_unknown_profile_rejected():
    with pytest.raises(ValueError, match='profile'):
        propose_scope(PARENT, 1, profile='everything')


def test_symmetry_breaking_that_creates_stereocenter_is_rejected():
    with pytest.raises(ValueError, match='stereo'):
        propose_scope('CC(O)(c1ccccc1)[c:1]1ccccc1', 1)


def test_explicit_hydrogen_atoms_are_not_silently_removed():
    with pytest.raises(ValueError, match='explicit hydrogen'):
        propose_scope('[H]C(=O)[c:1]1ccccc1', 1)


def test_handle_isotope_and_charge_preserved():
    for parent in ('[13CH3]C(=O)[c:5]1ccccc1', 'C[N+](C)(C)[c:5]1ccccc1'):
        result = propose_scope(parent, 5)
        reference = Chem.MolFromSmiles(parent)
        for candidate in result['candidates']:
            assert Chem.MolFromSmiles(candidate['mapped_smiles']).HasSubstructMatch(reference)


def test_repeated_calls_are_deterministic():
    assert propose_scope(PARENT, 1) == propose_scope(PARENT, 1)


@pytest.mark.parametrize('smiles', ['C[C@](C)(C)[c:1]1ccccc1', 'C/C[c:1]1ccccc1'])
def test_unsupported_input_stereo_is_not_silently_discarded(smiles):
    with pytest.raises(ValueError, match='stereo'):
        propose_scope(smiles, 1)
