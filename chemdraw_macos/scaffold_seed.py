"""Constrain new explicit-input MOL seeds to an existing native reference core.

This does not transform existing drawings. ChemDraw imports and renders the
new MOL, whose identity and native core coordinates must be checked afterward.
"""
import math
from .alignment import validate_scaffold_inputs, _input, _matches, _mean, _noncollinear


def _separate_new_branches(mol, locked):
    """Rotate only new singly attached branches, preserving all bond lengths."""
    from rdkit.Geometry import Point3D
    from .placement import segment_distance
    conf=mol.GetConformer();pending=set(range(mol.GetNumAtoms()))-set(locked)
    while pending:
        component={pending.pop()};todo=list(component)
        while todo:
            for atom in mol.GetAtomWithIdx(todo.pop()).GetNeighbors():
                i=atom.GetIdx()
                if i in pending:pending.remove(i);component.add(i);todo.append(i)
        attachments=[(i,n.GetIdx()) for i in component for n in mol.GetAtomWithIdx(i).GetNeighbors() if n.GetIdx() in locked]
        if len(attachments)!=1:continue
        _,anchor=attachments[0];origin=conf.GetAtomPosition(anchor)
        saved={i:conf.GetAtomPosition(i) for i in component};others=set(range(mol.GetNumAtoms()))-component
        moving=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()
                if b.GetBeginAtomIdx() in component or b.GetEndAtomIdx() in component]
        fixed=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()
               if b.GetBeginAtomIdx() not in component and b.GetEndAtomIdx() not in component]
        def clear():
            if any((conf.GetAtomPosition(i)-conf.GetAtomPosition(j)).Length()<=.45 for i in component for j in others):return False
            def xy(i):
                p=conf.GetAtomPosition(i);return p.x,p.y
            return all(segment_distance(xy(a),xy(b),xy(c),xy(d))>.05
                       for a,b in moving for c,d in fixed if not {a,b}&{c,d})
        if clear():continue
        for degrees in (30,-30,60,-60,90,-90,120,-120,150,-150,180):
            angle=math.radians(degrees);c,s=math.cos(angle),math.sin(angle)
            for i,p in saved.items():
                x,y=p.x-origin.x,p.y-origin.y
                conf.SetAtomPosition(i,Point3D(origin.x+c*x-s*y,origin.y+s*x+c*y,p.z))
            if clear():break
        else:
            for i,p in saved.items():conf.SetAtomPosition(i,p)


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
    def separated():
        conf=target.GetConformer()
        return all((conf.GetAtomPosition(i)-conf.GetAtomPosition(j)).Length()>.45
                   for i in range(target.GetNumAtoms()) for j in range(i))
    if not separated():
        # A fixed terminal methyl can collide with a new geminal substituent.
        _separate_new_branches(target,set(match))
        if not separated():raise ValueError('Constrained seed contains overlapping atoms; no native write performed')
        if any((target.GetConformer().GetAtomPosition(j)-conformer.GetAtomPosition(i)).Length()>.0002
               for i,j in enumerate(match)):
            raise ValueError('Constrained seed moved a reference atom; no native write performed')
    if any(a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for a in target.GetAtoms()):
        target.SetIntProp('_MolFileChiralFlag', 1)
    block = Chem.MolToMolBlock(target)
    decoded = Chem.MolFromMolBlock(block, removeHs=False)
    if decoded is None or Chem.MolToSmiles(decoded) != canonical:
        raise ValueError('Constrained MOL seed changed requested chemical identity')
    return block, {'reference_source': 'native ChemDraw coordinates',
                   'target_atom_indices': list(match), 'identity_roundtrip': True,
                   'native_remeasurement_required': True}
