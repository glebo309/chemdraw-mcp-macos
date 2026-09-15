"""Strict offline graph identifiers, not name resolution or figure rendering."""
import re


def _chemistry():
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import rdMolDescriptors
    except ImportError as exc:
        raise RuntimeError('Offline identifiers require the optional chemistry extra') from exc
    return Chem, rdBase, rdMolDescriptors


def _inchi_backend():
    try:
        from rdkit.Chem import rdinchi
    except ImportError:
        return None
    return rdinchi


def _supported_molecule(mol, Chem):
    if mol is None or not mol.GetNumAtoms():
        raise ValueError('Identifier did not produce a nonempty molecular graph')
    allowed_tags = {Chem.ChiralType.CHI_UNSPECIFIED,
                    Chem.ChiralType.CHI_TETRAHEDRAL_CW,
                    Chem.ChiralType.CHI_TETRAHEDRAL_CCW}
    allowed_bonds = {Chem.BondType.SINGLE, Chem.BondType.DOUBLE,
                     Chem.BondType.TRIPLE, Chem.BondType.AROMATIC}
    for atom in mol.GetAtoms():
        if atom.HasQuery() or not 1 <= atom.GetAtomicNum() <= 118 or atom.GetAtomMapNum():
            raise ValueError('Queries, dummy atoms and atom-map annotations are unsupported')
        if atom.GetChiralTag() not in allowed_tags:
            raise ValueError('Only ordinary tetrahedral atom stereochemistry is supported')
    for bond in mol.GetBonds():
        if bond.HasQuery() or bond.GetBondType() not in allowed_bonds:
            raise ValueError('Unsupported query, coordinate or exotic bond type')
    if mol.GetStereoGroups():
        raise ValueError('Enhanced stereo groups are unsupported')


def _parse_smiles(value, Chem):
    if '|' in value or re.search(r'@(?:TH|AL|SP|TB|OH)', value) or re.search(r'\[[^\]]*#', value):
        raise ValueError('CXSMILES, query atom syntax and extended stereochemistry syntax are unsupported')
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    params.removeHs = False
    params.sanitize = False
    mol = Chem.MolFromSmiles(value, params)
    _supported_molecule(mol, Chem)
    specified = {a.GetIdx() for a in mol.GetAtoms()
                 if a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED}
    directed = {b.GetIdx() for b in mol.GetBonds()
                if b.GetBondDir() in (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT)}
    try:
        Chem.SanitizeMol(mol)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    except Exception as exc:
        raise ValueError('Invalid molecular valence or stereochemistry') from exc
    if any(mol.GetAtomWithIdx(i).GetChiralTag() == Chem.ChiralType.CHI_UNSPECIFIED
           for i in specified):
        raise ValueError('Input tetrahedral stereochemistry would be silently discarded')
    stereo_double_atoms = set()
    for bond in mol.GetBonds():
        if bond.GetBondType() == Chem.BondType.DOUBLE and bond.GetStereo() in (
                Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ,
                Chem.BondStereo.STEREOCIS, Chem.BondStereo.STEREOTRANS):
            stereo_double_atoms.update((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()))
    for index in directed:
        bond = mol.GetBondWithIdx(index)
        if not stereo_double_atoms.intersection((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())):
            raise ValueError('Input directional bond would not describe retained alkene stereo')
    _supported_molecule(mol, Chem)
    return mol


def _parse_inchi(value, Chem, backend):
    if not re.fullmatch(r'InChI=1S/[A-Za-z0-9()*+,.;?/\-]+', value):
        raise ValueError('Only canonical Standard InChI input is supported')
    if backend is None:
        raise RuntimeError('InChI parsing is unavailable in this RDKit installation')
    try:
        mol, code, message, _ = backend.InchiToMol(value, True, False)
        if code != 0 or mol is None:
            raise ValueError('InChI parser returned an error or warning: ' + str(message))
        _supported_molecule(mol, Chem)
        rebuilt, code, _, _, _ = backend.MolToInchi(mol)
        if code not in (0, 1) or rebuilt != value:
            raise ValueError('InChI is noncanonical or contains layers not retained by parsing')
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        return mol
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError('Invalid or unsupported Standard InChI') from exc


def _inchi_result(mol, Chem, backend):
    result = {'status': 'unavailable', 'value': None, 'key': None,
              'reason': None, 'warnings': [], 'graph_roundtrip_equivalent': None}
    if backend is None:
        result['reason'] = 'InChI support is unavailable in this RDKit installation'
        return result
    try:
        value, code, message, _, _ = backend.MolToInchi(mol)
        if code not in (0, 1) or not value:
            result['reason'] = 'InChI generation failed: ' + str(message)
            return result
        key = backend.InchiToInchiKey(value)
        if not re.fullmatch(r'[A-Z]{14}-[A-Z]{10}-[A-Z]', key or ''):
            result['reason'] = 'InChIKey generation failed'
            return result
        result.update(status='available', value=value, key=key)
        if message:
            result['warnings'].append(message)
        restored, read_code, read_message, _ = backend.InchiToMol(value, True, False)
        if restored is not None and read_code in (0, 1):
            # Compare chemical graphs with explicit H on both sides. Do not
            # remove explicit H from the input molecule or canonical SMILES.
            graph = lambda m: Chem.MolToSmiles(Chem.AddHs(m), canonical=True, isomericSmiles=True)
            result['graph_roundtrip_equivalent'] = graph(mol) == graph(restored)
        if read_message:
            result['warnings'].append(read_message)
        if result['graph_roundtrip_equivalent'] is False:
            result['warnings'].append('Standard InChI roundtrip changes this graph; retain the canonical SMILES for exact graph identity')
    except Exception as exc:
        result.update(status='unavailable', value=None, key=None,
                      reason='InChI generation or verification failed: ' + str(exc),
                      graph_roundtrip_equivalent=None)
    return result


def inspect_identifier(value: str, input_format: str = 'smiles') -> dict:
    """Describe one strict SMILES or canonical Standard InChI, entirely offline.

    No name/CAS guessing, salt stripping, neutralization, tautomer conversion,
    drawing, native ChemDraw calls or external providers. Indices refer to the
    parsed input graph, not a ChemDraw document or canonical SMILES traversal.
    """
    if input_format not in ('smiles', 'inchi'):
        raise ValueError('input_format must be smiles or inchi; names and CAS are not resolved')
    if not isinstance(value, str) or not 1 <= len(value) <= 10000:
        raise ValueError('Identifier must be a nonempty string of at most 10000 characters')
    if not value.isascii() or any(c.isspace() or ord(c) < 33 for c in value):
        raise ValueError('Whitespace, trailing names and non-ASCII identifier text are unsupported')
    Chem, rdBase, descriptors = _chemistry()
    backend = _inchi_backend()
    mol = _parse_smiles(value, Chem) if input_format == 'smiles' else _parse_inchi(value, Chem, backend)
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    tetrahedral = []
    for atom in mol.GetAtoms():
        if atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED:
            tetrahedral.append({'atom_index': atom.GetIdx(), 'tag': str(atom.GetChiralTag()),
                                'cip': atom.GetProp('_CIPCode') if atom.HasProp('_CIPCode') else None})
    double_bonds = [{'bond_index': b.GetIdx(), 'begin_atom_index': b.GetBeginAtomIdx(),
                     'end_atom_index': b.GetEndAtomIdx(), 'configuration': str(b.GetStereo())}
                    for b in mol.GetBonds() if b.GetStereo() != Chem.BondStereo.STEREONONE]
    unspecified = [{'kind': str(s.type), 'index': s.centeredOn}
                   for s in Chem.FindPotentialStereo(mol, cleanIt=False, flagPossible=True)
                   if str(s.specified) == 'Unspecified']
    return {'input_format': input_format, 'canonical_smiles': canonical,
            'formula': descriptors.CalcMolFormula(mol, separateIsotopes=True, abbreviateHIsotopes=False),
            'formal_charge': Chem.GetFormalCharge(mol), 'component_count': len(Chem.GetMolFrags(mol)),
            'atom_count': mol.GetNumAtoms(),
            'isotopes': [{'atom_index': a.GetIdx(), 'element': a.GetSymbol(), 'mass_number': a.GetIsotope()}
                         for a in mol.GetAtoms() if a.GetIsotope()],
            'stereo': {'tetrahedral': tetrahedral, 'double_bonds': double_bonds,
                       'unspecified': unspecified, 'index_basis': 'Parsed input graph, zero-based'},
            'radical_electrons': sum(a.GetNumRadicalElectrons() for a in mol.GetAtoms()),
            'inchi': _inchi_result(mol, Chem, backend),
            'normalization': {'salt_neutralization': False, 'salt_stripping': False,
                              'tautomer_canonicalization': False, 'explicit_hydrogen_removal': False,
                              'note': 'Standard InChI has its own normalization; inspect its warnings and graph roundtrip separately'},
            'engine': {'name': 'RDKit', 'version': rdBase.rdkitVersion, 'offline': True}}
