"""Plan a complete molecule batch locally, then insert through the desktop API.

RDKit's ChemDraw writer supplies editable graphs, not rendered images. Existing
objects and document defaults are never restyled to accommodate new additions.
"""
import copy
import math
import statistics
import xml.etree.ElementTree as ET

from .polish import bounds, bond_lengths, chemical_signature, transform
from .shared import _page, plan_append
from .addin import get_backend


def _isolated(root, fragment):
    result=copy.deepcopy(root);page=result.find('page')
    page.clear();page.append(copy.deepcopy(fragment))
    return ET.tostring(result,encoding='unicode')


def inspect_graphs(text):
    from .editing import inspect_editable
    root=ET.fromstring(text);result=[]
    for fragment in root.findall('page/fragment'):
        try:
            value=inspect_editable(_isolated(root,fragment))
            result.append({'fragment_id':fragment.get('id'),
                'canonical_smiles':chemical_signature(_isolated(root,fragment))[0],
                'identity_source':'live_atom_bond_graph','atoms':value['atoms'],'bonds':value['bonds']})
        except (ValueError,RuntimeError,ImportError) as exc:
            result.append({'fragment_id':fragment.get('id'),'unsupported':str(exc),
                           'identity_source':'unresolved_live_graph'})
    return result


def plan_addition(before, structures, *, preset='house', columns=None, scaffold_smiles=None,allow_page_expansion=False):
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from .core import preset_settings
    from .draw import prepare_structures
    from .scaffold_seed import seed_from_native_scaffold
    if not hasattr(Chem,'MolToCDXMLBlock') or not Chem.HasChemDrawCDXSupport():
        raise ValueError('This API drawing path requires RDKit with ChemDraw CDXML writer support (2026.03.3 or newer)')
    records=prepare_structures(structures);spec=preset_settings(preset)
    if scaffold_smiles:
        from .alignment import validate_scaffold_inputs
        validate_scaffold_inputs([r['canonical_smiles'] for r in records],scaffold_smiles)
    def parse(smiles):
        options=Chem.SmilesParserParams();options.removeHs=False
        return Chem.MolFromSmiles(smiles,options)
    target,oldpage=_page(before,vertical_pages=allow_page_expansion);root=copy.deepcopy(target);page=root.find('page')
    for e in list(page):page.remove(e)
    if columns is not None and (type(columns) is not int or not 1<=columns<=24):
        raise ValueError('columns must be 1 through 24')
    fonts=root.find('fonttable')
    if fonts is None:fonts=ET.SubElement(root,'fonttable')
    name=spec['font'];font=next((f.get('id') for f in fonts if f.get('name')==name),None)
    if font is None:
        font=str(max([int(f.get('id')) for f in fonts]+[2])+1)
        ET.SubElement(fonts,'font',id=font,name=name,charset='Unicode')
    reference=None;reference_source=None
    def live_candidates(scaffold):
        candidates=[]
        for fragment in oldpage.findall('fragment'):
            text=_isolated(target,fragment)
            try:
                sm=chemical_signature(text)[0];core=parse(scaffold or sm)
                if core is not None and core.GetNumAtoms()>=3 and all(parse(r['canonical_smiles']).HasSubstructMatch(core,useChirality=True) for r in records):
                    if parse(sm).HasSubstructMatch(core,useChirality=True):candidates.append((text,scaffold or sm))
            except ValueError:continue
        return candidates
    candidates=live_candidates(scaffold_smiles)
    if not candidates and not scaffold_smiles:
        # Replacing a parent's substituent can remove part of its full graph.
        # Reuse the existing conservative supplied-core rule, not a guessed MCS.
        from .drawing_defaults import plan_drawing_defaults
        scaffold_smiles=plan_drawing_defaults(records)['scaffold_smiles']
        if scaffold_smiles:candidates=live_candidates(scaffold_smiles)
    if not scaffold_smiles and len(records)>1:
        # A depiction-only core: preserve a complete ring/linker framework from
        # an input, never a guessed MCS or a chemical transformation. Match every
        # graph with chirality before using it; do not infer scope categories.
        from rdkit.Chem.Scaffolds import MurckoScaffold
        mols=[parse(r['canonical_smiles']) for r in records]
        cores=[MurckoScaffold.GetScaffoldForMol(m) for m in mols]
        cores.sort(key=lambda m:(-m.GetNumAtoms(),Chem.MolToSmiles(m)))
        for core in cores:
            if core.GetNumHeavyAtoms()>=6 and all(m.HasSubstructMatch(core,useChirality=True) for m in mols):
                scaffold_smiles=Chem.MolToSmiles(core)
                candidates=live_candidates(scaffold_smiles)
                break
    if len(candidates)==1:
        reference,scaffold_smiles=candidates[0];reference_source='live_document'
        rr=ET.fromstring(reference);ff=rr.find('page/fragment')
        transform(ff,scale=float(spec['BondLength'])/statistics.median(bond_lengths(ff)))
        rr.set('BondLength',str(spec['BondLength']));reference=ET.tostring(rr,encoding='unicode')
    fragments=[];orientations=[]
    for record in records:
        if reference is not None and scaffold_smiles:
            block,_=seed_from_native_scaffold(record['canonical_smiles'],reference,scaffold_smiles)
            mol=Chem.MolFromMolBlock(block,removeHs=False)
            orientation={'policy':'reference_preserved','rotation_degrees':0.0}
        else:
            mol=parse(record['canonical_smiles']);rdDepictor.Compute2DCoords(mol)
            from .drawing_orientation import orient_new_molecule
            orientation=orient_new_molecule(mol)
        orientations.append({'compound_id':record['compound_id'],**orientation})
        seed=ET.fromstring(Chem.MolToCDXMLBlock(mol));fragment=seed.find('page/fragment')
        start=max([int(e.get('id')) for e in root.iter() if e.get('id')]+[1])+1
        ids={e.get('id'):str(start+j) for j,e in enumerate(fragment.iter()) if e.get('id')}
        for e in fragment.iter():
            for key in ('id','B','E'):
                if e.get(key) in ids:e.set(key,ids[e.get(key)])
        transform(fragment,scale=float(spec['BondLength'])/statistics.median(bond_lengths(fragment)))
        # Writer atom order is checked against the complete graph below. Labels
        # are explicit so the target's ACS defaults cannot shrink new atoms.
        for node,atom in zip(fragment.findall('n'),mol.GetAtoms()):
            node.set('NumHydrogens',str(atom.GetTotalNumHs()))
            node.set('LabelFont',font);node.set('LabelSize',str(spec['LabelSize']))
            if atom.GetAtomicNum()!=6 or atom.GetIsotope() or atom.GetFormalCharge():
                label=atom.GetSymbol();h=atom.GetTotalNumHs()
                if h:label+='H'+(str(h) if h>1 else '')
                charge=atom.GetFormalCharge()
                if charge:label+=(str(abs(charge)) if abs(charge)>1 else '')+('+' if charge>0 else '-')
                t=ET.SubElement(node,'t',p=node.get('p'))
                if atom.GetIsotope():
                    ET.SubElement(t,'s',font=font,size=str(spec['LabelSize']),face='64').text=str(atom.GetIsotope())
                ET.SubElement(t,'s',font=font,size=str(spec['LabelSize']),face='96').text=label
        for bond in fragment.findall('b'):
            for key in ('LineWidth','BoldWidth'):bond.set(key,str(spec[key]))
            bond.set('BondSpacing','18')
        # Carbon vertices need stroke clearance, not an imaginary atom label.
        # Actual ChemDraw glyph boxes are checked after insertion.
        envelopes=[]
        for n in fragment.findall('n'):
            x,y=map(float,n.get('p').split());label=''.join(n.itertext())
            px=py=float(spec['LineWidth'])+1
            if label:
                size=float(spec['LabelSize']);extra=len(n.get('Isotope',''))+(1 if n.get('Charge') else 0)
                px=max(size*.65,size*(len(label)+extra)*.72)
                py=size*(1.5 if int(n.get('NumHydrogens','0')) else 1)
            envelopes.append((x-px,y-py,x+px,y+py))
        bb=(min(b[0] for b in envelopes),min(b[1] for b in envelopes),max(b[2] for b in envelopes),max(b[3] for b in envelopes))
        fragment.set('BoundingBox',' '.join(map(str,bb)))
        probe=copy.deepcopy(root);pp=probe.find('page');pp.append(copy.deepcopy(fragment))
        if chemical_signature(ET.tostring(probe,encoding='unicode'))!=[record['canonical_smiles']]:
            raise ValueError('CDXML writer did not preserve requested chemistry')
        fragments.append(fragment)
        if reference is None and scaffold_smiles:
            reference=ET.tostring(probe,encoding='unicode');rr=ET.fromstring(reference)
            rr.set('BondLength',str(spec['BondLength']));reference=ET.tostring(rr,encoding='unicode')
            reference_source='first_requested_structure'
    cap=float(spec['CaptionSize']);gap=18.
    cellw=max(max(bounds(f).width,len(r['label'])*cap*.65) for f,r in zip(fragments,records))+gap
    structure_height=max(bounds(f).height for f in fragments)
    cellh=structure_height+cap*3+gap
    selected=None
    for cols in range(min(columns or 4,len(records)),0,-1):
        for e in list(page):page.remove(e)
        counter=max([int(e.get('id')) for e in target.iter() if e.get('id')]+[1])+1
        for i,(f,r) in enumerate(zip(fragments,records)):
            f=copy.deepcopy(f);box=bounds(f);x=(i%cols)*cellw;y=(i//cols)*cellh
            transform(f,dx=x+(cellw-gap-box.width)/2-box.left,
                      dy=y+(structure_height-box.height)/2-box.top)
            mapping={e.get('id'):str(counter+j) for j,e in enumerate(f.iter()) if e.get('id')}
            counter+=len(list(f.iter()))
            for e in f.iter():
                for key in ('id','B','E'):
                    if e.get(key) in mapping:e.set(key,mapping[e.get(key)])
            page.append(f)
            label=r['label']
            # IDs are internal provenance, not a second caption line.
            width=len(label)*cap*.65;cx=x+(cellw-gap)/2;cy=y+cellh-gap-cap
            t=ET.SubElement(page,'t',id=str(counter),p=f'{cx} {cy}',
                BoundingBox=f'{cx-width/2} {cy-cap} {cx+width/2} {cy+cap*.3}',
                Justification='Center',InterpretChemically='no')
            counter+=1;ET.SubElement(t,'s',font=font,size=str(cap)).text=label
        text=ET.tostring(root,encoding='unicode')
        try:selected=plan_append(before,text)
        except ValueError:continue
        # The first cell may be narrower than a later cell. Placement is the
        # envelope's destination, not a translation from the coordinate origin.
        left=min(bounds(e).left for e in page);top=min(bounds(e).top for e in page)
        for e in page:transform(e,dx=selected['left']-left,dy=selected['top']-top)
        break
    pages_added=0
    if selected is None and allow_page_expansion:
        extent=bounds(oldpage);old_n=int(oldpage.get('HeightPages','1'))
        sheet_h=extent.height/old_n
        cols=min(columns or 4,len(records),int((extent.width-48+gap)//cellw))
        rows=int((sheet_h-48)//cellh)
        if cols<1 or rows<1:raise ValueError('A table cell cannot fit the physical paper at this chemical scale')
        first=old_n if len(oldpage) else 0
        count=first+math.ceil(len(records)/(rows*cols))
        if count>20:raise ValueError('Table exceeds 20 physical pages')
        # Reuse the complete, validated batch. Every sheet has identical column
        # centres, row pitch, chemical scale and caption baselines.
        for i,(f,t) in enumerate(zip(page.findall('fragment'),page.findall('t'))):
            local=i%(rows*cols);sheet=first+i//(rows*cols)
            x=extent.left+24+(local%cols)*cellw
            y=extent.top+sheet*sheet_h+24+(local//cols)*cellh
            b=bounds(f)
            transform(f,dx=x+(cellw-gap)/2-b.center[0],dy=y+structure_height/2-b.center[1])
            tx,ty=map(float,t.get('p').split())
            transform(t,dx=x+(cellw-gap)/2-tx,dy=y+cellh-gap-cap-ty)
        page.set('HeightPages',str(count));page.set('WidthPages','1')
        page.set('BoundingBox',f'{extent.left:g} {extent.top:g} {extent.right:g} {extent.top+sheet_h*count:g}')
        pages_added=count-old_n;selected=True
    if selected is None:
        from .harness import NeedsInput
        raise NeedsInput('table_needs_space',
            'The complete table does not fit the free page space. Nothing was inserted. '
            'Automatic enlargement of the existing ChemDraw canvas is not supported yet.',
            requested_count=len(records),inserted_count=0,same_document_required=True,
            next_action='Keep the complete table together. Do not retry in smaller batches, '
            'omit molecules, shrink the chemical scale, or open a second document. '
            'The existing document needs more drawing space before the complete request can be retried.')
    return ET.tostring(root,encoding='unicode'),{'count':len(records),'columns':cols,'pages_added':pages_added,
        'scaffold_smiles':scaffold_smiles,'reference_source':reference_source,'preset':preset,'orientations':orientations,
        'coordinate_source':'RDKit constrained depiction and ChemDraw CDXML writer'}


def center_measured_payload(payload, measured):
    """Translate using native ink bearings, never alter chemistry or scale."""
    from .workflow import remap_ids
    from .batch import _verify
    _verify(payload,measured)
    mapping=remap_ids(payload,measured)
    root=ET.fromstring(payload);native=ET.fromstring(measured).find('page')
    expected={'structures':[],'captions':[]}
    for obj in root.find('page'):
        n=next(e for e in native if e.get('id')==mapping[obj.get('id')])
        ink=bounds(n)
        if obj.tag=='fragment':
            x,y=bounds(obj).center
            obj.set('BoundingBox',n.get('BoundingBox'))
            transform(obj,dx=x-ink.center[0],dy=y-ink.center[1])
            expected['structures'].append({'id':obj.get('id'),'x':x,'y':y})
        else:
            x,y=map(float,obj.get('p').split())
            obj.set('BoundingBox',n.get('BoundingBox'))
            transform(obj,dx=x-ink.center[0])
            expected['captions'].append({'id':obj.get('id'),'x':x,'baseline':y})
    return ET.tostring(root,encoding='unicode'),expected


def measure_table_payload(bridge,payload):
    """One hidden native measuring copy for the complete table, not per cell."""
    created=bridge.create(payload,visible=False)
    did=created['document']['document_id']
    snapshot=bridge._new_path('.cdxml','backups')
    # On uncertain native operations retain the copy and stop. Never retry.
    bridge.export(did,str(snapshot),'cdxml')
    corrected,expected=center_measured_payload(payload,snapshot.read_text())
    bridge.close(did)
    return corrected,expected


def verify_table_centres(payload,native,expected):
    from .workflow import remap_ids
    mapping=remap_ids(payload,native);page=ET.fromstring(native).find('page')
    for key in ('structures','captions'):
        for item in expected[key]:
            obj=next(e for e in page if e.get('id')==mapping[item['id']])
            ink=bounds(obj)
            if abs(ink.center[0]-item['x'])>.75:raise ValueError('Native horizontal table centering failed')
            if key=='structures' and abs(ink.center[1]-item['y'])>.75:raise ValueError('Native vertical table centering failed')
            if key=='captions' and abs(float(obj.get('p').split()[1])-item['baseline'])>.05:raise ValueError('Native caption baseline failed')


def run_api_drawing(bridge,plan,out,document_id=None):
    from pathlib import Path
    from .harness import NeedsInput
    from .workflow import _write_json
    from .timing import StageTimer
    timer=StageTimer()
    export_mode=plan.get('exports','full')
    if export_mode not in ('preview','full','canvas'):
        raise ValueError('exports must be preview, full or canvas')
    if plan.get('workflow','molecules')!='molecules' or plan.get('groups') is not None:
        raise NeedsInput('unsupported_shared_objects','Direct API insertion currently supports plain molecule batches, not decorated groups or reactions. Those require an explicitly requested separate workflow. No drawing was changed.')
    if plan.get('charge_style','plain')!='plain' or plan.get('layout') is not None or isinstance(plan.get('preset'),dict):
        raise NeedsInput('unsupported_shared_options','Direct API batches currently support plain charges, automatic grid placement, and house or ACS presets. Custom layout/style and circled charges require a separate explicit workflow. No drawing was changed.')
    docs=bridge.documents()['documents']
    if document_id is None:
        if not docs:
            # One working canvas, never one seed window per molecule.
            created=bridge.create('<CDXML BondLength="18"><page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"/></CDXML>',visible=True)
            document_id=created['document']['document_id']
        else:document_id=bridge._run('active_document')
    elif not any(d['document_id']==document_id for d in docs):
        raise ValueError('Shared document is absent; refresh document IDs')
    did=bridge._id(document_id);backend=get_backend(bridge);initial=backend.read(did)
    timer.mark('document_read')
    try:
        if ET.fromstring(initial['cdxml']).find('page/fragment') is not None:
            chemical_signature(initial['cdxml'])
    except ValueError as exc:
        raise ValueError('Existing content cannot be verified before insertion: '+str(exc)+
            '. Earlier chemically interpreted captions must be corrected or removed in ChemDraw first; no new objects were added.') from exc
    payload,planning=plan_addition(initial['cdxml'],plan['structures'],preset=plan.get('preset','house'),
        columns=plan.get('columns'),scaffold_smiles=plan.get('scaffold_smiles'),allow_page_expansion=plan.get('page_policy','add_pages')=='add_pages')
    timer.mark('layout')
    expected_centres=None
    if len(plan['structures'])>1:
        payload,expected_centres=measure_table_payload(bridge,payload)
        # The hidden measuring document is closed before targeting the original.
        fresh=backend.read(did)
        if fresh['source_token']!=initial['source_token']:raise ValueError('Source changed during table measurement; nothing appended')
        planning['layout_measurement']='native ink; one hidden measuring copy'
        timer.mark('native_table_measurement')
    out=Path(out);out.mkdir()
    (out/'before.cdxml').write_text(initial['cdxml']);(out/'payload.cdxml').write_text(payload)
    _write_json(out/'request.json',plan)
    try:
        page_options={'allow_page_expansion':True} if planning['pages_added'] or int(ET.fromstring(payload).find('page').get('HeightPages','1'))>1 else {}
        result=backend.append(did,payload,initial['source_token'],**page_options)
        timer.mark('append_and_verify')
    except Exception as exc:
        _write_json(out/'audit.json',{'status':'not_completed','message':str(exc),'planning':planning})
        raise
    figure=out/'figure';figure.mkdir()
    path=figure/'figure.cdxml';native=Path(result['after_snapshot']).read_text();path.write_text(native)
    from .workflow import remap_ids
    from .batch import NativeUncertain
    try:
        old=ET.fromstring(initial['cdxml']).find('page')
        existing=set(remap_ids(initial['cdxml'],native).values()) if len(old) else set()
        added=ET.fromstring(native);ap=added.find('page')
        for e in list(ap):
            if e.get('id') in existing:ap.remove(e)
        verify_style(ET.tostring(added,encoding='unicode'),plan.get('preset','house'))
        result['checks']['new_object_style_verified']=True
        if expected_centres:
            verify_table_centres(payload,ET.tostring(added,encoding='unicode'),expected_centres)
            result['checks']['native_table_centres_and_baselines_verified']=True
        timer.mark('style_and_layout_verify')
    except Exception as exc:
        _write_json(out/'audit.json',{'status':'uncertain','message':str(exc),'document_id':did})
        raise NativeUncertain('API append occurred but native style verification failed: '+str(exc)) from exc
    artifacts={'cdxml':str(path)}
    if export_mode!='canvas':
        try:
            svg=figure/'figure.svg'
            bridge.export(did,str(svg),'svg')
            timer.mark('native_svg_export')
            from .raster import rasterize_svg
            if export_mode=='preview':
                png=figure/'preview.png'
                png.write_bytes(rasterize_svg(svg.read_text(),1200,background='white'))
                artifacts['preview']=str(png)
            else:
                png=figure/'figure.png'
                png.write_bytes(rasterize_svg(svg.read_text(),plan.get('pixels',3200)))
                artifacts['png']=str(png)
            timer.mark('rasterize')
            fresh=backend.read(did)
            verify_export_snapshot(native,fresh['cdxml'])
            path.write_text(fresh['cdxml'])
            result['source_token']=fresh['source_token']
            result['checks']['native_svg_export']=True
            artifacts['svg']=str(svg)
            timer.mark('export_verify')
        except Exception as exc:
            _write_json(out/'audit.json',{'status':'uncertain','message':str(exc),'document_id':did,'timings':timer.report()})
            raise NativeUncertain('Drawing inserted; export did not complete. Do not draw it again: '+str(exc)) from exc
    timings=timer.report()
    result.update(stage='delivery',output_dir=str(out),artifacts=artifacts,visual_review='required',
        timings=timings,delivery={'mode':export_mode,'export_tool':'chemdraw_export_figure',
            'note':'Preview is for visual review, not a physical-scale publication export.' if export_mode=='preview' else
                   'No image export requested; inspect the editable ChemDraw canvas.' if export_mode=='canvas' else
                   'Full transparent image bundle; use export_figure for a specified physical scale.'},
        presentation={'mode':'shared','intermediates':'one hidden native measuring copy' if expected_centres else 'none'},planning=planning,
        audit={'status':'checks_passed','checks':result['checks'],'timings':timings},
        note='Appended once to the existing working document. CDXML artifact contains the whole current canvas.')
    _write_json(out/'audit.json',result['audit']);_write_json(out/'result.json',result)
    return result


def verify_style(text,preset):
    from .core import preset_settings
    spec=preset_settings(preset);root=ET.fromstring(text)
    fonts={f.get('id'):f.get('name') for f in root.findall('fonttable/font')}
    for f in root.findall('page/fragment'):
        if abs(statistics.median(bond_lengths(f))-float(spec['BondLength']))>.03:
            raise ValueError('Native style bond length differs')
        for b in f.findall('b'):
            for key in ('LineWidth','BoldWidth'):
                if abs(float(b.get(key,root.get(key,'0')))-float(spec[key]))>.03:
                    raise ValueError('Native style differs: '+key)
        for s in f.findall('.//n/t/s'):
            if fonts.get(s.get('font',root.get('LabelFont')))!=spec['font'] or abs(float(s.get('size',root.get('LabelSize','0')))-float(spec['LabelSize']))>.03:
                raise ValueError('Native style atom typography differs')
    for s in root.findall('page/t/s'):
        if fonts.get(s.get('font',root.get('CaptionFont')))!=spec['font'] or abs(float(s.get('size',root.get('CaptionSize','0')))-float(spec['CaptionSize']))>.03:
            raise ValueError('Native style caption typography differs')
    return True


def verify_export_snapshot(before,after):
    from .shared import fingerprint
    from .batch import _verify
    _verify(before,after)
    def stripped(text):
        root=ET.fromstring(text)
        for e in root.iter():
            if e.tag=='n':e.attrib.pop('AS',None)
            if e.tag=='b':e.attrib.pop('BS',None)
        return fingerprint(ET.tostring(root,encoding='unicode'))
    if stripped(before)!=stripped(after):raise ValueError('Document changed during export')
