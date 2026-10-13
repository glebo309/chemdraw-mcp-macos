"""Automatic peptide depiction is graph-driven, not tied to names or atom order."""
import math

import pytest
from rdkit import Chem
from rdkit.Chem import rdDepictor

TETRAPEPTIDE = 'CC(=O)NCC(=O)N[C@@H](Cc1ccccc1)C(=O)N[C@@H](CO)C(=O)N[C@@H](CC(C)C)C(=O)O'


def check_backbone(mol, path, length=1.5, tolerance=1e-6):
    conf = mol.GetConformer()
    points = [conf.GetAtomPosition(i) for i in path]
    for i, (a, b) in enumerate(zip(points, points[1:])):
        in_ring = mol.GetBondBetweenAtoms(path[i], path[i+1]).IsInRing()
        assert b.x - a.x == pytest.approx(length if in_ring else length * math.sqrt(3) / 2, abs=tolerance)
        assert abs(b.y - a.y) == pytest.approx(0 if in_ring else length / 2, abs=tolerance)
    assert max(p.y for p in points) - min(p.y for p in points) == pytest.approx(length / 2, abs=tolerance)


@pytest.mark.parametrize('sequence', list('ACDEFGHIKLMNPQRSTVWY'))
def test_natural_residue_sidechains_and_proline_keep_identity(sequence):
    from chemdraw_macos.peptide_layout import layout_linear_peptide
    mol = Chem.MolFromSequence('G' + sequence + 'A')
    expected = Chem.MolToSmiles(mol)
    report = layout_linear_peptide(mol)
    assert report['policy'] == 'linear_peptide'
    assert report['residue_count'] == 3
    check_backbone(mol, report['backbone_atom_indices'])
    decoded = Chem.MolFromMolBlock(Chem.MolToMolBlock(mol), removeHs=False)
    assert Chem.MolToSmiles(decoded) == expected
    conf = mol.GetConformer()
    assert all((conf.GetAtomPosition(i) - conf.GetAtomPosition(j)).Length() > .45
               for i in range(mol.GetNumAtoms()) for j in range(i))


@pytest.mark.parametrize('smiles', [TETRAPEPTIDE, TETRAPEPTIDE.replace('@@', '@'),
    TETRAPEPTIDE.replace('[C@@H]', 'C'), '[NH3+]CC(=O)N[C@@H](C)C(=O)[O-]',
    '[13CH3]C(=O)NCC(=O)N[C@@H](CO)C(=O)OC'])
def test_caps_charge_isotope_unspecified_and_d_stereo_preserved(smiles):
    from chemdraw_macos.peptide_layout import layout_linear_peptide
    mol = Chem.MolFromSmiles(smiles)
    expected = Chem.MolToSmiles(mol)
    report = layout_linear_peptide(mol)
    check_backbone(mol, report['backbone_atom_indices'])
    assert Chem.MolToSmiles(Chem.MolFromMolBlock(Chem.MolToMolBlock(mol))) == expected


@pytest.mark.parametrize('smiles', ['CC(=O)NCC(=O)O', 'CC(=O)Nc1ccc(O)cc1',
    'O=C1NCC(=O)NC1', 'NCC(=O)O.NCC(=O)O',
    'N[C@@H]1CSSC[C@H](NC(=O)[C@@H](C)NC1=O)C(=O)O'])
def test_nonpeptides_single_residues_cycles_and_crosslinks_unchanged(smiles):
    from chemdraw_macos.peptide_layout import layout_linear_peptide
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.Compute2DCoords(mol)
    before = mol.GetConformer().GetPositions().copy()
    assert layout_linear_peptide(mol) is None
    assert (before == mol.GetConformer().GetPositions()).all()


def test_default_front_door_layout_and_cdxml_identity():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.reaction_batch import EMPTY
    from chemdraw_macos.polish import chemical_signature
    text, report = plan_addition(EMPTY, [{'compound_id': '1', 'label': 'Peptide', 'smiles': TETRAPEPTIDE}])
    orientation = report['orientations'][0]
    assert orientation['policy'] == 'linear_peptide'
    assert chemical_signature(text) == [Chem.MolToSmiles(Chem.MolFromSmiles(TETRAPEPTIDE))]
    import xml.etree.ElementTree as ET
    mol = Chem.MolFromSmiles(Chem.MolToSmiles(Chem.MolFromSmiles(TETRAPEPTIDE)))
    conf = Chem.Conformer(mol.GetNumAtoms())
    for i, node in enumerate(ET.fromstring(text).findall('page/fragment/n')):
        x, y = map(float, node.get('p').split())
        conf.SetAtomPosition(i, (x, y, 0))
    mol.AddConformer(conf)
    # Read actual CDXML points: decoder units vary between RDKit builds.
    check_backbone(mol, orientation['backbone_atom_indices'], length=18, tolerance=.015)


def test_atom_order_does_not_reverse_peptide_direction():
    from chemdraw_macos.peptide_layout import layout_linear_peptide
    mol = Chem.MolFromSmiles(TETRAPEPTIDE)
    reversed_mol = Chem.RenumberAtoms(mol, list(reversed(range(mol.GetNumAtoms()))))
    for candidate in [mol, reversed_mol]:
        report = layout_linear_peptide(candidate)
        check_backbone(candidate, report['backbone_atom_indices'])
        assert candidate.GetAtomWithIdx(report['backbone_atom_indices'][-1]).GetAtomicNum() == 6


def test_live_peptide_reference_still_wins():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.reaction_batch import EMPTY
    import xml.etree.ElementTree as ET
    records = [{'compound_id': '1', 'label': 'Peptide', 'smiles': TETRAPEPTIDE}]
    before, _ = plan_addition(EMPTY, records)
    root = ET.fromstring(before)
    # Use exact native-style coordinates for the reference decoder's unit map.
    for node in root.findall('page/fragment/n'):
        x, y = map(float, node.get('p').split())
        node.set('p', f'{round(x)} {round(y)}')
    before = ET.tostring(root, encoding='unicode')
    result, report = plan_addition(before, records, allow_page_expansion=True)
    assert report['orientations'][0]['policy'] == 'reference_preserved'
    assert report['reference_source'] == 'live_document'
