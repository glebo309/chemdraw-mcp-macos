"""Explicit reaction participants and stacked native reaction steps.

Reaction-specific input support does not alter the public draw subset. All
chemistry is supplied; coefficients and ordered steps are not balance proofs.
"""
from contextlib import nullcontext
import copy
from decimal import Decimal
import math
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET

from .batch import _native, NativeUncertain, _document_content, _verify
from .core import preset_settings, style_cdxml
from .draw import prepare_structures, _validate_native_labels
from .geometry import Box, find_overlaps
from .polish import supported_root, chemical_signature, normalize_cdxml, bounds, transform, numbers, encode, bond_lengths
from .reaction import _text
from .workflow import remap_ids, _write_json, content_fingerprint


def _coefficient(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=999:
        raise ValueError('Coefficient must be a finite positive number up to 999')
    d=Decimal(str(value)).normalize()
    if d.as_tuple().exponent < -3:raise ValueError('Coefficient supports at most three decimal places')
    return format(d,'f')


def _condition(value):
    if not isinstance(value,str) or len(value)>120 or any(ord(c)<32 or ord(c)==127 for c in value) or (value and not value.strip()):
        raise ValueError('Conditions require single-line text of at most 120 characters')
    return value


def _alkali_seed(element, symbol):
    # Native-tested isolated-ion schema from test_scope_live.SALT. A MOL
    # import on ChemDraw 23 marks these ions AbnormalValence even after cleanup.
    root=ET.Element('CDXML',{'LabelFont':'3','LabelSize':'10'})
    fonts=ET.SubElement(root,'fonttable');ET.SubElement(fonts,'font',{'id':'3','name':'Arial','charset':'Unicode'})
    page=ET.SubElement(root,'page',{'id':'100','BoundingBox':'0 0 540 720'})
    f=ET.SubElement(page,'fragment',{'id':'1'})
    n=ET.SubElement(f,'n',{'id':'2','p':'50 60','Element':str(element),'Charge':'1','NumHydrogens':'0'})
    t=ET.SubElement(n,'t',{'p':'46 64'})
    ET.SubElement(t,'s',{'font':'3','size':'10','face':'96'}).text=symbol
    ET.SubElement(t,'s',{'font':'3','size':'10','face':'64'}).text='+'
    text=ET.tostring(root,encoding='unicode')
    if chemical_signature(text)!=['['+symbol+'+]']:raise ValueError('Explicit alkali CDXML seed identity failed')
    return text


def prepare_steps(steps):
    from rdkit import Chem
    from .identifiers import inspect_identifier
    if not isinstance(steps,list) or not 1<=len(steps)<=3:raise ValueError('Supply 1 through 3 explicit reaction steps')
    result=[];step_ids=set();identities={}
    for step in steps:
        if not isinstance(step,dict) or set(step)-{'step_id','reactants','products','conditions_above','conditions_below'}:
            raise ValueError('Unknown reaction step fields')
        sid=step.get('step_id')
        if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,31}',sid) or sid.lower() in step_ids:
            raise ValueError('Step IDs must be unique safe identifiers')
        step_ids.add(sid.lower());prepared={'step_id':sid,'conditions_above':_condition(step.get('conditions_above','')),'conditions_below':_condition(step.get('conditions_below',''))};seen=set()
        for side in ('reactants','products'):
            items=step.get(side)
            if not isinstance(items,list) or not 1<=len(items)<=3:raise ValueError('Each step side requires 1 through 3 explicit participants')
            prepared[side]=[]
            for item in items:
                if not isinstance(item,dict) or set(item)-{'compound_id','label','smiles','coefficient'} or not {'compound_id','label','smiles'}<=set(item):raise ValueError('Participant requires compound_id, label, smiles and optional coefficient')
                key=item['compound_id'];label=item['label']
                if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,31}',key) or key.lower() in seen:raise ValueError('Compound IDs must be unique within each step')
                seen.add(key.lower())
                if not isinstance(label,str) or not label.strip() or len(label)>120 or any(ord(c)<32 or ord(c)==127 for c in label):raise ValueError('Participant labels require 1 through 120 single-line characters')
                coefficient=_coefficient(item.get('coefficient',1))
                info=inspect_identifier(item['smiles'],'smiles');canonical=info['canonical_smiles']
                if key.lower() in identities and identities[key.lower()]!=(canonical,label):raise ValueError('Repeated compound identifier changed identity or label between explicit steps')
                identities[key.lower()]=(canonical,label)
                params=Chem.SmilesParserParams();params.removeHs=False;mol=Chem.MolFromSmiles(canonical,params)
                if mol is None or not 1<=mol.GetNumAtoms()<=150 or any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):raise ValueError('Reaction participants require supported nonradical graphs of 1 through 150 atoms')
                components=Chem.GetMolFrags(mol,asMols=True,sanitizeFrags=True)
                if not 1<=len(components)<=4:raise ValueError('A participant supports at most four explicit salt components')
                charges=[Chem.GetFormalCharge(c) for c in components]
                if len(components)>1 and (any(c==0 for c in charges) or sum(charges)!=0):raise ValueError('Disconnected participants must be explicit charge-balanced ionic salts, not mixtures or hydrates')
                parts=[]
                for comp in components:
                    smi=Chem.MolToSmiles(comp,isomericSmiles=True)
                    if comp.GetNumAtoms()>1:
                        seed=prepare_structures([{'compound_id':'component','label':'Component','smiles':smi}])[0]
                    else:
                        atom=comp.GetAtomWithIdx(0);z=atom.GetAtomicNum();q=atom.GetFormalCharge();h=atom.GetTotalNumHs()
                        if not ((z==8 and (q,h) in ((0,2),(-1,1))) or (z in (9,17,35,53) and q==-1 and h==0) or (z in (11,19) and q==1 and h==0)):
                            raise ValueError('Supported isolated participants are water, hydroxide, halide anions and Na+/K+ ions')
                        block=Chem.MolToMolBlock(comp);check=Chem.MolFromMolBlock(block,removeHs=False)
                        if check is None or Chem.MolToSmiles(check,isomericSmiles=True)!=smi:raise ValueError('Reaction MOL seed changed explicit identity')
                        seed={'canonical_smiles':smi,'molblock':block}
                    part={'canonical_smiles':smi,'molblock':seed['molblock'],'native_seed_format':'mol'}
                    if comp.GetNumAtoms()==1 and comp.GetAtomWithIdx(0).GetAtomicNum() in (11,19):
                        atom=comp.GetAtomWithIdx(0)
                        part.update(native_seed_format='cdxml',seed_cdxml=_alkali_seed(atom.GetAtomicNum(),atom.GetSymbol()))
                    parts.append(part)
                prepared[side].append({**copy.deepcopy(item),'canonical_smiles':canonical,'components':parts,'coefficient_text':coefficient})
        result.append(prepared)
    return result


def _layout_options(layout):
    defaults={'gap':16.,'label_gap':10.,'condition_gap':10.,'row_gap':120.,'margin':36.}
    if layout is None:return defaults
    if not isinstance(layout,dict) or set(layout)-set(defaults):raise ValueError('Unknown reaction layout fields')
    result={**defaults,**layout}
    for key,value in result.items():
        lo=0 if key=='margin' else 12 if key=='row_gap' else 4
        hi=120 if key=='row_gap' else 100 if key=='margin' else 60
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid reaction layout point distance: '+key)
    return result


def _union(elements):
    boxes=[bounds(e) for e in elements]
    return Box(min(b.left for b in boxes),min(b.top for b in boxes),max(b.right for b in boxes),max(b.bottom for b in boxes))


def _ink_place(e,cx,cy):
    b=bounds(e);transform(e,dx=cx-b.center[0],dy=cy-b.center[1])


def _region(page,margin):
    if page.get('WidthPages','1')!='1' or page.get('HeightPages','1')!='1':raise ValueError('Expanded reactions require one physical page')
    x,y,r,b=numbers(page.get('BoundingBox'),4)
    if r-x<=2*margin or b-y<=2*margin:raise ValueError('Reaction page region is empty')
    return x+margin,y+margin,r-margin,b-margin


def compose_series(native_by_smiles,prepared_steps,preset='house',layout=None):
    """Combine checked connected native components with explicit salt ownership."""
    options=_layout_options(layout);spec=preset_settings(preset);all_parts=[c for s in prepared_steps for side in ('reactants','products') for p in s[side] for c in p['components']]
    normalized={}
    for c in all_parts:
        smi=c['canonical_smiles']
        if smi in normalized:continue
        if smi not in native_by_smiles:raise ValueError('Missing checked native reaction component')
        text=normalize_cdxml(native_by_smiles[smi],preset)[0]
        if chemical_signature(text)!=[smi]:raise ValueError('Native component identity differs from explicit participant')
        rr=supported_root(text)
        if len(rr.findall('page/fragment'))!=1 or any(e.tag!='fragment' for e in rr.find('page')):raise ValueError('Expected a single connected native component with no page annotations')
        if any(e.tag not in ('n','b') for e in rr.find('page/fragment')):raise ValueError('Unsupported native component annotations')
        _validate_native_labels(text);normalized[smi]=rr
    root=copy.deepcopy(normalized[all_parts[0]['canonical_smiles']]);page=root.find('page')
    for e in list(page):page.remove(e)
    page.set('id','1');next_id=2
    def fresh():
        nonlocal next_id
        value=str(next_id);next_id+=1;return value
    recipe={'steps':[],'preset':preset,'layout_options':options}
    caption_size=float(spec['CaptionSize']);atom_size=float(spec['LabelSize']);font=root.get('CaptionFont')
    for prepared in prepared_steps:
        step={'step_id':prepared['step_id'],'reactants':[],'products':[],'plus_ids':[],'condition_sides':{}}
        for side in ('reactants','products'):
            for participant in prepared[side]:
                fids=[];cursor=0
                for comp in participant['components']:
                    f=copy.deepcopy(normalized[comp['canonical_smiles']].find('page/fragment'));mapping={e.get('id'):fresh() for e in f.iter() if e.get('id')}
                    for e in f.iter():
                        for attr in ('id','B','E'):
                            if e.get(attr):e.set(attr,mapping[e.get(attr)])
                        for attr in ('AS','BondOrdering','BondCircularOrdering'):e.attrib.pop(attr,None)
                    bb=bounds(f);transform(f,dx=cursor-bb.left,dy=-bb.center[1]);cursor+=bb.width+12
                    page.append(f);fids.append(f.get('id'))
                tid=fresh();_text(page,tid,participant['label'],0,100,caption_size,font)
                cid=None
                if participant['coefficient_text']!='1':cid=fresh();_text(page,cid,participant['coefficient_text'],0,100,atom_size,font)
                step[side].append({'compound_id':participant['compound_id'],'canonical_smiles':participant['canonical_smiles'],
                    'component_smiles':[c['canonical_smiles'] for c in participant['components']], 'fragment_ids':fids,
                    'label':participant['label'],'caption_id':tid,'coefficient_id':cid,'coefficient_text':participant['coefficient_text']})
            for _ in range(len(step[side])-1):
                tid=fresh();_text(page,tid,'+',0,100,atom_size,font);step['plus_ids'].append(tid)
        aid=fresh();step['arrow_id']=aid
        ET.SubElement(page,'arrow',{'id':aid,'Head3D':'172 100 0','Tail3D':'100 100 0','BoundingBox':'100 95 172 105',
            'ArrowheadHead':'Full','ArrowheadType':'Solid','HeadSize':'1000','ArrowheadCenterSize':'875','ArrowheadWidth':'250','LineWidth':spec['LineWidth']})
        for side in ('above','below'):
            condition=prepared['conditions_'+side]
            if condition:
                tid=fresh();_text(page,tid,condition,136,75 if side=='above' else 130,caption_size,font);step['condition_sides'][tid]=side
        scheme=ET.SubElement(page,'scheme',{'id':fresh()})
        attrs={'id':fresh(),'ReactionStepReactants':' '.join(f for p in step['reactants'] for f in p['fragment_ids']),
            'ReactionStepProducts':' '.join(f for p in step['products'] for f in p['fragment_ids']),'ReactionStepArrows':aid}
        for side,suffix in (('above','Above'),('below','Below')):
            tids=[t for t,s in step['condition_sides'].items() if s==side]
            if tids:attrs['ReactionStepObjects'+suffix+'Arrow']=' '.join(tids)
        ET.SubElement(scheme,'step',attrs);recipe['steps'].append(step)
    text=style_cdxml(ET.tostring(root,encoding='unicode'),preset)
    # Coefficients are owned reaction quantities, not molecule-name captions.
    # The general style pass styles page text as captions; restore only these
    # explicitly owned runs to atom typography before native measurement.
    styled=supported_root(text)
    for step in recipe['steps']:
        for participant in step['reactants']+step['products']:
            if participant['coefficient_id']:
                coefficient=styled.find(f'page/t[@id="{participant["coefficient_id"]}"]')
                for run in coefficient.iter('s'):
                    run.set('font',styled.get('LabelFont'));run.set('size',spec['LabelSize'])
                    run.set('face',str(int(spec.get('LabelFace','0'))&3))
    text=ET.tostring(styled,encoding='unicode')
    if chemical_signature(text)!=sorted(c['canonical_smiles'] for c in all_parts):raise ValueError('Composed reaction identity changed')
    return arrange_series(text,recipe,require_measured=False)


def remap_series(recipe,mapping):
    result=copy.deepcopy(recipe)
    for step in result['steps']:
        step['arrow_id']=mapping[step['arrow_id']];step['plus_ids']=[mapping[t] for t in step['plus_ids']]
        step['condition_sides']={mapping[t]:side for t,side in step['condition_sides'].items()}
        for p in step['reactants']+step['products']:
            p['fragment_ids']=[mapping[f] for f in p['fragment_ids']];p['caption_id']=mapping[p['caption_id']]
            if p['coefficient_id']:p['coefficient_id']=mapping[p['coefficient_id']]
    return result


def arrange_series(text,recipe,require_measured=True):
    root=supported_root(text);page=root.find('page');objects={e.get('id'):e for e in page};plan=copy.deepcopy(recipe)
    options=plan['layout_options'];region=_region(page,options['margin']);plan['region']=region;top=region[1]
    if require_measured and any(not e.get('BoundingBox') for e in page if e.tag in ('fragment','t','arrow')):raise ValueError('Native measured bounds required for reaction layout')
    for step in plan['steps']:
        units=[];plus_iter=iter(step['plus_ids']);arrow=objects[step['arrow_id']]
        head=list(numbers(arrow.get('Head3D'),3));tail=list(numbers(arrow.get('Tail3D'),3))
        length=max([72.]+[bounds(objects[t]).width+24 for t in step['condition_sides']]);head[0]=tail[0]+length
        arrow.set('Head3D',encode(head));ab=bounds(arrow);arrow.set('BoundingBox',encode((tail[0],ab.top,head[0],ab.bottom)))
        for g in page.findall('graphic'):
            if g.get('SupersededBy')==arrow.get('id'):g.set('BoundingBox',encode((head[0],head[1],tail[0],tail[1])))
        for side in ('reactants','products'):
            if side=='products':units.append(('object',arrow))
            for i,p in enumerate(step[side]):
                if i:units.append(('object',objects[next(plus_iter)]))
                units.append(('participant',p))
        widths=[];bodyheight=max(bounds(arrow).height,1.)
        for kind,unit in units:
            if kind=='object':widths.append(bounds(unit).width);bodyheight=max(bodyheight,bounds(unit).height);continue
            bb=_union([objects[f] for f in unit['fragment_ids']]);cb=bounds(objects[unit['caption_id']]);coef=objects.get(unit['coefficient_id'])
            left=max(bb.width/2+(bounds(coef).width+6 if coef is not None else 0),cb.width/2);right=max(bb.width/2,cb.width/2)
            unit['left_extent_pt']=left;unit['right_extent_pt']=right;widths.append(left+right);bodyheight=max(bodyheight,bb.height,bounds(coef).height if coef is not None else 0)
        total=sum(widths)+options['gap']*(len(widths)-1)
        if total>region[2]-region[0]+.01:raise ValueError(f'Reaction step {step["step_id"]} needs {total:.2f} pt and does not fit the native page; no shrinking performed')
        arrow_top_extent=tail[1]-bounds(arrow).top
        above=max([0.]+[bounds(objects[t]).height+options['condition_gap']+arrow_top_extent for t,s in step['condition_sides'].items() if s=='above'])
        y=top+max(bodyheight/2,arrow_top_extent,above);cursor=region[0];component_bounds=[]
        for (kind,unit),width in zip(units,widths):
            if kind=='object':
                if unit.tag=='arrow':
                    old=numbers(unit.get('Tail3D'),3);dx=cursor-old[0];dy=y-old[1];transform(unit,dx=dx,dy=dy)
                    for g in page.findall('graphic'):
                        if g.get('SupersededBy')==unit.get('id'):transform(g,dx=dx,dy=dy)
                else:_ink_place(unit,cursor+width/2,y)
            else:
                fs=[objects[f] for f in unit['fragment_ids']];bb=_union(fs);cx=cursor+unit['left_extent_pt']
                for f in fs:transform(f,dx=cx-bb.center[0],dy=y-bb.center[1])
                unit['molecule_center_x_pt']=cx
                if unit['coefficient_id']:
                    coef=objects[unit['coefficient_id']];_ink_place(coef,cx-bb.width/2-6-bounds(coef).width/2,y)
            component_bounds.append((cursor,cursor+width));cursor+=width+options['gap']
        ab=bounds(arrow);arrowcenter=(numbers(arrow.get('Head3D'),3)[0]+numbers(arrow.get('Tail3D'),3)[0])/2
        bottom=max(y+bodyheight/2,ab.bottom)
        for tid,side in step['condition_sides'].items():
            t=objects[tid];height=bounds(t).height
            cy=ab.top-options['condition_gap']-height/2 if side=='above' else ab.bottom+options['condition_gap']+height/2
            _ink_place(t,arrowcenter,cy);bottom=max(bottom,bounds(t).bottom)
        participants=step['reactants']+step['products'];ascent=max(numbers(objects[p['caption_id']].get('p'),2)[1]-bounds(objects[p['caption_id']]).top for p in participants)
        baseline=bottom+options['label_gap']+ascent
        for p in participants:
            t=objects[p['caption_id']];transform(t,dx=p['molecule_center_x_pt']-bounds(t).center[0],dy=baseline-numbers(t.get('p'),2)[1])
            bottom=max(bottom,bounds(t).bottom)
        step.update(top_pt=top,bottom_pt=bottom,caption_baseline_pt=baseline,center_y_pt=y,component_bounds_pt=component_bounds)
        top=bottom+options['row_gap']
    visible=[e for e in page if e.tag in ('fragment','t','arrow')];boxes=[bounds(e) for e in visible]
    if any(b.left<region[0]-.03 or b.top<region[1]-.03 or b.right>region[2]+.03 or b.bottom>region[3]+.03 for b in boxes):raise ValueError('Reaction series page overflow')
    if find_overlaps(boxes,[e.get('id') for e in visible],tolerance=.05):raise ValueError('Reaction series objects overlap')
    return ET.tostring(root,encoding='unicode'),plan


def verify_series(expected,native,plan):
    _verify(expected,native);mapped=remap_series(plan,remap_ids(expected,native));root=supported_root(native);page=root.find('page');objects={e.get('id'):e for e in page}
    spec=preset_settings(plan['preset']);parents={child:parent for parent in root.iter() for child in parent}
    def inherited(element,key):
        while element is not None:
            if element.get(key) is not None:return element.get(key)
            element=parents.get(element)
        return None
    region=_region(page,plan['layout_options']['margin'])
    if any(abs(x-y)>.03 for x,y in zip(region,plan['region'])):raise ValueError('Native page region changed')
    visible=[e for e in page if e.tag in ('fragment','t','arrow')]
    if any(not e.get('BoundingBox') for e in visible):raise ValueError('Missing native reaction ink bounds')
    boxes=[bounds(e) for e in visible]
    if any(b.left<region[0]-.05 or b.top<region[1]-.05 or b.right>region[2]+.05 or b.bottom>region[3]+.05 for b in boxes):raise ValueError('Native reaction page overflow')
    if find_overlaps(boxes,[e.get('id') for e in visible],tolerance=.05):raise ValueError('Native reaction ink overlaps')
    for step in mapped['steps']:
        arrow=objects[step['arrow_id']];head=numbers(arrow.get('Head3D'),3);tail=numbers(arrow.get('Tail3D'),3);cx=(head[0]+tail[0])/2
        for side in ('reactants','products'):
            for p in step[side]:
                fs=[objects[f] for f in p['fragment_ids']];bb=_union(fs);cap=objects[p['caption_id']]
                if ''.join(cap.itertext()).strip()!=p['label'] or abs(bounds(cap).center[0]-bb.center[0])>.75:raise ValueError('Native participant caption binding or centring changed')
                if abs(numbers(cap.get('p'),2)[1]-step['caption_baseline_pt'])>.05:raise ValueError('Native caption baseline changed')
                if (side=='reactants' and bb.right>=tail[0]) or (side=='products' and bb.left<=head[0]):raise ValueError('Native participant moved to wrong reaction side')
                if p['coefficient_id']:
                    c=objects[p['coefficient_id']]
                    if ''.join(c.itertext()).strip()!=p['coefficient_text'] or abs(bounds(c).right-(bb.left-6))>.75 or abs(bounds(c).center[1]-step['center_y_pt'])>.75:raise ValueError('Native coefficient value or placement changed')
                    runs=list(c.iter('s'))
                    if not runs:raise ValueError('Native coefficient typography missing')
                    for run in runs:
                        font=run.get('font',inherited(c,'CaptionFont'))
                        names=[f.get('name') for f in root.findall('fonttable/font') if f.get('id')==font]
                        if names!=[spec['font']]:raise ValueError('Native coefficient font family changed')
                        try:size=float(run.get('size',inherited(c,'CaptionSize')))
                        except (TypeError,ValueError) as exc:raise ValueError('Native coefficient size missing') from exc
                        # Same twentieth-point native quantization tolerance as
                        # verify_custom_style, including nonintegral presets.
                        if not math.isfinite(size) or abs(size-float(spec['LabelSize']))>.050001:raise ValueError('Native coefficient size changed')
        for tid,side in step['condition_sides'].items():
            b=bounds(objects[tid])
            if abs(b.center[0]-cx)>.75 or (side=='above' and b.bottom>=head[1]) or (side=='below' and b.top<=head[1]):raise ValueError('Native arrow condition placement changed')
    medians=[statistics.median(bond_lengths(f)) for f in page.findall('fragment') if bond_lengths(f)]
    if any(abs(m-float(preset_settings(plan['preset'])['BondLength']))>.03 for m in medians):raise ValueError('Native molecular bond scale changed')
    return {'checks':{'mapped_chemistry_and_stereo':True,'explicit_step_roles':True,'salt_component_ownership':True,'coefficient_values_and_placement':True,'coefficient_font_and_size':True,
        'caption_and_condition_alignment':True,'page_fit':True,'no_interobject_overlaps':True,'bond_scale_where_defined':True},
        'chemical_balance_certified':False,'steps':mapped['steps'],'median_bond_lengths_pt':medians}


def build_reaction_series(bridge,steps,output_dir,preset='house',pixels=3200,layout=None):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires an absolute new directory with existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    prepared=prepare_steps(steps);options=_layout_options(layout);preset_settings(preset)
    from .styles import require_style_fonts,verify_custom_style
    require_style_fonts(preset)
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 through 8192')
    audit={'status':'in_progress','checks':{},'visual_review':'required','renderer':'native ChemDraw','chemical_balance_certified':False,
        'limitations':'Explicit ordered reaction rows and coefficients; no inferred products, intermediate links, atom mapping, balancing, mechanism or experimental results.'}
    owned=[];native_by_smiles={}
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents);content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline['documents']}
        out.mkdir();seeds=out/'seeds';seeds.mkdir();_write_json(out/'request.json',{'schema_version':1,'steps':steps,'preset':preset,'pixels':pixels,'layout':options});_write_json(out/'audit.json',audit)
        try:
            parts=[c for s in prepared for side in ('reactants','products') for p in s[side] for c in p['components']]
            for c in parts:
                smi=c['canonical_smiles']
                if smi in native_by_smiles:continue
                key=f'component-{len(native_by_smiles)+1}';seed=seeds/f'{key}.mol';seed.write_text(c['molblock'])
                if c['native_seed_format']=='cdxml':
                    (seeds/f'{key}.cdxml').write_text(c['seed_cdxml'])
                    imported=_native(bridge.create,c['seed_cdxml'])
                else:imported=_native(bridge.import_file,str(seed))
                did=imported['document']['document_id'];owned.append(did)
                snap=seeds/f'{key}-imported.cdxml';_native(bridge.export,did,str(snap),'cdxml')
                if chemical_signature(snap.read_text())!=[smi]:raise ValueError('Native reaction component import changed identity')
                _native(bridge.clean,did);snap=seeds/f'{key}-clean.cdxml';_native(bridge.export,did,str(snap),'cdxml')
                if chemical_signature(snap.read_text())!=[smi]:raise ValueError('Native reaction component cleanup changed identity')
                native_by_smiles[smi]=snap.read_text();_native(bridge.close,did);owned.remove(did)
            composed,recipe=compose_series(native_by_smiles,prepared,preset,options);(out/'combined.cdxml').write_text(composed)
            result=_native(bridge.create,composed);intermediate=result['document']['document_id'];owned.append(intermediate)
            snap=out/'combined-native.cdxml';_native(bridge.export,intermediate,str(snap),'cdxml');native=snap.read_text();_verify(composed,native);verify_custom_style(composed,native,preset)
            recipe=remap_series(recipe,remap_ids(composed,native));arranged,plan=arrange_series(native,recipe);(out/'planned.cdxml').write_text(arranged);_write_json(out/'recipe.json',plan)
            result=_native(bridge.create,arranged);final_id=result['document']['document_id'];owned.append(final_id)
            for fmt in ('svg','png','cdxml'):_native(bridge.export,final_id,str(out/f'figure.{fmt}'),fmt,pixels)
            final=(out/'figure.cdxml').read_text();verification=verify_series(arranged,final,plan);verify_custom_style(arranged,final,preset)
            stable=out/'post-export.cdxml';_native(bridge.export,final_id,str(stable),'cdxml')
            if content_fingerprint(final)!=content_fingerprint(stable.read_text()):raise ValueError('Native working content changed during export')
            _native(bridge.close,intermediate);owned.remove(intermediate)
            if [d for d in _native(bridge.documents)['documents'] if d['document_id']!=final_id]!=baseline['documents']:raise ValueError('Pre-existing document inventory changed')
            for did,original in content.items():
                if _document_content(bridge,did)!=original:raise ValueError('Pre-existing document content changed')
            audit.update(status='checks_passed',verification=verification);audit['checks'].update(verification['checks'],native_component_import_identity=True,native_component_cleanup_identity=True,preexisting_documents_unchanged=True)
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Native reaction series</title><h1>Explicit reaction series</h1><p>Caller-supplied participants and coefficients. Not automatically balanced or chemically certified. Visual review required.</p><img style="max-width:100%;max-height:85vh" src="figure.png"><p><a href="figure.cdxml">Editable ChemDraw</a> <a href="figure.svg">SVG</a> <a href="audit.json">Audit</a></p>')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned,recovery='No retry or automatic close after uncertain native operation');_write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing),owned_document_ids=owned);_write_json(out/'audit.json',audit);raise
            _write_json(out/'audit.json',audit);raise
