"""Read or change a document's drawing settings in place (Document Settings).

Lengths and sizes are in points; ChemDraw stores them in twentieths of a
point. Changing a setting affects what is drawn or cleaned next, not the
coordinates of existing objects.
"""
from __future__ import annotations

from .core import document_row

# key -> (ChemDraw property, unit, minimum, maximum)
KEYS = {
    'bond_length_pt': ('fixed length', 'pt', .5, 200),
    'line_width_pt': ('line width', 'pt', .05, 20),
    'bold_width_pt': ('bold width', 'pt', .05, 20),
    'margin_width_pt': ('margin width', 'pt', 0, 20),
    'hash_spacing_pt': ('hash spacing', 'pt', .05, 20),
    'label_size_pt': ('label size', 'pt', 1, 200),
    'caption_size_pt': ('caption size', 'pt', 1, 200),
    'bond_spacing_percent': ('bond spacing', 'int', 1, 100),
    'chain_angle_deg': ('chain angle', 'int', 1, 359),
    'magnification_percent': ('magnification', 'int', 1, 999),
    'label_font': ('label font', 'text', None, None),
    'caption_font': ('caption font', 'text', None, None),
}
_ORDER = ('bond_length_pt', 'line_width_pt', 'bold_width_pt', 'label_size_pt', 'caption_size_pt',
          'label_font', 'caption_font', 'bond_spacing_percent', 'chain_angle_deg', 'margin_width_pt',
          'hash_spacing_pt', 'magnification_percent')


def _decode(values):
    out = {}
    for key, value in zip(_ORDER, values):
        unit = KEYS[key][1]
        out[key] = round(value / 20, 3) if unit == 'pt' else value
    return out


def _encode(key, value):
    if key not in KEYS:
        raise ValueError(f'Unknown setting {key!r}; choose from {sorted(KEYS)}')
    prop, unit, low, high = KEYS[key]
    if unit == 'text':
        if not isinstance(value, str) or not value.strip() or len(value) > 64 or any(ord(c) < 32 for c in value):
            raise ValueError(f'{key} must be a font name')
        return prop, value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{key} must be a number')
    if not low <= value <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return prop, str(round(value * 20) if unit == 'pt' else round(value))


def document_settings(bridge, document_id, settings: dict | None = None) -> dict:
    did = bridge._id(document_id)
    if not settings:
        row, values = bridge._run('get_settings', did)
        return {'document': document_row(row), 'settings': _decode(values)}
    if not isinstance(settings, dict):
        raise ValueError('settings must be an object')
    args = []
    for key, value in settings.items():
        args.extend(_encode(key, value))
    row, values = bridge._run('set_settings', did, *args)
    current = _decode(values)
    mismatched = {}
    for key, value in settings.items():
        actual = current[key]
        if KEYS[key][1] == 'text':
            if actual != value:
                mismatched[key] = actual
        elif abs(float(actual) - float(value)) > (.05 if KEYS[key][1] == 'pt' else .5):
            mismatched[key] = actual
    return {'document': document_row(row), 'settings': current, 'changed': sorted(settings),
            'not_applied': mismatched,
            'note': 'Affects what is drawn or cleaned next; existing objects keep their geometry. Undo is not recorded for settings.'}
