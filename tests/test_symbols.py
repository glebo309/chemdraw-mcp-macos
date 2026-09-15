import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.symbols import plan_symbols, verify_symbols, symbols_document, symbols_file
from chemdraw_macos.editing import source_token
from chemdraw_macos.batch import NativeUncertain
from test_batch import BatchBridge

RAW=(Path(__file__).parents[1]/'examples/sn2-annotation-input.cdxml').read_text()

def source():
    root=ET.fromstring(RAW)
    for f in root.findall('page/fragment'):
        for g in f.findall('graphic'):f.remove(g)
        # Removing native display-charge graphics also requires restoring the
        # formal-charge suffix in the chemical label for a valid plain source.
        for atom in f.findall('n'):
            if atom.get('Charge')=='-1':atom.find('t/s').text+='-'
    return ET.tostring(root,encoding='unicode')

REQUESTS=[{'key':'br-charge','kind':'charge','atom_id':'1100'},
          {'key':'i-charge','kind':'charge','atom_id':'4114'}]

def test_charge_placement_keeps_owner_uniquely_nearest():
    import math
    # Native tetramethylammonium geometry: a clear circle can still be nearer
    # a methyl carbon, causing ChemDraw to reassign the formal charge on save.
    text='''<CDXML BondLength="18" LabelSize="14" LineWidth="1.58"><page id="1" BoundingBox="0 0 300 300"><fragment id="2">
    <n id="3" p="62.09 159.20"/><n id="4" p="77.68 150.20" Element="7" Charge="1" NumHydrogens="0"><t p="72.63 155.36" BoundingBox="73.71 140.37 88.53 155.36"><s>N+</s></t></n>
    <n id="5" p="86.68 165.78"/><n id="6" p="93.27 141.20"/><n id="7" p="68.68 134.61"/>
    <b id="8" B="3" E="4"/><b id="9" B="4" E="5"/><b id="10" B="4" E="6"/><b id="11" B="4" E="7"/>
    </fragment></page></CDXML>'''
    try:
        planned,_=plan_symbols(text,[{'key':'n','kind':'charge','atom_id':'4'}])
    except ValueError as exc:
        assert 'No collision-free' in str(exc)
        return  # Refusal is safe when the original measured label leaves no room.
    root=ET.fromstring(planned);g=root.find('page/fragment/graphic')
    p=tuple(map(float,g.get('BoundingBox').split()[:2]))
    atoms={n.get('id'):tuple(map(float,n.get('p').split())) for n in root.findall('page/fragment/n')}
    assert all(math.dist(p,atoms['4'])+.25<=math.dist(p,q) for k,q in atoms.items() if k!='4')

def test_native_charge_symbols_are_uniform_and_keep_chemistry():
    text,plan=plan_symbols(source(),REQUESTS)
    root=ET.fromstring(text);gs=root.findall('page/fragment/graphic')
    assert len(gs)==2 and {g.get('SymbolType') for g in gs}=={'CircleMinus'}
    # Native probe established Symbol strokes render at 0.8 times this setting.
    assert {float(g.get('LineWidth')) for g in gs}=={1.975}
    spans=[abs(float(g.get('BoundingBox').split()[0])-float(g.get('BoundingBox').split()[2])) for g in gs]
    assert spans[0]==pytest.approx(spans[1])
    assert [g[0].attrib for g in gs]==[{'attribute':'Charge','object':'1100'},{'attribute':'Charge','object':'4114'}]
    assert verify_symbols(text,text)['checks']['symbol_geometry_preserved']
    assert plan['collision_checks']=='conservative symbol envelopes against labels, atoms, bonds and page objects'

def test_dots_are_native_graphics_not_radical_state_changes():
    text,plan=plan_symbols(source(),[{'key':'lp','kind':'lone_pair','atom_id':'2104'}, {'key':'dot','kind':'electron','atom_id':'3110'}])
    gs=ET.fromstring(text).findall('page/fragment/graphic')
    assert {g.get('GraphicType') for g in gs}=={'Symbol','Oval'}
    # Native LonePair attachment uses represent Radical but does not create an
    # atom Radical state; Electron must remain unassociated in this contract.
    assert len(next(g for g in gs if g.get('SymbolType')=='LonePair'))==1
    assert not list(next(g for g in gs if g.get('GraphicType')=='Oval'))
    assert 'Radical=' not in text
    assert verify_symbols(text,text)['checks']['symbol_geometry_preserved']

@pytest.mark.parametrize('req',[[{'key':'bad','kind':'charge','atom_id':'2104'}],REQUESTS+REQUESTS[:1],[{'key':'bad','kind':'radical','atom_id':'1100'}]])
def test_bad_requests_fail_closed(req):
    with pytest.raises(ValueError):plan_symbols(source(),req)

def test_existing_charge_not_duplicated():
    with pytest.raises(ValueError,match='already'):plan_symbols(RAW,REQUESTS)

def test_missing_native_label_box_rejected():
    text=source().replace('BoundingBox="24 95 37.16 105"','')
    with pytest.raises(ValueError,match='measured'):plan_symbols(text,REQUESTS)

@pytest.mark.parametrize('attribute,value',[('BoundingBox','0 0 10 0'),('LineWidth','.1'),('SymbolType','Electron')])
def test_native_changes_rejected(attribute,value):
    text,_=plan_symbols(source(),REQUESTS);root=ET.fromstring(text)
    root.find('page/fragment/graphic').set(attribute,value)
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_dot_cannot_acquire_radical_reference():
    text,_=plan_symbols(source(),[{'key':'lp','kind':'lone_pair','atom_id':'1100'}]);root=ET.fromstring(text)
    ET.SubElement(root.find('page/fragment/graphic'),'represent',{'attribute':'Radical','object':'1100'})
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_document_copy_and_source_preservation(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=source()
    result=symbols_document(b,1,str(tmp_path/'out'),REQUESTS,source_token(source()))
    assert result['audit']['status']=='checks_passed'
    assert b.docs[1]==source() and len(b.managed)==1
    assert (tmp_path/'out/review.html').is_file()

def test_stale_rejected_before_copy(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=source()
    with pytest.raises(ValueError,match='stale'):symbols_document(b,1,str(tmp_path/'out'),REQUESTS,'stale')
    assert not b.managed

def test_native_uncertainty_no_retry_or_close(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=source();export=b.export
    def fail(did,path,format,pixels=3200):
        if Path(path).name=='figure.svg':raise RuntimeError('timeout')
        return export(did,path,format,pixels)
    b.export=fail
    with pytest.raises(NativeUncertain):symbols_document(b,1,str(tmp_path/'out'),REQUESTS,source_token(source()))
    assert len(b.managed)==1 and not any(e[0]=='close' for e in b.events)
    assert json.loads((tmp_path/'out/audit.json').read_text())['status']=='uncertain'

def test_file_copy(tmp_path):
    path=tmp_path/'input.cdxml';path.write_text(source());b=BatchBridge(tmp_path/'work')
    result=symbols_file(b,str(path),str(tmp_path/'out'),REQUESTS)
    assert result['audit']['checks']['source_file_unchanged'] and path.read_text()==source()
    assert len(b.managed)==1

def arrow_for(sid,electrons=2):
    return {'key':'donation','electrons':electrons,'source':{'kind':'symbol','id':sid},
            'target':{'kind':'atom','id':'2103','offset':[0,-14]},'controls':[[0,-33],[0,-28]]}

def test_explicit_negative_charge_arrow_starts_at_symbol_edge():
    from chemdraw_macos.annotations import plan_annotations
    text,_=plan_annotations(RAW,[arrow_for('1500')])
    pts=list(map(float,ET.fromstring(text).find('page/curve').get('CurvePoints').split()))
    assert pts[0]==pytest.approx(42.7) and pts[1]<86

@pytest.mark.parametrize('kind,electrons',[('lone_pair',2),('electron',1)])
def test_graphical_dot_symbol_can_be_explicit_arrow_source(kind,electrons):
    from chemdraw_macos.annotations import plan_annotations,verify_annotations
    text,plan=plan_symbols(source(),[{'key':'source','kind':kind,'atom_id':'1100'}])
    drawn,_=plan_annotations(text,[arrow_for(plan['symbols'][0]['symbol_id'],electrons)])
    assert verify_annotations(drawn,drawn)['checks']['symbol_geometry_preserved']

def test_symbol_electron_count_mismatch_and_symbol_target_rejected():
    from chemdraw_macos.annotations import plan_annotations
    with pytest.raises(ValueError):plan_annotations(RAW,[arrow_for('1500',1)])
    arrow=arrow_for('1500');arrow['target']={'kind':'symbol','id':'4503'}
    with pytest.raises(ValueError):plan_annotations(RAW,[arrow])

def test_annotation_inspection_exposes_symbol_ids_and_charge():
    from chemdraw_macos.annotations import annotation_inventory
    report=annotation_inventory(RAW)
    assert report['symbols'][0]['id']=='1500'
    assert report['symbols'][0]['atom_id']=='1100'
    assert report['symbols'][0]['kind']=='CircleMinus'

def test_file_uncertainty_preserves_both_owned_documents(tmp_path):
    path=tmp_path/'input.cdxml';path.write_text(source());b=BatchBridge(tmp_path/'work');export=b.export
    def fail(did,path,format,pixels=3200):
        if Path(path).name=='figure.svg':raise RuntimeError('timeout')
        return export(did,path,format,pixels)
    b.export=fail
    with pytest.raises(NativeUncertain):symbols_file(b,str(path),str(tmp_path/'out'),REQUESTS)
    assert len(b.managed)==2 and not any(e[0]=='close' for e in b.events)

def test_no_free_space_rejected():
    root=ET.fromstring(source());root.find('page').set('BoundingBox','0 0 1 1')
    with pytest.raises(ValueError,match='collision-free'):plan_symbols(ET.tostring(root,encoding='unicode'),REQUESTS)

def test_graph_and_atom_coordinates_not_changed():
    text,_=plan_symbols(source(),REQUESTS);root=ET.fromstring(text)
    root.find('page/fragment/n').set('p','0 0')
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_native_calibrated_primitives_and_pair_endpoint_coverage():
    from chemdraw_macos.symbols import symbol_primitives
    circle=ET.fromstring('<graphic SymbolType="CircleMinus" BoundingBox="50 60 39.5 60" LineWidth="1.975"/>')
    assert symbol_primitives(circle)[0]==pytest.approx((50,60,6.2466666667))
    pair=ET.fromstring('<graphic SymbolType="LonePair" BoundingBox="50 60 46.5 60"/>')
    assert symbol_primitives(pair)[0]==pytest.approx((50,60,3.5*2/9))
    assert symbol_primitives(pair)[1]==pytest.approx((46.5,60,3.5*2/9))

def test_default_pair_and_electron_dots_have_same_size():
    from chemdraw_macos.symbols import symbol_primitives
    text,_=plan_symbols(source(),[{'key':'lp','kind':'lone_pair','atom_id':'2104'}, {'key':'dot','kind':'electron','atom_id':'3110'}])
    gs=ET.fromstring(text).findall('page/fragment/graphic')
    assert symbol_primitives(gs[0])[0][2]==pytest.approx(symbol_primitives(gs[1])[0][2],abs=.00001)

def test_symbol_tail_uses_measured_visible_circle_edge_not_handle_span():
    from chemdraw_macos.annotations import plan_annotations
    text,_=plan_annotations(RAW,[arrow_for('1500')]);pts=list(map(float,ET.fromstring(text).find('page/curve').get('CurvePoints').split()))
    assert pts[1]==pytest.approx(86-(10.5*4/9+2*.8),abs=.03)

def test_charge_graphic_replaces_only_redundant_display_suffix():
    text,_=plan_symbols(source(),REQUESTS);root=ET.fromstring(text)
    br=root.find('page/fragment/n[@id="1100"]')
    assert br.get('Charge')=='-1' and br.find('t/s').text=='Br'
    assert root.find('page/fragment/n[@id="4114"]/t/s').text=='I'

def test_lone_pair_native_association_is_explicit_and_verified():
    text,_=plan_symbols(RAW,[{'key':'lp','kind':'lone_pair','atom_id':'1100'}]);root=ET.fromstring(text)
    pair=root.find('page/fragment/graphic[@SymbolType="LonePair"]')
    assert pair.find('represent').attrib=={'attribute':'Radical','object':'1100'}
    pair.find('represent').set('object','4114')
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_electron_cannot_change_atom_radical_state():
    text,_=plan_symbols(RAW,[{'key':'electron','kind':'electron','atom_id':'1100'}]);root=ET.fromstring(text)
    root.find('page/fragment/n[@id="1100"]').set('Radical','Doublet')
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_graphical_electron_uses_exact_native_filled_circle_not_radical_symbol():
    text,_=plan_symbols(RAW,[{'key':'dot','kind':'electron','atom_id':'1100'}]);root=ET.fromstring(text)
    dot=root.find('page/fragment/graphic[@GraphicType="Oval"]')
    assert dot is not None and dot.get('OvalType')=='Circle Filled'
    assert dot.get('Center3D') and dot.get('MajorAxisEnd3D') and dot.get('MinorAxisEnd3D')
    assert dot.get('SymbolType') is None and not list(dot)
    assert all(n.get('Radical') is None for n in root.findall('page/fragment/n'))
    assert verify_symbols(text,text)['checks']['symbol_geometry_preserved']

@pytest.mark.parametrize('attribute,value',[('MinorAxisEnd3D','0 0 0'),('OvalType','Filled'),('color','2'),('FillType','Solid')])
def test_graphical_electron_rejects_nonexact_native_circle_subset(attribute,value):
    text,_=plan_symbols(RAW,[{'key':'dot','kind':'electron','atom_id':'1100'}]);root=ET.fromstring(text)
    dot=root.find('page/fragment/graphic[@GraphicType="Oval"]');dot.set(attribute,value)
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))

def test_lone_pair_effective_color_cannot_change_through_root_inheritance():
    text,_=plan_symbols(RAW,[{'key':'pair','kind':'lone_pair','atom_id':'1100'}]);root=ET.fromstring(text)
    root.set('color','2');root.find('page/fragment/graphic[@SymbolType="LonePair"]').attrib.pop('color')
    with pytest.raises(ValueError):verify_symbols(text,ET.tostring(root,encoding='unicode'))
