"""Batch explicit reactions locally, then measure and render with ChemDraw.

No per-participant native imports, cleanup, mouse actions or inferred chemistry.
The new drawing has real paper dimensions, independent of existing documents.
"""
from contextlib import nullcontext
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from .batch import _native, _document_content, _verify, NativeUncertain
from .core import style_cdxml
from .polish import chemical_signature
from .reaction_series import prepare_steps, compose_series, arrange_series, remap_series, verify_series
from .workflow import remap_ids, _write_json
from .timing import StageTimer


PAPERS = {'A4 portrait': (595,842), 'A4 landscape': (842,595),
          'A3 landscape': (1191,842)}
EMPTY = '<CDXML><page id="1" BoundingBox="0 0 2400 2400" WidthPages="1" HeightPages="1"/></CDXML>'


def _orient_nitro_seed(root):
    """Rigidly orient one explicit C-N(=O)-O nitro group away from N+ ink.

    Only fresh seeds are eligible. No atom moves relative to another, and no
    reflection, scale change, charge edit or stereochemical inference is made.
    """
    f=root.find('page/fragment');nodes={n.get('id'):n for n in f.findall('n')};anchors=[]
    for n in nodes.values():
        if n.get('Element')!='7' or n.get('Charge')!='1':continue
        bonds=[b for b in f.findall('b') if n.get('id') in (b.get('B'),b.get('E'))]
        adjacent=[(nodes[b.get('E') if b.get('B')==n.get('id') else b.get('B')],b) for b in bonds]
        oxy=[(a,b) for a,b in adjacent if a.get('Element')=='8']
        carbon=[a for a,b in adjacent if a.get('Element','6')=='6' and b.get('Order','1')=='1']
        if len(adjacent)==3 and len(oxy)==2 and len(carbon)==1 and sorted(b.get('Order','1') for a,b in oxy)==['1','2'] and any(a.get('Charge')=='-1' for a,b in oxy):
            anchors.append((n,carbon[0]))
    if len(anchors)!=1:return
    n,c=anchors[0];x,y=map(float,n.get('p').split());u,v=map(float,c.get('p').split())
    angle=-math.atan2(v-y,u-x);cosine,sine=math.cos(angle),math.sin(angle)
    boxes=[];size=float(root.get('LabelSize','14'))
    for node in nodes.values():
        u,v=map(float,node.get('p').split());u,v=cosine*(u-x)-sine*(v-y),sine*(u-x)+cosine*(v-y)
        node.set('p',f'{u:.6f} {v:.6f}')
        for t in node.findall('t'):t.set('p',node.get('p'))
        pad=size*max(1,len(''.join(node.itertext())))
        boxes.append((u-pad,v-size*2,u+pad,v+size*2))
    f.set('BoundingBox',' '.join(map(str,(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)))))


def set_paper(text, name):
    """ChemDraw 23 TPrint layout, calibrated on native blank-document exports.

    The old SDK's -3 orientation-only stub falls back to portrait on this Mac.
    Populate both print-info records and the native device/job defaults instead.
    All dimensions are points; the twelve-point printer border is not a scale.
    """
    w,h=PAPERS[name];root=ET.fromstring(text)
    record=[0]*60;record[0]=3;record[2:4]=[72,72]
    record[4:8]=[0,0,h-24,w-24];record[8:12]=[-12,-12,h-12,w-12]
    record[12:16]=[871 if h>w else 869,round(max(w,h)*120/72),round(min(w,h)*120/72),2]
    record[17:23]=record[2:8]
    for index,value in {23:1,25:100,27:1,28:1,29:257,31:1,32:9999,33:1,34:1,
                        41:2,42:25,43:400,46:64,51:1}.items():record[index]=value
    root.set('MacPrintInfo',struct.pack('>60h',*record).hex().upper())
    root.set('PrintMargins','0 0 0 0')
    page=root.find('page');page.set('BoundingBox',f'0 0 {w} {h}')
    page.set('WidthPages','1');page.set('HeightPages','1')
    return ET.tostring(root,encoding='unicode')


def _components(prepared,preset):
    from rdkit import Chem
    from .api_drawing import plan_addition
    from .reaction_series import _alkali_seed
    from .core import preset_settings
    result={};spec=preset_settings(preset)
    for step in prepared:
        for participant in step['reactants']+step['products']:
            for component in participant['components']:
                smi=component['canonical_smiles']
                if smi in result:continue
                mol=Chem.MolFromSmiles(smi)
                if mol.GetNumAtoms()>1:
                    text,_=plan_addition(style_cdxml(EMPTY,preset),[
                        {'compound_id':'component','label':'Component','smiles':smi}],preset=preset)
                    root=ET.fromstring(text);page=root.find('page')
                    for t in list(page.findall('t')):page.remove(t)
                    _orient_nitro_seed(root)
                elif mol.GetAtomWithIdx(0).GetAtomicNum() in (11,19):
                    atom=mol.GetAtomWithIdx(0)
                    root=ET.fromstring(style_cdxml(_alkali_seed(atom.GetAtomicNum(),atom.GetSymbol()),preset))
                else:
                    atom=mol.GetAtomWithIdx(0);h=atom.GetTotalNumHs();q=atom.GetFormalCharge()
                    root=ET.fromstring(style_cdxml(EMPTY,preset));page=root.find('page')
                    size=float(spec['LabelSize']);font=root.get('LabelFont')
                    f=ET.SubElement(page,'fragment',id='2',BoundingBox=f'0 0 {size*3} {size*2}')
                    n=ET.SubElement(f,'n',id='3',p=f'{size} {size}',Element=str(atom.GetAtomicNum()),NumHydrogens=str(h))
                    if q:n.set('Charge',str(q))
                    t=ET.SubElement(n,'t',p=n.get('p'))
                    label=atom.GetSymbol()+('H'+(str(h) if h>1 else '') if h else '')+('+' if q>0 else '-' if q<0 else '')
                    ET.SubElement(t,'s',font=font,size=str(size),face='96').text=label
                for t in root.findall('page/t'):t.set('InterpretChemically','no')
                for t in root.findall('.//n[@Charge]/t'):
                    t.set('LabelJustification','Best');t.set('LabelAlignment','Best')
                text=ET.tostring(root,encoding='unicode')
                if chemical_signature(text)!=[smi]:raise ValueError('Reaction seed changed explicit chemistry')
                result[smi]=text
    return result


def _space_error(detail,paper):
    from .harness import NeedsInput
    return NeedsInput('reaction_needs_space',
        'The complete reaction does not fit the selected physical paper at the requested chemical scale.',
        native_write_attempted=False, paper=paper, detail=str(detail),
        next_action='Choose a larger reaction_paper or report this layout limit. Do not use mouse control, '
        'remove participants, shorten supplied labels, shrink molecules, or retry the same request.')


def plan_reaction_batch(steps,preset='house',paper='auto'):
    if paper!='auto' and paper not in PAPERS:raise ValueError('Unsupported reaction paper')
    prepared=prepare_steps(steps);components=_components(prepared,preset)
    last=None
    for name in PAPERS if paper=='auto' else [paper]:
        try:
            text,plan=compose_series({s:set_paper(t,name) for s,t in components.items()},prepared,preset,text_width_factor=.6)
        except ValueError as exc:
            if 'fit' not in str(exc) and 'overflow' not in str(exc):raise
            last=exc;continue
        root=ET.fromstring(text)
        for t in root.findall('page/t'):t.set('InterpretChemically','no')
        plan['paper']={'name':name,'width_pt':PAPERS[name][0],'height_pt':PAPERS[name][1]}
        return ET.tostring(root,encoding='unicode'),plan
    raise _space_error(last,paper)


def _measured_layout(text,plan,paper):
    last=None
    for name in PAPERS if paper=='auto' else [paper]:
        try:arranged,result=arrange_series(set_paper(text,name),plan)
        except ValueError as exc:
            if 'fit' not in str(exc) and 'overflow' not in str(exc):raise
            last=exc;continue
        result['paper']={'name':name,'width_pt':PAPERS[name][0],'height_pt':PAPERS[name][1]}
        return arranged,result
    raise ValueError('Native measured reaction exceeds available paper: '+str(last))


def _verify_paper(text,paper):
    root=ET.fromstring(text)
    try:record=struct.unpack('>60h',bytes.fromhex(root.get('MacPrintInfo','')))
    except (ValueError,struct.error) as exc:raise ValueError('Missing native physical paper record') from exc
    if (record[2:4]!=(72,72) or record[25]!=100 or
        record[11]-record[9]!=paper['width_pt'] or record[10]-record[8]!=paper['height_pt']):
        raise ValueError('Native physical paper or print scale changed')


def run_reaction_batch(bridge,steps,out,*,preset='house',paper='auto',presentation='background'):
    from .api_drawing import verify_export_snapshot
    from .raster import rasterize_svg
    from .physical_export import physical_svg,physical_png
    from .styles import require_style_fonts,verify_custom_style
    from .placement import collision_pairs
    if presentation not in ('auto','background','interactive'):raise ValueError('Reactions require a separate output document')
    out=Path(out)
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires an absolute new folder with existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    timer=StageTimer()
    require_style_fonts(preset)
    planned,plan=plan_reaction_batch(steps,preset,paper)
    timer.mark('local_reaction_preflight')
    owned=[];audit={'status':'in_progress','checks':{},'visual_review':'required'}
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents)['documents']
        original={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline}
        out.mkdir();(out/'planned.cdxml').write_text(planned)
        _write_json(out/'request.json',{'steps':steps,'preset':preset,'reaction_paper':paper})
        try:
            created=_native(bridge.create,planned,visible=False);did=created['document']['document_id'];owned.append(did)
            snap=out/'measured.cdxml';_native(bridge.export,did,str(snap),'cdxml')
            native=snap.read_text();_verify(planned,native)
            recipe=remap_series(plan,remap_ids(planned,native))
            arranged,plan=_measured_layout(native,recipe,paper)
            _native(bridge.close,did);owned.remove(did)
            timer.mark('native_batch_measurement')
            (out/'arranged.cdxml').write_text(arranged);_write_json(out/'recipe.json',plan)
            created=_native(bridge.create,arranged,visible=False);did=created['document']['document_id'];owned.append(did)
            figure=out/'figure';figure.mkdir();cdxml=figure/'figure.cdxml'
            _native(bridge.export,did,str(cdxml),'cdxml');native=cdxml.read_text()
            verification=verify_series(arranged,native,plan)
            _verify_paper(native,plan['paper'])
            verify_custom_style(arranged,native,preset)
            collisions=collision_pairs(native,measured=True)
            if collisions:raise ValueError('Delivered placement collision candidates: '+repr(sorted(collisions)[:8]))
            verification['checks'].update(native_style=True,no_placement_collision_candidates=True,physical_paper=True)
            timer.mark('native_layout_verification')
            svg=figure/'figure.svg';_native(bridge.export,did,str(svg),'svg')
            raw_svg=svg.read_text()
            (figure/'figure.png').write_bytes(physical_png(raw_svg,600))
            (figure/'preview.png').write_bytes(rasterize_svg(svg.read_text(),1200,background='white'))
            svg.write_text(physical_svg(raw_svg)[0])
            post=out/'post-export.cdxml';_native(bridge.export,did,str(post),'cdxml')
            verify_export_snapshot(native,post.read_text())
            _native(bridge.close,did);owned.remove(did)
            current=_native(bridge.documents)['documents']
            if sorted(current,key=lambda d:d['document_id'])!=sorted(baseline,key=lambda d:d['document_id']):
                raise ValueError('Pre-existing document inventory changed')
            for oid,before in original.items():
                if _document_content(bridge,oid)!=before:raise ValueError('Pre-existing document content changed')
            timer.mark('export_and_preservation')
            checks={**verification['checks'],'preexisting_documents_unchanged':True,'native_svg_export':True,'working_content_unchanged':True}
            audit.update(status='checks_passed',checks=checks,verification=verification,timings=timer.report())
            result={'status':'completed','stage':'delivery','artifacts':{fmt:str(figure/('preview.png' if fmt=='preview' else 'figure.'+fmt)) for fmt in ('cdxml','svg','png','preview')},
                'checks':checks,'audit':audit,'planning':plan,'timings':timer.report(),'visual_review':'required',
                'document':created['document'],'document_closed':True,
                'presentation':{'mode':'background','intermediates':'one whole-reaction measuring document'},
                'note':'Native desktop rendering, not display-free. No per-participant imports or mouse control. Original documents are unchanged.'}
            if presentation=='interactive':
                shown=_native(bridge.create,native,visible=False);shown_id=shown['document']['document_id'];owned.append(shown_id)
                check=out/'presented.cdxml';_native(bridge.export,shown_id,str(check),'cdxml')
                _verify(native,check.read_text())
                _native(bridge.set_visibility,shown_id,True)
                result.update(document=shown['document'],document_closed=False,presentation={'mode':'interactive','intermediates':'one whole-reaction measuring document'})
            _write_json(out/'audit.json',audit);_write_json(out/'result.json',result)
            return result
        except NativeUncertain as exc:
            audit.update(status='uncertain',message=str(exc),owned_document_ids=owned)
            _write_json(out/'audit.json',audit)
            raise
        except Exception as exc:
            audit.update(status='failed',message=str(exc))
            _write_json(out/'audit.json',audit)
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',message=str(closing),owned_document_ids=owned)
                    _write_json(out/'audit.json',audit);raise
            raise
