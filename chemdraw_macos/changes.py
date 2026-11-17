"""What changed in a live document since the previous read in this server."""
from __future__ import annotations

from collections import Counter
import xml.etree.ElementTree as ET

_previous: dict[int, dict] = {}
_COUNTED = ('fragment', 'n', 'b', 't', 'arrow', 'graphic', 'curve', 'bracketedgroup', 'spectrum')


def summarize(state: dict) -> dict:
    return {'graphs': Counter(state['graphs']), 'captions': Counter(state['captions']),
            'counts': {k: v for k, v in state['counts'].items() if v}}


def _minus(a: Counter, b: Counter) -> list:
    return sorted((a - b).elements())


def diff(before: dict, after: dict) -> dict:
    keys = set(before['counts']) | set(after['counts'])
    counts = {k: [before['counts'].get(k, 0), after['counts'].get(k, 0)] for k in sorted(keys)
              if before['counts'].get(k, 0) != after['counts'].get(k, 0)}
    result = {'molecules_added': _minus(after['graphs'], before['graphs']),
              'molecules_removed': _minus(before['graphs'], after['graphs']),
              'captions_added': _minus(after['captions'], before['captions']),
              'captions_removed': _minus(before['captions'], after['captions']),
              'object_count_changes': counts}
    result['changed'] = any(result.values())
    return result


def _rdkit_smiles(cdxml: str) -> str | None:
    """Lenient RDKit reading, used only to name a change, never as identity proof."""
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog('rdApp.*')
        mols = [m for m in Chem.MolsFromCDXML(cdxml) if m is not None]
        return '.'.join(sorted(Chem.MolToSmiles(m) for m in mols)) or None
    except Exception:
        return None


def state_from_cdxml(cdxml: str) -> dict:
    root = ET.fromstring(cdxml)
    atom_texts = {id(t) for n in root.iter('n') for t in n.iter('t')}
    captions = [''.join(t.itertext()).strip() for t in root.iter('t') if id(t) not in atom_texts]
    graphs = []
    try:
        from .api_drawing import _isolated
        from .polish import chemical_signature
        for fragment in root.findall('page/fragment'):
            isolated = _isolated(root, fragment)
            try:
                graphs.append(chemical_signature(isolated)[0])
            except (ValueError, RuntimeError):
                graphs.append(_rdkit_smiles(isolated) or 'unresolved fragment ' + str(fragment.get('id')))
    except ImportError:
        graphs = ['fragment ' + str(f.get('id')) for f in root.findall('page/fragment')]
    counts = Counter(e.tag for e in root.iter() if e.tag in _COUNTED)
    return {'graphs': graphs, 'captions': captions, 'counts': dict(counts)}


def remember(document_id: int, cdxml: str) -> None:
    """Keep the raw text only; it is summarized when changes are requested."""
    _previous[document_id] = cdxml


def document_changes(bridge, document_id) -> dict:
    from .addin import read_preserving_active
    did = bridge._id(document_id)
    snapshot = read_preserving_active(bridge, did)
    current = summarize(state_from_cdxml(snapshot['cdxml']))
    before = _previous.get(did)
    if isinstance(before, str):
        before = summarize(state_from_cdxml(before))
    _previous[did] = current
    if before is None:
        return {'document': snapshot['document'], 'baseline': True, 'changed': None,
                'molecules': sorted(current['graphs'].elements()), 'object_counts': current['counts'],
                'note': 'First read of this document in this server; later calls report changes since now.'}
    return {'document': snapshot['document'], 'baseline': False, **diff(before, current)}
