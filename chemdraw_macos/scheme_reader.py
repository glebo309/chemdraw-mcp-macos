"""Read an existing ChemDraw reaction scheme into reactants / reagents / products.

Wraps the vendored cdxml-toolkit perception code (offline: no ChemScript, no
PubChem, no OPSIN). Classification is a heuristic (Schneider fingerprint + curated
reagent table), so every result is a proposal for review, never a certified record.
"""
import contextlib
import os
import sys
import tempfile
from pathlib import Path

MAX_CDXML_BYTES = 8_000_000


def _species(sp):
    return {k: v for k, v in {
        'id': sp.id, 'role': sp.role, 'role_detail': sp.role_detail, 'name': sp.name,
        'smiles': sp.smiles, 'formula': sp.formula, 'mw': round(sp.mw, 3) if sp.mw else None,
        'is_substrate': sp.is_substrate or None, 'is_product': sp.is_dp or None,
        'is_solvent': sp.is_solvent or None, 'display_text': sp.display_text,
        'source': sp.source, 'source_id': sp.source_id,
        'classification_method': sp.classification_method}.items() if v not in (None, '')}


def _reclassify_by_product_overlap(species, min_atoms=4, min_fraction=0.3):
    """Drawn structures that share a scaffold with a product contribute atoms.

    The upstream fingerprint classifier can file a real electrophile as a reagent;
    solvents, bases and catalysts share no scaffold with products, so they stay put.
    """
    from rdkit import Chem
    from rdkit.Chem import rdFMCS
    products = [Chem.MolFromSmiles(s['smiles']) for s in species
                if (s.get('is_product') or s['role'] == 'product') and s.get('smiles')]
    products = [m for m in products if m is not None]
    for s in species:
        if s['role'] != 'non_contributing' or s.get('source') != 'fragment' or not s.get('smiles'):
            continue
        mol = Chem.MolFromSmiles(s['smiles'])
        if mol is None or not products:
            continue
        for prod in products:
            mcs = rdFMCS.FindMCS([mol, prod], timeout=2, ringMatchesRingOnly=True, completeRingsOnly=True)
            if mcs.numAtoms >= min_atoms and mcs.numAtoms >= min_fraction * mol.GetNumHeavyAtoms():
                s['role'] = 'atom_contributing'
                s['reclassified'] = f'shares {mcs.numAtoms}-atom scaffold with a product'
                break


def read_reaction(cdxml=None, path=None):
    """Parse one reaction scheme from CDXML text or a .cdxml path."""
    if (cdxml is None) == (path is None):
        raise ValueError('Supply exactly one of cdxml text or path')
    if path is not None:
        source = Path(path)
        if source.suffix.lower() != '.cdxml' or not source.is_file():
            raise ValueError('path must be an existing .cdxml file')
        if source.stat().st_size > MAX_CDXML_BYTES:
            raise ValueError('CDXML file is too large')
        cdxml = source.read_text('utf-8')
    elif len(cdxml.encode('utf-8')) > MAX_CDXML_BYTES:
        raise ValueError('CDXML text is too large')
    if '<CDXML' not in cdxml:
        raise ValueError('Input is not CDXML')
    from defusedxml import ElementTree as SafeET
    SafeET.fromstring(cdxml.encode('utf-8'))  # rejects entity/DTD tricks before the vendored parser
    from ._cdxml_toolkit.perception.reaction_parser import parse_reaction
    with tempfile.TemporaryDirectory(prefix='chemdraw-scheme-') as tmp:
        scheme = os.path.join(tmp, 'scheme.cdxml')
        Path(scheme).write_text(cdxml, 'utf-8')
        with contextlib.redirect_stdout(sys.stderr):  # never corrupt the MCP stdio stream
            desc = parse_reaction(cdxml=scheme, use_network=False, use_rxn_insight=False)
    species = [_species(s) for s in desc.species]
    _reclassify_by_product_overlap(species)
    return {
        'reaction_smiles': desc.reaction_smiles, 'reaction_class': desc.reaction_class,
        'reaction_name': desc.reaction_name,
        'reactants': [s for s in species if s.get('is_substrate') or s['role'] == 'atom_contributing' and not s.get('is_product')],
        'reagents': [s for s in species if s['role'] == 'non_contributing'],
        'products': [s for s in species if s.get('is_product') or s['role'] == 'product'],
        'conditions': desc.conditions, 'warnings': desc.warnings,
        'review': 'Heuristic roles: confirm reactant vs reagent assignment and structures before relying on them.'}
