"""Bounded axis alignment for fresh 2D seeds, never for a live reference."""
import math
import statistics


def orient_new_molecule(mol):
    """Align regular six-rings or long acyclic zigzags by a rigid rotation.

    This is a page convention, not a conformer or stereochemistry operation.
    Irregular rings, chairs and cages do not qualify. No coordinates are mirrored,
    rescaled or moved relative to another atom; labels are created afterwards.
    """
    conf = mol.GetConformer()
    candidates = []
    policy = 'axis_aligned_six_ring'
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) != 6:
            continue
        edges = [(conf.GetAtomPosition(j) - conf.GetAtomPosition(i))
                 for i, j in zip(ring, ring[1:] + ring[:1])]
        lengths = [edge.Length() for edge in edges]
        median = statistics.median(lengths)
        if median <= 0 or any(abs(length / median - 1) > .02 for length in lengths):
            continue
        angles = [math.atan2(edge.y, edge.x) for edge in edges]
        turns = [(b - a + math.pi) % (2 * math.pi) - math.pi
                 for a, b in zip(angles, angles[1:] + angles[:1])]
        if (any(abs(abs(turn) - math.pi / 3) > math.radians(2) for turn in turns)
                or not (all(turn > 0 for turn in turns) or all(turn < 0 for turn in turns))):
            continue
        for index, angle in enumerate(angles):
            rotation = (math.pi / 2 - angle + math.pi / 2) % math.pi - math.pi / 2
            candidates.append((abs(rotation), rotation, ring[index], ring[(index + 1) % 6]))
    if not candidates and not mol.GetRingInfo().NumRings() and mol.GetNumHeavyAtoms()>=6:
        # Regular acyclic seeds share a 60-degree bond grid. Snap that grid to
        # +/-30 degrees and vertical, eliminating global depiction tilt while
        # retaining the complete conformer and its stereochemical handedness.
        bonds=list(mol.GetBonds())
        angles=[]
        for bond in bonds:
            v=conf.GetAtomPosition(bond.GetEndAtomIdx())-conf.GetAtomPosition(bond.GetBeginAtomIdx())
            angles.append(math.atan2(v.y,v.x))
        if angles:
            angle=(math.pi/6-angles[0]+math.pi/6)%(math.pi/3)-math.pi/6
            errors=[abs((a+angle-math.pi/6+math.pi/6)%(math.pi/3)-math.pi/6) for a in angles]
            if max(errors)<math.radians(2):
                candidates.append((abs(angle),angle,bonds[0].GetBeginAtomIdx(),bonds[0].GetEndAtomIdx()))
                policy='axis_aligned_acyclic'
    if not candidates:
        return {'policy': 'seed_preserved', 'rotation_degrees': 0.0}
    # Quantize only the tie-break key, never atom coordinates or the rotation.
    _, angle, a, b = min(candidates, key=lambda c: (round(c[0], 8), c[2], c[3]))
    cosine, sine = math.cos(angle), math.sin(angle)
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (cosine * p.x - sine * p.y, sine * p.x + cosine * p.y, p.z))
    return {'policy': policy, 'rotation_degrees': math.degrees(angle),
            'anchor_atom_indices': [a, b]}
