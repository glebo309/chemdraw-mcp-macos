import math
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.alignment import align_native_structures, validate_scaffold, validate_scaffold_inputs
from chemdraw_macos.polish import chemical_signature
from test_editing import CHIRAL


# Minimal graph/coordinates transcribed from the native acetophenone software
# demonstration; no application defaults or external artwork are embedded.
ACETOPHENONE = '''<CDXML BondLength="30" LabelFont="3" LabelSize="10" BoundingBox="206 350 320 420"><fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable><page id="21" BoundingBox="0 0 523 770" HeightPages="1" WidthPages="1"><fragment id="1" BoundingBox="206 350 320 420">
<n id="2" p="312.54 412.57"/><n id="3" p="297.54 386.59"/><n id="4" p="312.54 360.61" Element="8" NumHydrogens="0"><t p="308.65 364.30" BoundingBox="309 356 316 365"><s font="3" size="10" face="96">O</s></t></n><n id="5" p="267.54 386.59"/><n id="6" p="252.54 360.61"/><n id="7" p="222.54 360.61"/><n id="8" p="207.54 386.59"/><n id="9" p="222.54 412.57"/><n id="10" p="252.54 412.57"/>
<b id="11" B="2" E="3"/><b id="12" B="3" E="4" Order="2"/><b id="13" B="3" E="5"/><b id="14" B="5" E="6" Order="2"/><b id="15" B="6" E="7"/><b id="16" B="7" E="8" Order="2"/><b id="17" B="8" E="9"/><b id="18" B="9" E="10" Order="2"/><b id="19" B="10" E="5"/></fragment></page></CDXML>'''


def rotated(text, degrees, dx=70, dy=-40, mirror=False, scale=1):
    root = ET.fromstring(text)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    for element in root.find('page/fragment').iter():
        if element.get('p'):
            x, y = map(float, element.get('p').split())
            if mirror:
                x = -x
            element.set('p', f'{scale*(c*x-s*y)+dx:.9f} {scale*(s*x+c*y)+dy:.9f}')
    return ET.tostring(root, encoding='unicode')


def positions(text):
    return {n.get('id'): tuple(map(float, n.get('p').split()))
            for n in ET.fromstring(text).findall('page/fragment/n')}


def test_thirty_degree_native_core_is_rigidly_aligned():
    tilted = rotated(ACETOPHENONE, 30)
    aligned, audit = align_native_structures([ACETOPHENONE, tilted], 'CC(=O)c1ccccc1')
    assert len(aligned) == 2
    assert aligned[0] == ACETOPHENONE
    for key, point in positions(aligned[0]).items():
        assert positions(aligned[1])[key] == pytest.approx(point, abs=1e-5)
    assert audit['structures'][1]['rotation_degrees'] == pytest.approx(-30, abs=1e-6)
    assert audit['structures'][1]['scaffold_rmsd_pt'] < 1e-6
    assert audit['structures'][1]['max_pairwise_distance_change_pt'] < 1e-5
    assert all(audit['checks'].values())
    assert audit['native_remeasurement_required'] is True
    assert chemical_signature(aligned[1]) == chemical_signature(tilted)


def test_ink_bounds_removed_and_label_anchors_rigidly_rotated():
    aligned, _ = align_native_structures([ACETOPHENONE, rotated(ACETOPHENONE, 30)], 'CC(=O)c1ccccc1')
    root = ET.fromstring(aligned[1])
    assert root.get('BoundingBox') is None
    assert root.find('page').get('BoundingBox') == '0 0 523 770'
    assert all(e.get('BoundingBox') is None for e in root.find('page/fragment').iter())
    actual = tuple(map(float, root.find('page/fragment/n/t').get('p').split()))
    assert actual == pytest.approx((308.65, 364.30), abs=1e-5)


def test_assigned_stereo_retained_by_rotation():
    scaffold = chemical_signature(CHIRAL)[0]
    tilted = rotated(CHIRAL, -61)
    aligned, _ = align_native_structures([CHIRAL, tilted], scaffold)
    assert chemical_signature(aligned[1]) == chemical_signature(CHIRAL)
    assert ET.fromstring(aligned[1]).find('.//b[@id="10"]').get('Display') == 'WedgeBegin'


def test_reflected_chiral_graph_is_not_fixed_by_reflection():
    with pytest.raises(ValueError):
        align_native_structures([CHIRAL, rotated(CHIRAL, 0, mirror=True)], chemical_signature(CHIRAL)[0])


def test_scale_mismatch_fails_instead_of_resizing():
    with pytest.raises(ValueError, match='RMSD'):
        align_native_structures([ACETOPHENONE, rotated(ACETOPHENONE, 0, scale=1.2)], 'CC(=O)c1ccccc1')


@pytest.mark.parametrize('scaffold', ['CC', 'C', '*CC', 'CCO name', '[CH2]CC', '[c:1]1ccccc1', 'c1ccncc1'])
def test_missing_or_unsupported_scaffolds_fail(scaffold):
    with pytest.raises(ValueError):
        align_native_structures([ACETOPHENONE], scaffold)


def test_collinear_three_atom_match_rejected():
    text = '''<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/><n id="4" p="30 0"/><n id="5" p="60 0"/><b id="6" B="3" E="4"/><b id="7" B="4" E="5"/></fragment></page></CDXML>'''
    with pytest.raises(ValueError, match='noncollinear'):
        align_native_structures([text], 'CCC')


def test_unknown_native_annotation_and_radical_rejected():
    annotation = ACETOPHENONE.replace('</fragment>', '<graphic id="30"/></fragment>')
    with pytest.raises(ValueError):
        align_native_structures([annotation], 'c1ccccc1')
    radical = ACETOPHENONE.replace('id="2" p=', 'id="2" NumHydrogens="2" p=')
    with pytest.raises(ValueError, match='radical'):
        align_native_structures([radical], 'c1ccccc1')


def test_symmetric_scaffold_matching_is_deterministic():
    texts = [ACETOPHENONE, rotated(ACETOPHENONE, 30)]
    assert align_native_structures(texts, 'c1ccccc1') == align_native_structures(texts, 'c1ccccc1')


def test_new_draw_input_rejects_page_captions_and_multiple_fragments():
    captioned = ACETOPHENONE.replace('</page>', '<t id="100" p="0 0"><s>Label</s></t></page>')
    with pytest.raises(ValueError):
        align_native_structures([captioned], 'c1ccccc1')
    with pytest.raises(ValueError):
        align_native_structures([], 'c1ccccc1')


def test_scaffold_preflight_needs_no_native_data():
    info = validate_scaffold('CC(=O)c1ccccc1')
    assert info['canonical_smiles'] == 'CC(=O)c1ccccc1'
    assert info['heavy_atom_count'] == 9


def test_all_input_graphs_are_checked_before_native_work():
    result = validate_scaffold_inputs(['CC(=O)c1ccccc1', 'CC(=O)c1ccc(C)cc1'], 'CC(=O)c1ccccc1')
    assert result['match_counts'] == [2, 2]
    with pytest.raises(ValueError, match='missing'):
        validate_scaffold_inputs(['CC(=O)c1ccccc1', 'CCO'], 'CC(=O)c1ccccc1')
    with pytest.raises(ValueError):
        validate_scaffold_inputs(['CCC extra'], 'CCC')
    with pytest.raises(ValueError):
        validate_scaffold_inputs([], 'CCC')


def test_preflight_rejects_stereochemically_opposite_scaffold():
    with pytest.raises(ValueError, match='incompatible'):
        validate_scaffold_inputs(['C[C@H](O)CC'], 'C[C@@H](O)CC')
