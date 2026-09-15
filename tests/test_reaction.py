import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.reaction import compose_reaction, build_reaction, arrange_reaction, verify_reaction
from chemdraw_macos.batch import NativeUncertain
from chemdraw_macos.polish import chemical_signature, bounds
from test_draw import ETHANOL


def item(key, label='Ethanol', smiles='CCO'):
    return {'compound_id':key,'label':label,'smiles':smiles}


def measured(text):
    """Fake native bounds only; actual renderer validation belongs to live tests."""
    root=ET.fromstring(text)
    for t in root.findall('.//t'):
        x,y=map(float,t.get('p').split());size=float(t.find('s').get('size','10'))
        width=len(''.join(t.itertext()).strip())*size*.55
        t.set('BoundingBox',f'{x-width/2} {y-size*.8} {x+width/2} {y+size*.2}')
    for f in root.findall('page/fragment'):
        points=[tuple(map(float,n.get('p').split())) for n in f.findall('n')]
        boxes=[bounds(t) for t in f.findall('.//t')]
        f.set('BoundingBox',' '.join(map(str,[min([x for x,y in points]+[b.left for b in boxes]),
            min([y for x,y in points]+[b.top for b in boxes]),max([x for x,y in points]+[b.right for b in boxes]),
            max([y for x,y in points]+[b.bottom for b in boxes])])) )
    return ET.tostring(root,encoding='unicode')


def test_composition_has_explicit_roles_labels_conditions_and_unique_ids():
    reactants=[item('r1'),item('r2','Second reagent')];products=[item('p1','Product')]
    text,recipe=compose_reaction([ETHANOL]*3,reactants,products,conditions_above='Catalyst',conditions_below='25 °C')
    root=ET.fromstring(text);page=root.find('page')
    assert chemical_signature(text)==['CCO']*3
    ids=[e.get('id') for e in page.iter() if e.get('id')]
    assert len(ids)==len(set(ids))
    assert len(recipe['caption_map'])==3 and len(recipe['plus_ids'])==1
    assert [r['role'] for r in recipe['roles']]==['reactant','reactant','product']
    assert [r['compound_id'] for r in recipe['roles']]==['r1','r2','p1']
    step=page.find('scheme/step')
    assert step.get('ReactionStepReactants').split()==[r['fragment_id'] for r in recipe['roles'][:2]]
    assert step.get('ReactionStepProducts')==recipe['roles'][2]['fragment_id']
    assert len(recipe['condition_map'][recipe['arrow_id']])==2
    assert page.get('BoundingBox')=='0 0 540 720'


@pytest.mark.parametrize('reactants,products,condition',[
    ([],[item('p')],''),([item('r')]*4,[item('p')],''),
    ([item('same')],[item('SAME')],''),([item('r')],[item('p')],'bad\ncondition'),
    ([item('r')],[item('p')],True),([item('r')],[item('p')],'x'*121),
])
def test_invalid_reaction_input_fails_before_native(tmp_path,reactants,products,condition):
    class NoNative:
        def __getattr__(self,name):raise AssertionError(name)
    with pytest.raises(ValueError):
        build_reaction(NoNative(),reactants,products,str(tmp_path/'out'),conditions_above=condition)
    assert not (tmp_path/'out').exists()


def test_unknown_native_identity_and_page_overflow_rejected():
    with pytest.raises(ValueError,match='identity'):
        compose_reaction([ETHANOL]*2,[item('r')],[item('p',smiles='CCN')])
    with pytest.raises(ValueError,match='fit|overflow|page'):
        compose_reaction([ETHANOL]*2,[item('r','x'*110)],[item('p','y'*110)])


def test_native_measured_row_has_centred_conditions_and_caption_baseline():
    text,recipe=compose_reaction([ETHANOL]*2,[item('r')],[item('p','Product')],conditions_above='Catalyst',conditions_below='Solvent')
    arranged,plan=arrange_reaction(measured(text),recipe)
    final=measured(arranged)
    report=verify_reaction(arranged,final,plan)
    assert all(report['checks'].values())
    assert report['roles'][0]['compound_id']=='r'
    page=ET.fromstring(final).find('page');arrow=page.find('arrow')
    center=(float(arrow.get('Head3D').split()[0])+float(arrow.get('Tail3D').split()[0]))/2
    for tid in recipe['condition_map'][recipe['arrow_id']]:
        assert bounds(page.find(f't[@id="{tid}"]')).center[0]==pytest.approx(center,abs=.01)
    baseline=[float(page.find(f't[@id="{tid}"]').get('p').split()[1]) for tid in recipe['caption_map'].values()]
    assert max(baseline)-min(baseline)<.01


@pytest.mark.parametrize('corruption',['roles','label','position','extra'])
def test_native_corruption_is_not_certified(corruption):
    text,recipe=compose_reaction([ETHANOL]*2,[item('r')],[item('p','Product')])
    arranged,plan=arrange_reaction(measured(text),recipe)
    root=ET.fromstring(measured(arranged));page=root.find('page')
    if corruption=='roles':page.find('scheme/step').set('ReactionStepProducts',recipe['roles'][0]['fragment_id'])
    elif corruption=='label':page.find('t/s').text='Wrong'
    elif corruption=='position':page.find('fragment/n').set('p','0 0')
    else:ET.SubElement(page,'t',{'id':'9999','p':'400 500','BoundingBox':'390 490 410 510'})
    with pytest.raises(ValueError):verify_reaction(arranged,ET.tostring(root,encoding='unicode'),plan)


def test_missing_scaffold_rejected_before_native(tmp_path):
    class NoNative:
        def __getattr__(self,name):raise AssertionError(name)
    with pytest.raises(ValueError,match='scaffold'):
        build_reaction(NoNative(),[item('r')],[item('p')],str(tmp_path/'out'),scaffold_smiles='c1ccccc1')


class ReactionBridge:
    def __init__(self,workspace):
        self.workspace=workspace;self.counter=10;self.docs={1:measured(ETHANOL)};self.events=[]
    def documents(self):return {'documents':[{'document_id':d,'modified':False} for d in sorted(self.docs)]}
    def _new_path(self,suffix,category='scratch'):
        self.counter+=1;p=self.workspace/category/f'{self.counter}{suffix}';p.parent.mkdir(parents=True,exist_ok=True);return p
    def create(self,text):
        self.counter+=1;self.docs[self.counter]=measured(text);self.events.append(('create',self.counter))
        return {'document':{'document_id':self.counter}}
    def import_file(self,path):self.events.append(('import',path));return self.create(ETHANOL)
    def clean(self,did):self.events.append(('clean',did))
    def export(self,did,path,fmt,pixels=3200):
        self.events.append(('export',did,fmt));Path(path).write_text(self.docs[did] if fmt=='cdxml' else 'preview')
    def close(self,did):
        assert did!=1;self.events.append(('close',did));del self.docs[did]


def test_build_outputs_native_review_and_preserves_originals(tmp_path):
    b=ReactionBridge(tmp_path/'work');original=b.docs[1]
    result=build_reaction(b,[item('r')],[item('p','Product')],str(tmp_path/'out'),conditions_above='Catalyst')
    assert b.docs[1]==original and set(b.docs)=={1,result['document']['document_id']}
    assert all(result['audit']['checks'].values())
    assert result['audit']['visual_review']=='required'
    for name in ('figure.cdxml','figure.svg','figure.png','review.html','request.json','audit.json'):
        assert (tmp_path/'out'/name).is_file()
    assert len([e for e in b.events if e[0]=='clean'])==2


@pytest.mark.parametrize('operation',['import_file','clean','create','export','close'])
def test_uncertain_native_call_not_retried_or_closed(tmp_path,operation):
    b=ReactionBridge(tmp_path/'work');original=getattr(b,operation);triggered=[]
    def uncertain(*args,**kwargs):
        triggered.append(args)
        raise RuntimeError('uncertain-operation')
    setattr(b,operation,uncertain)
    with pytest.raises(NativeUncertain):build_reaction(b,[item('r')],[item('p')],str(tmp_path/'out'))
    assert len(triggered)==1
    assert not any(e[0]=='close' for e in b.events)
    if (tmp_path/'out'/'audit.json').exists():
        assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='uncertain'


def test_uncertain_final_export_stops_without_closing_any_more_documents(tmp_path):
    b=ReactionBridge(tmp_path/'work');original=b.export;events_at_failure=[]
    def fail_final(did,path,fmt,pixels=3200):
        if Path(path).name=='figure.png':
            events_at_failure.extend(b.events)
            raise RuntimeError('final export timeout')
        return original(did,path,fmt,pixels)
    b.export=fail_final
    with pytest.raises(NativeUncertain,match='final export timeout'):
        build_reaction(b,[item('r')],[item('p')],str(tmp_path/'out'))
    assert b.events==events_at_failure
    assert len(b.docs)==3  # source, owned composition and uncertain final copy
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='uncertain'


def test_changed_preexisting_unsaved_content_is_not_certified(tmp_path):
    b=ReactionBridge(tmp_path/'work');original=b.export
    def mutate(did,path,fmt,pixels=3200):
        result=original(did,path,fmt,pixels)
        if Path(path).name=='figure.png':b.docs[1]=b.docs[1].replace('OH','Changed')
        return result
    b.export=mutate
    with pytest.raises(ValueError,match='Pre-existing document content'):
        build_reaction(b,[item('r')],[item('p')],str(tmp_path/'out'))
    assert set(b.docs)=={1}
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='failed'


def test_native_ink_overflow_and_displaced_caption_fail_verification():
    text,recipe=compose_reaction([ETHANOL]*2,[item('r')],[item('p','Product')])
    arranged,plan=arrange_reaction(measured(text),recipe)
    native=ET.fromstring(measured(arranged));caption=native.find('page/t')
    caption.set('BoundingBox','0 0 999 999')
    with pytest.raises(ValueError,match='page'):
        verify_reaction(arranged,ET.tostring(native,encoding='unicode'),plan)


def test_reaction_uses_validated_custom_style(tmp_path,monkeypatch):
    from chemdraw_macos.core import PRESETS
    spec={**PRESETS['house'],'font':'Arial','BondLength':'20','LineWidth':'1.8'}
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts',lambda:{'Arial'})
    b=ReactionBridge(tmp_path/'work')
    result=build_reaction(b,[item('r')],[item('p')],str(tmp_path/'out'),preset=spec)
    assert result['audit']['verification']['median_bond_lengths_pt']==pytest.approx([20,20],abs=.03)
    root=ET.fromstring((tmp_path/'out'/'figure.cdxml').read_text())
    assert float(root.get('LineWidth'))==1.8


def test_composition_retains_custom_caption_face_and_font():
    from chemdraw_macos.core import PRESETS
    spec={**PRESETS['house'],'font':'Arial','CaptionFontName':'Helvetica','CaptionFace':'1'}
    text,recipe=compose_reaction([ETHANOL]*2,[item('r')],[item('p')],conditions_above='Catalyst',preset=spec)
    root=ET.fromstring(text);fonts={f.get('id'):f.get('name') for f in root.findall('fonttable/font')}
    for t in root.findall('page/t'):
        assert fonts[t.find('s').get('font')]=='Helvetica'
        assert t.find('s').get('face')=='1'


def test_missing_custom_font_rejected_without_native_or_output(tmp_path,monkeypatch):
    from chemdraw_macos.core import PRESETS
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts',lambda:set())
    class NoNative:
        def __getattr__(self,name):raise AssertionError(name)
    with pytest.raises(ValueError,match='font'):
        build_reaction(NoNative(),[item('r')],[item('p')],str(tmp_path/'out'),preset={**PRESETS['house'],'font':'Missing'})
    assert not (tmp_path/'out').exists()
