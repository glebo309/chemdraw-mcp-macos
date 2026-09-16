import copy
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.complexes import plan_complex, verify_complex


def test_shipped_chelate_is_black_by_default():
    import json
    from pathlib import Path
    r=json.loads((Path(__file__).parents[1]/'examples/coordination-ruthenium-chelate.json').read_text())
    assert all('color' not in a for a in r['atoms'])
    root=ET.fromstring(plan_complex(r)[0])
    assert all(n.get('color','0')=='0' for n in root.findall('.//n'))


def spatial():
    return {'schema_version': 2, 'label': 'Explicit spatial fixture',
            'atoms': [
                {'id':'ru','element':'Ru','charge':0,'hydrogens':0,'position':[180,180,0]},
                {'id':'n','element':'N','charge':0,'hydrogens':3,'position':[140,210,20],'color':'#214EAF'},
                {'id':'o','element':'O','charge':0,'hydrogens':2,'position':[220,150,-20]}],
            'bonds': [
                {'begin':'n','end':'ru','order':'coordination','display':'WedgeEnd'},
                {'begin':'o','end':'ru','order':'coordination','display':'WedgedHashEnd'}],
            'attachments': [], 'overall_charge': 2}


def test_spatial_coordination_is_not_a_dative_arrow():
    text, plan = plan_complex(spatial())
    root = ET.fromstring(text)
    assert [b.get('Order') for b in root.findall('.//b')] == ['1','1']
    assert {b.get('Display') for b in root.findall('.//b')} == {'WedgeEnd','WedgedHashEnd'}
    assert plan['overall_charge'] == 2
    assert 'annotation' in plan['charge_semantics']
    assert len(root.findall('page/graphic[@GraphicType="Line"]'))==2
    checks = verify_complex(text,text)['checks']
    assert checks['donor_colours_preserved']
    assert checks['whole_complex_charge_annotation_preserved']


@pytest.mark.parametrize('change',['display','colour','charge','bracket','extra','filled','stroke'])
def test_spatial_native_changes_fail(change):
    text,_=plan_complex(spatial()); root=ET.fromstring(text)
    if change=='display': root.find('.//b').set('Display','Solid')
    if change=='colour': root.find('.//colortable/color').set('r','1')
    if change=='charge': root.findall('page/t')[1].find('s').text='3+'
    if change=='bracket': root.find('page/graphic').set('BoundingBox','10 10 20 20')
    if change=='extra': ET.SubElement(root.find('page'),'curve',{'id':'999'})
    if change=='filled': root.find('page/graphic').set('FillType','Solid')
    if change=='stroke': root.find('.//b').set('LineWidth','9')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


def haptic():
    r=spatial(); r['overall_charge']=None
    r['atoms']=[{'id':'fe','element':'Fe','charge':0,'hydrogens':0,'position':[180,180,0]}]
    for i,p in enumerate(([120,120,0],[140,100,0],[160,120,0])):
        r['atoms'].append({'id':f'c{i}','element':'C','charge':0,'hydrogens':1,'position':p})
    r['attachments']=[{'id':'ring','position':[140,120,0],'atoms':['c0','c1','c2']}]
    r['bonds']=[{'begin':'c0','end':'c1','order':'1','display':'Solid'},
                {'begin':'c1','end':'c2','order':'1','display':'Solid'},
                {'begin':'c2','end':'c0','order':'1','display':'Solid'},
                {'begin':'ring','end':'fe','order':'haptic','display':'Solid'}]
    return r


def test_haptic_attachment_is_a_native_non_atom_node():
    text,_=plan_complex(haptic()); root=ET.fromstring(text)
    node=root.find('.//n[@NodeType="MultiAttachment"]')
    assert len(node.get('Attachments').split())==3
    assert node.get('Element') is None
    assert verify_complex(text,text)['checks']['multicentre_attachments_preserved']
    node.set('Attachments','4 5')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


def test_native_implicit_carbon_hydrogens_and_warnings_are_reported():
    import json
    from pathlib import Path
    r=json.loads((Path(__file__).parents[1]/'examples/coordination-ruthenium-chelate.json').read_text())
    text,plan=plan_complex(r); root=ET.fromstring(text)
    for a in r['atoms']:
        root.find(f".//n[@id='{plan['atom_ids'][a['id']]}']").set('NumHydrogens',str(a['hydrogens']))
    text=ET.tostring(root,encoding='unicode')
    for n in root.findall('.//n[@Element="6"]'): n.attrib.pop('NumHydrogens')
    root.find('.//n[@Element="7"]').set('Warning','An atom in this label has an invalid valence.')
    root.find('.//b').set('BondCircularOrdering','0 0 0 0')
    audit=verify_complex(text,ET.tostring(root,encoding='unicode'))
    assert audit['native_warnings']
    assert audit['chemical_plausibility']=='not validated'
    root.find('.//b').set('BondCircularOrdering','0 0 0 9999')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


@pytest.mark.parametrize('change',['missing','duplicate','unknown','arrow','charge','colour','endpoint'])
def test_invalid_spatial_inputs_fail_closed(change):
    r=haptic()
    if change=='missing': r['attachments'][0]['atoms'].append('absent')
    if change=='duplicate': r['attachments'][0]['atoms'][1]='c0'
    if change=='unknown': r['attachments'][0]['charge']=1
    if change=='arrow': r['bonds'][-1]['display']='WedgeEnd'
    if change=='charge': r['overall_charge']=True
    if change=='colour': r['atoms'][0]['color']='blue'
    if change=='endpoint': r['bonds'][-1]['end']='c0'
    with pytest.raises(ValueError): plan_complex(r)


def test_native_haptic_crossing_order_is_preserved():
    import json
    from pathlib import Path
    r=json.loads((Path(__file__).parents[1]/'examples/coordination-ferrocene.json').read_text())
    text,plan=plan_complex(r); root=ET.fromstring(text)
    bond=root.find(f".//b[@B='{plan['atom_ids']['centre0']}']")
    bond.set('Z','999' if int(bond.get('Z'))<int(root.findall('.//b')[-1].get('Z')) else '-999')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


def test_aromatic_haptic_rings_use_skeletal_carbons_and_native_ellipses():
    r=haptic()
    for b in r['bonds']:
        if b['order']!='haptic': b['order']='1.5'
    r['attachments'][0]['ellipse']=[18,8]
    text,_=plan_complex(r); root=ET.fromstring(text)
    assert all(n.find('t') is None and n.get('NumHydrogens') is None for n in root.findall('.//n[@Element="6"]'))
    assert len(root.findall('page/graphic[@GraphicType="Oval"]'))==1
    assert verify_complex(text,text)['checks']['multicentre_attachments_preserved']
    root.find('page/graphic').set('OvalType','Filled')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


def test_native_corner_line_supersession_is_checked():
    text,_=plan_complex(spatial()); root=ET.fromstring(text); page=root.find('page')
    for i,g in enumerate(page.findall('graphic')):
        x,y,u,v=g.get('BoundingBox').split(); aid=str(900+i);g.set('SupersededBy',aid)
        ET.SubElement(page,'arrow',{'id':aid,'Head3D':f'{x} {y} 0','Tail3D':f'{u} {v} 0','FillType':'None','ArrowheadType':'Solid'})
    assert verify_complex(text,ET.tostring(root,encoding='unicode'))['checks']['whole_complex_charge_annotation_preserved']
    page.find('arrow').set('ArrowheadHead','Full')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))
