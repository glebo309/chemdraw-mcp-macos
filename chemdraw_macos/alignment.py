"""Explicit common-scaffold rigid rotations of private native molecule copies.

No reflection, scaling, graph edits, automatic scaffold inference or renderer.
Native ChemDraw must remeasure rotated atom-label ink before final layout.
"""
import math
import xml.etree.ElementTree as ET

from .editing import _decoded
from .identifiers import inspect_identifier
from .polish import chemical_signature, numbers
from .scope import _root


def validate_scaffold(scaffold_smiles: str) -> dict:
    """Offline syntax/chemistry preflight; native geometry is checked later."""
    info = inspect_identifier(scaffold_smiles, 'smiles')
    from rdkit import Chem
    params = Chem.SmilesParserParams(); params.removeHs = False
    mol = Chem.MolFromSmiles(info['canonical_smiles'], params)
    if (len(Chem.GetMolFrags(mol)) != 1 or not 3 <= mol.GetNumAtoms() <= 150 or
            any(a.GetAtomicNum() == 1 for a in mol.GetAtoms())):
        raise ValueError('Scaffold requires one connected graph of 3 through 150 heavy atoms, without explicit H nodes.')
    if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
        raise ValueError('Radical scaffold is unsupported.')
    return {'canonical_smiles': info['canonical_smiles'], 'heavy_atom_count': mol.GetNumHeavyAtoms()}


def _matches(mol, scaffold):
    matches = mol.GetSubstructMatches(scaffold, uniquify=False, useChirality=True, maxMatches=1000)
    if not matches:
        raise ValueError('Explicit scaffold is missing or stereochemically incompatible with a structure.')
    if len(matches) >= 1000:
        raise ValueError('Scaffold match limit reached; provide a more specific scaffold.')
    return sorted(matches)


def validate_scaffold_inputs(smiles_list: list[str], scaffold_smiles: str) -> dict:
    """Check every explicit input graph contains the scaffold before native work.

    Geometry and noncollinearity still require native coordinates later.
    """
    if not isinstance(smiles_list, list) or not 1 <= len(smiles_list) <= 24:
        raise ValueError('Supply 1 through 24 explicit SMILES inputs.')
    from rdkit import Chem
    info = validate_scaffold(scaffold_smiles)
    scaffold = Chem.MolFromSmiles(info['canonical_smiles'])
    counts = []
    for smiles in smiles_list:
        identifier = inspect_identifier(smiles, 'smiles')
        params = Chem.SmilesParserParams(); params.removeHs = False
        mol = Chem.MolFromSmiles(identifier['canonical_smiles'], params)
        if len(Chem.GetMolFrags(mol)) != 1 or mol.GetNumAtoms() > 150:
            raise ValueError('Alignment requires connected structures of at most 150 atoms.')
        if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
            raise ValueError('Radical alignment input is unsupported.')
        counts.append(len(_matches(mol, scaffold)))
    return {**info, 'match_counts': counts, 'native_geometry_checked': False}


def _noncollinear(points):
    cx, cy = _mean(points)
    xx = sum((x-cx)**2 for x, _ in points)
    yy = sum((y-cy)**2 for _, y in points)
    xy = sum((x-cx)*(y-cy) for x, y in points)
    if xx*yy-xy*xy <= 1e-8*(xx+yy)**2:
        raise ValueError('Scaffold requires noncollinear native atom coordinates.')


def _mean(points):
    return tuple(sum(p[k] for p in points)/len(points) for k in (0, 1))


def _fit(points, reference):
    """Least-squares orientation-preserving 2D rigid fit, with scale fixed at 1."""
    pc, qc = _mean(points), _mean(reference)
    a = b = 0.
    for (x, y), (u, v) in zip(points, reference):
        x -= pc[0]; y -= pc[1]; u -= qc[0]; v -= qc[1]
        a += x*u + y*v
        b += x*v - y*u
    angle = math.atan2(b, a)
    c, s = math.cos(angle), math.sin(angle)
    translation = (qc[0]-c*pc[0]+s*pc[1], qc[1]-s*pc[0]-c*pc[1])
    def apply(point):
        x, y = point
        return c*x-s*y+translation[0], s*x+c*y+translation[1]
    rmsd = math.sqrt(sum(math.dist(apply(p), q)**2 for p, q in zip(points, reference))/len(points))
    return angle, translation, rmsd, apply


def _input(text, scaffold):
    root = _root(text)
    fragments = root.findall('page/fragment')
    if len(fragments) != 1 or root.findall('page/t'):
        raise ValueError('Alignment requires one native molecule without page captions.')
    mol, atom_ids = _decoded(text)
    if mol.GetNumAtoms() > 150:
        raise ValueError('Alignment supports at most 150 atoms per structure.')
    matches = _matches(mol, scaffold)
    by_index = {index: key for key, index in atom_ids.items()}
    positions = {atom_ids[n.get('id')]: numbers(n.get('p'), 2) for n in fragments[0].findall('n')}
    return root, sorted(matches), positions, by_index


def align_native_structures(texts: list[str], scaffold_smiles: str) -> tuple[list[str], dict]:
    """Align explicit scaffold matches to the first native input using only rigid motion.

    Reference matching uses the lexicographically first decoded atom-index tuple.
    Target matches minimize RMSD; ties within 0.000001 pt prefer the smallest
    absolute rotation, then signed angle and atom-index tuple. Symmetric cores
    therefore make a deterministic drawing choice, not a chemical equivalence
    claim about substituents outside the supplied scaffold.
    """
    if not isinstance(texts, list) or not 1 <= len(texts) <= 24:
        raise ValueError('Supply 1 through 24 explicit native structure texts.')
    info = validate_scaffold(scaffold_smiles)
    from rdkit import Chem
    scaffold = Chem.MolFromSmiles(info['canonical_smiles'])
    decoded = [_input(text, scaffold) for text in texts]
    reference_match = decoded[0][1][0]
    reference = [decoded[0][2][i] for i in reference_match]
    _noncollinear(reference)
    output = []; reports = []
    for index, (text, (root, matches, positions, ids)) in enumerate(zip(texts, decoded)):
        fits = []
        for match in ([reference_match] if index == 0 else matches):
            points = [positions[i] for i in match]
            _noncollinear(points)
            angle, translation, rmsd, apply = _fit(points, reference)
            fits.append((match, angle, translation, rmsd, apply))
        minimum = min(f[3] for f in fits)
        eligible = [f for f in fits if f[3] <= minimum + 1e-6]
        match, angle, translation, rmsd, apply = min(eligible, key=lambda f: (abs(f[1]), f[1], f[0]))
        if rmsd > .25:
            raise ValueError(f'Scaffold rigid-fit RMSD {rmsd:.4f} pt exceeds 0.25 pt; no scaling or reflection was applied.')
        changed = abs(angle) > 1e-10 or math.hypot(*translation) > 1e-8
        if changed:
            root.attrib.pop('BoundingBox', None)
            for element in root.find('page/fragment').iter():
                if element.get('p'):
                    element.set('p', ' '.join(f'{v:.9f}' for v in apply(numbers(element.get('p'), 2))))
                element.attrib.pop('BoundingBox', None)
                element.attrib.pop('AS', None)
                element.attrib.pop('BondOrdering', None)
            result = ET.tostring(root, encoding='unicode')
        else:
            result = text
        if chemical_signature(result) != chemical_signature(text):
            raise ValueError('Chemical graph or stereochemistry changed during rigid alignment.')
        actual_root = _root(result)
        actual = {n.get('id'): numbers(n.get('p'), 2) for n in actual_root.findall('page/fragment/n')}
        original = {ids[i]: p for i, p in positions.items()}
        pairwise = max((abs(math.dist(original[a], original[b])-math.dist(actual[a], actual[b]))
                        for j, a in enumerate(original) for b in list(original)[j+1:]), default=0.)
        if pairwise > 1e-6:
            raise ValueError('Rigid alignment changed internal pairwise distances.')
        output.append(result)
        reports.append({'index': index, 'rotation_degrees': math.degrees(angle) if changed else 0.,
                        'translation_pt': list(translation) if changed else [0., 0.],
                        'scaffold_rmsd_pt': rmsd, 'match_atom_ids': [ids[i] for i in match],
                        'max_pairwise_distance_change_pt': pairwise,
                        'native_remeasurement_required': changed})
    return output, {'scaffold_smiles': info['canonical_smiles'],
                    'reference_match_atom_ids': [decoded[0][3][i] for i in reference_match],
                    'structures': reports,
                    'checks': {'chemical_graph_and_stereo_preserved': True,
                               'internal_distances_preserved': True, 'proper_rotation_only': True,
                               'scaffold_rmsd_within_0_25_pt': True},
                    'native_remeasurement_required': any(r['native_remeasurement_required'] for r in reports),
                    'limitations': 'Explicit scaffold only. Symmetric matches use minimum RMSD, then smallest rotation and stable indices. No reflection, scaling, native rendering or collision certification; native label remeasurement and visual review are required.'}
