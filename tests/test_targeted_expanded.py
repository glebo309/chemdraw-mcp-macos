import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import style_cdxml
from chemdraw_macos.editing import source_token
from chemdraw_macos.polish import chemical_signature
from chemdraw_macos.targeted import prepare_selection, plan_target_edit
from test_targeted import sheet


def edit(text, kind, oid, operation):
    return plan_target_edit(text, prepare_selection(text,kind,[oid],source_token(text)),operation)


@pytest.mark.parametrize('operation,smiles',[
    ({'kind':'set_atom','element':'O','hydrogens':1,'charge':0},'CO'),
    ({'kind':'set_atom','element':'N','hydrogens':3,'charge':1},'C[NH3+]'),
])
def test_atom_and_charge_changes_preserve_unselected_molecule(operation,smiles):
    text=sheet();planned,report=edit(text,'atom','12',operation)
    assert chemical_signature(planned)==sorted([smiles,'CO'])
    assert ET.tostring(ET.fromstring(text).find("page/fragment[@id='20']"))==ET.tostring(ET.fromstring(planned).find("page/fragment[@id='20']"))
    assert report['original_atom_coordinates_preserved']


def test_bond_order_requires_explicit_endpoint_hydrogens():
    op={'kind':'set_bond_order','order':2,'hydrogens':{'21':2,'22':0}}
    planned,_=edit(sheet(),'bond','23',op)
    assert chemical_signature(planned)==['C=O','CN']
    with pytest.raises(ValueError):edit(sheet(),'bond','23',{**op,'hydrogens':{'21':2}})


def test_attach_supplied_fragment_and_remove_exact_branch():
    fragment=style_cdxml('<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/><n id="4" Element="8" NumHydrogens="1" p="18 0"><t><s>OH</s></t></n><b id="5" B="3" E="4"/></fragment></page></CDXML>','house')
    attached,report=edit(sheet(),'atom','12',{'kind':'attach_fragment','fragment_cdxml':fragment,'attachment_atom_id':'3','angle_degrees':0})
    assert chemical_signature(attached)==['CNCO','CO']
    assert report['added_atoms']==2
    new=ET.fromstring(attached)
    joining=next(b for b in new.findall('.//b') if b.get('B')=='12')
    restored,removal=edit(attached,'bond',joining.get('id'),{'kind':'remove_substituent','keep_atom_id':'12','hydrogens':2})
    assert chemical_signature(restored)==chemical_signature(sheet())
    assert len(removal['removed_atom_ids'])==2


def test_removal_refuses_ring_bond():
    ring,_=edit(sheet(),'atom','12',{'kind':'attach_ring','size':6,'angle_degrees':0})
    f=ET.fromstring(ring).find('page/fragment')
    b=f.findall('b')[-1]
    with pytest.raises(ValueError,match='ring|disconnect'):
        edit(ring,'bond',b.get('id'),{'kind':'remove_substituent','keep_atom_id':b.get('B'),'hydrogens':3})


@pytest.mark.parametrize('operation',[
    {'kind':'set_atom','element':'N','hydrogens':4,'charge':0},
    {'kind':'set_atom','element':'N','hydrogens':True,'charge':0},
    {'kind':'set_atom','element':'N','hydrogens':3,'charge':True},
    {'kind':'set_atom','element':'Fe','hydrogens':0,'charge':2},
])
def test_invalid_edit_does_not_sanitize_away_requested_chemistry(operation):
    with pytest.raises(ValueError):edit(sheet(),'atom','12',operation)


def test_new_bond_crossing_existing_bond_is_rejected():
    # Vertical obstacle crosses the new joining bond but is clear of all new atoms.
    root=ET.fromstring(sheet());f=ET.SubElement(root.find('page'),'fragment',{'id':'60'})
    ET.SubElement(f,'n',{'id':'61','p':'127 50'})
    ET.SubElement(f,'n',{'id':'62','p':'127 150'})
    ET.SubElement(f,'b',{'id':'63','B':'61','E':'62'})
    text=ET.tostring(root,encoding='unicode')
    with pytest.raises(ValueError,match='[Cc]ollision|overlap|cross'):
        edit(text,'atom','12',{'kind':'attach_ring','size':6,'angle_degrees':0})


def test_new_ring_avoids_caption_ink_and_auto_search_finds_another_angle():
    root=ET.fromstring(sheet());caption=root.find('page/t')
    caption.set('BoundingBox','134 90 205 110');caption.set('p','134 105')
    text=ET.tostring(root,encoding='unicode')
    with pytest.raises(ValueError,match='[Cc]ollision|overlap'):
        edit(text,'atom','12',{'kind':'attach_ring','size':6,'angle_degrees':0})
    planned,report=edit(text,'atom','12',{'kind':'attach_ring','size':6,'angle_degrees':'auto'})
    assert report['placement']['angle_degrees']!=0
    assert report['placement']['checked_candidates']>1
    assert chemical_signature(planned)==['CNC1CCCCC1','CO']


def test_builtin_style_overrides_inherited_local_settings():
    root=ET.fromstring(sheet());f=root.find('page/fragment')
    f.set('LabelSize','29');f.set('BondSpacing','45')
    n=f.find('n');n.set('LabelFont','999');n.set('LabelSize','27')
    result=ET.fromstring(style_cdxml(ET.tostring(root,encoding='unicode'),'house'))
    assert result.find('page/fragment').get('LabelSize')=='14'
    assert result.find('page/fragment').get('BondSpacing')=='18'
    assert result.find('.//n').get('LabelFont')==result.get('LabelFont')


def test_builtin_style_is_verified_not_silently_skipped():
    from chemdraw_macos.styles import verify_custom_style
    text=sheet()
    assert verify_custom_style(text,text,'house')['verified']
    root=ET.fromstring(text);root.find('.//b').set('LineWidth','.1')
    with pytest.raises(ValueError,match='style|Width'):
        verify_custom_style(text,ET.tostring(root,encoding='unicode'),'house')


def test_reaction_caption_clearance_matches_shared_lab_default():
    from chemdraw_macos.reaction import compose_reaction,arrange_reaction
    from chemdraw_macos.lab_style import DEFAULTS
    from chemdraw_macos.polish import bounds
    from test_reaction import item,measured
    from test_draw import ETHANOL
    text,recipe=compose_reaction([ETHANOL]*2,[item('r')],[item('p')])
    arranged,plan=arrange_reaction(measured(text),recipe)
    page=ET.fromstring(arranged).find('page')
    bottom=max(bounds(e).bottom for e in page if e.get('id') in recipe['component_ids'])
    tops=[bounds(page.find(f"t[@id='{tid}']")).top for tid in recipe['caption_map'].values()]
    assert min(tops)-bottom==pytest.approx(DEFAULTS['grid']['label_gap'],abs=.01)
    assert plan['gap_pt']==DEFAULTS['reaction']['gap']


def test_native_label_overlap_is_rejected_even_when_atom_positions_are_clear():
    from chemdraw_macos.placement import check_edit_placement
    root=ET.fromstring(sheet())
    for n in root.findall('.//n'):
        t=n.find('t')
        if t is not None:
            x,y=map(float,n.get('p').split());t.set('BoundingBox',f'{x-5} {y-6} {x+5} {y+6}')
    root.find('page/t').set('BoundingBox','90 140 180 150')
    before=ET.tostring(root,encoding='unicode')
    root.find(".//n[@id='12']/t").set('BoundingBox','110 94 305 190')
    with pytest.raises(ValueError,match='collision'):
        check_edit_placement(before,ET.tostring(root,encoding='unicode'),measured=True)


def test_charge_placement_accounts_for_actual_obstacle_bond_width():
    from chemdraw_macos.symbols import plan_symbols,symbol_primitives,_distance_segment
    from test_symbols import source,REQUESTS
    first,plan=plan_symbols(source(),REQUESTS[:1])
    g=ET.fromstring(first).find('page/fragment/graphic')
    x,y,r=symbol_primitives(g)[0]
    root=ET.fromstring(source());f=ET.SubElement(root.find('page'),'fragment',{'id':'9000'})
    a=(x+r+3,y-24);b=(x+r+3,y+24)
    ET.SubElement(f,'n',{'id':'9001','p':f'{a[0]} {a[1]}'})
    ET.SubElement(f,'n',{'id':'9002','p':f'{b[0]} {b[1]}'})
    ET.SubElement(f,'b',{'id':'9003','B':'9001','E':'9002','LineWidth':'8'})
    text,plan=plan_symbols(ET.tostring(root,encoding='unicode'),REQUESTS[:1])
    g=ET.fromstring(text).find('page/fragment/graphic');px,py,pr=symbol_primitives(g)[0]
    assert _distance_segment((px,py),a,b)>=pr+plan['clearance_pt']+4


def test_charge_clearance_rechecked_against_native_label_bounds():
    from chemdraw_macos.symbols import plan_symbols,verify_symbol_clearance
    from test_symbols import source,REQUESTS
    text,plan=plan_symbols(source(),REQUESTS[:1]);root=ET.fromstring(text)
    x,y=plan['symbols'][0]['center_pt']
    root.find('page/t').set('BoundingBox',f'{x-4} {y-4} {x+4} {y+4}')
    with pytest.raises(ValueError,match='clearance|collision'):
        verify_symbol_clearance(ET.tostring(root,encoding='unicode'),[plan['symbols'][0]['symbol_id']],2)


def test_fragment_join_does_not_hide_a_carbon_in_a_straight_line():
    import math
    fragment=style_cdxml('<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/><n id="4" Element="8" NumHydrogens="1" p="18 0"><t><s>OH</s></t></n><b id="5" B="3" E="4"/></fragment></page></CDXML>','house')
    planned,report=edit(sheet(),'atom','12',{'kind':'attach_fragment','fragment_cdxml':fragment,'attachment_atom_id':'3','angle_degrees':0})
    root=ET.fromstring(planned)
    p=lambda aid:tuple(map(float,root.find(f".//n[@id='{aid}']").get('p').split()))
    anchor=p(report['fragment_atom_id_map']['3']);oxygen=p(report['fragment_atom_id_map']['4']);nitrogen=p('12')
    a=tuple(x-y for x,y in zip(nitrogen,anchor));b=tuple(x-y for x,y in zip(oxygen,anchor))
    assert sum(x*y for x,y in zip(a,b))/(math.hypot(*a)*math.hypot(*b))==pytest.approx(-.5,abs=1e-5)


def test_attachment_does_not_hide_the_existing_carbon_either():
    # Existing N is to the right of C. Extending C leftward would hide the CH2.
    with pytest.raises(ValueError,match='collision|carbon'):
        edit(sheet(),'atom','11',{'kind':'attach_ring','size':6,'angle_degrees':180})
    planned,report=edit(sheet(),'atom','11',{'kind':'attach_ring','size':6,'angle_degrees':'auto'})
    assert report['placement']['angle_degrees'] not in (0,180)


def test_attach_single_carbon_fragment_as_methyl():
    fragment=style_cdxml('<CDXML><page id="1"><fragment id="2"><n id="3" p="0 0"/></fragment></page></CDXML>','house')
    planned,report=edit(sheet(),'atom','12',{'kind':'attach_fragment','fragment_cdxml':fragment,'attachment_atom_id':'3','angle_degrees':'auto'})
    assert chemical_signature(planned)==['CNC','CO']
    assert report['added_atoms']==1
