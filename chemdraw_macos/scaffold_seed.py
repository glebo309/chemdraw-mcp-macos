"""Constrain new explicit-input MOL seeds to an existing native reference core.

This does not transform existing drawings. ChemDraw imports and renders the
new MOL, whose identity and native core coordinates must be checked afterward.
"""
import math
from .alignment import validate_scaffold_inputs, _input, _matches, _mean, _noncollinear


def seed_from_native_scaffold(smiles, reference_text, scaffold_smiles):
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Geometry import Point3D
    info = validate_scaffold_inputs([smiles], scaffold_smiles)
    reference = Chem.MolFromSmiles(info['canonical_smiles'])
    root, matches, positions, _ = _input(reference_text, reference)
    points = [positions[i] for i in matches[0]]
    _noncollinear(points)
    # CDXML has downward-positive y; MOL has upward-positive y.
    native_length = float(root.get('BondLength', '30'))
    if not math.isfinite(native_length) or native_length <= 0:
        raise ValueError('Invalid native reference bond length')
    scale = 1.5/native_length
    cx, cy = _mean(points)
    conformer = Chem.Conformer(reference.GetNumAtoms())
    for i, (x, y) in enumerate(points):
        conformer.SetAtomPosition(i, Point3D((x-cx)*scale, -(y-cy)*scale, 0))
    reference.AddConformer(conformer)
    parser = Chem.SmilesParserParams(); parser.removeHs = False
    target = Chem.MolFromSmiles(smiles, parser)
    canonical = Chem.MolToSmiles(target)
    match = _matches(target, reference)[0]
    params = rdDepictor.ConstrainedDepictionParams()
    params.alignOnly = False
    params.acceptFailure = False
    params.adjustMolBlockWedging = True
    params.forceRDKit = True
    rdDepictor.GenerateDepictionMatching2DStructure(target, reference, list(enumerate(match)), params=params)
    if any(a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for a in target.GetAtoms()):
        target.SetIntProp('_MolFileChiralFlag', 1)
    block = Chem.MolToMolBlock(target)
    decoded = Chem.MolFromMolBlock(block, removeHs=False)
    if decoded is None or Chem.MolToSmiles(decoded) != canonical:
        raise ValueError('Constrained MOL seed changed requested chemical identity')
    return block, {'reference_source': 'native ChemDraw coordinates',
                   'target_atom_indices': list(match), 'identity_roundtrip': True,
                   'native_remeasurement_required': True}
