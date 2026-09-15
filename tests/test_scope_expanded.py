"""Explicit-site proposals on pre-substituted and heteroaromatic parents."""

import json

import pytest

Chem = pytest.importorskip('rdkit.Chem')

from chemdraw_macos.scope_design import propose_custom_scope, propose_scope


PYRIDINE = 'n1[cH:2]c[cH:4]cc1'
PRESUBSTITUTED = 'Cc1[cH:2]cc(Cl)[cH:5]c1'
GROUPS = ['Me', 'OMe', 'CF3', 'CN', 'NO2', 'F', 'Cl', 'Br', 'iPr', 'tBu']


def identity(smiles):
    mol = Chem.MolFromSmiles(smiles)
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(mol, isomericSmiles=True)


def test_selected_pyridine_positions_are_explicit_and_not_guessed():
    result = propose_custom_scope(PYRIDINE, [2, 4], ['Me'])
    assert result['profile'] == 'custom'
    assert result['status'] == 'proposal'
    assert result['parent']['site_atom_maps'] == [2, 4]
    assert {c['canonical_smiles'] for c in result['candidates']} == {
        identity('n1ccccc1'), identity('Cc1ccccn1'), identity('Cc1ccncc1')}
    assert [c['display_label'] for c in result['candidates']] == [
        'Parent reference', 'Me at parent atom map 2', 'Me at parent atom map 4']
    assert all(c['yield_percent'] is None for c in result['candidates'])
    for candidate in result['candidates'][1:]:
        assert len(candidate['substitutions']) == 1
        assert set(candidate['substitutions'][0]) == {
            'site_atom_map', 'parent_atom_index', 'substituent'}
        assert all(candidate['checks'].values())
    json.dumps(result, allow_nan=False)


def test_presubstituted_parent_keeps_every_existing_group():
    result = propose_custom_scope(PRESUBSTITUTED, [2, 5], ['OMe', 'CF3'])
    assert len(result['candidates']) == 5
    source = Chem.MolFromSmiles(identity(PRESUBSTITUTED))
    for candidate in result['candidates']:
        product = Chem.MolFromSmiles(candidate['canonical_smiles'])
        assert product.HasSubstructMatch(source, useChirality=True)
        assert sum(a.GetAtomicNum() == 17 for a in product.GetAtoms()) == 1
    assert {c['substitutions'][0]['site_atom_map'] for c in result['candidates'][1:]} == {2, 5}


@pytest.mark.parametrize('parent', [
    'o1[cH:2]ccc1', 's1[cH:2]ccc1', '[nH]1[cH:2]ccc1',
    'n1[cH:2]nccc1', 'c1[cH:2]n[nH]c1',
])
def test_simple_five_and_six_membered_heterorings(parent):
    result = propose_custom_scope(parent, [2], GROUPS, include_parent=False)
    assert len(result['candidates']) == 10
    assert {c['substitutions'][0]['substituent'] for c in result['candidates']} == set(GROUPS)
    for candidate in result['candidates']:
        assert candidate['canonical_smiles'] == identity(candidate['mapped_smiles'])
        assert all(candidate['checks'].values())


def test_symmetric_requests_deduplicate_graph_but_retain_requested_routes():
    result = propose_custom_scope('[cH:1]1[cH:2]cccc1', [1, 2], ['Me'], False)
    assert len(result['candidates']) == 1
    candidate = result['candidates'][0]
    assert {v['site_atom_map'] for v in candidate['requested_variants']} == {1, 2}
    assert len(candidate['substitutions']) == 1
    assert result['requested_candidate_count'] == 2
    assert result['deduplicated_candidate_count'] == 1


def test_ids_ignore_map_numbers_and_request_order_is_deterministic():
    first = propose_custom_scope(PYRIDINE, [2, 4], ['Me', 'Cl'])
    other = propose_custom_scope('n1[cH:22]c[cH:44]cc1', [44, 22], ['Cl', 'Me'])
    assert {c['candidate_id'] for c in first['candidates']} == {
        c['candidate_id'] for c in other['candidates']}
    assert first == propose_custom_scope(PYRIDINE, [2, 4], ['Me', 'Cl'])


@pytest.mark.parametrize('parent', [
    'C[C@H](O)c1[cH:2]cc(Cl)cc1',
    '[13CH3]C(=O)c1[cH:2]cc(Cl)cc1',
    'C[N+](C)(C)c1[cH:2]cc(Cl)cc1',
])
def test_remote_stereo_isotope_and_charge_are_preserved(parent):
    result = propose_custom_scope(parent, [2], GROUPS)
    source = Chem.MolFromSmiles(identity(parent))
    for candidate in result['candidates']:
        assert Chem.MolFromSmiles(candidate['canonical_smiles']).HasSubstructMatch(source, useChirality=True)


@pytest.mark.parametrize('parent,sites', [
    ('n1ccccc1', [2]),
    ('[n:2]1ccccc1', [2]),
    ('[nH:2]1cccc1', [2]),
    ('C[c:2]1ccccc1', [2]),
    ('[CH3:2]c1ccccc1', [2]),
    ('[cH:2]1cccc2ccccc12', [2]),
    ('[13cH:2]1ccccc1', [2]),
    ('[nH+]1[cH:2]cccc1', [2]),
    ('[cH:2]1cccc[cH:2]1', [2]),
    ('[cH:2]1ccccc1.[Cl-]', [2]),
    ('[H]Oc1[cH:2]cccc1', [2]),
    ('*c1[cH:2]cccc1', [2]),
    ('C/C=C/c1[cH:2]cccc1', [2]),
    ('CC(O)c1[cH:2]cccc1', [2]),
    ('CC(O)(c1ccccc1)c1[cH:2]cccc1', [2]),
    ('[cH:2]1ccccc1 name', [2]),
    ('[cH:2]1ccccc1 |atomProp:0.x.y|', [2]),
])
def test_unsupported_or_ambiguous_parent_fails_closed(parent, sites):
    with pytest.raises(ValueError):
        propose_custom_scope(parent, sites, ['Me'])


@pytest.mark.parametrize('sites', [None, [], '2', [0], [-2], [True], [2.0], ['2'], [2, 2], {}])
def test_site_list_is_strict_and_unique(sites):
    with pytest.raises(ValueError, match='site_atom_maps'):
        propose_custom_scope(PYRIDINE, sites, ['Me'])


@pytest.mark.parametrize('groups', [None, [], 'Me', ['Me', 'Me'], ['Et'], ['C'],
                                   ['[CH3]'], ['cl'], [1], [{}]])
def test_substituent_list_is_strict_curated_and_unique(groups):
    with pytest.raises(ValueError, match='substituents'):
        propose_custom_scope(PYRIDINE, [2], groups)


@pytest.mark.parametrize('include', [None, 0, 1, 'false'])
def test_include_parent_requires_boolean(include):
    with pytest.raises(ValueError, match='include_parent'):
        propose_custom_scope(PYRIDINE, [2], ['Me'], include)


def test_limit_counts_requested_combinations_before_deduplication():
    # Ten mapped H sites across two independently isolated rings.
    parent = 'c1([cH:1][cH:2][cH:3][cH:4][cH:5]1)c1[cH:6][cH:7][cH:8][cH:9][cH:10]1'
    result = propose_custom_scope(parent, list(range(1, 11)), GROUPS, False)
    assert result['requested_candidate_count'] == 100
    assert len(result['candidates']) <= 100
    with pytest.raises(ValueError, match='100'):
        propose_custom_scope(parent, list(range(1, 11)), GROUPS)


def test_standard_profile_contract_is_unchanged():
    assert len(propose_scope('CC(=O)[c:1]1ccccc1', 1)['candidates']) == 14
    with pytest.raises(ValueError):
        propose_scope(PRESUBSTITUTED, 2)
