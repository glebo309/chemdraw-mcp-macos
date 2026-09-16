"""Conservative 2D clearance checks, separate from chemical validation.

Preflight uses estimated label boxes only when native bounds are unavailable.
Post-render checks require measured text bounds. Bond envelopes conservatively
include double/triple spacing and wedge width; this is not a pixel-ink certificate.
"""
import math
from .core import validate_cdxml
from .polish import numbers
from .symbols import _distance_segment


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def segment_distance(a,b,c,d):
    if _cross(a,b,c)*_cross(a,b,d)<0 and _cross(c,d,a)*_cross(c,d,b)<0:return 0.
    return min(_distance_segment(a,c,d),_distance_segment(b,c,d),
               _distance_segment(c,a,b),_distance_segment(d,a,b))


def _edges(box):
    l,t,r,b=box;p=[(l,t),(r,t),(r,b),(l,b)]
    return list(zip(p,p[1:]+p[:1]))


def _point_box(p,box):
    l,t,r,b=box
    return math.hypot(max(l-p[0],0,p[0]-r),max(t-p[1],0,p[1]-b))


def _segment_box(a,b,box):
    if _point_box(a,box)==0 or _point_box(b,box)==0:return 0.
    return min(segment_distance(a,b,c,d) for c,d in _edges(box))


def collision_pairs(text, measured=False, clearance=1.):
    root=validate_cdxml(text);nodes={n.get('id'):n for n in root.findall('.//n')}
    points={i:numbers(n.get('p'),2) for i,n in nodes.items()};labels={};bonds=[];hits=set()
    parents={child:parent for parent in root.iter() for child in parent}
    def inherited(e,key,default):
        while e is not None:
            if e.get(key) is not None:return e.get(key)
            e=parents.get(e)
        return default
    for t in root.findall('.//t'):
        owner=parents.get(t);atom=owner is not None and owner.tag=='n'
        key='a:'+owner.get('id') if atom else 't:'+t.get('id','')
        value=''.join(t.itertext()).strip()
        if not value:continue
        if t.get('BoundingBox'):
            x,y,u,v=numbers(t.get('BoundingBox'),4);box=(min(x,u),min(y,v),max(x,u),max(y,v))
        else:
            if measured:raise ValueError('Native measured label bounds missing for '+key)
            size=max([float(s.get('size',inherited(t,'LabelSize' if atom else 'CaptionSize','10'))) for s in t.findall('s')]+[1.])
            x,y=points[owner.get('id')] if atom else numbers(t.get('p'),2)
            width=.6*size*len(value)
            box=(x-width/2,y-size*.6,x+width/2,y+size*.4) if atom else (x,y-size,x+width,y+size*.2)
        labels[key]=box
    for b in root.findall('.//b'):
        a,e=b.get('B'),b.get('E');length=math.dist(points[a],points[e])
        width=float(inherited(b,'LineWidth','.6'))/2
        if b.get('Order','1') in ('2','3','1.5'):
            width+=length*float(inherited(b,'BondSpacing','18'))/100
        if 'Wedge' in b.get('Display','') or 'Wedged' in b.get('Display',''):
            width=max(width,float(inherited(b,'BoldWidth','2')))
        bonds.append((b.get('id'),a,e,width))
    def add(a,b):hits.add(tuple(sorted((a,b))))
    for aid,node in nodes.items():
        attached=[b for b in root.findall('.//b') if aid in (b.get('B'),b.get('E'))]
        if node.get('Element','6')!='6' or node.find('t') is not None or len(attached)!=2 or any(b.get('Order','1')!='1' for b in attached):continue
        others=[b.get('E') if b.get('B')==aid else b.get('B') for b in attached]
        a,b=points[others[0]],points[others[1]];p=points[aid]
        if abs(_cross(a,p,b))<.001 and sum((a[k]-p[k])*(b[k]-p[k]) for k in (0,1))<0:
            add('a:'+aid,'hidden-carbon')
    for i,(aid,a) in enumerate(points.items()):
        for bid,b in list(points.items())[i+1:]:
            if math.dist(a,b)<2+clearance:add('a:'+aid,'a:'+bid)
        for key,box in labels.items():
            if key!='a:'+aid and _point_box(a,box)<clearance:add('a:'+aid,key)
    for i,(key,a) in enumerate(labels.items()):
        for other,b in list(labels.items())[i+1:]:
            if min(a[2],b[2])-max(a[0],b[0])>0 and min(a[3],b[3])-max(a[1],b[1])>0:add(key,other)
    for i,(bid,a,b,width) in enumerate(bonds):
        for oid,c,d,otherwidth in bonds[i+1:]:
            if {a,b}&{c,d}:continue
            if segment_distance(points[a],points[b],points[c],points[d])<width+otherwidth+clearance:add('b:'+bid,'b:'+oid)
        for aid,p in points.items():
            if aid not in (a,b) and _distance_segment(p,points[a],points[b])<width+clearance:add('b:'+bid,'a:'+aid)
        for key,box in labels.items():
            if key in ('a:'+a,'a:'+b):continue
            if _segment_box(points[a],points[b],box)<width+clearance:add('b:'+bid,key)
    return hits


def check_edit_placement(before,after,measured=False):
    previous=collision_pairs(before,measured=measured)
    added=collision_pairs(after,measured=measured)-previous
    if added:raise ValueError('Introduced placement collision: '+repr(sorted(added)[:8]))
    return {'new_collisions':0,'existing_collision_pairs':len(previous),
            'label_bounds':'native measured' if measured else 'native where available; otherwise estimated',
            'scope':'atom spacing, label boxes and conservative bond envelopes; not exact rendered ink'}
