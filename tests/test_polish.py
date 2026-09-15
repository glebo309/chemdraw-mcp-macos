import math
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import (
    analyze_cdxml, chemical_signature, normalize_cdxml, layout_row,
)
from chemdraw_macos.geometry import Box, find_overlaps


SAMPLE = '''<CDXML BondLength="30" LineWidth="0.6" LabelSize="10" LabelFont="3">
<fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable>
<page id="100" BoundingBox="0 0 540 720">
<fragment id="1" BoundingBox="30 40 68 50">
<n id="2" p="30 45"/><n id="3" Element="8" NumHydrogens="1" p="60 45"><t p="55 49" BoundingBox="55 40 68 50"><s font="3" size="10">OH</s></t></n>
<b id="4" B="2" E="3"/></fragment>
<t id="10" p="49 100" BoundingBox="25 93 74 102"><s font="3" size="10">Methanol</s></t>
<fragment id="20" BoundingBox="260 110 323 120">
<n id="21" p="260 115"/><n id="22" p="285 115"/><n id="23" Element="8" NumHydrogens="1" p="310 115"><t p="305 119" BoundingBox="305 110 323 120"><s font="3" size="10">OH</s></t></n>
<b id="24" B="21" E="22"/><b id="25" B="22" E="23"/></fragment>
<t id="30" p="290 180" BoundingBox="270 173 310 182"><s font="3" size="10">Ethanol</s></t>
</page></CDXML>'''


def test_normalizes_actual_coordinates_not_just_setting():
    result, audit = normalize_cdxml(SAMPLE, 'house')
    report = analyze_cdxml(result)
    assert [m['median_bond_pt'] for m in report['molecules']] == pytest.approx([18,18])
    assert audit['checks']['chemistry_preserved']
    assert audit['scales'] == pytest.approx({'1': .6, '20': .72})
    assert chemical_signature(result) == chemical_signature(SAMPLE)
    root = ET.fromstring(result)
    assert all(float(b.get('LineWidth')) == 1.58 for b in root.iter('b'))
    assert all(s.get('size') == '14' for n in root.iter('n') for s in n.iter('s'))


def test_layout_uses_measured_bounds_caption_baseline_and_equal_gaps():
    result, audit = layout_row(SAMPLE, caption_map={'1':'10', '20':'30'}, gap=24)
    report = analyze_cdxml(result)
    a,b = [Box(*m['bounds_pt']) for m in report['molecules']]
    assert a.center[1] == pytest.approx(b.center[1])
    assert b.left-a.right == pytest.approx(24)
    root=ET.fromstring(result)
    labels=[root.find(f'.//t[@id="{i}"]') for i in ['10','30']]
    assert float(labels[0].get('p').split()[1]) == float(labels[1].get('p').split()[1])
    assert float(labels[0].get('p').split()[1]) == pytest.approx(max(a.bottom,b.bottom)+14)
    assert audit['checks']['no_component_overlaps']
    assert chemical_signature(result) == chemical_signature(SAMPLE)


def test_ambiguous_unassigned_text_is_rejected_not_moved_by_guess():
    with pytest.raises(ValueError, match='Unassigned text'):
        layout_row(SAMPLE, caption_map={'1':'10'})


def test_duplicate_caption_owner_and_missing_id_are_rejected():
    with pytest.raises(ValueError):
        layout_row(SAMPLE,caption_map={'1':'10','20':'10'})
    with pytest.raises(ValueError):
        layout_row(SAMPLE,caption_map={'999':'10','20':'30'})


def test_reaction_arrow_conditions_and_plus_move_as_owned_objects():
    root=ET.fromstring(SAMPLE);page=root.find('page')
    ET.SubElement(page,'arrow',{'id':'50','Head3D':'220 80 0','Tail3D':'150 80 0','BoundingBox':'150 77 220 83'})
    t=ET.SubElement(page,'t',{'id':'51','p':'165 60','BoundingBox':'140 52 190 62'})
    ET.SubElement(t,'s',{'size':'10'}).text='example'
    ET.SubElement(page,'graphic',{'id':'52','SupersededBy':'50','BoundingBox':'220 80 150 80','GraphicType':'Line','ArrowType':'FullHead'})
    result,audit=layout_row(ET.tostring(root,encoding='unicode'),caption_map={'1':'10','20':'30'},condition_map={'50':['51']})
    r=ET.fromstring(result);arrow=r.find('.//arrow');label=r.find('.//t[@id="51"]')
    head=list(map(float,arrow.get('Head3D').split()));tail=list(map(float,arrow.get('Tail3D').split()))
    assert float(label.get('p').split()[0]) == pytest.approx((head[0]+tail[0])/2)
    assert float(label.get('p').split()[1]) < head[1]
    assert audit['checks']['chemistry_preserved']


def test_normalizing_retains_isotope_charge_and_wedge_semantics():
    sample='''<CDXML><page><fragment id="1"><n id="2" Element="7" Charge="1" NumHydrogens="3" p="30 0"/><n id="3" Isotope="13" p="0 0"/><b id="4" B="3" E="2" Display="WedgeBegin"/></fragment></page></CDXML>'''
    result,_=normalize_cdxml(sample,'house')
    r=ET.fromstring(result)
    assert r.find('.//n[@id="2"]').get('Charge')=='1'
    assert r.find('.//n[@id="3"]').get('Isotope')=='13'
    assert r.find('.//b').get('Display')=='WedgeBegin'
    assert chemical_signature(sample)==chemical_signature(result)


@pytest.mark.parametrize('replacement',['NaN 45','inf 45','30'])
def test_bad_coordinates_fail_closed(replacement):
    with pytest.raises(ValueError):normalize_cdxml(SAMPLE.replace('30 45',replacement),'house')


def test_zero_bonds_nested_abbreviations_and_queries_fail_closed():
    with pytest.raises(ValueError):normalize_cdxml(SAMPLE.replace('60 45','30 45'),'house')
    for attr in ['NodeType="Nickname"','NodeType="GenericNickname"','ElementList="6 7"']:
        with pytest.raises(ValueError,match='Unsupported'):
            normalize_cdxml(SAMPLE.replace('id="2"',f'id="2" {attr}'),'house')


def test_width_limit_does_not_silently_shrink_molecules():
    with pytest.raises(ValueError,match='width'):
        layout_row(SAMPLE,caption_map={'1':'10','20':'30'},width=40)


def test_imported_overlap_helper():
    assert find_overlaps([Box(0,0,10,10),Box(5,5,15,15)],ids=['a','b']) == [('a','b')]
    assert find_overlaps([Box(0,0,10,10),Box(11,0,20,10)]) == []


def test_signature_detects_connectivity_and_charge_changes():
    assert chemical_signature(SAMPLE)!=chemical_signature(SAMPLE.replace('Element="8"','Element="7"'))


def test_native_tetrahedral_geometry_metadata_can_be_preserved():
    text=SAMPLE.replace('id="2"','id="2" Geometry="Tetrahedral"')
    result,_=normalize_cdxml(text)
    assert ET.fromstring(result).find('.//n[@id="2"]').get('Geometry')=='Tetrahedral'
    with pytest.raises(ValueError,match='Unsupported'):
        normalize_cdxml(text.replace('Tetrahedral','Octahedral'))


def test_native_bond_drawing_order_metadata_is_preserved():
    source=SAMPLE.replace('id="4" B=', 'id="4" BondCircularOrdering="0 0 0 0" B=')
    result,_=normalize_cdxml(source)
    assert ET.fromstring(result).find('.//b[@id="4"]').get('BondCircularOrdering')=='0 0 0 0'
    assert chemical_signature(result)==chemical_signature(source)
