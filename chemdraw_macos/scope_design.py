"""Offline, reviewable candidate proposals, not reaction or yield prediction.

RDKit constructs and checks molecular graphs here. This module does not draw,
call ChemDraw, resolve names, access providers, or write any files.
"""

from hashlib import sha256
import re


def _chem():
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError('Scope proposals require the optional chemistry extra.') from exc
    return Chem


def _identity(Chem, mol):
    copy = Chem.Mol(mol)
    for atom in copy.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(copy, canonical=True, isomericSmiles=True)


def _stereo(Chem, mol):
    result = {}
    for item in Chem.FindPotentialStereo(mol):
        if (item.type != Chem.StereoType.Atom_Tetrahedral or
                item.specified != Chem.StereoSpecified.Specified):
            raise ValueError('Only fully assigned tetrahedral parent stereo is supported.')
        result[item.centeredOn] = (str(item.type), str(item.specified), str(item.descriptor),
                                  tuple(item.controllingAtoms))
    return result


def _parse_parent(Chem, smiles):
    if (not isinstance(smiles, str) or not smiles or len(smiles) > 10000 or
            not smiles.isascii() or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in smiles)):
        raise ValueError('Provide one explicit SMILES without names or extended annotations.')
    if '/' in smiles or '\\' in smiles:
        raise ValueError('Directional bond stereo is outside this profile.')
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    params.removeHs = False
    mol = Chem.MolFromSmiles(smiles, params)
    if mol is None or len(Chem.GetMolFrags(mol)) != 1 or mol.GetNumAtoms() > 200:
        raise ValueError('Provide one supported connected molecule of at most 200 atoms.')
    if len(re.findall(r'@+', smiles)) != sum(
            a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for a in mol.GetAtoms()):
        raise ValueError('Input atom stereo was discarded or is unsupported.')
    if mol.GetStereoGroups():
        raise ValueError('Enhanced stereo is not supported.')
    maps = [a.GetAtomMapNum() for a in mol.GetAtoms() if a.GetAtomMapNum()]
    if len(maps) != len(set(maps)):
        raise ValueError('Atom maps must be unique.')
    for atom in mol.GetAtoms():
        if (atom.GetAtomicNum() not in {6, 7, 8, 9, 15, 16, 17, 35, 53} or
                atom.HasQuery() or atom.GetNumRadicalElectrons()):
            raise ValueError('Unsupported atom, explicit hydrogen, query or radical parent.')
    for bond in mol.GetBonds():
        if bond.HasQuery() or bond.GetBondType() not in {
                Chem.BondType.SINGLE, Chem.BondType.DOUBLE, Chem.BondType.TRIPLE, Chem.BondType.AROMATIC}:
            raise ValueError('Unsupported parent bond.')
    return mol


def _parent(Chem, smiles, handle):
    if type(handle) is not int or handle <= 0:
        raise ValueError('handle_atom_map must be a positive integer.')
    mol = _parse_parent(Chem, smiles)
    anchors = [a for a in mol.GetAtoms() if a.GetAtomMapNum() == handle]
    if len(anchors) != 1:
        raise ValueError('The explicit reaction-handle ring anchor map was not found.')
    anchor = anchors[0].GetIdx()
    rings = [r for r in mol.GetRingInfo().AtomRings() if anchor in r]
    if len(rings) != 1 or len(rings[0]) != 6:
        raise ValueError('Anchor must belong to one isolated six-membered aromatic carbon ring.')
    ring = set(rings[0])
    for idx in ring:
        atom = mol.GetAtomWithIdx(idx)
        if (atom.GetAtomicNum() != 6 or not atom.GetIsAromatic() or atom.GetIsotope() or
                atom.GetFormalCharge() or mol.GetRingInfo().NumAtomRings(idx) != 1):
            raise ValueError('Selected ring must be isolated, non-isotopic, neutral aromatic carbon.')
        outside = [n.GetIdx() for n in atom.GetNeighbors() if n.GetIdx() not in ring]
        if idx == anchor:
            if len(outside) != 1 or atom.GetTotalNumHs() != 0:
                raise ValueError('Anchor must have exactly one existing outside reaction-handle bond.')
        elif outside or atom.GetTotalNumHs() != 1:
            raise ValueError('First scope profile requires a monosubstituted ring with five H sites.')
    # Ring numbering is relative to the handle, not asserted IUPAC numbering.
    # Either traversal is equivalent for this deliberately monosubstituted ring.
    order = [anchor]
    while len(order) < 6:
        neighbors = sorted(n.GetIdx() for n in mol.GetAtomWithIdx(order[-1]).GetNeighbors()
                           if n.GetIdx() in ring and n.GetIdx() not in order)
        if not neighbors:
            raise ValueError('Unsupported aromatic ring connectivity.')
        order.append(neighbors[0])
    return mol, order, _stereo(Chem, mol)


def _verify_parent(Chem, parent, candidate, sites, stereo):
    if candidate.GetNumAtoms() < parent.GetNumAtoms():
        raise ValueError('Parent atom was removed.')
    for atom in parent.GetAtoms():
        other = candidate.GetAtomWithIdx(atom.GetIdx())
        for getter in ('GetAtomicNum', 'GetFormalCharge', 'GetIsotope', 'GetAtomMapNum',
                       'GetIsAromatic', 'GetChiralTag', 'GetNumRadicalElectrons'):
            if getattr(atom, getter)() != getattr(other, getter)():
                raise ValueError('Parent atom property changed.')
        expected_h = atom.GetTotalNumHs() - (1 if atom.GetIdx() in sites else 0)
        if other.GetTotalNumHs() != expected_h:
            raise ValueError('Unexpected parent hydrogen change.')
    for bond in parent.GetBonds():
        other = candidate.GetBondBetweenAtoms(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
        if other is None or (other.GetBondType(), other.GetStereo(), tuple(other.GetStereoAtoms())) != (
                bond.GetBondType(), bond.GetStereo(), tuple(bond.GetStereoAtoms())):
            raise ValueError('Parent bond changed.')
    if _stereo(Chem, candidate) != stereo:
        raise ValueError('Substitution creates, removes or changes supported parent stereo.')


_GROUPS = {'Me': 'C', 'OMe': 'OC', 'CF3': 'C(F)(F)F', 'CN': 'C#N',
           'NO2': '[N+](=O)[O-]', 'F': 'F', 'Cl': 'Cl', 'Br': 'Br',
           'iPr': 'C(C)C', 'tBu': 'C(C)(C)C'}


def _build(Chem, parent, order, additions, stereo):
    candidate = Chem.RWMol(parent)
    sites = []
    for position, group in additions:
        site = order[position - 1]
        sites.append(site)
        fragment = Chem.MolFromSmiles(_GROUPS[group])
        start = candidate.GetNumAtoms()
        candidate = Chem.RWMol(Chem.CombineMols(candidate, fragment))
        candidate.GetAtomWithIdx(site).SetNumExplicitHs(0)
        candidate.AddBond(site, start, Chem.BondType.SINGLE)
    result = candidate.GetMol()
    Chem.SanitizeMol(result)
    _verify_parent(Chem, parent, result, sites, stereo)
    smiles = Chem.MolToSmiles(result, canonical=True, isomericSmiles=True)
    parsed = Chem.MolFromSmiles(smiles)
    if parsed is None or Chem.MolToSmiles(parsed, canonical=True, isomericSmiles=True) != smiles:
        raise ValueError('Candidate SMILES roundtrip failed.')
    return result, smiles


def propose_scope(parent_smiles: str, handle_atom_map: int, profile: str = 'standard') -> dict:
    """Propose a deduplicated, map-anchored aromatic starter scope entirely offline.

    ``handle_atom_map`` marks the aromatic carbon attached to the existing
    reaction handle, not the atom that undergoes the reaction. Candidate labels
    describe changes relative to that parent. No candidate is a predicted result.
    """
    if profile != 'standard':
        raise ValueError('Only the standard scope profile is supported.')
    Chem = _chem()
    parent, order, stereo = _parent(Chem, parent_smiles, handle_atom_map)
    parent_identity = _identity(Chem, parent)
    specs = [([], 'Parent reference', 'reference', 'Reference with the original handle unchanged.')]
    for position in (2, 3, 4):
        specs.append(([(position, 'Me')], f'{position}-Me relative to parent', 'positional',
                      'Matched methyl series at ortho, meta and para sites relative to the handle.'))
    specs += [([(4, 'Me')], '4-Me relative to parent', 'electron_donating',
               'Para methyl provides a modest donating comparison.')]
    for group, category in [('OMe', 'electron_donating'), ('CF3', 'electron_withdrawing'),
                            ('CN', 'electron_withdrawing'), ('NO2', 'electron_withdrawing'),
                            ('F', 'halogen'), ('Cl', 'halogen'), ('Br', 'halogen')]:
        specs.append(([(4, group)], f'4-{group} relative to parent', category,
                      f'Para {group} extends the {category.replace("_", " ")} comparison.'))
    for group in ('Me', 'iPr', 'tBu'):
        specs.append(([(2, group)], f'2-{group} relative to parent', 'steric',
                      f'Ortho {group} probes crowding near the fixed handle; electronics also change.'))
    specs.append(([(2, 'Me'), (6, 'Me')], '2,6-Me2 relative to parent', 'steric',
                  'Two ortho methyl groups probe crowding on both sides of the handle.'))
    candidates = {}
    for additions, label, category, rationale in specs:
        mol, mapped = _build(Chem, parent, order, additions, stereo)
        identity = _identity(Chem, mol)
        if identity in candidates:
            existing = candidates[identity]
            if category not in existing['categories']:
                existing['categories'].append(category)
            if rationale not in existing['rationale']:
                existing['rationale'].append(rationale)
            continue
        candidates[identity] = {
            'candidate_id': 'scope-' + sha256(identity.encode()).hexdigest()[:16],
            'canonical_smiles': identity, 'mapped_smiles': mapped, 'display_label': label,
            'substitutions': [{'position': p, 'substituent': g, 'parent_atom_index': order[p - 1]}
                              for p, g in additions],
            'categories': [category], 'rationale': [rationale], 'yield_percent': None,
            'compatibility_questions': [
                'Are the parent handle and added groups compatible with the intended reaction and conditions?',
                'Is this candidate available or synthetically accessible for the study?'],
            'checks': {'parent_heavy_atom_graph_preserved': True,
                       'existing_stereochemistry_preserved': True,
                       'smiles_roundtrip_verified': True},
        }
    return {'schema_version': 1, 'status': 'proposal', 'profile': profile,
            'parent': {'canonical_smiles': parent_identity,
                       'mapped_smiles': Chem.MolToSmiles(parent, isomericSmiles=True),
                       'handle_atom_map': handle_atom_map,
                       'ring_positions': [{'position': i + 1, 'parent_atom_index': idx}
                                          for i, idx in enumerate(order)]},
            'candidates': list(candidates.values()),
            'limitations': [
                'Candidate proposal only; not chemical compatibility, reactivity or yield prediction.',
                'Labels are relative substitutions, not generated systematic chemical names.',
                'Only an isolated monosubstituted benzene ring and fully assigned tetrahedral stereo are supported.',
                'No rendering, native cleanup, name resolution, external lookup or experimental results are produced.',
                'Chemical review and explicit candidate selection precede a native drawing workflow.']}


def _custom_sites(Chem, parent, site_atom_maps):
    by_map = {a.GetAtomMapNum(): a for a in parent.GetAtoms() if a.GetAtomMapNum()}
    indices = []
    ring_info = parent.GetRingInfo()
    for atom_map in site_atom_maps:
        atom = by_map.get(atom_map)
        if atom is None:
            raise ValueError(f'site_atom_maps contains absent parent atom map {atom_map}.')
        if (atom.GetAtomicNum() != 6 or not atom.GetIsAromatic() or
                atom.GetTotalNumHs() != 1 or atom.GetDegree() != 2):
            raise ValueError(f'Site atom map {atom_map} must be an H-bearing aromatic carbon.')
        rings = [r for r in ring_info.AtomRings() if atom.GetIdx() in r]
        if len(rings) != 1 or len(rings[0]) not in (5, 6):
            raise ValueError('Each selected site must belong to one isolated five- or six-membered ring.')
        ring = set(rings[0])
        for idx in ring:
            member = parent.GetAtomWithIdx(idx)
            if (member.GetAtomicNum() not in {6, 7, 8, 16} or not member.GetIsAromatic() or
                    member.GetFormalCharge() or member.GetIsotope() or
                    ring_info.NumAtomRings(idx) != 1):
                raise ValueError('Selected rings must be isolated, neutral, non-isotopic aromatic C/N/O/S rings.')
            ring_bonds = [b for b in member.GetBonds() if b.GetOtherAtomIdx(idx) in ring]
            if len(ring_bonds) != 2 or any(b.GetBondType() != Chem.BondType.AROMATIC for b in ring_bonds):
                raise ValueError('Selected rings require simple aromatic ring connectivity.')
        indices.append(atom.GetIdx())
    return indices


def propose_custom_scope(parent_smiles: str, site_atom_maps: list[int],
                         substituents: list[str], include_parent: bool = True) -> dict:
    """Propose single substitutions at caller-selected mapped aromatic H sites.

    Supports isolated five/six-membered C/N/O/S aromatic rings, including existing
    substituents. Each map is a parent atom identifier, never a systematic ring
    locant. Substituents are selected from the fixed vocabulary in ``_GROUPS``.
    """
    if (not isinstance(site_atom_maps, list) or not site_atom_maps or
            any(type(m) is not int or m <= 0 for m in site_atom_maps) or
            len(site_atom_maps) != len(set(site_atom_maps))):
        raise ValueError('site_atom_maps must be a nonempty list of unique positive integers.')
    if (not isinstance(substituents, list) or not substituents or
            any(not isinstance(g, str) or g not in _GROUPS for g in substituents) or
            len(substituents) != len(set(substituents))):
        raise ValueError('substituents must be a nonempty unique list selected from: ' + ', '.join(_GROUPS))
    if type(include_parent) is not bool:
        raise ValueError('include_parent must be a boolean.')
    requested_count = len(site_atom_maps) * len(substituents) + int(include_parent)
    if requested_count > 100:
        raise ValueError('A custom scope may request at most 100 candidates including the parent before deduplication.')
    Chem = _chem()
    parent = _parse_parent(Chem, parent_smiles)
    sites = _custom_sites(Chem, parent, site_atom_maps)
    stereo = _stereo(Chem, parent)
    specs = [None] if include_parent else []
    specs.extend((i, group) for i in range(len(sites)) for group in substituents)
    candidates = {}
    for spec in specs:
        additions = [] if spec is None else [(spec[0] + 1, spec[1])]
        mol, mapped = _build(Chem, parent, sites, additions, stereo)
        identity = _identity(Chem, mol)
        substitution = ([] if spec is None else [{
            'site_atom_map': site_atom_maps[spec[0]],
            'parent_atom_index': sites[spec[0]], 'substituent': spec[1]}])
        if identity in candidates:
            candidates[identity]['requested_variants'].extend(substitution)
            continue
        label = ('Parent reference' if spec is None else
                 f'{spec[1]} at parent atom map {site_atom_maps[spec[0]]}')
        candidates[identity] = {
            'candidate_id': 'scope-' + sha256(identity.encode()).hexdigest()[:16],
            'canonical_smiles': identity, 'mapped_smiles': mapped, 'display_label': label,
            'substitutions': substitution, 'requested_variants': list(substitution),
            'categories': ['reference' if spec is None else 'selected_site_scan'],
            'rationale': ['Unchanged parent reference.' if spec is None else
                          'One selected substituent at one explicitly mapped parent H site.'],
            'yield_percent': None,
            'compatibility_questions': [
                'Are the parent and added group compatible with the intended reaction and conditions?',
                'Is this candidate available or synthetically accessible for the study?'],
            'checks': {'parent_heavy_atom_graph_preserved': True,
                       'existing_stereochemistry_preserved': True,
                       'smiles_roundtrip_verified': True},
        }
    return {
        'schema_version': 1, 'status': 'proposal', 'profile': 'custom',
        'parent': {'canonical_smiles': _identity(Chem, parent),
                   'mapped_smiles': Chem.MolToSmiles(parent, isomericSmiles=True),
                   'site_atom_maps': list(site_atom_maps),
                   'sites': [{'site_atom_map': m, 'parent_atom_index': idx}
                             for m, idx in zip(site_atom_maps, sites)]},
        'substituents': list(substituents), 'include_parent': include_parent,
        'requested_candidate_count': requested_count,
        'deduplicated_candidate_count': len(candidates),
        'candidates': list(candidates.values()),
        'limitations': [
            'Candidate proposal only; not chemical compatibility, reactivity or yield prediction.',
            'Map IDs identify supplied parent atoms, not systematic ring positions or chemical names.',
            'Each candidate adds one curated substituent at one explicitly selected aromatic carbon H site.',
            'Selected rings must be isolated neutral non-isotopic five/six-membered aromatic C/N/O/S rings.',
            'Symmetry-equivalent products share one graph and retain all requested variants.',
            'No rendering, native cleanup, name resolution, external lookup or experimental results are produced.',
            'Chemical review and explicit candidate selection precede a native drawing workflow.'],
    }
