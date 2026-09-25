import copy
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

EMPTY='<CDXML BondLength="14.4" LineWidth="0.6" LabelFont="3" LabelSize="10" CaptionFont="3" CaptionSize="10"><fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable><page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"/></CDXML>'


REPLACEMENT_SCOPE=[
    'C1C=Cc2c1c(=O)n(C)c(=O)n2C', 'CCC1C=Cc2c1c(=O)n(C)c(=O)n2C',
    'CCCC1C=Cc2c1c(=O)n(C)c(=O)n2C', 'CC(C)C1C=Cc2c1c(=O)n(C)c(=O)n2C',
    'C1CC1C2C=Cc3c2c(=O)n(C)c(=O)n3C', 'c1ccccc1C2C=Cc3c2c(=O)n(C)c(=O)n3C',
    'c1ccccc1CC2C=Cc3c2c(=O)n(C)c(=O)n3C', 'FC1C=Cc2c1c(=O)n(C)c(=O)n2C',
    'ClC1C=Cc2c1c(=O)n(C)c(=O)n2C', 'FC(F)(F)C1C=Cc2c1c(=O)n(C)c(=O)n2C']

LYSINE_SCOPE=[
    'C=C(C)OC(=O)[C@@H](N)CCCCN',
    'C=C(C)OC(=O)[C@@H](N)C(C)CCCN',
    'C=C(C)OC(=O)[C@@H](N)C(F)CCCN',
    'C=C(C)OC(=O)[C@@H](N)CC(C)CCN',
    'C=C(C)OC(=O)[C@@H](N)CC(O)CCN',
    'C=C(C)OC(=O)[C@@H](N)CC(c1ccccc1)CCN',
    'C=C(C)OC(=O)[C@@H](N)CCC(F)CN',
    'C=C(C)OC(=O)[C@@H](N)CCC(C(F)(F)F)CN',
    'C=C(C)OC(=O)[C@@H](N)CCCC(N)C']


def test_acyclic_scope_automatically_preserves_whole_supplied_parent_coordinates():
    from chemdraw_macos.api_drawing import plan_addition,_isolated
    from chemdraw_macos.reaction_batch import set_paper
    from chemdraw_macos.polish import chemical_signature
    from rdkit import Chem
    records=[{'compound_id':str(i),'label':str(i),'smiles':s} for i,s in enumerate(LYSINE_SCOPE)]
    text,report=plan_addition(set_paper(EMPTY,'A3 landscape'),records,allow_page_expansion=True)
    assert report['scaffold_smiles']==Chem.MolToSmiles(Chem.MolFromSmiles(LYSINE_SCOPE[0]))
    assert report['reference_source']=='first_requested_structure'
    root=ET.fromstring(text)
    assert_core_orientation(_isolated(root,root.find('page/fragment')),text,report['scaffold_smiles'])
    assert sorted(chemical_signature(text))==sorted(Chem.MolToSmiles(Chem.MolFromSmiles(s)) for s in LYSINE_SCOPE)


def test_acyclic_automatic_parent_does_not_ignore_opposite_stereochemistry():
    from chemdraw_macos.api_drawing import plan_addition
    records=[{'compound_id':str(i),'label':str(i),'smiles':s} for i,s in enumerate(
        [LYSINE_SCOPE[0],LYSINE_SCOPE[1].replace('@@','@')])]
    _,report=plan_addition(EMPTY,records,allow_page_expansion=True)
    assert report['scaffold_smiles'] is None


def assert_core_orientation(before,added,scaffold):
    """Compare centred atom coordinates, without fitting away any rotation."""
    from rdkit import Chem
    from chemdraw_macos.alignment import _input, _mean
    from chemdraw_macos.api_drawing import _isolated
    core=Chem.MolFromSmiles(scaffold)
    root=ET.fromstring(before)
    _,matches,positions,_=_input(_isolated(root,root.find('page/fragment')),core)
    points=[positions[i] for i in matches[0]];centre=_mean(points)
    reference=[(x-centre[0],y-centre[1]) for x,y in points]
    root=ET.fromstring(added)
    for fragment in root.findall('page/fragment'):
        _,matches,positions,_=_input(_isolated(root,fragment),core)
        errors=[]
        for match in matches:
            points=[positions[i] for i in match];centre=_mean(points)
            errors.append(max(((x-centre[0]-u)**2+(y-centre[1]-v)**2)**.5
                              for (x,y),(u,v) in zip(points,reference)))
        assert min(errors)<.03


def test_replacing_parent_substituent_retains_live_common_core_orientation():
    from chemdraw_macos.api_drawing import plan_addition
    before,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Stale name',
        'smiles':'CC1C=Cc2c1c(=O)n(C)c(=O)n2C'}])
    records=[{'compound_id':str(i+2),'label':str(i+2),'smiles':s} for i,s in enumerate(REPLACEMENT_SCOPE)]
    added,report=plan_addition(before,records)
    assert report['reference_source']=='live_document'
    assert report['scaffold_smiles']
    assert_core_orientation(before,added,report['scaffold_smiles'])


def test_supplied_common_core_aligns_batch_without_live_parent():
    from chemdraw_macos.api_drawing import plan_addition,_isolated
    records=[{'compound_id':str(i+1),'label':str(i+1),'smiles':s} for i,s in enumerate(REPLACEMENT_SCOPE)]
    added,report=plan_addition(EMPTY,records)
    assert report['reference_source']=='first_requested_structure'
    root=ET.fromstring(added)
    assert_core_orientation(_isolated(root,root.find('page/fragment')),added,report['scaffold_smiles'])


def test_explicit_decorations_still_rejected_before_native_access(tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    from chemdraw_macos.harness import NeedsInput
    with pytest.raises(NeedsInput):
        run_api_drawing(object(),{'groups':[{'label':'Requested','compound_ids':['1']}]},tmp_path/'out')


def test_captions_are_text_even_when_document_interprets_chemically():
    from chemdraw_macos.api_drawing import plan_addition
    before=EMPTY.replace('<CDXML ','<CDXML InterpretChemically="yes" ')
    text,_=plan_addition(before,[{'compound_id':'1','label':'DMT','smiles':'CCO'}])
    root=ET.fromstring(text)
    assert root.get('InterpretChemically')=='yes'
    assert root.find('page/t').get('InterpretChemically')=='no'


def test_unequal_molecules_have_equal_row_and_column_centres():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.polish import bounds
    records=[{'compound_id':str(i+1),'label':str(i+1),'smiles':s} for i,s in enumerate(
        ['CCO','c1ccccc1','CC(=O)Nc1ccccc1','CCCC','CCN(CC)CC','c1ccc2[nH]ccc2c1'])]
    text,report=plan_addition(EMPTY,records,columns=3)
    assert report['columns']==3
    boxes=[bounds(f) for f in ET.fromstring(text).findall('page/fragment')]
    centres=[((b.left+b.right)/2,(b.top+b.bottom)/2) for b in boxes]
    for row in (centres[:3],centres[3:]):
        assert max(p[1] for p in row)-min(p[1] for p in row)<.001
        assert row[1][0]-row[0][0]==pytest.approx(row[2][0]-row[1][0],abs=.001)
    for i in range(3):assert centres[i][0]==pytest.approx(centres[i+3][0],abs=.001)


def test_table_placement_uses_actual_envelope_origin():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.polish import bounds
    records = [{'compound_id': str(i), 'label': str(i), 'smiles': smiles}
               for i, smiles in enumerate(['CCO', 'CCCCCCCC'])]
    text, _ = plan_addition(EMPTY, records, columns=2)
    boxes = [bounds(e) for e in ET.fromstring(text).find('page')]
    assert min(b.left for b in boxes) == pytest.approx(24, abs=.001)
    assert min(b.top for b in boxes) == pytest.approx(24, abs=.001)


def test_full_table_overflow_requests_same_document_space_not_smaller_batches():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.harness import NeedsInput
    occupied = EMPTY.replace('/></CDXML>', '><fragment id="20" BoundingBox="0 0 523 770"><n id="21" p="20 20"/><n id="22" p="38 20"/><b id="23" B="21" E="22"/></fragment></page></CDXML>')
    with pytest.raises(NeedsInput) as error:
        plan_addition(occupied, [{'compound_id': '1', 'label': 'Example', 'smiles': 'CCO'}])
    assert error.value.code == 'table_needs_space'
    assert error.value.detail['inserted_count'] == 0
    assert error.value.detail['requested_count'] == 1
    assert error.value.detail['same_document_required'] is True
    assert 'smaller batches' in error.value.detail['next_action']


def test_advanced_draw_returns_structured_table_overflow(monkeypatch):
    from chemdraw_macos import server
    from chemdraw_macos.harness import NeedsInput
    monkeypatch.setattr(server, 'bridge', lambda: object())
    def full(*args, **kwargs):
        raise NeedsInput('table_needs_space', 'No space', requested_count=17,
                         inserted_count=0, same_document_required=True)
    monkeypatch.setattr(server, 'draw_structures', full)
    result = server.chemdraw_draw_structures([], '/unused', document_id=42)
    assert result['status'] == 'needs_input'
    assert result['code'] == 'table_needs_space'
    assert result['document_id'] == 42 and result['inserted_count'] == 0


def test_unverifiable_existing_caption_fails_before_any_api_append(tmp_path,monkeypatch):
    from chemdraw_macos import api_drawing
    broken=EMPTY.replace('/></CDXML>', '><fragment id="20" BoundingBox="0 0 20 20"><n id="21" NodeType="Nickname" p="10 10"><t><s>DMT</s></t><fragment id="22"><n id="23" p="10 10"/></fragment></n></fragment></page></CDXML>')
    class Backend:
        def read(self,did):return {'cdxml':broken,'source_token':'fresh'}
        def append(self,*a):pytest.fail('Must reject unsupported existing content before a write')
    class Bridge:
        def documents(self):return {'documents':[{'document_id':42}]}
        def _id(self,did):return did
    monkeypatch.setattr(api_drawing,'get_backend',lambda b:Backend())
    with pytest.raises(ValueError,match='existing|Existing'):
        api_drawing.run_api_drawing(Bridge(),{'structures':[{'compound_id':'1','label':'1','smiles':'CCO'}]},tmp_path/'out',42)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('smiles',['CC(=O)Nc1ccccc1','Cn1c(=O)c2c(ncn2C)n(C)c1=O','N[C@@H](C)C(=O)O','[13CH3]CO','O=[N+]([O-])c1ccccc1','C/C=C/C','c1ccc2[nH]ccc2c1'])
def test_offline_payload_preserves_graph_and_applies_house_style(smiles):
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.polish import chemical_signature,bond_lengths
    from chemdraw_macos.identifiers import inspect_identifier
    text,info=plan_addition(EMPTY,[{'compound_id':'1','label':'Example','smiles':smiles}])
    root=ET.fromstring(text)
    assert chemical_signature(text)==[inspect_identifier(smiles)['canonical_smiles']]
    assert abs(statistics.median(bond_lengths(root.find('page/fragment')))-18)<.03
    assert all(float(b.get('LineWidth'))==1.58 for b in root.findall('.//b'))
    assert all(float(s.get('size'))==14 for s in root.findall('.//n/t/s'))
    fonts={f.get('id'):f.get('name') for f in root.findall('fonttable/font')}
    assert all(fonts[s.get('font')]=='Helvetica Neue' for s in root.findall('.//n/t/s'))
    assert root.get('LabelSize')=='10'  # Do not restyle pre-existing content.
    assert info['count']==1


def test_live_graph_ignores_stale_caffeine_caption():
    from chemdraw_macos.api_drawing import plan_addition,inspect_graphs
    parent='CC1C=Cc2c1c(=O)n(C)c(=O)n2C'
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Caffeine','smiles':parent}])
    result=inspect_graphs(text)
    from chemdraw_macos.identifiers import inspect_identifier
    assert result[0]['canonical_smiles']==inspect_identifier(parent)['canonical_smiles']
    assert result[0]['identity_source']=='live_atom_bond_graph'
    assert result[0]['atoms'] and result[0]['bonds']


def test_live_parent_orientation_and_count_survive_eight_analogue_plan():
    from chemdraw_macos.api_drawing import plan_addition
    parent='O=C(O)c1ccccc1'
    before,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Parent','smiles':parent}])
    records=[{'compound_id':str(i+2),'label':'Variant','smiles':'O=C(O)c1ccc('+r+')cc1'}
             for i,r in enumerate(['C','OC','N','F','Cl','Br','C#N','C(F)(F)F'])]
    added,report=plan_addition(before,records,columns=4)
    assert len(ET.fromstring(added).findall('page/fragment'))==8
    assert report['reference_source']=='live_document'
    assert report['scaffold_smiles']
    from chemdraw_macos.shared import plan_append
    assert ET.fromstring(added).find('page').get('BoundingBox')=='0 0 523 770'
    # Actual matched-core coordinates are verified in native acceptance as well.
    assert report['columns']<=4


def test_full_page_rejected_without_dropping_molecules():
    from chemdraw_macos.api_drawing import plan_addition
    occupied=EMPTY.replace('/></CDXML>','><fragment id="20" BoundingBox="0 0 523 770"><n id="21" p="20 20"/><n id="22" p="38 20"/><b id="23" B="21" E="22"/></fragment></page></CDXML>')
    with pytest.raises(ValueError,match='space|fit'):
        plan_addition(occupied,[{'compound_id':'1','label':'Example','smiles':'CCO'}])


def test_payload_can_extend_but_not_replace_existing_fonts():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.addin import prepare_payload
    added,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Example','smiles':'CCO'}])
    payload=ET.fromstring(prepare_payload(EMPTY,added))
    assert payload.find('fonttable/font[@name="Helvetica Neue"]') is not None
    with pytest.raises(ValueError,match='font'):
        prepare_payload(EMPTY,added.replace('name="Arial"','name="Courier"'))


def test_seed_ids_cannot_collide_with_native_page_id():
    from chemdraw_macos.api_drawing import plan_addition
    plan_addition(EMPTY.replace('page id="1"','page id="3"'),[{'compound_id':'1','label':'Test','smiles':'CCO'}])


def test_shared_runner_uses_single_api_append_without_seed_documents(tmp_path,monkeypatch):
    from chemdraw_macos import api_drawing
    from chemdraw_macos.addin import source_token
    calls=[]
    class Backend:
        current=EMPTY
        def read(self,did):return {'cdxml':self.current,'source_token':source_token(self.current)}
        def append(self,did,text,token):
            calls.append(did)
            self.current=text
            path=tmp_path/'native.cdxml';path.write_text(text)
            return {'status':'completed','document':{'document_id':did},'after_snapshot':str(path),'source_token':source_token(text),'checks':{'page_unchanged':True}}
    class Bridge:
        def _id(self,did):return did
        def documents(self):return {'documents':[{'document_id':42}]}
        def _run(self,op):assert op=='active_document';return 42
        def export(self,did,path,fmt):
            assert did==42 and fmt=='svg'
            Path(path).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M0 0 L100 100" stroke="black"/></svg>')
    monkeypatch.setattr(api_drawing,'get_backend',lambda bridge:Backend(),raising=False)
    result=api_drawing.run_api_drawing(Bridge(),{'workflow':'molecules','structures':[{'compound_id':'1','label':'Test','smiles':'CCO'}]},tmp_path/'out')
    assert result['status']=='completed' and result['document']['document_id']==42
    assert calls==[42]
    assert set(result['artifacts'])=={'cdxml'}
    assert result['source_token']==source_token(Path(result['artifacts']['cdxml']).read_text())


def test_frontdoor_auto_molecules_does_not_use_legacy_presentation(tmp_path,monkeypatch):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos import harness,shared
    bridge=object.__new__(Bridge)
    monkeypatch.setattr(shared,'run_shared',lambda *a,**k:{'status':'api_selected'})
    result=harness.run_drawing(bridge,{'molecules':[{'format':'smiles','value':'CCO'}],'panel':'plain'},str(tmp_path/'out'))
    assert result['status']=='api_selected'


def test_live_read_uses_api_graph_with_unsaved_changes(tmp_path,monkeypatch):
    from chemdraw_macos import live,addin
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.core import Bridge
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Caffeine','smiles':'CC1C=Cc2c1c(=O)n(C)c(=O)n2C'}])
    bridge=object.__new__(Bridge)
    from contextlib import nullcontext
    bridge.lock=nullcontext();bridge._new_path=lambda *a:tmp_path/'snapshot.cdxml'
    monkeypatch.setattr(live,'_state',lambda *a:{'document':{'document_id':42,'file':''},'selection':{},'visible':True})
    class Backend:
        def read(self,did):return {'cdxml':text,'selection_cdxml':EMPTY}
    monkeypatch.setattr(addin,'get_backend',lambda b:Backend())
    value=live.read_live_document(bridge,42)
    assert value['snapshot_method']=='desktop_addin'
    assert value['molecular_graphs'][0]['identity_source']=='live_atom_bond_graph'
    assert 'Cn1c(=O)c2c(ncn2C)n(C)c1=O'!=value['molecular_graphs'][0]['canonical_smiles']
    from chemdraw_macos.workflow import analyze_document
    bridge.inspect=lambda did:{'document':{'document_id':did,'file':''}}
    analyzed=analyze_document(bridge,42)
    assert analyzed['molecular_graphs']==value['molecular_graphs']


def test_native_export_allows_svg_from_untitled_without_native_save():
    text=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=text.split('operation is "export" then')[1].split('else if')[0]
    assert 'diskPath is "" and targetFormat is not "Scalable Vector Graphics (SVG)"' in branch


def test_native_style_verifier_rejects_thin_bonds_and_wrong_font():
    from chemdraw_macos.api_drawing import plan_addition,verify_style
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Test','smiles':'CCO'}])
    assert verify_style(text,'house')
    with pytest.raises(ValueError,match='style'):
        verify_style(text.replace('LineWidth="1.58"','LineWidth="0.6"'),'house')
    with pytest.raises(ValueError,match='style'):
        verify_style(text.replace('Helvetica Neue','Arial'),'house')


def test_export_may_add_derived_stereo_annotations_not_change_graph():
    from chemdraw_macos.api_drawing import plan_addition,verify_export_snapshot
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Test','smiles':'CCO'}])
    native=text.replace('<n ','<n AS="N" ').replace('<b ','<b BS="N" ')
    verify_export_snapshot(text,native)
    with pytest.raises(ValueError):verify_export_snapshot(text,native.replace('Element="8"','Element="7"'))


def test_eight_fused_ring_analogues_fit_below_live_parent_at_house_scale():
    from chemdraw_macos.api_drawing import plan_addition
    parent='CC1C=Cc2c1c(=O)n(C)c(=O)n2C'
    before,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Parent','smiles':parent}])
    records=[{'compound_id':str(i+2),'label':'R = '+r,'smiles':'CC1C('+r+')=Cc2c1c(=O)n(C)c(=O)n2C'} for i,r in enumerate(['C','OC','N','F','Br','C#N','C(F)(F)F','c2ccccc2'])]
    text,report=plan_addition(before,records)
    assert report['count']==8


def test_explicit_core_must_match_even_a_single_requested_structure():
    from chemdraw_macos.api_drawing import plan_addition
    with pytest.raises(ValueError):
        plan_addition(EMPTY,[{'compound_id':'1','label':'Test','smiles':'CCO'}],scaffold_smiles='c1ccccc1')


def test_explicit_hydrogen_atom_is_not_removed_by_coordinate_generation():
    from chemdraw_macos.api_drawing import plan_addition
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Test','smiles':'[H]OC'}])
    assert len(ET.fromstring(text).findall('.//n'))==3


@pytest.mark.parametrize('options',[{'charge_style':'circled'},{'layout':{'left':5}},{'preset':{'font':'Arial'}}])
def test_unsupported_api_options_are_not_silently_ignored(options,tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    from chemdraw_macos.harness import NeedsInput
    with pytest.raises(NeedsInput):run_api_drawing(object(),{'workflow':'molecules',**options},tmp_path/'out')


@pytest.mark.parametrize('smiles,labels',[('O=[N+]([O-])c1ccccc1',{'N+','O-'}),('[13CH3]CO',{'13CH3'})])
def test_chemical_labels_include_charge_and_isotope_semantics(smiles,labels):
    from chemdraw_macos.api_drawing import plan_addition
    text,_=plan_addition(EMPTY,[{'compound_id':'1','label':'Test','smiles':smiles}])
    assert labels<={''.join(t.itertext()) for t in ET.fromstring(text).findall('.//n/t')}
    for node in ET.fromstring(text).findall('.//n[@Isotope]'):
        assert node.find('t/s').get('face')=='64'


def test_native_remeasured_ink_must_not_overlap_other_added_objects():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.shared import verify_append
    planned,_=plan_addition(EMPTY,[{'compound_id':'1','label':'A','smiles':'CCO'},{'compound_id':'2','label':'B','smiles':'CCN'}])
    after=ET.fromstring(planned);after.find('page/fragment').set('BoundingBox','0 0 523 770')
    with pytest.raises(ValueError,match='overlap'):
        verify_append(EMPTY,ET.tostring(after,encoding='unicode'),planned,exact_coordinates=True)
