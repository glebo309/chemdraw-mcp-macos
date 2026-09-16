import copy
import xml.etree.ElementTree as ET
import pytest

from test_api_drawing import EMPTY
from chemdraw_macos.api_drawing import plan_addition
from chemdraw_macos.polish import bounds, bond_lengths


def test_complete_table_adds_defined_pages_at_same_scale():
    records=[{'compound_id':str(i),'label':f'Analogue {i}',
              'smiles':'CCN(CC)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)C'} for i in range(20)]
    payload, report=plan_addition(EMPTY,records,columns=2,allow_page_expansion=True)
    page=ET.fromstring(payload).find('page')
    assert int(page.get('HeightPages')) > 1 and page.get('WidthPages')=='1'
    assert len(page.findall('fragment'))==20
    assert report['pages_added']>0
    cells=page.findall('fragment')
    xs=[]
    for f in cells:
        b=bounds(f); sheet=int(b.top//770)
        assert b.top>=sheet*770+24 and b.bottom<=(sheet+1)*770-24
        assert sorted(bond_lengths(f))[len(bond_lengths(f))//2]==pytest.approx(18,abs=.02)
        xs.append(b.center[0])
    assert xs[::2]==pytest.approx([xs[0]]*10)
    assert xs[1::2]==pytest.approx([xs[1]]*10)


def test_expansion_preserves_existing_and_requires_explicit_permission():
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    parent,_=plan_addition(EMPTY,[{'compound_id':'parent','label':'Parent','smiles':'CCO'}])
    records=[{'compound_id':str(i),'label':f'Analogue {i}','smiles':'CCN(CC)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)C'} for i in range(24)]
    payload, report=plan_addition(parent,records,columns=2,allow_page_expansion=True)
    with pytest.raises(ValueError):prepare_payload(parent,payload)
    safe=prepare_payload(parent,payload,allow_page_expansion=True)
    old=ET.fromstring(parent); combined=ET.fromstring(safe)
    for obj in old.find('page'):combined.find('page').append(copy.deepcopy(obj))
    checked=verify_append(parent,ET.tostring(combined,encoding='unicode'),safe,
                          exact_coordinates=True,allow_page_expansion=True)
    assert checked['existing_content_preserved'] and checked['page_expansion_verified']
    assert checked['page_unchanged'] is False
    bad=ET.fromstring(safe);bad.find('page').set('BoundingBox','0 0 1000 1540')
    with pytest.raises(ValueError):prepare_payload(parent,ET.tostring(bad,encoding='unicode'),allow_page_expansion=True)


def test_native_ink_not_estimated_envelope_drives_final_centres():
    from chemdraw_macos.api_drawing import center_measured_payload
    payload,_=plan_addition(EMPTY,[{'compound_id':'a','label':'Short','smiles':'CCO'},
                                   {'compound_id':'b','label':'Long','smiles':'CCCCCCCC'}],columns=2)
    measured=ET.fromstring(payload)
    for f in measured.findall('page/fragment'):
        b=bounds(f)
        f.set('BoundingBox',f'{b.left+3} {b.top+2} {b.right-1} {b.bottom-4}')
    for t in measured.findall('page/t'):
        b=bounds(t);t.set('BoundingBox',f'{b.left+2} {b.top} {b.right+4} {b.bottom}')
    corrected,expected=center_measured_payload(payload,ET.tostring(measured,encoding='unicode'))
    for a,b in zip(ET.fromstring(payload).findall('page/fragment'),ET.fromstring(corrected).findall('page/fragment')):
        assert bounds(a).center==pytest.approx(bounds(b).center)
        assert bounds(b).width==pytest.approx(bounds(a).width-4)
    assert [bounds(t).center[0] for t in ET.fromstring(corrected).findall('page/t')]==pytest.approx([e['x'] for e in expected['captions']])


def test_analogue_ring_core_is_oriented_even_when_no_whole_parent_is_shared():
    records=[{'compound_id':str(i),'label':str(i),'smiles':s} for i,s in enumerate([
        'CCN(CC)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)C',
        'CC(C)N(C)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)C',
        'CCCN1C[C@@H](C=C2[C@H]1CC3=CNC4=CC=CC2=C34)C(=O)N(CC)CC',
        'CCN(CC)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)CC=C'])]
    payload,report=plan_addition(EMPTY,records,columns=2,allow_page_expansion=True)
    assert report['scaffold_smiles'] is not None
    from test_api_drawing import assert_core_orientation
    from chemdraw_macos.api_drawing import _isolated
    r=ET.fromstring(payload)
    assert_core_orientation(_isolated(r,r.find('page/fragment')),payload,report['scaffold_smiles'])
