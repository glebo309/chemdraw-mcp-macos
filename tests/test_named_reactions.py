"""Named-reaction proposals: offline, read-only, products validated by the identifier gate."""
import json
import pytest

pytest.importorskip('rdkit')
from rdkit import Chem
from rdkit.Chem import AllChem

from chemdraw_macos import named_reactions as nr, reagents
from chemdraw_macos.identifiers import inspect_identifier


def canon(smiles):
    return inspect_identifier(smiles)['canonical_smiles']


def test_every_template_parses_and_is_one_or_two_component():
    table = nr.templates()
    assert len(table) >= 150
    for name, t in table.items():
        rxn = AllChem.ReactionFromSmarts(t['smarts'])
        assert rxn.GetNumReactantTemplates() == t['n_reactants'], name
        assert rxn.GetNumProductTemplates() >= 1, name


@pytest.mark.parametrize('reaction, substrate, partner, expected', [
    ('amide_coupling', 'CC(=O)O', 'NCc1ccccc1', 'CC(=O)NCc1ccccc1'),
    ('BOC deprotection', 'CC(C)(C)OC(=O)NCc1ccccc1', None, 'NCc1ccccc1'),
    ('nitro-reduction', 'c1ccc([N+](=O)[O-])cc1', None, 'Nc1ccccc1'),
    ('suzuki_coupling', 'Brc1ccccc1', 'OB(O)c1ccccc1', 'c1ccc(-c2ccccc2)cc1'),
])
def test_known_reactions_give_expected_product(reaction, substrate, partner, expected):
    out = nr.propose_products(reaction, substrate, partner)
    assert canon(expected) in {c['smiles'] for c in out['candidates']}
    assert all(c['inchikey'] and c['delta_vs_reactants'] for c in out['candidates'])
    assert 'review' in out


def test_partner_order_does_not_matter():
    a = nr.propose_products('amide_coupling', 'CC(=O)O', 'NCc1ccccc1')
    b = nr.propose_products('amide_coupling', 'NCc1ccccc1', 'CC(=O)O')
    assert {c['smiles'] for c in a['candidates']} == {c['smiles'] for c in b['candidates']}


def test_products_carry_no_atom_maps():
    out = nr.propose_products('suzuki_coupling', 'Brc1ccccc1', 'OB(O)c1ccccc1')
    for c in out['candidates']:
        assert not any(a.GetAtomMapNum() for a in Chem.MolFromSmiles(c['smiles']).GetAtoms())


def test_regiochemical_ambiguity_is_reported_not_resolved():
    out = nr.propose_products('amide_coupling', 'CC(=O)O', 'NCCN')
    assert out['ambiguous'] is (len(out['candidates']) > 1)


@pytest.mark.parametrize('args, message', [
    (('amide_coupling', 'CC(=O)O', None), 'needs a partner'),
    (('nitro_reduction', 'CCO', 'CC'), 'omit partner'),
    (('nitro_reduction', 'CCO', None), 'no match'),
    (('not_a_reaction_xyz', 'CCO', None), 'Unknown reaction'),
    (('nitro_reduction', 'c1ccc([N+](=O)[O-])cc1[*]', None), 'unsupported'),
])
def test_bad_requests_fail_loudly(args, message):
    with pytest.raises(ValueError, match=message):
        nr.propose_products(*args)


def test_list_filters():
    deprot = nr.list_reactions(category='deprotection')
    assert deprot and all(r['category'] == 'deprotection' for r in deprot)
    assert any('suzuki' in r['name'] for r in nr.list_reactions(query='suzuki'))


def test_reagent_data_is_valid_chemistry():
    data = json.loads((nr.DATA / 'reagents.json').read_text('utf-8'))
    for key, entry in data.items():
        smiles = entry.get('smiles') or []
        for s in ([smiles] if isinstance(smiles, str) else smiles):
            assert Chem.MolFromSmiles(s) is not None, key


def test_reagent_lookup_aliases_subscripts_and_misses():
    assert reagents.lookup_reagent('Cs₂CO₃')['display'] == 'Cs2CO3'
    assert reagents.lookup_reagent('cesium carbonate')['role'] == 'base'
    assert reagents.lookup_reagent('CuI')['display'] == 'CuI'
    assert reagents.lookup_reagent('unobtainium') is None
    assert {r['role'] for r in reagents.list_reagents('solvent')} == {'solvent'}
