"""ChemDraw's chemical warnings for a live document, read without a modal alert.

ChemDraw writes each warning it would show (valence, unusual bonds,
unrecognized labels) as a Warning attribute in the document's CDXML. Reading
those attributes gives the same findings as Check Structure without the alert
that blocks ChemDraw until it is closed.
"""
from __future__ import annotations

from defusedxml import ElementTree as SafeET

_KINDS = {'n': 'atom', 'b': 'bond', 'fragment': 'fragment', 't': 'text', 'graphic': 'graphic', 'arrow': 'arrow'}


def structure_warnings(cdxml: str) -> dict:
    root = SafeET.fromstring(cdxml, forbid_entities=True, forbid_external=True)
    warnings = []
    for element in root.iter():
        text = element.get('Warning')
        if text:
            warnings.append({'object': _KINDS.get(element.tag, element.tag), 'id': element.get('id'), 'warning': text})
    return {'ok': not warnings, 'warnings': warnings}


def check_structure(bridge, document_id) -> dict:
    from .addin import read_preserving_active
    did = bridge._id(document_id)
    snapshot = read_preserving_active(bridge, did)
    result = structure_warnings(snapshot['cdxml'])
    result.update(document=snapshot['document'], source='ChemDraw chemical warnings in the live document',
                  source_token=snapshot['source_token'])
    return result
