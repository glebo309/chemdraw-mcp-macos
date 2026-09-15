"""Explicit native electron-flow curves, based on the working SN2 drawing.

No graph edits, mechanism inference, automatic routing or native attachment claim.
"""
from contextlib import nullcontext
import copy
import hashlib
import html
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .core import validate_cdxml
from .polish import supported_root, numbers
from .editing import atom_mapping, source_token
from .workflow import remap_ids, _file_hash, _write_json
from .batch import _verify as verify_core, _native, NativeUncertain


def _positive(value):
    try:value=float(value)
    except (ValueError,TypeError) as exc:raise ValueError('Invalid existing annotation dimension') from exc
    if not math.isfinite(value) or value<=0:raise ValueError('Existing annotation dimensions must be finite and positive')
    return value


def _symbol_kind(g):
    if g.get('GraphicType')=='Symbol':return g.get('SymbolType')
    if g.get('GraphicType')=='Oval' and g.get('OvalType')=='Circle Filled':return 'Electron'
    return None


def _validate_dot(g,fragment,root):
    if g.get('GraphicType')=='Oval':
        allowed={'id','BoundingBox','Z','Warning','LineWidth','GraphicType','OvalType','Center3D','MajorAxisEnd3D','MinorAxisEnd3D','color'}
        if list(g) or set(g.attrib)-allowed or g.get('OvalType')!='Circle Filled' or g.get('color',root.get('color','0'))!='0':
            raise ValueError('Only an unassociated solid black circular electron annotation is supported')
        c=numbers(g.get('Center3D'),3);major=numbers(g.get('MajorAxisEnd3D'),3);minor=numbers(g.get('MinorAxisEnd3D'),3)
        r=major[0]-c[0]
        if r<=0 or any(abs(v)>.001 for v in (c[2],major[2],minor[2])) or abs(major[1]-c[1])>.03 or abs(minor[0]-c[0])>.03 or abs(minor[1]-c[1]-r)>.03:
            raise ValueError('Electron annotation must remain an axis-aligned native filled circle')
        if not _close_numbers(g.get('BoundingBox'),' '.join(map(str,(*major[:2],*c[:2])))):
            raise ValueError('Electron circle handle geometry is inconsistent')
        _positive(g.get('LineWidth',root.get('LineWidth','.6')))
        return
    if set(g.attrib)-{'id','BoundingBox','Z','Warning','LineWidth','GraphicType','SymbolType','color','bgcolor'}:
        raise ValueError('Unsupported graphical electron styling')
    if list(g):
        if g.get('SymbolType')!='LonePair' or len(g)!=1 or g[0].tag!='represent' or g[0].attrib.keys()!={'attribute','object'} or len(g[0]) or g[0].get('attribute')!='Radical':
            raise ValueError('Only a bounded LonePair native association is supported')
        atom=fragment.find(f'n[@id="{g[0].get("object")}"]')
        if atom is None or atom.get('Radical') not in (None,'None'):
            raise ValueError('LonePair association must refer to an existing nonradical atom in its fragment')
    numbers(g.get('BoundingBox'),4);_positive(g.get('LineWidth',root.get('LineWidth','.6')))


def _root(text):
    root=supported_root(text);page=root.find('page')
    # CDXML character content lives in s runs. Pretty-print indentation between
    # runs is XML formatting, not spaces/newlines in a chemical label.
    for e in root.iter():
        if e.tag!='s' and e.text is not None and not e.text.strip():e.text=None
        if e.tail is not None and not e.tail.strip():e.tail=None
    if any(e.tag not in ('fragment','t','arrow','graphic','scheme','curve') for e in page):
        raise ValueError('Unsupported annotation page object')
    for f in page.findall('fragment'):
        for e in f:
            if e.tag in ('n','b'):continue
            if e.tag=='graphic' and _symbol_kind(e) in ('LonePair','Electron'):
                _validate_dot(e,f,root)
                continue
            if e.tag!='graphic' or e.get('GraphicType')!='Symbol' or e.get('SymbolType') not in ('CirclePlus','CircleMinus'):
                raise ValueError('Only existing circled-charge molecular graphics are supported')
            if set(e.attrib)-{'id','BoundingBox','Z','Warning','LineWidth','GraphicType','SymbolType','color','bgcolor'}:
                raise ValueError('Unsupported charge graphic styling')
            if len(e)!=1 or e[0].tag!='represent' or e[0].get('attribute')!='Charge':
                raise ValueError('Charge symbol needs an explicit matching atom reference')
            if set(e[0].attrib)!={'attribute','object'} or len(e[0]):raise ValueError('Unsupported charge reference')
            atom=f.find(f'n[@id="{e[0].get("object")}"]')
            sign=1 if e.get('SymbolType')=='CirclePlus' else -1
            if atom is None or int(atom.get('Charge','0'))!=sign:raise ValueError('Charge symbol differs from atom charge')
            numbers(e.get('BoundingBox'),4)
            _positive(e.get('LineWidth',root.get('LineWidth','.6')))
    for c in page.findall('curve'):
        allowed={'id','Z','LineWidth','CurveType','ArrowheadHead','ArrowheadTail','ArrowheadType','HeadSize',
                 'ArrowheadCenterSize','ArrowheadWidth','CurvePoints','color','FillType'}
        if list(c) or set(c.attrib)-allowed:raise ValueError('Unsupported curve properties')
        _positive(c.get('LineWidth',root.get('LineWidth','.6')))
        for dimension in ('HeadSize','ArrowheadCenterSize','ArrowheadWidth'):
            if dimension in c.attrib:_positive(c.get(dimension))
        pts=numbers(c.get('CurvePoints'),12)
        if pts[:2]!=pts[2:4] or pts[-2:]!=pts[-4:-2]:raise ValueError('Only one cubic electron-flow curve is supported')
        if c.get('ArrowheadHead') not in ('Full','HalfLeft','HalfRight') or c.get('ArrowheadTail','None')!='None':
            raise ValueError('Unsupported curve head')
        flag='8' if c.get('ArrowheadHead')=='Full' else '32'
        if c.get('CurveType',flag)!=flag or c.get('FillType','None')!='None' or c.get('ArrowheadType','Solid')!='Solid':
            raise ValueError('Unsupported or inconsistent curve style')
    return root


def _core(text):
    root=_root(text);page=root.find('page')
    for c in page.findall('curve'):page.remove(c)
    for f in page.findall('fragment'):
        for g in f.findall('graphic'):f.remove(g)
    return ET.tostring(root,encoding='unicode')


def _single(root,fid):
    r=copy.deepcopy(root);p=r.find('page')
    for e in list(p):
        if e.tag!='fragment' or e.get('id')!=fid:p.remove(e)
    return ET.tostring(r,encoding='unicode')


def _close_numbers(a,b,tol=.03):
    try:
        aa=numbers(a);bb=numbers(b)
        return len(aa)==len(bb) and all(abs(x-y)<tol for x,y in zip(aa,bb))
    except ValueError:return False


def verify_annotations(expected,native):
    if any(_symbol_kind(g) in ('LonePair','Electron') for text in (expected,native) for g in validate_cdxml(text).findall('page/fragment/graphic')):
        from .symbols import verify_symbols
        return verify_symbols(expected,native)
    old=_root(expected);new=_root(native)
    a=_core(expected);b=_core(native);verify_core(a,b)
    mapping=remap_ids(a,b);ar=validate_cdxml(a);br=validate_cdxml(b)
    for f in ar.find('page').findall('fragment'):
        fid=f.get('id');nm=mapping[fid]
        nodes,_=atom_mapping(_single(ar,fid),_single(br,nm));mapping.update(nodes)
        nf=br.find(f'page/fragment[@id="{nm}"]')
        for bond in f.findall('b'):
            hits=[t for t in nf.findall('b') if {t.get('B'),t.get('E')}=={nodes[bond.get('B')],nodes[bond.get('E')]}]
            if len(hits)!=1:raise ValueError('Ambiguous native bond mapping')
            mapping[bond.get('id')]=hits[0].get('id')
    for tag,selector in [('charge','page/fragment/graphic'),('curve','page/curve')]:
        originals=old.findall(selector);candidates=new.findall(selector)
        if len(originals)!=len(candidates):raise ValueError(f'Native {tag} count changed')
        used=set()
        for e in originals:
            def matches(n):
                if tag=='charge':
                    if n.get('SymbolType')!=e.get('SymbolType') or n[0].get('object')!=mapping[e[0].get('object')]:return False
                    if e.get('bgcolor',old.get('bgcolor','1'))!=n.get('bgcolor',new.get('bgcolor','1')):return False
                    coords='BoundingBox';numeric=('LineWidth',)
                else:
                    if e.get('ArrowheadHead')!=n.get('ArrowheadHead'):return False
                    coords='CurvePoints';numeric=('LineWidth','HeadSize','ArrowheadCenterSize','ArrowheadWidth')
                if e.get('color','0')!=n.get('color','0'):return False
                return _close_numbers(e.get(coords),n.get(coords)) and all(_close_numbers(e.get(k,old.get(k,'0')),n.get(k,new.get(k,'0'))) for k in numeric)
            hits=[n for n in candidates if n.get('id') not in used and matches(n)]
            if len(hits)!=1:raise ValueError(f'Native {tag} geometry, style or association changed')
            used.add(hits[0].get('id'));mapping[e.get('id')]=hits[0].get('id')
    return {'id_map':mapping,'checks':{'mapped_chemistry_preserved':True,'atom_coordinates_preserved':True,
        'existing_charge_symbols_preserved':True,'curve_geometry_preserved':True}}


def annotation_inventory(text):
    root=_root(text);verify_core(_core(text),_core(text))
    return {'source_token':source_token(text),
            'atoms':[{'id':n.get('id'),'element':int(n.get('Element','6')),'position_pt':list(numbers(n.get('p'),2)),
                      'label':''.join(n.itertext()).strip(),
                      'label_bounds_pt':list(numbers(n.find('t').get('BoundingBox'),4)) if n.find('t') is not None and n.find('t').get('BoundingBox') else None} for n in root.findall('.//n')],
            'bonds':[{'id':b.get('id'),'begin':b.get('B'),'end':b.get('E')} for b in root.findall('.//b')],
            'curves':[{'id':c.get('id'),'head':c.get('ArrowheadHead'),'points':list(numbers(c.get('CurvePoints'),12))} for c in root.findall('page/curve')],
            'symbols':[{'id':g.get('id'),'kind':_symbol_kind(g),'native_graphic_type':g.get('GraphicType'),'geometry_pt':list(numbers(g.get('BoundingBox'),4)),
                        'atom_id':g[0].get('object') if len(g) else None} for g in root.findall('page/fragment/graphic')],
            'note':'Offsets and cubic controls are explicit page-point geometry. Ownership is recorded in the recipe, not a promise of native moving attachment.'}


def inspect_annotations_document(bridge,document_id):
    path=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(path),'cdxml')
    return {**annotation_inventory(path.read_text()),'snapshot':str(path),'document':bridge.inspect(document_id)['document']}


def _vec(v,limit):
    if not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>limit for x in v):
        raise ValueError('Expected two finite point offsets within the supported range')
    return tuple(v)


def _endpoint(root,ref):
    if not isinstance(ref,dict) or set(ref)!={'kind','id','offset'} or ref['kind'] not in ('atom','bond') or not isinstance(ref['id'],str):
        raise ValueError('Endpoint needs kind atom/bond, explicit id and offset')
    tag='n' if ref['kind']=='atom' else 'b';obj=root.find(f'.//{tag}[@id="{ref["id"]}"]')
    if obj is None:raise ValueError('Endpoint ID does not match requested atom/bond kind')
    if tag=='n':x,y=numbers(obj.get('p'),2)
    else:
        aa=numbers(root.find(f'.//n[@id="{obj.get("B")}"]').get('p'),2)
        bb=numbers(root.find(f'.//n[@id="{obj.get("E")}"]').get('p'),2)
        x,y=((aa[0]+bb[0])/2,(aa[1]+bb[1])/2)
    dx,dy=_vec(ref['offset'],36);point=(x+dx,y+dy)
    if tag=='n':
        t=obj.find('t')
        if t is not None:
            if not t.get('BoundingBox'):raise ValueError('Native measured atom-label bounds required; inspect/import a native copy first')
            x1,y1,x2,y2=numbers(t.get('BoundingBox'),4)
            if min(x1,x2)-1<=point[0]<=max(x1,x2)+1 and min(y1,y2)-1<=point[1]<=max(y1,y2)+1:
                raise ValueError('Arrow endpoint overlaps its atom label or clearance margin')
        elif math.hypot(dx,dy)<1:raise ValueError('Endpoint requires clearance from its atom position')
    return point


def _require_electron_source(ref):
    if isinstance(ref,dict) and ref.get('kind')=='atom':
        raise ValueError('Select a displayed negative charge/lone pair (two electrons), electron dot (one electron), or donating bond; atom-label sources are not supported. Add a symbol first if needed.')


def plan_annotations(text,arrows,line_width=.9):
    root=_root(text);annotation_inventory(text)
    if not isinstance(arrows,list) or not 1<=len(arrows)<=50:raise ValueError('Supply 1 through 50 explicit arrows')
    if type(line_width) not in (int,float) or not math.isfinite(line_width) or not .2<=line_width<=3:raise ValueError('Line width must be 0.2 through 3 pt')
    page=root.find('page');next_id=max(int(e.get('id')) for e in root.iter() if e.get('id'))+1
    keys=set();planned=[]
    for arrow in arrows:
        if not isinstance(arrow,dict) or set(arrow)-{'key','electrons','fishhook_side','source','target','controls'}:raise ValueError('Unknown arrow fields')
        key=arrow.get('key')
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',key) or key in keys:raise ValueError('Arrow keys must be unique safe identifiers')
        keys.add(key);electrons=arrow.get('electrons')
        if type(electrons) is not int or electrons not in (1,2):raise ValueError('Electrons must be 1 or 2')
        side=arrow.get('fishhook_side','left')
        if side not in ('left','right') or ('fishhook_side' in arrow and electrons!=1):raise ValueError('Fishhook side applies only to single-electron arrows')
        controls=arrow.get('controls')
        if not isinstance(controls,list) or len(controls)!=2:raise ValueError('Two explicit cubic control offsets are required')
        v=_vec(controls[0],200);w=_vec(controls[1],200)
        ref=arrow.get('source')
        _require_electron_source(ref)
        if isinstance(ref,dict) and ref.get('kind')=='symbol':
            if set(ref)!={'kind','id'} or not isinstance(ref['id'],str):raise ValueError('Symbol source needs explicit kind and id, without offsets')
            g=root.find(f'page/fragment/graphic[@id="{ref["id"]}"]')
            allowed=('CircleMinus','LonePair') if electrons==2 else ('Electron',)
            if g is None or _symbol_kind(g) not in allowed:raise ValueError('Symbol source does not match electron count; positive charges cannot donate')
            from .symbols import symbol_source_edge
            start=symbol_source_edge(g,v,root.get('LineWidth','.6'))
        else:start=_endpoint(root,ref)
        end=_endpoint(root,arrow.get('target'))
        if math.dist(start,end)<1:raise ValueError('Coincident curve endpoints')
        c1=(start[0]+v[0],start[1]+v[1]);c2=(end[0]+w[0],end[1]+w[1])
        if math.dist(start,c1)<.1 or math.dist(end,c2)<.1:raise ValueError('Degenerate cubic control tangent')
        points=(start,start,c1,c2,end,end);head='Full' if electrons==2 else ('HalfLeft' if side=='left' else 'HalfRight')
        cid=str(next_id);next_id+=1
        ET.SubElement(page,'curve',{'id':cid,'CurveType':'8' if electrons==2 else '32','ArrowheadHead':head,
            'ArrowheadType':'Solid','FillType':'None','HeadSize':'250','ArrowheadCenterSize':'220','ArrowheadWidth':'140',
            'LineWidth':str(line_width),'color':'0','CurvePoints':' '.join(f'{n:.5f}' for p in points for n in p)})
        planned.append({**copy.deepcopy(arrow),'curve_id':cid,'start_pt':start,'end_pt':end,'head':head})
    return ET.tostring(root,encoding='unicode'),{'arrows':planned,'line_width':line_width,
        'endpoint_label_clearance_pt':1,'routing':'Explicit cubic controls, not automatic collision avoidance',
        'attachment':'Recipe-owned symbol/bond source and atom/bond target IDs; native moving attachment is not asserted'}


def annotate_document(bridge,document_id,output_dir,arrows,expected_source_token,line_width=.9,pixels=3200):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 through 8192')
    created=None;audit={'status':'in_progress','checks':{},'visual_review':'required'}
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.inspect,document_id)['document'];disk_hash=_file_hash(baseline)
        snapshot=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(snapshot),'cdxml')
        source=snapshot.read_text()
        if source_token(source)!=expected_source_token:raise ValueError('Source snapshot is stale; inspect annotations again')
        planned,plan=plan_annotations(source,arrows,line_width)
        out.mkdir();(out/'before.cdxml').write_text(source)
        _write_json(out/'recipe.json',{'schema_version':1,'arrows':arrows,'expected_source_token':expected_source_token,'line_width':line_width,'pixels':pixels})
        audit['plan']=plan;_write_json(out/'audit.json',audit)
        try:
            for fmt in ('svg','png'):_native(bridge.export,document_id,str(out/f'before.{fmt}'),fmt,pixels)
            result=_native(bridge.create,planned);created=result['document']['document_id']
            audit['working_document_id']=created;_write_json(out/'audit.json',audit)
            # Render exports may trigger native normalization. Verify the saved
            # working document only after those exports have completed.
            for fmt in ('svg','png','cdxml'):_native(bridge.export,created,str(out/f'figure.{fmt}'),fmt,pixels)
            final=(out/'figure.cdxml').read_text();verification=verify_annotations(planned,final)
            audit['checks'].update(verification['checks']);audit['native_verification']=verification
            after=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(after),'cdxml')
            if source_token(after.read_text())!=expected_source_token or _native(bridge.inspect,document_id)['document']!=baseline or _file_hash(baseline)!=disk_hash:
                raise ValueError('Source changed during annotation')
            audit['checks']['source_document_unchanged']=True;audit['status']='checks_passed'
            audit['limitations']='No chemical or radical-state edits. Own atom-label endpoint clearance only; whole-route, charge, caption and arrowhead clearance still require visual review. No native moving attachment guarantee.'
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Native electron-flow annotation</title>
<style>body{font:16px system-ui;margin:32px;background:#f2f4f5}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{padding:20px;background:white;margin:0;border-radius:12px}img{width:100%;height:340px;object-fit:contain}a{color:#17617c}</style>
<h1>Native electron-flow annotation</h1><p>Explicit displayed electron-source symbols or donating bonds; atom/bond targets. Chemistry retained. Visual review of the mechanism and curve clearance remains required.</p>
<main><figure><figcaption>Before</figcaption><img src="before.png" alt="Source"></figure><figure><figcaption>After</figcaption><img src="figure.png" alt="Annotated copy"></figure></main>
<p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="figure.svg">SVG</a> · <a href="figure.png">PNG</a> · <a href="recipe.json">Recipe</a> · <a href="audit.json">Audit</a></p></html>''')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),recovery='Operation not retried; inspect owned working document and backups before continuing')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            if created is not None:
                try:_native(bridge.close,created)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit);raise
            _write_json(out/'audit.json',audit);raise


def annotate_file(bridge,path,output_dir,arrows,expected_source_token=None,line_width=.9,pixels=3200):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 through 8192')
    path=Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower()!='.cdxml':raise ValueError('Annotation file input requires CDXML')
    data=path.read_bytes();file_hash=hashlib.sha256(data).hexdigest()
    source=data.decode('utf-8');plan_annotations(source,arrows,line_width)
    if expected_source_token is not None and source_token(source)!=expected_source_token:raise ValueError('File source snapshot is stale')
    result=_native(bridge.create,source);did=result['document']['document_id'];uncertain=False;completed=None
    try:
        report=inspect_annotations_document(bridge,did);native=Path(report['snapshot']).read_text()
        mapping=verify_annotations(source,native)['id_map']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=file_hash:raise ValueError('Source file changed during import')
        mapped=copy.deepcopy(arrows)
        for arrow in mapped:
            for end in ('source','target'):arrow[end]['id']=mapping[arrow[end]['id']]
        completed=annotate_document(bridge,did,output_dir,mapped,source_token(native),line_width,pixels)
        try:preserved=hashlib.sha256(path.read_bytes()).hexdigest()==file_hash
        except OSError:preserved=False
        completed['audit']['checks']['source_file_unchanged']=preserved
        completed['audit'].update(source_file=str(path),source_file_sha256=file_hash)
        if not preserved:completed['audit'].update(status='failed',error='Source file changed during annotation')
        _write_json(out/'audit.json',completed['audit'])
        if not preserved:
            _native(bridge.close,completed['document']['document_id'])
            raise ValueError('Source file changed during annotation')
        return completed
    except NativeUncertain:uncertain=True;raise
    finally:
        if not uncertain:
            try:_native(bridge.close,did)
            except NativeUncertain as exc:
                if completed:
                    completed['audit'].update(status='uncertain',close_error=str(exc))
                    _write_json(out/'audit.json',completed['audit'])
                raise
