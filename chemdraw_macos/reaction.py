"""Explicit one-step reaction composition, with native saved-role/ink checks.

No reaction prediction, name inference, automatic stoichiometry or GUI fallback.
RDKit supplies checked MOL seeds; desktop ChemDraw cleans and renders them.
"""
from contextlib import nullcontext
import copy
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from .batch import _native, NativeUncertain, _document_content, _verify
from .core import preset_settings
from .draw import prepare_structures, combine_native_structures
from .geometry import find_overlaps
from .polish import (supported_root, chemical_signature, bounds, transform, numbers,
                     encode, layout_row, normalize_cdxml, bond_lengths)
from .workflow import remap_ids, _write_json, content_fingerprint


def _prepare(reactants, products, conditions_above, conditions_below):
    for side in (reactants,products):
        if not isinstance(side,list) or not 1<=len(side)<=3:
            raise ValueError('Supply 1 through 3 explicit compounds on each reaction side')
    for condition in (conditions_above,conditions_below):
        if (not isinstance(condition,str) or len(condition)>120
                or any(ord(c)<32 or ord(c)==127 for c in condition)):
            raise ValueError('Conditions must be single-line text of at most 120 characters')
        if condition and not condition.strip():raise ValueError('Condition cannot be whitespace only')
    return prepare_structures(reactants+products)


def _visible(page):
    return [e for e in page if e.tag in ('fragment','t','arrow')]


def _region(page):
    if page.get('WidthPages','1')!='1' or page.get('HeightPages','1')!='1':
        raise ValueError('Reaction requires one physical page')
    x,y,r,b=numbers(page.get('BoundingBox'),4)
    if r-x<=72 or b-y<=72:raise ValueError('Invalid or too small reaction page')
    return (x+36,y+36,r-36,b-36)


def _text(page,tid,value,x,y,size,font):
    # Conservative estimates stage objects only. Native exports must measure
    # every final ink box; these estimates are never accepted as final evidence.
    width=max(size*.7,len(value)*size)
    t=ET.SubElement(page,'t',{'id':tid,'p':encode((x,y)),
        'BoundingBox':encode((x-width/2,y-size,x+width/2,y+size*.25)),
        'Justification':'Center','CaptionJustification':'Center'})
    ET.SubElement(t,'s',{'font':font,'size':str(size),'face':'0'}).text=value
    return t


def compose_reaction(native_texts,reactants,products,conditions_above='',conditions_below='',preset='house'):
    """Compose native single-molecule snapshots and return explicit ownership.

    Inputs are ordered reactants then products. Bounds here stage the first
    native import; arrange_reaction subsequently uses actual native ink.
    """
    records=_prepare(reactants,products,conditions_above,conditions_below)
    combined,cells=combine_native_structures(native_texts,records,preset)
    root=supported_root(combined);page=root.find('page');region=_region(page)
    objects={e.get('id'):e for e in page};next_id=max(int(e.get('id')) for e in page.iter() if e.get('id'))+1
    def fresh():
        nonlocal next_id
        result=str(next_id);next_id+=1;return result
    spec=preset_settings(preset)
    caption_size=float(spec['CaptionSize']);atom_size=float(spec['LabelSize'])
    font=root.get('CaptionFont');main=[];roles=[];caption_map={};plus_ids=[]
    max_height=max(bounds(objects[c['fragment_ids'][0]]).height for c in cells)
    y=region[1]+max_height/2+caption_size*3
    cursor=region[0]
    arrow=None;condition_map={};condition_sides={}
    for i,(cell,record) in enumerate(zip(cells,records)):
        if i==len(reactants):
            aid=fresh();length=max(72.,max(len(conditions_above),len(conditions_below))*caption_size+24)
            # Native arrow attributes follow the exercised oxidation fixture.
            arrow=ET.SubElement(page,'arrow',{'id':aid,'Head3D':encode((cursor+length,y,0)),
                'Tail3D':encode((cursor,y,0)),'BoundingBox':encode((cursor,y-5,cursor+length,y+5)),
                'ArrowheadHead':'Full','ArrowheadType':'Solid','HeadSize':'1000',
                'ArrowheadCenterSize':'875','ArrowheadWidth':'250','LineWidth':spec['LineWidth']})
            main.append(arrow);condition_map[aid]=[]
            for side,value,offset in [('above',conditions_above,-18),('below',conditions_below,24)]:
                if value:
                    tid=fresh();_text(page,tid,value,cursor+length/2,y+offset,caption_size,font)
                    condition_map[aid].append(tid);condition_sides[tid]=side
            cursor+=length+24
        elif i:
            tid=fresh();plus=_text(page,tid,'+',cursor+atom_size/2,y+atom_size*.3,atom_size,font)
            plus_ids.append(tid);main.append(plus);cursor+=atom_size+24
        fid=cell['fragment_ids'][0];tid=cell['caption_id'];f=objects[fid];t=objects[tid]
        box=bounds(f);width=max(box.width,len(record['label'])*caption_size)
        cx=cursor+width/2
        transform(f,dx=cx-box.center[0],dy=y-box.center[1])
        page.remove(t);_text(page,tid,record['label'],cx,y+max_height/2+24,caption_size,font)
        main.append(f);caption_map[fid]=tid
        roles.append({'compound_id':record['compound_id'],'role':'reactant' if i<len(reactants) else 'product',
                      'fragment_id':fid,'caption_id':tid,'label':record['label'],'canonical_smiles':record['canonical_smiles']})
        cursor+=width+24
    if cursor-24>region[2]:raise ValueError('Initial reaction row does not fit the native page; use fewer compounds or shorter labels')
    visible=_visible(page)
    if max(bounds(e).bottom for e in visible)>region[3]:raise ValueError('Reaction page overflow')
    scheme=ET.SubElement(page,'scheme',{'id':fresh()})
    attrs={'id':fresh(),'ReactionStepReactants':' '.join(r['fragment_id'] for r in roles if r['role']=='reactant'),
           'ReactionStepProducts':' '.join(r['fragment_id'] for r in roles if r['role']=='product'),
           'ReactionStepArrows':arrow.get('id')}
    for side,suffix in [('above','Above'),('below','Below')]:
        tids=[tid for tid,value in condition_sides.items() if value==side]
        if tids:attrs['ReactionStepObjects'+suffix+'Arrow']=' '.join(tids)
    ET.SubElement(scheme,'step',attrs)
    for t in page.findall('t'):
        for run in t.findall('s'):run.set('face',spec.get('CaptionFace','0'))
    text=ET.tostring(root,encoding='unicode')
    if chemical_signature(text)!=sorted(r['canonical_smiles'] for r in records):raise ValueError('Reaction composition changed identity')
    return text,{'caption_map':caption_map,'condition_map':condition_map,'condition_sides':condition_sides,
                 'roles':roles,'arrow_id':arrow.get('id'),'plus_ids':plus_ids,
                 'component_ids':[e.get('id') for e in main],'preset':preset}


def _remap(recipe,mapping):
    result=copy.deepcopy(recipe)
    result['caption_map']={mapping[f]:mapping[t] for f,t in recipe['caption_map'].items()}
    result['condition_map']={mapping[a]:[mapping[t] for t in ts] for a,ts in recipe['condition_map'].items()}
    result['condition_sides']={mapping[t]:side for t,side in recipe['condition_sides'].items()}
    result['arrow_id']=mapping[recipe['arrow_id']]
    result['plus_ids']=[mapping[t] for t in recipe['plus_ids']]
    result['component_ids']=[mapping[t] for t in recipe['component_ids']]
    result['roles']=[{**r,'fragment_id':mapping[r['fragment_id']],'caption_id':mapping[r['caption_id']]} for r in recipe['roles']]
    return result


def arrange_reaction(native_text,recipe):
    """Use measured ink and the existing row planner, failing on page overflow."""
    root=supported_root(native_text);page=root.find('page');region=_region(page)
    for e in _visible(page):
        if not e.get('BoundingBox'):raise ValueError('Native measured bounds required for every reaction object')
    objects={e.get('id'):e for e in page};arrow=objects[recipe['arrow_id']]
    head=list(numbers(arrow.get('Head3D'),3));tail=numbers(arrow.get('Tail3D'),3)
    required=max([bounds(objects[t]).width+24 for t in recipe['condition_map'][arrow.get('id')]]+[72.])
    if head[0]-tail[0]<required:
        delta=required-(head[0]-tail[0]);head[0]+=delta;arrow.set('Head3D',encode(head))
        box=list(numbers(arrow.get('BoundingBox'),4));box[2]+=delta;arrow.set('BoundingBox',encode(box))
        for g in page.findall('graphic'):
            if g.get('SupersededBy')==arrow.get('id'):
                # Keep native fallback endpoints coherent with the arrow.
                bb=list(numbers(g.get('BoundingBox'),4));bb[0]+=delta;g.set('BoundingBox',encode(bb))
    source=ET.tostring(root,encoding='unicode');last_error=None
    # Equal main-component gaps grow together when captions require more room.
    for gap in range(24,121,6):
        try:
            arranged,layout=layout_row(source,recipe['caption_map'],recipe['condition_map'],gap=gap,label_gap=14.,width=region[2]-region[0])
            final=supported_root(arranged);fp=final.find('page');visible=_visible(fp)
            left=min(bounds(e).left for e in visible);top=min(bounds(e).top for e in visible)
            for e in fp:
                if e.tag!='scheme':transform(e,dx=region[0]-left,dy=region[1]-top)
            boxes=[bounds(e) for e in visible]
            if any(b.right>region[2]+.03 or b.bottom>region[3]+.03 for b in boxes):
                raise ValueError('Measured reaction labels/conditions overflow native page')
            if find_overlaps(boxes,[e.get('id') for e in visible],tolerance=.05):
                raise ValueError('Measured reaction labels/conditions overlap')
            output=ET.tostring(final,encoding='unicode')
            baseline=numbers(fp.find(f't[@id="{next(iter(recipe["caption_map"].values()))}"]').get('p'),2)[1]
            return output,{**copy.deepcopy(recipe),'gap_pt':gap,'region':region,'caption_baseline_pt':baseline,
                           'layout':layout}
        except ValueError as exc:last_error=exc
    raise ValueError(f'Reaction does not fit without overlap: {last_error}')


def verify_reaction(expected,native,plan):
    """Check requested role bindings and saved native ink, not reaction validity."""
    _verify(expected,native)
    mapping=remap_ids(expected,native);actual=_remap(plan,mapping)
    root=supported_root(native);page=root.find('page');objects={e.get('id'):e for e in page}
    region=_region(page)
    if any(abs(a-b)>.03 for a,b in zip(region,plan['region'])):raise ValueError('Native saved page changed')
    visible=_visible(page)
    if any(not e.get('BoundingBox') for e in visible):raise ValueError('Final native ink bounds missing')
    boxes=[bounds(e) for e in visible]
    if any(b.left<region[0]-.05 or b.top<region[1]-.05 or b.right>region[2]+.05 or b.bottom>region[3]+.05 for b in boxes):
        raise ValueError('Final native reaction ink exceeds page')
    if find_overlaps(boxes,[e.get('id') for e in visible],tolerance=.05):raise ValueError('Final native reaction objects overlap')
    arrow=objects[actual['arrow_id']];head=numbers(arrow.get('Head3D'),3);tail=numbers(arrow.get('Tail3D'),3)
    center=(head[0]+tail[0])/2
    for role in actual['roles']:
        f=objects[role['fragment_id']];caption=objects[role['caption_id']]
        if ''.join(caption.itertext()).strip()!=role['label']:raise ValueError('Native compound caption binding changed')
        if abs(bounds(caption).center[0]-bounds(f).center[0])>.75:raise ValueError('Native caption is not centred')
        if abs(numbers(caption.get('p'),2)[1]-plan['caption_baseline_pt'])>.05:raise ValueError('Native caption baseline changed')
        if role['role']=='reactant' and bounds(f).right>=tail[0]:raise ValueError('Reactant moved to wrong arrow side')
        if role['role']=='product' and bounds(f).left<=head[0]:raise ValueError('Product moved to wrong arrow side')
    for tid,side in actual['condition_sides'].items():
        b=bounds(objects[tid])
        if abs(b.center[0]-center)>.75:raise ValueError('Native arrow condition is not centred')
        if (side=='above' and b.bottom>=head[1]) or (side=='below' and b.top<=head[1]):
            raise ValueError('Native condition moved to wrong arrow side')
    components=[objects[oid] for oid in actual['component_ids']]
    gaps=[bounds(b).left-bounds(a).right for a,b in zip(components,components[1:])]
    if any(abs(g-plan['gap_pt'])>.1 for g in gaps):raise ValueError('Native reaction spacing changed')
    medians=[statistics.median(bond_lengths(f)) for f in page.findall('fragment')]
    if any(abs(v-float(preset_settings(plan['preset'])['BondLength']))>.03 for v in medians):raise ValueError('Native molecular scale changed')
    return {'checks':{'mapped_chemistry_and_stereo':True,'explicit_reaction_roles':True,
            'caption_bindings_and_alignment':True,'condition_alignment':True,'equal_component_gaps':True,
            'page_fit':True,'no_interobject_overlaps':True,'bond_scale':True},
            'roles':actual['roles'],'median_bond_lengths_pt':medians,'gaps_pt':gaps,'region':region}


def build_reaction(bridge,reactants,products,output_dir,conditions_above='',conditions_below='',preset='house',pixels=3200,scaffold_smiles=None,layout=None):
    # Preserve the original connected-structure route; expanded inputs have a
    # reaction-specific validator, never a relaxed general draw validator.
    expanded=layout is not None
    if isinstance(reactants,list) and isinstance(products,list):
        from .identifiers import inspect_identifier
        from rdkit import Chem
        for item in reactants+products:
            if isinstance(item,dict):
                if 'coefficient' in item:expanded=True
                if isinstance(item.get('smiles'),str):
                    smi=inspect_identifier(item['smiles'],'smiles')['canonical_smiles']
                    if '.' in smi or Chem.MolFromSmiles(smi).GetNumAtoms()==1:expanded=True
    if expanded:
        if scaffold_smiles is not None:raise ValueError('Expanded reaction participants do not yet support scaffold alignment')
        from .reaction_series import build_reaction_series
        return build_reaction_series(bridge,[{'step_id':'reaction','reactants':reactants,'products':products,
            'conditions_above':conditions_above,'conditions_below':conditions_below}],output_dir,preset,pixels,layout)
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path with existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    preset_settings(preset)
    from .styles import require_style_fonts
    require_style_fonts(preset)
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be 256 through 8192')
    records=_prepare(reactants,products,conditions_above,conditions_below)
    if scaffold_smiles is not None:
        from .alignment import validate_scaffold_inputs
        validate_scaffold_inputs([r['canonical_smiles'] for r in records],scaffold_smiles)
    audit={'status':'in_progress','checks':{},'visual_review':'required','renderer':'native ChemDraw',
           'coordinate_seed':'RDKit MOL; native import and cleanup',
           'limitations':'Explicit one-step roles only. Labels/conditions are caller supplied; no name, stoichiometry, mechanism or reaction-feasibility inference. No complete glyph/collision certification.'}
    owned=[];texts=[]
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents)
        content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline['documents']}
        out.mkdir();seeds=out/'seeds';seeds.mkdir()
        _write_json(out/'request.json',{'schema_version':1,'reactants':reactants,'products':products,
            'conditions_above':conditions_above,'conditions_below':conditions_below,'preset':preset,
            'pixels':pixels,'scaffold_smiles':scaffold_smiles})
        _write_json(out/'audit.json',audit)
        try:
            for record in records:
                key=record['compound_id'];seed=seeds/f'{key}.mol';seed.write_text(record['molblock'])
                result=_native(bridge.import_file,str(seed));did=result['document']['document_id'];owned.append(did)
                initial=seeds/f'{key}-imported.cdxml';_native(bridge.export,did,str(initial),'cdxml')
                if chemical_signature(initial.read_text())!=[record['canonical_smiles']]:raise ValueError('Native MOL import changed requested identity')
                _native(bridge.clean,did)
                target=seeds/f'{key}-clean.cdxml';_native(bridge.export,did,str(target),'cdxml')
                text=target.read_text()
                if chemical_signature(text)!=[record['canonical_smiles']]:raise ValueError('Native cleanup changed requested identity')
                texts.append(text);_native(bridge.close,did);owned.remove(did)
            if scaffold_smiles is not None:
                from .alignment import align_native_structures
                texts,alignment=align_native_structures([normalize_cdxml(t,preset)[0] for t in texts],scaffold_smiles)
                audit['alignment']=alignment
            combined,recipe=compose_reaction(texts,reactants,products,conditions_above,conditions_below,preset)
            (out/'combined.cdxml').write_text(combined)
            result=_native(bridge.create,combined);did=result['document']['document_id'];owned.append(did)
            snap=out/'combined-native.cdxml';_native(bridge.export,did,str(snap),'cdxml');native=snap.read_text()
            _verify(combined,native);recipe=_remap(recipe,remap_ids(combined,native))
            from .styles import verify_custom_style
            verify_custom_style(combined,native,preset)
            arranged,plan=arrange_reaction(native,recipe);(out/'planned.cdxml').write_text(arranged)
            _write_json(out/'recipe.json',plan)
            result=_native(bridge.create,arranged);final_id=result['document']['document_id'];owned.append(final_id)
            for fmt in ('cdxml','svg','png'):_native(bridge.export,final_id,str(out/f'figure.{fmt}'),fmt,pixels)
            final=(out/'figure.cdxml').read_text();verification=verify_reaction(arranged,final,plan)
            style_check=verify_custom_style(arranged,final,preset)
            if style_check is not None:audit['custom_style_verification']=style_check
            stable=out/'post-export.cdxml';_native(bridge.export,final_id,str(stable),'cdxml')
            if content_fingerprint(final)!=content_fingerprint(stable.read_text()):raise ValueError('Native working content changed during export')
            _native(bridge.close,did);owned.remove(did)
            current=_native(bridge.documents)['documents']
            if [d for d in current if d['document_id']!=final_id]!=baseline['documents']:raise ValueError('Pre-existing document inventory changed')
            for oid,original in content.items():
                if _document_content(bridge,oid)!=original:raise ValueError('Pre-existing document content changed')
            audit.update(status='checks_passed',verification=verification)
            audit['checks'].update(verification['checks'],native_import_identity=True,native_cleanup_identity=True,
                                   working_content_unchanged=True,preexisting_documents_unchanged=True)
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Native reaction</title><style>body{font:16px system-ui;margin:32px;background:#f2f4f5}figure{background:white;padding:24px}img{max-width:100%;max-height:80vh}</style><h1>Native ChemDraw reaction</h1><p>Explicit reactants, products and conditions. No predicted chemistry or experimental results. Visual review required.</p><figure><img src="figure.png" alt="Native reaction scheme"></figure><p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="figure.svg">SVG</a> · <a href="figure.png">PNG</a> · <a href="audit.json">Audit</a> · <a href="request.json">Request</a></p></html>''')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned,
                         recovery='No retries or automatic closes after uncertain native operation. Inspect retained documents and snapshots.')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing),owned_document_ids=owned)
                    _write_json(out/'audit.json',audit);raise
            _write_json(out/'audit.json',audit);raise
