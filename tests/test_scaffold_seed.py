import pytest
from rdkit import Chem
from test_alignment import ACETOPHENONE
from test_editing import CHIRAL
from chemdraw_macos.polish import chemical_signature


def test_seed_uses_native_reference_coordinates_and_preserves_explicit_graph():
    from chemdraw_macos.scaffold_seed import seed_from_native_scaffold
    from chemdraw_macos.alignment import _input,validate_scaffold
    smiles='CC(=O)c1ccc(C)cc1'
    scaffold='CC(=O)c1ccccc1'
    block,audit=seed_from_native_scaffold(smiles,ACETOPHENONE,scaffold)
    mol=Chem.MolFromMolBlock(block,removeHs=False)
    assert Chem.MolToSmiles(mol)==Chem.MolToSmiles(Chem.MolFromSmiles(smiles))
    query=Chem.MolFromSmiles(validate_scaffold(scaffold)['canonical_smiles'])
    _,matches,points,_=_input(ACETOPHENONE,query)
    native=[points[i] for i in matches[0]]
    cx=sum(p[0] for p in native)/len(native);cy=sum(p[1] for p in native)/len(native)
    for index,target_index in enumerate(audit['target_atom_indices']):
        p=mol.GetConformer().GetAtomPosition(target_index)
        assert (p.x,p.y)==pytest.approx(((native[index][0]-cx)*.05,-(native[index][1]-cy)*.05),abs=.0001)
    assert audit['reference_source']=='native ChemDraw coordinates'


def test_seed_preserves_assigned_stereo():
    from chemdraw_macos.scaffold_seed import seed_from_native_scaffold
    smiles=chemical_signature(CHIRAL)[0]
    block,_=seed_from_native_scaffold(smiles,CHIRAL,smiles)
    assert Chem.MolToSmiles(Chem.MolFromMolBlock(block,removeHs=False))==smiles


def test_seed_rejects_missing_core():
    from chemdraw_macos.scaffold_seed import seed_from_native_scaffold
    with pytest.raises(ValueError):seed_from_native_scaffold('CCO',ACETOPHENONE,'CC(=O)c1ccccc1')
