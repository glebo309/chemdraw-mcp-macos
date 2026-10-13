"""Named-reaction product PROPOSALS from reviewed SMARTS templates.

Nothing here draws, chooses or certifies. Each call returns every distinct
product graph the template can form, with formula/mass deltas, so a person (or the
calling assistant) reviews them and then supplies the chosen product explicitly
to chemdraw_draw. Templates: reactions_classic.json (hand-written, from
cdxml-toolkit, MIT) and reactions_datamol.json (datamol, Apache-2.0).
"""
import json
from functools import lru_cache
from pathlib import Path

from .identifiers import inspect_identifier, _chemistry

DATA = Path(__file__).parent / 'data'
MAX_PRODUCTS = 12
_CATEGORY_TAGS = (('protecting', 'protection'), ('coupling', 'coupling'), ('heterocycle', 'heterocycle_formation'))


def _count_reactants(smarts):
    depth = count = 0
    for ch in smarts.split('>>')[0]:
        depth += (ch in '[(') - (ch in '])')
        count += (ch == '.' and depth == 0)
    return count + 1


def _datamol_category(tags):
    low = {t.lower() for t in tags}
    if any('deprotect' in t for t in low):
        return 'deprotection'
    for needle, category in _CATEGORY_TAGS:
        if any(needle in t for t in low):
            return category
    return 'functional_group'


@lru_cache(maxsize=1)
def templates():
    """Name -> template. Classic entries win name collisions (snake_case keys)."""
    merged = {}
    for key, entry in json.loads((DATA / 'reactions_datamol.json').read_text('utf-8')).items():
        smarts = entry.get('syn_smarts')
        if not smarts:
            continue
        classes = entry.get('rhs_classes', [])
        n = _count_reactants(smarts)
        merged[key.replace('-', '_')] = {
            'description': entry.get('description') or entry.get('long_name') or key,
            'long_name': entry.get('long_name', ''), 'smarts': smarts, 'n_reactants': n,
            'substrate_hint': ', '.join(classes), 'reagent_hint': ', '.join(classes[1:]) or None,
            'conditions': [], 'category': _datamol_category(entry.get('tags', [])), 'source': 'datamol'}
    for key, entry in json.loads((DATA / 'reactions_classic.json').read_text('utf-8')).items():
        merged[key] = dict(entry, long_name=entry.get('long_name', ''), source='classic')
    return merged


def _normal(name):
    return name.strip().lower().replace('-', '_').replace(' ', '_')


def find_template(name):
    table = templates()
    by_key = {_normal(k): k for k in table}
    key = by_key.get(_normal(name))
    if key:
        return key, table[key]
    q = _normal(name)
    near = [k for k in table if q in k.lower() or k.lower() in q]
    near += [k for k in table if k not in near and set(q.split('_')) & set(k.lower().split('_'))]
    raise ValueError(f'Unknown reaction {name!r}. Closest: {", ".join(near[:6]) or "none"}. '
                     f'Call chemdraw_list_reactions ({len(table)} available).')


def list_reactions(category=None, query=None):
    rows = []
    for name, t in sorted(templates().items()):
        if category and t['category'] != category:
            continue
        hay = ' '.join((name, t['description'], t['long_name'], t['substrate_hint'] or '')).lower()
        if query and query.lower() not in hay:
            continue
        rows.append({'name': name, 'category': t['category'], 'n_reactants': t['n_reactants'],
                     'description': t['description'], 'substrate': t['substrate_hint'],
                     'partner': t['reagent_hint'], 'conditions': t['conditions'], 'source': t['source']})
    return rows


def _formula_counts(mol, Chem):
    counts = {}
    for atom in Chem.AddHs(mol).GetAtoms():
        counts[atom.GetSymbol()] = counts.get(atom.GetSymbol(), 0) + 1
    return counts


def _delta(before, after):
    parts = []
    for el in sorted(set(before) | set(after), key=lambda e: (e != 'C', e != 'H', e)):
        d = after.get(el, 0) - before.get(el, 0)
        if d:
            parts.append(f'{el}{"+" if d > 0 else "-"}{abs(d) if abs(d) != 1 else ""}')
    return ' '.join(parts) or 'no change'


def propose_products(reaction, substrate, partner=None):
    """Run one template on explicit SMILES; return every distinct sanitised product."""
    from rdkit.Chem import AllChem, Descriptors
    Chem, _, rdMolDescriptors = _chemistry()
    key, tmpl = find_template(reaction)
    rxn = AllChem.ReactionFromSmarts(tmpl['smarts'])
    n = tmpl['n_reactants']
    if n > 2:
        raise ValueError(f'{key} needs {n} reactants; only 1- and 2-component templates are supported')
    if n == 2 and not partner:
        raise ValueError(f'{key} needs a partner ({tmpl["reagent_hint"] or "coupling partner"})')
    if n == 1 and partner:
        raise ValueError(f'{key} is single-component; omit partner')
    sub = inspect_identifier(substrate)
    inputs = [sub] + ([inspect_identifier(partner)] if n == 2 else [])
    mols = [Chem.MolFromSmiles(i['canonical_smiles']) for i in inputs]
    orders = [tuple(mols)] + ([tuple(reversed(mols))] if n == 2 else [])
    seen, candidates = set(), []
    for order in orders:
        for result in rxn.RunReactants(order):
            for prod in result[:1]:
                for atom in prod.GetAtoms():
                    atom.SetAtomMapNum(0)
                try:
                    Chem.SanitizeMol(prod)
                    identity = inspect_identifier(Chem.MolToSmiles(prod))
                except Exception:
                    continue
                inchikey = identity['inchi']['key'] or identity['canonical_smiles']
                if inchikey in seen:
                    continue
                seen.add(inchikey)
                pm = Chem.MolFromSmiles(identity['canonical_smiles'])
                before = {}
                for m in mols:
                    for el, c in _formula_counts(m, Chem).items():
                        before[el] = before.get(el, 0) + c
                candidates.append({
                    'smiles': identity['canonical_smiles'], 'inchikey': identity['inchi']['key'],
                    'formula': rdMolDescriptors.CalcMolFormula(pm),
                    'delta_vs_reactants': _delta(before, _formula_counts(pm, Chem)),
                    'mw': round(Descriptors.MolWt(pm), 3),
                    'stereo_note': 'Template does not set new stereocentres; assign by hand.'})
                if len(candidates) >= MAX_PRODUCTS:
                    break
    if not candidates:
        raise ValueError(f'{key}: no match. Substrate should be {tmpl["substrate_hint"] or "a matching substrate"}'
                         + (f'; partner {tmpl["reagent_hint"]}.' if n == 2 and tmpl['reagent_hint'] else '.'))
    return {'reaction': key, 'description': tmpl['description'], 'category': tmpl['category'],
            'template_source': tmpl['source'], 'conditions_typical': tmpl['conditions'],
            'candidates': candidates, 'ambiguous': len(candidates) > 1,
            'review': 'Proposals only: confirm regiochemistry, stereochemistry, by-products and '
                      'conditions, then pass the chosen product SMILES to chemdraw_draw.'}
