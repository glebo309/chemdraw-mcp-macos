"""Regression for reaction overflow before per-participant native work."""
import statistics
import struct
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import bond_lengths, chemical_signature, bounds
from test_reaction import item, measured, ReactionBridge


def reaction(long=False):
    return [{'step_id':'hydrolysis',
        'reactants':[item('substrate','Long substrate caption' if long else 'Substrate','CCOC(=O)c1ccccc1'),
                     item('water','Water','O')],
        'products':[item('alcohol','Alcohol','CCO'),item('acid','Benzoic acid','O=C(O)c1ccccc1')],
        'conditions_above':'Enzyme',
        'conditions_below':'100 mM HEPES, 500 mM NaCl, pH 7.5, room temperature' if long else ''}]


def test_full_reaction_is_preflighted_on_real_paper_without_dropping_water():
    from chemdraw_macos.reaction_batch import plan_reaction_batch
    text,plan=plan_reaction_batch(reaction(True))
    root=ET.fromstring(text);page=root.find('page')
    assert len(page.findall('fragment'))==4 and 'O' in chemical_signature(text)
    assert page.get('WidthPages')==page.get('HeightPages')=='1'
    assert plan['paper']['name']!='A4 portrait'
    record=struct.unpack('>60h',bytes.fromhex(root.get('MacPrintInfo')))
    assert record[2:4]==(72,72) and record[25]==100
    assert record[11]-record[9]==plan['paper']['width_pt']
    assert record[10]-record[8]==plan['paper']['height_pt']
    assert record[17:23]==record[2:8]  # Native TPrint includes a second print-info record.
    assert record[12]==869  # ChemDraw 23 landscape device/orientation value.
    for f in page.findall('fragment'):
        if bond_lengths(f):assert statistics.median(bond_lengths(f))==pytest.approx(18,abs=.03)
    assert '100 mM HEPES, 500 mM NaCl, pH 7.5, room temperature' in ''.join(page.itertext())


def test_explicit_small_paper_fails_before_native_or_output_creation(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    from chemdraw_macos.harness import NeedsInput
    class NoNative:
        def __getattr__(self,key):pytest.fail('Native accessed before layout: '+key)
    with pytest.raises(NeedsInput) as error:
        run_reaction_batch(NoNative(),reaction(True),tmp_path/'out',paper='A4 portrait')
    assert error.value.code=='reaction_needs_space'
    assert error.value.detail['native_write_attempted'] is False
    assert 'mouse' in error.value.detail['next_action']
    assert not (tmp_path/'out').exists()


class BatchBridge(ReactionBridge):
    def create(self,text,visible=False):
        assert visible is False
        return super().create(text)
    def export(self,did,path,fmt,pixels=3200):
        from pathlib import Path
        if fmt=='svg':
            self.events.append(('export',did,fmt))
            Path(path).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"/>')
        else:super().export(did,path,fmt,pixels)


def test_batch_uses_two_whole_document_imports_and_one_svg_export(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    b=BatchBridge(tmp_path/'work');original=b.docs.copy()
    result=run_reaction_batch(b,reaction(),tmp_path/'out')
    assert result['status']=='completed' and b.docs==original
    assert len([e for e in b.events if e[0]=='create'])==2
    assert not any(e[0] in ('import','clean') for e in b.events)
    assert len([e for e in b.events if e[0]=='export' and e[2]=='svg'])==1
    assert all(result['checks'].values())
    assert set(result['artifacts'])=={'cdxml','svg','png','preview'}


def test_uncertain_native_write_is_never_retried_or_closed(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    from chemdraw_macos.batch import NativeUncertain
    b=BatchBridge(tmp_path/'work');calls=[]
    def broken(*args,**kwargs):
        calls.append(1)
        raise RuntimeError('lost native response')
    b.create=broken
    with pytest.raises(NativeUncertain):run_reaction_batch(b,reaction(),tmp_path/'out')
    assert calls==[1] and not any(e[0]=='close' for e in b.events)


def test_harness_routes_reactions_before_legacy_untitled_guard(tmp_path,monkeypatch):
    from chemdraw_macos import harness, reaction_batch
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'documents',lambda:pytest.fail('Legacy preflight used'))
    def capture(bridge,steps,out,**kwargs):
        assert steps[0]['reactants'][1]['smiles']=='O'
        return {'status':'batch-routed'}
    monkeypatch.setattr(reaction_batch,'run_reaction_batch',capture)
    result=harness.run_drawing(b,{'molecules':[{'format':'smiles','value':'CCO'},{'format':'smiles','value':'O'}],
        'products':[{'format':'smiles','value':'CC=O'}]},str(tmp_path/'out'),presentation='background')
    assert result['status']=='batch-routed'


def test_reaction_result_retains_resolved_input_provenance(tmp_path,monkeypatch):
    from chemdraw_macos import harness,reaction_batch
    monkeypatch.setattr(reaction_batch,'run_reaction_batch',lambda *a,**kw:{'status':'completed'})
    result=harness.run_drawing(object(),{'molecules':[{'format':'smiles','value':'CCO'}],
        'products':[{'format':'smiles','value':'CC=O'}]},str(tmp_path/'out'),presentation='background')
    assert [p['value'] for p in result['plan']['provenance']]==['CCO','CC=O']


def test_mismatched_native_physical_paper_cannot_pass(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    class WrongPaper(BatchBridge):
        def export(self,did,path,fmt,pixels=3200):
            super().export(did,path,fmt,pixels)
            if fmt=='cdxml' and str(path).endswith('figure.cdxml'):
                from pathlib import Path
                p=Path(path);root=ET.fromstring(p.read_text())
                record=list(struct.unpack('>60h',bytes.fromhex(root.get('MacPrintInfo'))));record[11]-=10
                root.set('MacPrintInfo',struct.pack('>60h',*record).hex());p.write_text(ET.tostring(root,encoding='unicode'))
    with pytest.raises(ValueError,match='physical paper'):
        run_reaction_batch(WrongPaper(tmp_path/'work'),reaction(),tmp_path/'out')


def test_mcp_guidance_prohibits_gui_retry_and_reaction_content_changes():
    from chemdraw_macos.server import INSTRUCTIONS,chemdraw_draw
    guidance=INSTRUCTIONS+chemdraw_draw.__doc__
    assert 'Do not use mouse' in guidance
    assert 'Do not remove participants' in guidance
    assert 'legacy separate export' not in chemdraw_draw.__doc__


def glycoside_reaction():
    return [{'step_id':'hydrolysis','reactants':[
        item('substrate','4-Nitrophenyl beta-D-glucopyranoside','O=[N+]([O-])c1ccc(O[C@@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)cc1'),
        item('water','Water','O')], 'products':[
        item('glucose','D-Glucose','OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O'),
        item('phenol','4-Nitrophenol','O=[N+]([O-])c1ccc(O)cc1')],
        'conditions_above':'Glycosidase',
        'conditions_below':'100 mM HEPES, 500 mM NaCl, pH 7.5, room temperature'}]


def test_original_long_glycoside_request_fits_without_input_changes():
    from chemdraw_macos.reaction_batch import plan_reaction_batch
    from chemdraw_macos.reaction_series import prepare_steps
    steps=glycoside_reaction();text,plan=plan_reaction_batch(steps)
    expected=prepare_steps(steps)[0]
    assert chemical_signature(text)==sorted(p['canonical_smiles'] for p in expected['reactants']+expected['products'])
    labels=[p['label'] for p in plan['steps'][0]['reactants']+plan['steps'][0]['products']]
    assert labels==[p['label'] for p in steps[0]['reactants']+steps[0]['products']]
    assert plan['paper']['name'] in ('A4 portrait','A4 landscape','A3 landscape')


def test_unverified_a2_paper_is_rejected_before_native(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    with pytest.raises(ValueError,match='Unsupported reaction paper'):
        run_reaction_batch(object(),reaction(),tmp_path/'out',paper='A2 landscape')


def test_batch_png_and_svg_preserve_physical_scale(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    from PIL import Image
    result=run_reaction_batch(BatchBridge(tmp_path/'work'),reaction(),tmp_path/'out')
    root=ET.parse(result['artifacts']['svg']).getroot()
    assert root.get('width')=='300pt'
    assert Image.open(result['artifacts']['png']).info['dpi']==pytest.approx((600,600),abs=.02)


def test_reaction_paper_cannot_be_silently_ignored_on_molecule_request(tmp_path):
    from chemdraw_macos.harness import run_drawing
    result=run_drawing(object(),{'molecules':[{'value':'CCO','format':'smiles'}],
        'reaction_paper':'A3 landscape'},str(tmp_path/'out'))
    assert result['status']=='rejected' and result['stage']=='input'
    assert 'reaction_paper requires products' in result['message']


def test_batch_rejects_native_collision_candidates(tmp_path,monkeypatch):
    from chemdraw_macos import reaction_batch,placement
    monkeypatch.setattr(placement,'collision_pairs',lambda *a,**kw:{('a:10','b:20')})
    b=BatchBridge(tmp_path/'work')
    with pytest.raises(ValueError,match='collision'):
        reaction_batch.run_reaction_batch(b,reaction(),tmp_path/'out')
    assert not any(e[0]=='export' and e[2]=='svg' for e in b.events)


def test_batch_verifies_native_style(tmp_path,monkeypatch):
    from chemdraw_macos import reaction_batch,styles
    def reject(*a,**kw):raise ValueError('Native custom style changed LineWidth')
    monkeypatch.setattr(styles,'verify_custom_style',reject)
    with pytest.raises(ValueError,match='LineWidth'):
        reaction_batch.run_reaction_batch(BatchBridge(tmp_path/'work'),reaction(),tmp_path/'out')


def test_reaction_charge_labels_request_native_bond_aware_alignment():
    from chemdraw_macos.reaction_batch import plan_reaction_batch
    text,_=plan_reaction_batch(glycoside_reaction())
    for node in ET.fromstring(text).findall('.//n[@Charge]'):
        assert node.find('t').get('LabelJustification')=='Best'
        assert node.find('t').get('LabelAlignment')=='Best'


def test_single_nitro_group_has_clear_charge_quadrant_without_graph_changes():
    from chemdraw_macos.reaction_batch import plan_reaction_batch
    text,_=plan_reaction_batch(glycoside_reaction());r=ET.fromstring(text)
    for f in r.findall('page/fragment'):
        nodes={n.get('id'):n for n in f.findall('n')}
        for n in f.findall('n[@Element="7"][@Charge="1"]'):
            neighbors=[nodes[b.get('E') if b.get('B')==n.get('id') else b.get('B')]
                       for b in f.findall('b') if n.get('id') in (b.get('B'),b.get('E'))]
            anchor=next(a for a in neighbors if a.get('Element','6')=='6')
            x,y=map(float,n.get('p').split());xx,yy=map(float,anchor.get('p').split())
            assert xx>x and yy==pytest.approx(y,abs=.001)


class ChargedBatchBridge(BatchBridge):
    def create(self,text,visible=False):
        from chemdraw_macos.symbols import symbol_primitives
        result=super().create(text,visible=visible);did=result['document']['document_id']
        root=ET.fromstring(self.docs[did])
        # The legacy fake measures only atoms/text. Native ChemDraw additionally
        # includes displayed charge circles in the molecular ink bounds.
        for f in root.findall('page/fragment'):
            b=bounds(f);boxes=[(b.left,b.top,b.right,b.bottom)]
            for g in f.findall('graphic'):
                boxes.extend((x-r,y-r,x+r,y+r) for x,y,r in symbol_primitives(g))
            f.set('BoundingBox',' '.join(map(str,(min(b[0] for b in boxes),min(b[1] for b in boxes),
                                                 max(b[2] for b in boxes),max(b[3] for b in boxes)))))
        self.docs[did]=ET.tostring(root,encoding='unicode')
        return result


def test_reaction_circles_existing_charges_and_checks_native_clearance(tmp_path):
    from chemdraw_macos.reaction_batch import run_reaction_batch
    from chemdraw_macos.symbols import verify_symbol_clearance
    steps=[{'step_id':'charged','reactants':[item('a','Acetate','CC(=O)[O-]')],
            'products':[item('b','Methylammonium','C[NH3+]')]}]
    b=ChargedBatchBridge(tmp_path/'work');original=b.docs.copy()
    result=run_reaction_batch(b,steps,tmp_path/'out')
    root=ET.parse(result['artifacts']['cdxml']).getroot()
    symbols=root.findall('page/fragment/graphic')
    assert {g.get('SymbolType') for g in symbols}=={'CirclePlus','CircleMinus'}
    assert len(symbols)==2
    assert result['checks']['native_charge_clearance']
    assert result['checks']['native_charge_ownership']
    assert result['presentation']['measurement_documents']==2
    verify_symbol_clearance(ET.tostring(root,encoding='unicode'),[g.get('id') for g in symbols],2)
    assert b.docs==original
    assert len([e for e in b.events if e[0]=='create'])==3


def test_circled_reaction_rejects_a_native_symbol_moved_onto_a_bond(tmp_path):
    from pathlib import Path
    from chemdraw_macos.reaction_batch import run_reaction_batch
    class CollidingCharge(ChargedBatchBridge):
        def export(self,did,path,fmt,pixels=3200):
            super().export(did,path,fmt,pixels)
            if fmt=='cdxml' and Path(path).name=='figure.cdxml':
                root=ET.parse(path).getroot()
                symbol=root.find('page/fragment/graphic')
                if symbol is not None:symbol.set('BoundingBox','0 0 10.5 0')
                Path(path).write_text(ET.tostring(root,encoding='unicode'))
    steps=[{'step_id':'charged','reactants':[item('a','Acetate','CC(=O)[O-]')],
            'products':[item('b','Acetic acid','CC(=O)O')]}]
    b=CollidingCharge(tmp_path/'work')
    with pytest.raises(ValueError,match='charge|symbol|collision'):
        run_reaction_batch(b,steps,tmp_path/'out')
    assert not any(e[0]=='export' and e[2]=='svg' for e in b.events)
