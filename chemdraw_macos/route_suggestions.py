"""Bounded geometry-only route proposals requiring an explicit selection."""
import copy
import hashlib
import json
import math
from pathlib import Path

from . import annotations as ann
from .batch import _native
from .editing import source_token
from .polish import numbers
from .symbols import symbol_primitives, _distance_segment
from .workflow import _write_json
from .native_lock import native_transaction

_STEPS = 64


def _reference(root, ref, source, electrons):
    if source: ann._require_electron_source(ref)
    if not isinstance(ref,dict) or set(ref) != {'kind','id'} or not isinstance(ref['id'],str):
        raise ValueError('Route endpoint requires exactly an explicit kind and id, without offsets')
    kind = ref['kind']
    if kind not in ('atom','bond','symbol') or (kind == 'symbol' and not source):
        raise ValueError('Routes support atom/bond endpoints and source-only donor symbols')
    tag = {'atom':'n','bond':'b','symbol':'graphic'}[kind]
    objects = [e for e in root.findall(f'page/fragment/{tag}') if e.get('id') == ref['id']]
    if len(objects) != 1: raise ValueError('Route endpoint kind/id does not identify one supported object')
    obj = objects[0]
    if kind == 'atom': return obj,numbers(obj.get('p'),2)
    if kind == 'symbol':
        allowed = ('CircleMinus','LonePair') if electrons == 2 else ('Electron',)
        if ann._symbol_kind(obj) not in allowed: raise ValueError('Donor symbol does not match the explicit electron count')
        x,y,_ = symbol_primitives(obj,root.get('LineWidth','.6'))[0]
        return obj,(x,y)
    positions = {n.get('id'):numbers(n.get('p'),2) for n in root.findall('page/fragment/n')}
    a,b = positions[obj.get('B')],positions[obj.get('E')]
    return obj,((a[0]+b[0])/2,(a[1]+b[1])/2)


def _box_distance(p, box):
    return math.hypot(max(box[0]-p[0],0,p[0]-box[2]),max(box[1]-p[1],0,p[1]-box[3]))


def _segment_distance(a,b,c,d):
    def cross(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    x,y,z,w = cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if x*y <= 0 and z*w <= 0 and max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0])) and max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1])):
        return 0.
    return min(_distance_segment(a,c,d),_distance_segment(b,c,d),_distance_segment(c,a,b),_distance_segment(d,a,b))


def _segment_box_distance(a,b,box):
    if _box_distance(a,box) == 0 or _box_distance(b,box) == 0: return 0.
    x,y,xx,yy = box; corners = ((x,y),(xx,y),(xx,yy),(x,yy))
    return min(_segment_distance(a,b,corners[i],corners[(i+1)%4]) for i in range(4))


def _obstacles(root):
    items = []; counts = {'labels':0,'atoms':0,'bonds':0,'symbols':0,'page_objects':0}
    for text in root.findall('page/t') + root.findall('page/fragment/n/t'):
        if not text.get('BoundingBox'): raise ValueError('Native measured text bounds are required for route suggestions')
        x,y,xx,yy = numbers(text.get('BoundingBox'),4)
        items.append(dict(kind='box',box=(min(x,xx),min(y,yy),max(x,xx),max(y,yy)),id=None))
        counts['labels'] += 1
    positions = {n.get('id'):numbers(n.get('p'),2) for n in root.findall('page/fragment/n')}
    for aid,p in positions.items():
        items.append(dict(kind='circle',center=p,radius=1.,id=aid)); counts['atoms'] += 1
    for bond in root.findall('page/fragment/b'):
        a,b = positions[bond.get('B')],positions[bond.get('E')]
        line = ann._positive(bond.get('LineWidth',root.get('LineWidth','.6')))
        bold = ann._positive(bond.get('BoldWidth',root.get('BoldWidth',str(line))))
        order = float(bond.get('Order','1'))
        spacing = float(bond.get('BondSpacing',root.get('BondSpacing','18')))
        if not math.isfinite(spacing) or not 0 <= spacing <= 100: raise ValueError('Unsupported bond spacing for obstacle bounds')
        # Conservative capsule around multiple lines / bold and wedge depiction.
        radius = max(line,bold)/2 + max(0,math.ceil(order)-1)*math.dist(a,b)*spacing/100
        items.append(dict(kind='segment',a=a,b=b,radius=radius,id=bond.get('id'))); counts['bonds'] += 1
    for graphic in root.findall('page/fragment/graphic'):
        for x,y,r in symbol_primitives(graphic,root.get('LineWidth','.6')):
            items.append(dict(kind='circle',center=(x,y),radius=r,id=graphic.get('id')))
        counts['symbols'] += 1
    for obj in root.findall('page/arrow') + root.findall('page/curve'):
        pts = numbers(obj.get('CurvePoints'),12) if obj.tag == 'curve' else numbers(obj.get('BoundingBox'),4)
        pad = 4 + ann._positive(obj.get('LineWidth',root.get('LineWidth','.6')))
        items.append(dict(kind='box',box=(min(pts[::2])-pad,min(pts[1::2])-pad,max(pts[::2])+pad,max(pts[1::2])+pad),id=obj.get('id')))
        counts['page_objects'] += 1
    if len(items) > 2000: raise ValueError('Route obstacle count exceeds 2000')
    return items,counts


def _endpoint_ref(root, ref, obj, base, direction, clearance):
    if ref['kind'] == 'symbol': return dict(ref)
    if ref['kind'] == 'bond': return {**ref,'offset':[0.,0.]}
    length = math.hypot(*direction)
    if length < .1: raise ValueError('Degenerate route tangent')
    dx,dy = direction[0]/length,direction[1]/length
    text = obj.find('t'); box = None
    if text is not None:
        a,b,c,d = numbers(text.get('BoundingBox'),4); box = (min(a,c),min(b,d),max(a,c),max(b,d))
    for distance in range(2,37):
        p = (base[0]+dx*distance,base[1]+dy*distance)
        if (box is None and distance >= clearance+1) or (box is not None and _box_distance(p,box) >= clearance):
            result = {**ref,'offset':[dx*distance,dy*distance]}
            ann._endpoint(root,result)
            return result
    raise ValueError('No bounded atom endpoint outside measured label clearance')


def _cubic_points(curve):
    raw = numbers(curve.get('CurvePoints'),12)
    p = [(raw[i],raw[i+1]) for i in (0,4,6,8)]
    points = []
    for i in range(_STEPS+1):
        t = i/_STEPS; u = 1-t
        points.append(tuple(u**3*p[0][k]+3*u*u*t*p[1][k]+3*u*t*t*p[2][k]+t**3*p[3][k] for k in (0,1)))
    second = [math.hypot(*(p[j][k]-2*p[j+1][k]+p[j+2][k] for k in (0,1))) for j in (0,1)]
    error = 6*max(second)/(8*_STEPS**2)
    return points,error


def _clearance(points,error,obstacles,page_box,line_width,source,target):
    minimum = math.inf; exceptions = []
    for end,ref in [('source',source),('target',target)]:
        if ref['kind'] in ('bond','symbol'): exceptions.append({'endpoint':end,'object_id':ref['id'],'max_contact_distance_pt':12,'max_curve_fraction':4/_STEPS})
    for i,(a,b) in enumerate(zip(points,points[1:])):
        edge = min(a[0]-page_box[0],b[0]-page_box[0],a[1]-page_box[1],b[1]-page_box[1],page_box[2]-a[0],page_box[2]-b[0],page_box[3]-a[1],page_box[3]-b[1])
        minimum = min(minimum,edge-line_width/2-error)
        for obstacle in obstacles:
            if any(obstacle['id'] == ex['object_id'] and
                   ((ex['endpoint'] == 'source' and i < 4 and max(math.dist(a,points[0]),math.dist(b,points[0])) <= 12)
                    or (ex['endpoint'] == 'target' and i >= _STEPS-4 and max(math.dist(a,points[-1]),math.dist(b,points[-1])) <= 12)) for ex in exceptions):
                continue
            if obstacle['kind'] == 'box': distance = _segment_box_distance(a,b,obstacle['box'])
            elif obstacle['kind'] == 'circle': distance = _distance_segment(obstacle['center'],a,b)-obstacle['radius']
            else: distance = _segment_distance(a,b,obstacle['a'],obstacle['b'])-obstacle['radius']
            minimum = min(minimum,distance-line_width/2-error)
    return minimum,exceptions


def suggest_routes(cdxml,source,target,electrons=2,fishhook_side=None,line_width=.9,clearance=2,max_candidates=5):
    if type(electrons) is not int or electrons not in (1,2): raise ValueError('Electrons must be explicitly 1 or 2')
    if fishhook_side not in (None,'left','right') or (electrons == 2 and fishhook_side is not None): raise ValueError('Fishhook side applies only to one-electron arrows')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 10: raise ValueError('Return limit must be 1 through 10')
    for value,lo,hi in [(line_width,.2,3),(clearance,1,12)]:
        if type(value) not in (int,float) or not math.isfinite(value) or not lo <= value <= hi: raise ValueError('Invalid route width or clearance')
    root = ann._root(cdxml); ann.annotation_inventory(cdxml)
    source_obj,a = _reference(root,source,True,electrons); target_obj,b = _reference(root,target,False,electrons)
    distance = math.dist(a,b)
    if not 1 <= distance <= 600: raise ValueError('Endpoint separation must be 1 through 600 pt')
    page = numbers(root.find('page').get('BoundingBox'),4)
    if page[2] <= page[0] or page[3] <= page[1]: raise ValueError('Invalid native page bounds')
    obstacles,counts = _obstacles(root)
    ux,uy = (b[0]-a[0])/distance,(b[1]-a[1])/distance
    candidates = []; evaluated = 0; rejected = 0; all_exceptions = []
    for height in (18,30,48,72,108,144):
        for side in (-1,1):
            for reach in (.15,.30):
                evaluated += 1
                v = (ux*distance*reach-uy*height*side,uy*distance*reach+ux*height*side)
                w = (-ux*distance*reach-uy*height*side,-uy*distance*reach+ux*height*side)
                try:
                    sr = _endpoint_ref(root,source,source_obj,a,v,clearance+line_width/2+.10)
                    tr = _endpoint_ref(root,target,target_obj,b,w,clearance+line_width/2+.10)
                    arrow = dict(key='suggested-route',electrons=electrons,source=sr,target=tr,controls=[list(v),list(w)])
                    if electrons == 1: arrow['fishhook_side'] = fishhook_side or 'left'
                    planned,_ = ann.plan_annotations(cdxml,[arrow],line_width)
                    curve = ann._root(planned).findall('page/curve')[-1]
                    points,error = _cubic_points(curve)
                    separation,exceptions = _clearance(points,error,obstacles,page,line_width,source,target)
                    if separation < clearance: rejected += 1; continue
                except ValueError:
                    rejected += 1; continue
                length = sum(math.dist(x,y) for x,y in zip(points,points[1:]))
                digest = hashlib.sha256(json.dumps(arrow,sort_keys=True).encode()).hexdigest()[:16]
                arrow['key'] = f'route-{digest}'
                candidates.append({'candidate_id':digest,'arrow':arrow,'score':round(length,6),
                    'minimum_clearance_pt':separation,'collision_check':{'obstacle_counts':counts,
                    'curve_approximation_segments':_STEPS,'curve_approximation_error_bound_pt':error,
                    'geometry':'Conservative cubic chord capsules against measured labels, atom/symbol circles, bond capsules and page-object boxes',
                    'arrowhead_ink':'Not certified; native visual review required'},'intentional_contact_exceptions':exceptions})
                all_exceptions = exceptions
    candidates.sort(key=lambda c:(c['score'],-c['minimum_clearance_pt'],c['candidate_id']))
    retained = candidates[:max_candidates]
    return {'status':'suggestions' if retained else 'no_route','source_token':source_token(cdxml),
        'request':dict(source=copy.deepcopy(source),target=copy.deepcopy(target),electrons=electrons,fishhook_side=fishhook_side,line_width=line_width,clearance=clearance,max_candidates=max_candidates),
        'candidates':retained,'evaluated_candidates':evaluated,'rejected_candidates':rejected,
        'feasible_candidates':len(candidates),'omitted_feasible_candidates':len(candidates)-len(retained),
        'selected_candidate':None,'selection_required':True,'intentional_contact_exceptions':all_exceptions,
        'semantics':'Geometry proposals only, no donor/acceptor, chemistry or mechanism inference',
        'visual_review':'required'}


def select_route(report,candidate_id,cdxml):
    if not isinstance(report,dict) or report.get('source_token') != source_token(cdxml): raise ValueError('Route suggestion snapshot is stale')
    if not isinstance(candidate_id,str): raise ValueError('An explicit candidate_id selection is required')
    matches = [candidate for candidate in report.get('candidates',[]) if candidate.get('candidate_id') == candidate_id]
    if len(matches) != 1: raise ValueError('Selected route ID is not unique in the proposal')
    recomputed = suggest_routes(cdxml,**report['request'])
    expected = [candidate for candidate in recomputed['candidates'] if candidate['candidate_id'] == candidate_id]
    if len(expected) != 1 or matches[0] != expected[0]: raise ValueError('Selected route geometry/report changed or was tampered with')
    return copy.deepcopy(expected[0]['arrow'])


@native_transaction
def annotate_selected_route_document(bridge,document_id,output_dir,suggestions,candidate_id,pixels=3200):
    snapshot = bridge._new_path('.cdxml','backups'); _native(bridge.export,document_id,str(snapshot),'cdxml')
    arrow = select_route(suggestions,candidate_id,snapshot.read_text())
    result = ann.annotate_document(bridge,document_id,output_dir,[arrow],suggestions['source_token'],suggestions['request']['line_width'],pixels)
    _record_selection(result,suggestions,candidate_id,arrow)
    return result


def _record_selection(result,suggestions,candidate_id,arrow):
    planned = result['audit']['plan']['arrows'][0]
    native_id = result['audit']['native_verification']['id_map'][planned['curve_id']]
    result['audit']['route_selection'] = {'candidate_id':candidate_id,'source_token':suggestions['source_token'],
        'explicit_selection':True,'source_arrow':copy.deepcopy(arrow),
        'native_planned_arrow':copy.deepcopy(planned),'native_curve_id':native_id,
        'native_snapshot':'figure.cdxml','source_native_snapshot':'before.cdxml'}
    _write_json(Path(result['output_dir'])/'audit.json',result['audit'])
    _write_json(Path(result['output_dir'])/'route-suggestions.json',suggestions)


@native_transaction
def annotate_selected_route_file(bridge,path,output_dir,suggestions,candidate_id,pixels=3200):
    path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower() != '.cdxml': raise ValueError('Selected route file input requires CDXML')
    with path.open('rb') as handle: data = handle.read(10_000_001)
    if len(data) > 10_000_000: raise ValueError('Source exceeds 10 MB')
    arrow = select_route(suggestions,candidate_id,data.decode('utf-8'))
    # The existing file workflow freezes the source again and rejects a changed
    # token before native creation, then remaps original endpoint IDs on import.
    result = ann.annotate_file(bridge,str(path),output_dir,[arrow],suggestions['source_token'],suggestions['request']['line_width'],pixels)
    _record_selection(result,suggestions,candidate_id,arrow)
    return result
