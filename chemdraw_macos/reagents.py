"""Curated offline reagent/solvent/catalyst lookup (names, aliases, roles).

192 reviewed entries from cdxml-toolkit (MIT). Used to label reaction conditions
and to resolve shorthand such as Cs2CO3 or Pd(dppf)Cl2 without a network call.
Reference data, not a naming service: unlisted names return None.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

_SUBSCRIPTS = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
_SOLVATE = re.compile(r'[·.](?:chcl3|dcm|ch2cl2|h2o|hcl|thf|dme|meoh|etoh|et2o)\s*$', re.I)


def _key(name):
    return _SOLVATE.sub('', name.translate(_SUBSCRIPTS).strip()).lower()


@lru_cache(maxsize=1)
def _index():
    data = json.loads((Path(__file__).parent / 'data' / 'reagents.json').read_text('utf-8'))
    index = {}
    for key, entry in data.items():
        for alias in (key, entry['display'], *entry.get('aliases', ())):
            index.setdefault(_key(alias), entry)
    return index


def _first(smiles):
    return smiles[0] if isinstance(smiles, list) else smiles


def lookup_reagent(name):
    """Return {display, role, smiles, aliases} for a known reagent, else None."""
    entry = _index().get(_key(name))
    if entry is None:
        return None
    return {'display': entry['display'], 'role': entry.get('role'), 'smiles': _first(entry.get('smiles')),
            'aliases': list(entry.get('aliases', ()))}


def list_reagents(role=None):
    seen, rows = set(), []
    for entry in _index().values():
        if id(entry) in seen or (role and entry.get('role') != role):
            continue
        seen.add(id(entry))
        rows.append({'display': entry['display'], 'role': entry.get('role'), 'smiles': _first(entry.get('smiles'))})
    return sorted(rows, key=lambda r: r['display'].lower())
