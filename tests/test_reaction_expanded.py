import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chemdraw_macos.reaction_series import prepare_steps, compose_series, arrange_series, verify_series, build_reaction_series
from chemdraw_macos.draw import prepare_structures
from chemdraw_macos.batch import NativeUncertain
from test_draw import ETHANOL
from test_reaction import item, measured, ReactionBridge


def single(element,label,charge=0,hydrogens=0):
    root=ET.fromstring(ETHANOL);page=root.find('page')
    for c in list(page):page.remove(c)
    f=ET.SubElement(page,'fragment',{'id':'1'})
    n=ET.SubElement(f,'n',{'id':'2','p':'50 50','Element':str(element),'NumHydrogens':str(hydrogens)})
    if charge:n.set('Charge',str(charge))
    t=ET.SubElement(n,'t',{'p':'50 50'});ET.SubElement(t,'s',{'font':'3','size':'10','face':'96'}).text=label
    return measured(ET.tostring(root,encoding='unicode'))


NATIVE={'CCO':measured(ETHANOL),'O':single(8,'OH2',hydrogens=2),
        '[Cl-]':single(17,'Cl-',-1),'[Br-]':single(35,'Br-',-1),'[Na+]':single(11,'Na+',1)}


def steps():
    return [{'step_id':'first','reactants':[item('ethanol'),item('water','Water','O')],
             'products':[item('product','Product')],'conditions_above':'Step 1'},
            {'step_id':'second','reactants':[item('product','Product')],
             'products':[{**item('salt','NaCl','[Na+].[Cl-]'),'coefficient':2}],'conditions_below':'Explicit condition'}]


def test_water_halides_and_salt_components_have_checked_mol_seeds():
    prepared=prepare_steps(steps())
    salt=prepared[1]['products'][0]
    assert sorted(c['canonical_smiles'] for c in salt['components'])==['[Cl-]','[Na+]']
    assert salt['coefficient_text']=='2'
    assert all(c['molblock'].endswith('M  END\n') for s in prepared for side in ('reactants','products') for p in s[side] for c in p['components'])
    assert prepared[0]['reactants'][1]['canonical_smiles']=='O'
    with pytest.raises(ValueError):prepare_structures([item('water','Water','O')])
    with pytest.raises(ValueError):prepare_structures([item('salt','Salt','[Na+].[Cl-]')])


@pytest.mark.parametrize('value',[0,-1,True,float('nan'),'2',10000])
def test_invalid_coefficients_fail_before_native(tmp_path,value):
    ss=steps();ss[0]['reactants'][0]['coefficient']=value
    class NoNative:
        def __getattr__(self,name):raise AssertionError(name)
    with pytest.raises(ValueError):build_reaction_series(NoNative(),ss,str(tmp_path/'out'))
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('smiles',['[Fe+2]','[He]','C.O','[Na+].CCO','[CH3]','[Na+].[Na+]'])
def test_unsupported_single_atoms_radicals_and_nonsalt_mixtures_rejected(smiles):
    ss=steps();ss[0]['reactants'][0]=item('bad','Unsupported',smiles)
    with pytest.raises(ValueError):prepare_steps(ss)


def test_repeated_identifier_must_keep_explicit_identity_and_label():
    ss=steps();ss[1]['reactants'][0]['smiles']='CCN'
    with pytest.raises(ValueError,match='identity|identifier'):prepare_steps(ss)


def test_combined_multistep_roles_coefficients_salt_ownership_and_measured_layout():
    ss=prepare_steps(steps());text,recipe=compose_series(NATIVE,ss)
    root=ET.fromstring(text)
    assert len(root.findall('page/scheme/step'))==2
    salt=recipe['steps'][1]['products'][0]
    assert len(salt['fragment_ids'])==2 and salt['coefficient_id'] is not None
    arranged,plan=arrange_series(measured(text),recipe)
    report=verify_series(arranged,measured(arranged),plan)
    assert all(report['checks'].values())
    assert report['chemical_balance_certified'] is False
    assert len(ET.fromstring(arranged).findall('page'))==1
    assert plan['steps'][1]['top_pt']>plan['steps'][0]['bottom_pt']


@pytest.mark.parametrize('corrupt',['coefficient','role','caption','position','overflow'])
def test_native_changes_rejected(corrupt):
    text,recipe=compose_series(NATIVE,prepare_steps(steps()));arranged,plan=arrange_series(measured(text),recipe)
    root=ET.fromstring(measured(arranged));page=root.find('page');salt=plan['steps'][1]['products'][0]
    if corrupt=='coefficient':page.find(f't[@id="{salt["coefficient_id"]}"]/s').text='3'
    elif corrupt=='role':page.find('scheme/step').set('ReactionStepProducts',salt['fragment_ids'][0])
    elif corrupt=='caption':page.find(f't[@id="{salt["caption_id"]}"]/s').text='Other'
    elif corrupt=='position':page.find('fragment/n').set('p','0 0')
    else:page.find(f't[@id="{salt["caption_id"]}"]').set('BoundingBox','0 0 999 999')
    with pytest.raises(ValueError):verify_series(arranged,ET.tostring(root,encoding='unicode'),plan)


def test_page_overflow_fails_without_shrinking():
    ss=steps();ss[0]['reactants'][0]['label']='A'*120
    with pytest.raises(ValueError,match='page|fit|overflow'):compose_series(NATIVE,prepare_steps(ss))


class SeriesBridge(ReactionBridge):
    def import_file(self,path):
        from rdkit import Chem
        mol=Chem.MolFromMolBlock(Path(path).read_text(),removeHs=False)
        smiles=Chem.MolToSmiles(mol,isomericSmiles=True)
        self.events.append(('import',path));return self.create(NATIVE[smiles])


def test_multistep_build_exports_one_native_figure_and_preserves_originals(tmp_path):
    b=SeriesBridge(tmp_path/'work');original=b.docs[1]
    result=build_reaction_series(b,steps(),str(tmp_path/'out'))
    assert result['audit']['status']=='checks_passed'
    assert b.docs[1]==original and set(b.docs)=={1,result['document']['document_id']}
    assert len(ET.fromstring((tmp_path/'out/figure.cdxml').read_text()).findall('page/scheme/step'))==2
    assert (tmp_path/'out/review.html').is_file()


def test_native_uncertainty_stops_without_any_further_close(tmp_path):
    b=SeriesBridge(tmp_path/'work');export=b.export;at_failure=[]
    def fail(did,path,fmt,pixels=3200):
        if Path(path).name=='figure.png':at_failure.extend(b.events);raise RuntimeError('timeout')
        return export(did,path,fmt,pixels)
    b.export=fail
    with pytest.raises(NativeUncertain):build_reaction_series(b,steps(),str(tmp_path/'out'))
    assert b.events==at_failure
    assert json.loads((tmp_path/'out/audit.json').read_text())['status']=='uncertain'

def test_alkali_ions_use_explicit_checked_cdxml_seed_not_abnormal_valence_override():
    ss=prepare_steps(steps());parts=ss[1]['products'][0]['components']
    sodium=next(c for c in parts if c['canonical_smiles']=='[Na+]')
    assert sodium['native_seed_format']=='cdxml'
    assert 'AbnormalValence' not in sodium['seed_cdxml']
    assert ET.fromstring(sodium['seed_cdxml']).find('page/fragment/n').get('Charge')=='1'
    assert next(c for c in parts if c['canonical_smiles']=='[Cl-]')['native_seed_format']=='mol'

def test_old_reaction_entry_accepts_explicit_water_and_coefficients(tmp_path):
    from chemdraw_macos.reaction import build_reaction
    b=SeriesBridge(tmp_path/'work')
    result=build_reaction(b,[item('water','Water','O')],[{**item('ethanol'),'coefficient':.5}],str(tmp_path/'out'))
    assert result['audit']['status']=='checks_passed'
    assert result['audit']['verification']['steps'][0]['products'][0]['coefficient_text']=='0.5'

def test_layout_fields_are_explicit_and_measured():
    layout={'gap':20,'label_gap':12,'condition_gap':14,'row_gap':40,'margin':42}
    text,recipe=compose_series(NATIVE,prepare_steps(steps()),layout=layout)
    arranged,plan=arrange_series(measured(text),recipe)
    assert plan['layout_options']==layout and plan['region'][0]==42
    assert plan['steps'][1]['top_pt']-plan['steps'][0]['bottom_pt']==pytest.approx(40)
    assert all(verify_series(arranged,measured(arranged),plan)['checks'].values())


def test_explicit_hydroxide_ion_and_sodium_hydroxide_salt():
    ss=[{'step_id':'neutralization','reactants':[item('base','Sodium hydroxide','[Na+].[OH-]')],
         'products':[item('ion','Hydroxide','[OH-]')]}]
    result=prepare_steps(ss)
    hydroxide=next(c for c in result[0]['reactants'][0]['components'] if c['canonical_smiles']=='[OH-]')
    assert hydroxide['native_seed_format']=='mol'
    from rdkit import Chem
    atom=Chem.MolFromMolBlock(hydroxide['molblock'],removeHs=False).GetAtomWithIdx(0)
    assert atom.GetFormalCharge()==-1 and atom.GetTotalNumHs()==1


def test_native_asymmetric_arrow_ink_keeps_condition_inside_top_margin():
    # ChemDraw's saved arrow ink is not symmetric around its Tail3D y.
    ss=[{'step_id':'small','reactants':[item('a','Water','O')],
         'products':[item('b','Water','O')],'conditions_above':'SN2'}]
    text,recipe=compose_series(NATIVE,prepare_steps(ss))
    root=ET.fromstring(measured(text));arrow=root.find('page/arrow')
    from chemdraw_macos.polish import numbers,encode
    x,y,z=numbers(arrow.get('Tail3D'),3);h=numbers(arrow.get('Head3D'),3)
    arrow.set('BoundingBox',encode((x,y-5.5,h[0],y+4.5)))
    arranged,plan=arrange_series(ET.tostring(root,encoding='unicode'),recipe)
    condition=ET.fromstring(arranged).find(f'page/t[@id="{next(iter(plan["steps"][0]["condition_sides"]))}"]')
    assert numbers(condition.get('BoundingBox'),4)[1]>=plan['region'][1]-.03


def test_default_row_gap_separates_native_arrow_caption_detection_regions():
    _,recipe=compose_series(NATIVE,prepare_steps(steps()))
    assert recipe['layout_options']['row_gap']==120
    assert recipe['steps'][1]['top_pt']-recipe['steps'][0]['bottom_pt']==pytest.approx(120)


@pytest.mark.parametrize('custom',[False,True])
def test_coefficient_preserves_atom_font_size_after_document_style(custom):
    from chemdraw_macos.core import preset_settings
    preset=preset_settings('house') if custom else 'house'
    if custom:preset.update(font='Arial',CaptionFontName='Times New Roman',LabelSize='14.03')
    text,recipe=compose_series(NATIVE,prepare_steps(steps()),preset)
    root=ET.fromstring(text);spec=preset_settings(preset)
    fonts={f.get('id'):f.get('name') for f in root.find('fonttable')}
    for step in recipe['steps']:
        for participant in step['reactants']+step['products']:
            if participant['coefficient_id']:
                for run in root.find(f'page/t[@id="{participant["coefficient_id"]}"]').findall('s'):
                    assert float(run.get('size'))==float(spec['LabelSize'])
                    assert fonts[run.get('font')]==spec['font']


@pytest.mark.parametrize('corrupt',['size','font'])
def test_native_coefficient_wrong_typography_rejected(corrupt):
    text,recipe=compose_series(NATIVE,prepare_steps(steps()));arranged,plan=arrange_series(measured(text),recipe)
    root=ET.fromstring(measured(arranged));cid=plan['steps'][1]['products'][0]['coefficient_id']
    run=root.find(f'page/t[@id="{cid}"]/s')
    if corrupt=='size':run.set('size','8.25')
    else:
        ET.SubElement(root.find('fonttable'),'font',{'id':'9999','name':'Courier','charset':'Unicode'})
        run.set('font','9999')
    with pytest.raises(ValueError,match='coefficient.*(font|size|typography)'):
        verify_series(arranged,ET.tostring(root,encoding='unicode'),plan)


def test_native_coefficient_size_allows_documented_twentieth_point_quantization():
    from chemdraw_macos.core import preset_settings
    preset=preset_settings('house');preset['LabelSize']='14.03'
    text,recipe=compose_series(NATIVE,prepare_steps(steps()),preset);arranged,plan=arrange_series(measured(text),recipe)
    root=ET.fromstring(measured(arranged));cid=plan['steps'][1]['products'][0]['coefficient_id']
    run=root.find(f'page/t[@id="{cid}"]/s');run.set('size','14')
    assert verify_series(arranged,ET.tostring(root,encoding='unicode'),plan)['checks']['coefficient_font_and_size']
    run.set('size','14.09')
    with pytest.raises(ValueError,match='coefficient.*size'):
        verify_series(arranged,ET.tostring(root,encoding='unicode'),plan)
