"""Offline ink boxes must track ChemDraw's own boxes (no native measuring copy)."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chemdraw_macos import ink
from chemdraw_macos.polish import bounds

NATIVE = Path(__file__).parent / 'fixtures' / 'native-reaction-append' / 'after.cdxml'


def test_native_fragments_match_model_within_one_point():
    fragments = [f for f in ET.fromstring(NATIVE.read_text()).findall('page/fragment') if f.get('BoundingBox')]
    assert len(fragments) == 5
    for f in fragments:
        box, _ = ink.fragment_ink(f, 1.58, 14, envelope={n.get('id'): (0, 0, 0, 0) for n in f.findall('n')})
        native = bounds(f)
        assert abs(box[0] - native.left) < 1 and abs(box[2] - native.right) < 1.1, f.get('id')
        assert abs((box[0] + box[2]) / 2 - native.center[0]) < .8
        assert abs(box[1] - native.top) < 1 and abs(box[3] - native.bottom) < 1


# (label, alignment) -> native (left - x, right - x) at 14 pt, measured in ChemDraw 23.
@pytest.mark.parametrize('text, alignment, left, right', [
    ('OH', 'Left', -4.79, 14.34), ('OH', 'Right', -14.34, 4.79),
    ('NH2', 'Right', -19.91, 3.99), ('Cl', 'Left', -4.45, 7.21),
    ('Cl', 'Right', -11.06, .60), ('Br', 'Left', -3.70, 9.46), ('CH3', 'Right', -19.91, 4.49)])
def test_label_extents_match_native_table(text, alignment, left, right):
    l, _, r, _ = ink.label_box(text, 14, alignment, 0, 0)
    assert abs(l - left) < 1.3 and abs(r - right) < 1.3


def test_alignment_follows_bond_direction():
    assert ink.alignment_for([(10, 0)], 0, 0) == 'Right'     # bond to the right: label runs left
    assert ink.alignment_for([(-10, 3)], 0, 0) == 'Left'
    assert ink.alignment_for([(-9, -5), (9, -5)], 0, 0) == 'Below'
    assert ink.alignment_for([(-9, 5), (9, 5)], 0, 0) == 'Above'


def test_unmodelled_label_uses_the_conservative_envelope_not_a_guess():
    # Four bonds on a labelled atom: ChemDraw centres it; outside the model, so fall back.
    f = ET.fromstring('<fragment id="1"><n id="2" p="0 0"><t><s>Ru</s></t></n>'
                      '<n id="3" p="18 0"/><n id="4" p="-18 0"/><n id="5" p="0 18"/><n id="6" p="0 -18"/>'
                      '<b id="7" B="2" E="3"/><b id="8" B="2" E="4"/><b id="9" B="2" E="5"/><b id="10" B="2" E="6"/></fragment>')
    envelope = {'2': (-40, -20, 40, 20)}
    envelope.update({i: (x - 1, y - 1, x + 1, y + 1) for i, (x, y) in {'3': (18, 0), '4': (-18, 0), '5': (0, 18), '6': (0, -18)}.items()})
    box, _ = ink.fragment_ink(f, 1.58, 14, envelope=envelope)
    assert box[0] <= -40 and box[2] >= 40
    with pytest.raises(ValueError, match='outside the ink model'):
        ink.fragment_ink(f, 1.58, 14)
