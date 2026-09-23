"""Bounded native symbol graphics, without changing atom chemistry."""
from contextlib import nullcontext
import copy
import hashlib
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from . import annotations as ann
from .core import validate_cdxml
from .editing import source_token
from .polish import numbers
from .batch import _native, NativeUncertain
from .workflow import _file_hash, _write_json
from .native_lock import native_transaction

DOTS={'LonePair','Electron'}
KINDS={'charge':None,'lone_pair':'LonePair','electron':'Electron'}


def _split(text):
    root=validate_cdxml(text);clean=copy.deepcopy(root);dots=[]
    for f in clean.findall('page/fragment'):
        for g in f.findall('graphic'):
            if ann._symbol_kind(g) not in DOTS:continue
            ann._validate_dot(g,f,clean)
            dots.append((f.get('id'),g));f.remove(g)
    ann._root(ET.tostring(clean,encoding='unicode'))
    return root,ET.tostring(clean,encoding='unicode'),dots


def verify_symbols(expected,native):
    old,a,ds=_split(expected);new,b,ns=_split(native)
    result=ann.verify_annotations(a,b);mapping=result['id_map'];used=set()
    if len(ds)!=len(ns):raise ValueError('Native electron symbol count changed')
    for fid,g in ds:
        hits=[n for nf,n in ns if nf==mapping[fid] and n.get('id') not in used
              and n.get('SymbolType')==g.get('SymbolType') and n.get('GraphicType')==g.get('GraphicType') and n.get('OvalType')==g.get('OvalType')
              and ann._close_numbers(g.get('BoundingBox'),n.get('BoundingBox'))
              and all(ann._close_numbers(g.get(k),n.get(k)) for k in ('Center3D','MajorAxisEnd3D','MinorAxisEnd3D') if g.get('GraphicType')=='Oval')
              and ann._close_numbers(g.get('LineWidth',old.get('LineWidth','.6')),n.get('LineWidth',new.get('LineWidth','.6')))
              and len(g)==len(n) and (not len(g) or n[0].get('object')==mapping[g[0].get('object')])
              and g.get('color',old.get('color','0'))==n.get('color',new.get('color','0')) and g.get('bgcolor',old.get('bgcolor','1'))==n.get('bgcolor',new.get('bgcolor','1'))]
        if len(hits)!=1:raise ValueError('Native electron symbol geometry, style or ownership changed')
        mapping[g.get('id')]=hits[0].get('id');used.add(hits[0].get('id'))
    result['checks']['symbol_geometry_preserved']=True
    return result


def symbol_inventory(text):
    root,clean,_=_split(text);verify_symbols(text,text)
    result=ann.annotation_inventory(clean);result['source_token']=source_token(text)
    result['symbols']=[{'id':g.get('id'),'kind':ann._symbol_kind(g),'native_graphic_type':g.get('GraphicType'),'geometry_pt':list(numbers(g.get('BoundingBox'),4)),
        'atom_id':g[0].get('object') if len(g) else None} for g in root.findall('page/fragment/graphic')]
    return result


@native_transaction
def inspect_symbols_document(bridge,document_id):
    snapshot=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(snapshot),'cdxml')
    return {**symbol_inventory(snapshot.read_text()),'snapshot':str(snapshot),'document':_native(bridge.inspect,document_id)['document']}


def _distance_segment(p,a,b):
    v=(b[0]-a[0],b[1]-a[1]);den=v[0]**2+v[1]**2
    t=max(0,min(1,((p[0]-a[0])*v[0]+(p[1]-a[1])*v[1])/den)) if den else 0
    return math.dist(p,(a[0]+t*v[0],a[1]+t*v[1]))


def symbol_primitives(g,default_line_width=.6):
    """Visible circles calibrated from native 23.0.1 SVG probes (±0.03 pt)."""
    if g.get('GraphicType')=='Oval':
        c=numbers(g.get('Center3D'),3);m=numbers(g.get('MajorAxisEnd3D'),3)
        return [(c[0],c[1],m[0]-c[0])]
    x,y,hx,hy=numbers(g.get('BoundingBox'),4);span=math.hypot(hx-x,hy-y)
    if span<=0:raise ValueError('Symbol handle span must be positive')
    kind=g.get('SymbolType')
    if kind in ('CirclePlus','CircleMinus'):
        return [(x,y,span*4/9+.8*float(g.get('LineWidth',default_line_width)))]
    if kind=='LonePair':return [(x,y,span*2/9),(hx,hy,span*2/9)]
    if kind=='Electron':return [(x,y,span/9)]
    raise ValueError('Unsupported native symbol geometry')


def symbol_source_edge(g,tangent,default_line_width=.6):
    length=math.hypot(*tangent)
    if length<.1:raise ValueError('Symbol source requires a nonzero departure tangent')
    dx,dy=(tangent[0]/length,tangent[1]/length)
    # A pair consists of TWO circles. Select the one furthest in the departure
    # direction, never place the tail in the empty space between those dots.
    x,y,r=max(symbol_primitives(g,default_line_width),key=lambda p:p[0]*dx+p[1]*dy+p[2])
    return x+r*dx,y+r*dy


def _replace_charge_suffix(atom,charge):
    """Transfer only a redundant terminal elemental-label charge to its glyph."""
    from rdkit import Chem
    label=atom.find('t')
    if label is None:return
    runs=label.findall('s');text=''.join(run.text or '' for run in runs)
    if '+' not in text and '-' not in text:return
    element=Chem.GetPeriodicTable().GetElementSymbol(int(atom.get('Element','6')))
    sign='+' if charge==1 else '-'
    if not re.fullmatch(re.escape(element)+r'(?:H[0-9]*)?'+re.escape(sign),text):
        raise ValueError('Cannot safely transfer a noncanonical chemical charge label to a circled symbol')
    last=next(run for run in reversed(runs) if run.text)
    last.text=last.text[:-1]
    if not last.text:label.remove(last)


def _placement_obstacles(root):
    page=root.find('page');bounds=numbers(page.get('BoundingBox'),4)
    atoms={n.get('id'):n for n in root.findall('page/fragment/n')}
    positions={k:numbers(n.get('p'),2) for k,n in atoms.items()}
    parents={child:parent for parent in root.iter() for child in parent}
    def inherited(e,key,default):
        while e is not None:
            if e.get(key) is not None:return float(e.get(key))
            e=parents.get(e)
        return default
    boxes=[];segments=[]
    for t in root.findall('page/fragment/n/t')+root.findall('page/t'):
        if not t.get('BoundingBox'):raise ValueError('Native measured label bounds required before symbol placement')
        x,y,xx,yy=numbers(t.get('BoundingBox'),4);boxes.append((min(x,xx),min(y,yy),max(x,xx),max(y,yy)))
    for b in root.findall('page/fragment/b'):
        a,e=positions[b.get('B')],positions[b.get('E')];width=inherited(b,'LineWidth',.6)/2
        if b.get('Order','1') in ('2','3','1.5'):width+=math.dist(a,e)*inherited(b,'BondSpacing',18)/100
        if 'Wedge' in b.get('Display','') or 'Wedged' in b.get('Display',''):width=max(width,inherited(b,'BoldWidth',2))
        segments.append((a,e,width))
    for obj in list(page.findall('arrow'))+list(page.findall('curve')):
        pts=numbers(obj.get('CurvePoints')) if obj.tag=='curve' else numbers(obj.get('BoundingBox'),4)
        boxes.append((min(pts[::2]),min(pts[1::2]),max(pts[::2]),max(pts[1::2])))
    return bounds,atoms,positions,boxes,segments


def _primitive_free(primitive,bounds,positions,boxes,segments,occupied,clearance):
    px,py,pr=primitive;q=(px,py);r=pr+clearance
    return (bounds[0]+r<=px<=bounds[2]-r and bounds[1]+r<=py<=bounds[3]-r
        and not any(math.hypot(max(b[0]-px,0,px-b[2]),max(b[1]-py,0,py-b[3]))<r for b in boxes)
        and not any(math.dist(q,pt)<r for pt in positions.values())
        and not any(_distance_segment(q,a,b)<r+width for a,b,width in segments)
        and not any(math.dist(q,(ox,oy))<r+orr for ox,oy,orr in occupied))


def _owner_ink_distance(point,atom):
    label=atom.find('t')
    if label is None:return math.dist(point,numbers(atom.get('p'),2))
    x,y,xx,yy=numbers(label.get('BoundingBox'),4)
    return math.hypot(max(min(x,xx)-point[0],0,point[0]-max(x,xx)),
                      max(min(y,yy)-point[1],0,point[1]-max(y,yy)))


def verify_symbol_clearance(text,symbol_ids,clearance):
    root,_,_=_split(text);bounds,atoms,positions,boxes,segments=_placement_obstacles(root)
    graphics={g.get('id'):g for g in root.findall('page/fragment/graphic')}
    for sid in symbol_ids:
        if sid not in graphics:raise ValueError('Native symbol missing during clearance check')
        occupied=[p for gid,g in graphics.items() if gid!=sid for p in symbol_primitives(g,root.get('LineWidth','.6'))]
        for p in symbol_primitives(graphics[sid],root.get('LineWidth','.6')):
            if not _primitive_free(p,bounds,positions,boxes,segments,occupied,clearance):raise ValueError('Native symbol clearance collision: '+sid)
    return {'verified':True,'count':len(symbol_ids),'clearance_pt':clearance,
            'scope':'measured labels, atoms, conservative bond envelopes, symbols and page/arrow bounds'}


def plan_symbols(text,symbols,span=None,line_width=None,clearance=2):
    root,_,_=_split(text);symbol_inventory(text)
    if not isinstance(symbols,list) or not 1<=len(symbols)<=50:raise ValueError('Supply 1 through 50 explicit symbols')
    span=float(root.get('LabelSize','10'))*.75 if span is None else span
    line_width=float(root.get('LineWidth','.6')) if line_width is None else line_width
    for value,lo,hi in ((span,2,24),(line_width,.2,3),(clearance,1,12)):
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid symbol span, line width or clearance')
    page=root.find('page');bounds,atoms,positions,boxes,segments=_placement_obstacles(root);occupied=[]
    for g in root.findall('page/fragment/graphic'):occupied.extend(symbol_primitives(g,root.get('LineWidth','.6')))
    next_id=max(int(e.get('id')) for e in root.iter() if e.get('id'))+1;keys=set();records=[]
    for req in symbols:
        if not isinstance(req,dict) or set(req)!={'key','kind','atom_id'}:raise ValueError('Symbols require explicit key, kind and atom_id')
        key=req['key'];kind=req['kind'];aid=req['atom_id']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',key) or key in keys:raise ValueError('Unique safe symbol keys required')
        keys.add(key)
        if not isinstance(kind,str) or kind not in KINDS or not isinstance(aid,str) or aid not in atoms:raise ValueError('Unsupported symbol kind or atom ID')
        atom=atoms[aid];fragment=next(f for f in page.findall('fragment') if atom in list(f))
        symbol=KINDS[kind]
        if kind=='charge':
            charge=int(atom.get('Charge','0'))
            if charge not in (-1,1):raise ValueError('Circled charge requires an existing formal atom charge of +1 or -1')
            if any(g.find(f'represent[@attribute="Charge"][@object="{aid}"]') is not None for g in fragment.findall('graphic')):raise ValueError('Atom already has a charge symbol')
            symbol='CirclePlus' if charge==1 else 'CircleMinus'
            _replace_charge_suffix(atom,charge)
        x,y=positions[aid];neighbors=[]
        for b in fragment.findall('b'):
            if aid in (b.get('B'),b.get('E')):neighbors.append(positions[b.get('E') if b.get('B')==aid else b.get('B')])
        vx=sum(x-p[0] for p in neighbors);vy=sum(y-p[1] for p in neighbors)
        angle=math.atan2(vy,vx) if math.hypot(vx,vy)>.01 else -math.pi/4
        chosen=None;anchor_candidate=None
        handle_span=span if kind=='charge' else span/3 if kind=='lone_pair' else span*2/3
        raw_width=line_width/.8
        radius=span*4/9+line_width if kind=='charge' else handle_span*2/9 if kind=='lone_pair' else handle_span/9
        # A coarse angular grid missed narrow, valid spaces around nitro N.
        # Refine charge candidates only; keep size, clearance and owner checks.
        distances=([i/2 for i in range(math.ceil((radius+clearance+2)*2),73)]
                   if kind=='charge' else range(math.ceil(radius+clearance+2),37))
        turns=([0]+[sign*i for i in range(1,97) for sign in (1,-1)] if kind=='charge'
               else (0,1,-1,2,-2,3,-3,4,-4,5,-5,6,-6,7,-7,8))
        angle_step=math.pi/(96 if kind=='charge' else 8)
        for distance in distances:
            for turn in turns:
                a=angle+turn*angle_step;p=(x+distance*math.cos(a),y+distance*math.sin(a))
                # ChemDraw may replace an explicit Charge association with a
                # nearby atom on save. Never place a charge in another atom's
                # nearest-owner region, even if its circle has no ink collision.
                if kind=='charge' and any(math.dist(p,(x,y))+.25>math.dist(p,q)
                                          for other,q in positions.items() if other!=aid):continue
                # Pair axis is perpendicular to the outward direction and its
                # two dots straddle the chosen centre; the atom stays untouched.
                if kind=='lone_pair':
                    half=(-math.sin(a)*handle_span/2,math.cos(a)*handle_span/2)
                    ends=(p[0]+half[0],p[1]+half[1],p[0]-half[0],p[1]-half[1])
                else:ends=(p[0],p[1],p[0]-handle_span,p[1])
                probe=ET.Element('graphic',{'SymbolType':symbol,'LineWidth':str(raw_width),'BoundingBox':' '.join(map(str,ends))})
                primitives=symbol_primitives(probe)
                if not all(_primitive_free(p,bounds,positions,boxes,segments,occupied,clearance+.05) for p in primitives):continue
                # Prefer the owner's visible label as well as its anchor.
                # Some native-tested crowded layouts have no such candidate;
                # retain the anchor-safe candidate and require native ownership
                # verification in either case, never infer chemistry from distance.
                if kind=='charge' and any(_owner_ink_distance(p,atom)+.25>_owner_ink_distance(p,other)
                                          for other_id,other in atoms.items() if other_id!=aid):
                    if anchor_candidate is None:anchor_candidate=(p,ends,primitives)
                    continue
                chosen=p;break
            if chosen:break
        if chosen is None and anchor_candidate is not None:chosen,ends,primitives=anchor_candidate
        if chosen is None:raise ValueError('No collision-free symbol position within the bounded search')
        cx,cy=chosen;sid=str(next_id);next_id+=1
        g=ET.SubElement(fragment,'graphic',{'id':sid,'GraphicType':'Symbol','SymbolType':symbol,'LineWidth':str(raw_width),
            'color':'0','BoundingBox':' '.join(f'{v:.5f}' for v in ends)})
        if kind=='electron':
            # ChemDraw's native Electron Symbol near an atom sets Radical=Doublet.
            # Use its verified native filled-circle graphic for a purely visual
            # electron annotation, and say so in the inventory and audit.
            g.attrib={'id':sid,'GraphicType':'Oval','OvalType':'Circle Filled','LineWidth':'.20','color':'0',
                'BoundingBox':f'{cx+radius:.5f} {cy:.5f} {cx:.5f} {cy:.5f}',
                'Center3D':f'{cx:.5f} {cy:.5f} 0','MajorAxisEnd3D':f'{cx+radius:.5f} {cy:.5f} 0',
                'MinorAxisEnd3D':f'{cx:.5f} {cy+radius:.5f} 0'}
        if kind=='charge':ET.SubElement(g,'represent',{'attribute':'Charge','object':aid})
        if kind=='lone_pair':ET.SubElement(g,'represent',{'attribute':'Radical','object':aid})
        occupied.extend(primitives);records.append({**req,'symbol_id':sid,'center_pt':[cx,cy],'handle_span_pt':handle_span,
            'native_representation':'filled_circle_annotation' if kind=='electron' else symbol})
    return ET.tostring(root,encoding='unicode'),{'symbols':records,'span_pt':span,'line_width_pt':line_width,'native_graphic_line_width_pt':raw_width,'clearance_pt':clearance,
        'collision_checks':'conservative symbol envelopes against labels, atoms, bonds and page objects',
        'semantics':'Existing formal charges only. LonePair native attachment does not change atom Radical state. Electron requests use native filled-circle annotations, not radical-state Electron Symbols.'}


def _destination(output_dir,pixels):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 through 8192')
    return out


def symbols_document(bridge,document_id,output_dir,symbols,expected_source_token,span=None,line_width=None,clearance=2,pixels=3200):
    out=_destination(output_dir,pixels);created=None;audit={'status':'in_progress','checks':{},'visual_review':'required'}
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.inspect,document_id)['document'];disk_hash=_file_hash(baseline)
        snapshot=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(snapshot),'cdxml');source=snapshot.read_text()
        if source_token(source)!=expected_source_token:raise ValueError('Source snapshot is stale; inspect symbols again')
        planned,plan=plan_symbols(source,symbols,span,line_width,clearance)
        out.mkdir();(out/'before.cdxml').write_text(source);audit['plan']=plan
        _write_json(out/'recipe.json',{'schema_version':1,'symbols':symbols,'expected_source_token':expected_source_token,'span':span,'line_width':line_width,'clearance':clearance,'pixels':pixels})
        _write_json(out/'audit.json',audit)
        try:
            for fmt in ('svg','png'):_native(bridge.export,document_id,str(out/f'before.{fmt}'),fmt,pixels)
            result=_native(bridge.create,planned);created=result['document']['document_id'];audit['working_document_id']=created
            _write_json(out/'audit.json',audit)
            # Render exports may trigger native normalization. Verify the saved
            # working document only after those exports have completed.
            for fmt in ('svg','png','cdxml'):_native(bridge.export,created,str(out/f'figure.{fmt}'),fmt,pixels)
            verification=verify_symbols(planned,(out/'figure.cdxml').read_text());audit['checks'].update(verification['checks']);audit['native_verification']=verification
            native_ids=[verification['id_map'][s['symbol_id']] for s in plan['symbols']]
            audit['native_clearance']=verify_symbol_clearance((out/'figure.cdxml').read_text(),native_ids,clearance)
            audit['checks']['native_symbol_clearance']=True
            check=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(check),'cdxml')
            if source_token(check.read_text())!=expected_source_token or _native(bridge.inspect,document_id)['document']!=baseline or _file_hash(baseline)!=disk_hash:raise ValueError('Source changed during symbol creation')
            audit['checks']['source_document_unchanged']=True;audit['status']='checks_passed'
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Native symbols</title><h1>Native symbol copy</h1><p>Visual review required. Dots are graphical annotations, not radical-state edits.</p><img width="48%" src="before.png"><img width="48%" src="figure.png"><p><a href="figure.cdxml">Editable ChemDraw</a> <a href="figure.svg">SVG</a> <a href="audit.json">Audit</a></p>')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),recovery='No retry or close; inspect working documents and snapshots')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            if created is not None:
                try:_native(bridge.close,created)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit);raise
            _write_json(out/'audit.json',audit);raise


@native_transaction
def symbols_file(bridge,path,output_dir,symbols,expected_source_token=None,span=None,line_width=None,clearance=2,pixels=3200):
    out=_destination(output_dir,pixels);path=Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower()!='.cdxml':raise ValueError('Symbol input requires CDXML')
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();source=data.decode('utf-8')
    plan_symbols(source,symbols,span,line_width,clearance)
    if expected_source_token is not None and source_token(source)!=expected_source_token:raise ValueError('File snapshot is stale')
    result=_native(bridge.create,source);did=result['document']['document_id'];uncertain=False;completed=None
    try:
        report=inspect_symbols_document(bridge,did);native=Path(report['snapshot']).read_text();mapping=verify_symbols(source,native)['id_map']
        if path.read_bytes()!=data:raise ValueError('Source file changed during import')
        mapped=[{**r,'atom_id':mapping[r['atom_id']]} for r in symbols]
        completed=symbols_document(bridge,did,output_dir,mapped,source_token(native),span,line_width,clearance,pixels)
        try:preserved=path.read_bytes()==data
        except OSError:preserved=False
        completed['audit']['checks']['source_file_unchanged']=preserved;completed['audit'].update(source_file=str(path),source_file_sha256=digest)
        if not preserved:completed['audit'].update(status='failed',error='Source file changed during symbol creation')
        _write_json(out/'audit.json',completed['audit'])
        if not preserved:
            _native(bridge.close,completed['document']['document_id']);raise ValueError('Source file changed during symbol creation')
        return completed
    except NativeUncertain:uncertain=True;raise
    finally:
        if not uncertain:
            try:_native(bridge.close,did)
            except NativeUncertain as exc:
                if completed:
                    completed['audit'].update(status='uncertain',close_error=str(exc));_write_json(out/'audit.json',completed['audit'])
                raise
