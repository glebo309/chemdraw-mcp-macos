import math
import xml.etree.ElementTree as ET

import pytest

from test_api_drawing import EMPTY, assert_core_orientation

CAFFEINE = 'Cn1c(=O)c2c(ncn2C)n(C)c1=O'


def test_fresh_caffeine_has_vertical_fused_edge_and_upright_carbonyl():
    from chemdraw_macos.api_drawing import plan_addition
    from rdkit import Chem
    text, report = plan_addition(EMPTY, [{'compound_id': '1', 'label': 'Caffeine', 'smiles': CAFFEINE}])
    mol = Chem.MolsFromCDXML(text)[0]
    conf = mol.GetConformer()
    rings = mol.GetRingInfo().AtomRings()
    six = next(r for r in rings if len(r) == 6)
    five = next(r for r in rings if len(r) == 5)
    a, b = set(six) & set(five)
    assert conf.GetAtomPosition(a).x == pytest.approx(conf.GetAtomPosition(b).x, abs=.002)
    assert sum(conf.GetAtomPosition(i).x for i in six) / 6 > sum(conf.GetAtomPosition(i).x for i in five) / 5
    carbonyls = [bond for bond in mol.GetBonds() if bond.GetBondTypeAsDouble() == 2 and
                 any(atom.GetAtomicNum() == 8 for atom in (bond.GetBeginAtom(), bond.GetEndAtom()))]
    assert any(abs(conf.GetAtomPosition(b.GetBeginAtomIdx()).x - conf.GetAtomPosition(b.GetEndAtomIdx()).x) < .002 for b in carbonyls)
    assert report['orientations'][0]['policy'] == 'axis_aligned_six_ring'


@pytest.mark.parametrize('smiles', [CAFFEINE, 'c1ccccc1', 'Cc1ccc(C(=O)O)cc1', 'c1ccc2[nH]ccc2c1', 'N[C@@H](C)c1ccccc1'])
def test_orientation_is_a_proper_rigid_rotation_not_new_geometry(smiles):
    from chemdraw_macos.drawing_orientation import orient_new_molecule
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.Compute2DCoords(mol)
    before = Chem.Mol(mol)
    report = orient_new_molecule(mol)
    assert report['policy'] == 'axis_aligned_six_ring'
    assert abs(report['rotation_degrees']) <= 30.001
    c0, c1 = before.GetConformer(), mol.GetConformer()
    for i in range(mol.GetNumAtoms()):
        for j in range(i):
            assert (c0.GetAtomPosition(i) - c0.GetAtomPosition(j)).Length() == pytest.approx(
                (c1.GetAtomPosition(i) - c1.GetAtomPosition(j)).Length(), abs=1e-8)
    assert Chem.MolToSmiles(mol) == Chem.MolToSmiles(before)
    ring = mol.GetRingInfo().AtomRings()[0]
    def area(conf):
        return sum(conf.GetAtomPosition(i).x * conf.GetAtomPosition(j).y -
                   conf.GetAtomPosition(j).x * conf.GetAtomPosition(i).y
                   for i, j in zip(ring, ring[1:] + ring[:1]))
    assert area(c0) == pytest.approx(area(c1), abs=1e-8)


def test_manually_rotated_live_reference_wins_over_default():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.polish import transform
    text, _ = plan_addition(EMPTY, [{'compound_id': '1', 'label': 'Reference', 'smiles': CAFFEINE}])
    root = ET.fromstring(text)
    fragment = root.find('page/fragment')
    # Move a rotated reference into roomy paper, including its stored bounds.
    for node in fragment.findall('n'):
        x, y = map(float, node.get('p').split())
        angle = math.radians(13)
        point = f'{x * math.cos(angle) - y * math.sin(angle)} {x * math.sin(angle) + y * math.cos(angle)}'
        node.set('p', point)
        for caption in node.findall('t'):
            caption.set('p', point)
    fragment.set('BoundingBox', '0 0 250 250')
    root.find('page').set('BoundingBox', '0 0 1000 1000')
    for caption in list(root.findall('page/t')):
        root.find('page').remove(caption)
    before = ET.tostring(root, encoding='unicode')
    added, report = plan_addition(before, [{'compound_id': '2', 'label': 'New', 'smiles': CAFFEINE}])
    assert report['reference_source'] == 'live_document'
    assert_core_orientation(before, added, report['scaffold_smiles'])
    assert report['orientations'][0]['policy'] == 'reference_preserved'


def test_nonhexagonal_molecule_keeps_existing_seed_orientation():
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from chemdraw_macos.drawing_orientation import orient_new_molecule
    mol = Chem.MolFromSmiles('CCO')
    rdDepictor.Compute2DCoords(mol)
    before = mol.GetConformer().GetPositions().copy()
    assert orient_new_molecule(mol)['policy'] == 'seed_preserved'
    assert (mol.GetConformer().GetPositions() == before).all()
def test_fresh_acyclic_lysine_parent_has_exact_zigzag_axes_without_stereo_change():
    import math
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from chemdraw_macos.drawing_orientation import orient_new_molecule
    mol=Chem.MolFromSmiles('C=C(C)OC(=O)[C@@H](N)CCCCN')
    rdDepictor.Compute2DCoords(mol)
    before=Chem.MolToSmiles(mol)
    conf=mol.GetConformer()
    lengths=[(conf.GetAtomPosition(b.GetBeginAtomIdx())-conf.GetAtomPosition(b.GetEndAtomIdx())).Length()
             for b in mol.GetBonds()]
    report=orient_new_molecule(mol)
    assert report['policy']=='axis_aligned_acyclic'
    for bond,length in zip(mol.GetBonds(),lengths):
        v=conf.GetAtomPosition(bond.GetEndAtomIdx())-conf.GetAtomPosition(bond.GetBeginAtomIdx())
        angle=math.degrees(math.atan2(v.y,v.x))
        assert abs((angle-30+30)%60-30)<1e-6
        assert abs(v.Length()-length)<1e-9
    # The carbonyl is vertical; chain segments alternate +/-30 degrees.
    v=conf.GetAtomPosition(5)-conf.GetAtomPosition(4)
    assert abs(v.x)<1e-9
    assert Chem.MolToSmiles(Chem.MolFromMolBlock(Chem.MolToMolBlock(mol)))==before
