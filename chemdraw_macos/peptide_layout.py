"""Horizontal N-to-C coordinate seeds for unambiguous linear alpha peptides.

Only fresh structures use this policy. Cyclic, cross-linked and branched
backbones retain the ordinary depiction policy; no chemistry is rewritten.
"""
import math


def layout_linear_peptide(mol):
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Geometry import Point2D

    if len(Chem.GetMolFrags(mol)) != 1:
        return None
    query = Chem.MolFromSmarts('[#7;!a]-[C;X4]-[C;X3](=[O;X1])')
    residues = mol.GetSubstructMatches(query)
    if len(residues) < 2:
        return None
    # Every residue must have a unique N, alpha carbon and carbonyl. Do not
    # guess one path through a branched or multiply interpretable backbone.
    if any(len({r[k] for r in residues}) != len(residues) for k in range(3)):
        return None
    by_n = {r[0]: r for r in residues}
    links = {}
    for n, alpha, carbonyl, oxygen in residues:
        following = [a.GetIdx() for a in mol.GetAtomWithIdx(carbonyl).GetNeighbors()
                     if a.GetIdx() in by_n]
        if len(following) > 1:
            return None
        if following:
            nxt = following[0]
            if mol.GetBondBetweenAtoms(carbonyl, nxt).IsInRing():
                return None
            links[n] = nxt
    starts = set(by_n) - set(links.values())
    if len(starts) != 1 or len(set(links.values())) != len(links):
        return None
    ordered = []
    n = starts.pop()
    while n not in {r[0] for r in ordered}:
        ordered.append(by_n[n])
        if n not in links:
            break
        n = links[n]
    if len(ordered) != len(residues):
        return None
    backbone = [i for r in ordered for i in r[:3]]
    carbonyls = {r[2]: r[3] for r in ordered}
    # Include a unique N-acyl cap on the same axis without prescribing the
    # cap's identity or changing the number of peptide residues.
    caps = []
    for atom in mol.GetAtomWithIdx(ordered[0][0]).GetNeighbors():
        if atom.GetIdx() in backbone or atom.GetAtomicNum() != 6:
            continue
        oxygens = [b.GetOtherAtom(atom).GetIdx() for b in atom.GetBonds()
                   if b.GetBondTypeAsDouble() == 2 and b.GetOtherAtom(atom).GetAtomicNum() == 8]
        if len(oxygens) == 1:
            caps.append((atom.GetIdx(), oxygens[0]))
    if len(caps) > 1:
        return None
    if caps:
        backbone.insert(0, caps[0][0])
        carbonyls.update(caps)
    coords = {backbone[0]: Point2D(0, 0)}
    prolines = []
    for a, b in zip(backbone, backbone[1:]):
        p = coords[a]
        bond = mol.GetBondBetweenAtoms(a, b)
        if bond.IsInRing():
            # A proline N-C alpha edge must be horizontal so its five-ring
            # lies outside the backbone strip, not over a neighbouring amide.
            rings = [r for r in mol.GetRingInfo().AtomRings() if a in r and b in r]
            if (len(rings) != 1 or len(rings[0]) != 5 or
                    mol.GetAtomWithIdx(a).GetAtomicNum() != 7 or
                    any(mol.GetAtomWithIdx(i).GetAtomicNum() != 6 for i in rings[0] if i != a)):
                return None
            coords[b] = Point2D(p.x + 1.5, p.y)
            prolines.append((a, b, rings[0]))
        else:
            coords[b] = Point2D(p.x + 1.5 * math.sqrt(3) / 2, .75 - p.y)
    for n, alpha, ring in prolines:
        previous, current = n, alpha
        sign = 1 if coords[n].y else -1
        for step in range(1, 4):
            nxt = next(a.GetIdx() for a in mol.GetAtomWithIdx(current).GetNeighbors()
                       if a.GetIdx() in ring and a.GetIdx() != previous)
            angle = sign * step * 2 * math.pi / 5
            p = coords[current]
            coords[nxt] = Point2D(p.x + 1.5 * math.cos(angle), p.y + 1.5 * math.sin(angle))
            previous, current = current, nxt
    for carbonyl, oxygen in carbonyls.items():
        p = coords[carbonyl]
        coords[oxygen] = Point2D(p.x, p.y + (1.5 if p.y else -1.5))
    candidate = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(candidate, canonOrient=False, coordMap=coords, forceRDKit=True)
    conf = candidate.GetConformer()
    if any(abs(conf.GetAtomPosition(i).x - p.x) > 1e-6 or
           abs(conf.GetAtomPosition(i).y - p.y) > 1e-6 for i, p in coords.items()):
        raise ValueError('Peptide depiction moved a constrained backbone atom; no native write performed')
    if any((conf.GetAtomPosition(i) - conf.GetAtomPosition(j)).Length() <= .45
           for i in range(candidate.GetNumAtoms()) for j in range(i)):
        raise ValueError('Peptide depiction contains overlapping atoms; no native write performed')
    decoded = Chem.MolFromMolBlock(Chem.MolToMolBlock(candidate), removeHs=False)
    if decoded is None or Chem.MolToSmiles(decoded) != Chem.MolToSmiles(mol):
        raise ValueError('Peptide depiction changed molecular identity; no native write performed')
    mol.RemoveAllConformers()
    mol.AddConformer(Chem.Conformer(conf), assignId=True)
    return {'policy': 'linear_peptide', 'residue_count': len(residues),
            'backbone_atom_indices': backbone, 'direction': 'N-to-C'}
