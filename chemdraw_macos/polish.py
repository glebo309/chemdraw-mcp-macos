"""Measured CDXML transformations, not a replacement chemical renderer.

Flat, one-page molecular drawings only. No reflections, H removal, stereo
invention, automatic abbreviation expansion or inferred caption ownership.
"""
from __future__ import annotations

import math
import statistics
import xml.etree.ElementTree as ET

from .core import PRESETS, style_cdxml, validate_cdxml, preset_settings
from .geometry import Box, find_overlaps


def numbers(value, count=None):
    try:
        result = tuple(map(float, value.split()))
    except (AttributeError, ValueError) as exc:
        raise ValueError('Invalid coordinate') from exc
    if (count is not None and len(result) != count) or not all(map(math.isfinite, result)):
        raise ValueError('Invalid coordinate dimensions or nonfinite value')
    return result


def encode(values):
    return ' '.join(f'{v:.6f}' for v in values)


def supported_root(text):
    root = validate_cdxml(text)
    pages = root.findall('page')
    if len(pages) != 1:
        raise ValueError('Unsupported: polish requires exactly one page')
    page = pages[0]
    if list(root.iter('bracketedgroup')):
        raise ValueError('Unsupported polymer/repeat-group semantics')
    arrow_ids={a.get('id') for a in page.findall('arrow')}
    for g in page.findall('graphic'):
        if not g.get('SupersededBy') or g.get('SupersededBy') not in arrow_ids:
            raise ValueError('Unsupported page graphic; only native arrow fallback graphics supported')
    if page.findall('.//group'):
        raise ValueError('Unsupported: grouped drawings must be ungrouped in a working copy first')
    fragments = page.findall('fragment')
    if not fragments or len(fragments) != len(list(root.iter('fragment'))):
        raise ValueError('Unsupported: require flat molecular fragments, no nested abbreviations')
    all_ids = [e.get('id') for e in page.iter() if e.get('id')]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('Duplicate CDXML object IDs')
    for f in fragments:
        if not f.get('id') or not f.findall('n'):
            raise ValueError('Unsupported: fragment must have ID and atoms')
        ids = {n.get('id') for n in f.findall('n')}
        for n in f.findall('n'):
            numbers(n.get('p'), 2)
            allowed_atom = {'id','p','Z','Element','NumHydrogens','Charge','Isotope','AS','AtomID',
                            'NeedsClean','color','bgcolor','NodeType','ShowAtomQuery','ShowAtomStereo',
                            'ShowAtomNumber','LabelDisplay','LabelJustification','LabelAlignment',
                            'LabelFace','LabelSize','LabelFont','HydrogenPosition','Warning','BondOrdering','Geometry'}
            if set(n.attrib)-allowed_atom:
                raise ValueError('Unsupported atom attributes: '+', '.join(sorted(set(n.attrib)-allowed_atom)))
            if not 1 <= int(n.get('Element','6')) <= 118:
                raise ValueError('Unsupported wildcard/query element')
            if n.get('Geometry') not in (None,'Tetrahedral'):
                raise ValueError('Unsupported non-tetrahedral geometry metadata')
            if (not n.get('id') or n.get('NodeType', 'Element') not in ('Element', 'Unspecified')
                    or any(k in n.attrib for k in ('ElementList', 'GenericNickname', 'AtomList',
                                                  'EnhancedStereoType', 'EnhancedStereoGroupNum'))):
                raise ValueError('Unsupported atom query, abbreviation or enhanced stereo')
        for b in f.findall('b'):
            allowed_bond={'id','B','E','Order','Display','Display2','Z','color','bgcolor',
                          'LineWidth','BoldWidth','BondSpacing','DoublePosition','BS','BondOrdering','BondCircularOrdering','CrossingBonds','Warning'}
            if set(b.attrib)-allowed_bond:
                raise ValueError('Unsupported bond attributes: '+', '.join(sorted(set(b.attrib)-allowed_bond)))
            if b.get('B') not in ids or b.get('E') not in ids:
                raise ValueError('Dangling bond endpoint')
            if b.get('Order', '1') not in ('1', '2', '3', '1.5'):
                raise ValueError('Unsupported bond order/query')
        from .crossings import validate_crossings
        validate_crossings(f)
    return root


def chemical_signature(text):
    """Decode coordinates and wedges, ignoring cached atom stereo assignments.

    This verifies preservation of supported graphs, not source identity or a
    reaction mechanism. Failing/partial parser results are never accepted.
    """
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError('Chemistry validation requires: uv sync --extra chemistry') from exc
    root = supported_root(text)
    for e in root.iter():
        e.attrib.pop('AS', None)
        e.attrib.pop('BondOrdering', None)
    mols = Chem.MolsFromCDXML(ET.tostring(root, encoding='unicode'), removeHs=False)
    fragments = root.find('page').findall('fragment')
    if len(mols) != len(fragments) or any(m is None for m in mols):
        raise ValueError('Unsupported or partially parsed chemistry; refusing to proceed')
    if sum(m.GetNumAtoms() for m in mols) != sum(len(f.findall('n')) for f in fragments):
        raise ValueError('Parser did not retain every explicit atom')
    return sorted(Chem.MolToSmiles(m, isomericSmiles=True) for m in mols)


def bond_lengths(fragment):
    nodes = {n.get('id'): numbers(n.get('p'), 2) for n in fragment.findall('n')}
    lengths = [math.dist(nodes[b.get('B')], nodes[b.get('E')]) for b in fragment.findall('b')]
    if any(v < .001 for v in lengths):
        raise ValueError('Zero-length bond; native cleanup/review required first')
    return lengths


def bounds(element):
    if element.get('BoundingBox'):
        x1,y1,x2,y2 = numbers(element.get('BoundingBox'), 4)
        return Box(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
    points = [numbers(n.get('p'),2) for n in element.iter('n')]
    if not points:
        raise ValueError(f'Native measured bounds missing for {element.tag} {element.get("id")}')
    return Box(min(p[0] for p in points), min(p[1] for p in points),
               max(p[0] for p in points), max(p[1] for p in points))


def analyze_cdxml(text):
    root = supported_root(text)
    molecules = []
    for f in root.find('page').findall('fragment'):
        lengths = bond_lengths(f)
        molecules.append({'id':f.get('id'), 'bounds_pt':list(vars(bounds(f)).values()),
                          'atoms':len(f.findall('n')), 'bonds':len(lengths),
                          'median_bond_pt':statistics.median(lengths) if lengths else None})
    texts = [{'id':t.get('id'), 'text':''.join(t.itertext()),
              'position_pt':list(numbers(t.get('p'),2)) if t.get('p') else None,
              'bounds_pt':list(numbers(t.get('BoundingBox'),4)) if t.get('BoundingBox') else None}
             for t in root.find('page').findall('t')]
    return {'molecules':molecules, 'texts':texts,
            'arrows':[{'id':a.get('id'), 'head':a.get('Head3D'), 'tail':a.get('Tail3D')}
                      for a in root.find('page').findall('arrow')]}


def transform(element, scale=1., cx=0., cy=0., dx=0., dy=0.):
    """Positive uniform scale and translation only; charge-symbol size retained."""
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Only positive uniform scales are allowed')
    for e in element.iter():
        for key, count in (('p',2), ('BoundingBox',4), ('Head3D',3), ('Tail3D',3),
                           ('Center3D',3), ('MajorAxisEnd3D',3), ('MinorAxisEnd3D',3)):
            if not e.get(key):
                continue
            v = list(numbers(e.get(key),count))
            if key == 'BoundingBox' and e.get('SymbolType') in ('CirclePlus','CircleMinus'):
                # First pair is the native centre; second pair is a size handle.
                ox,oy = v[2]-v[0],v[3]-v[1]
                v[0],v[1] = cx+(v[0]-cx)*scale+dx,cy+(v[1]-cy)*scale+dy
                v[2],v[3] = v[0]+ox,v[1]+oy
            else:
                for i in range(0, count-1, 2):
                    v[i] = cx+(v[i]-cx)*scale+dx
                    v[i+1] = cy+(v[i+1]-cy)*scale+dy
            e.set(key,encode(v))


def normalize_cdxml(text, preset='house'):
    original = chemical_signature(text)
    root = supported_root(style_cdxml(text,preset))
    target = float(preset_settings(preset)['BondLength'])
    scales = {}
    for f in root.find('page').findall('fragment'):
        lengths = bond_lengths(f)
        scale = target/statistics.median(lengths) if lengths else 1.
        if not .1 <= scale <= 10:
            raise ValueError('Implausible molecular scale; inspect source units first')
        cx,cy = bounds(f).center
        transform(f,scale,cx,cy)
        scales[f.get('id')] = scale
    result = ET.tostring(root,encoding='unicode')
    if chemical_signature(result) != original:
        raise ValueError('Chemistry changed during normalization; refusing output')
    return result, {'scales':scales, 'target_bond_pt':target,
                    'checks':{'chemistry_preserved':True},
                    'orientation':'preserved; no rotation or reflection'}


def place_text(text,x,y):
    """Centre existing text while retaining its native-measured glyph bounds."""
    old = bounds(text)
    px,py = numbers(text.get('p'),2)
    # Native text p is a baseline anchor, while bounds describe visible ink.
    transform(text,dx=x-old.center[0],dy=y-py)
    text.set('p',encode((x,y)))
    text.set('Justification','Center')
    text.set('CaptionJustification','Center')


def layout_row(text, caption_map=None, condition_map=None, gap=24., label_gap=14., width=None):
    root = supported_root(text)
    original = chemical_signature(text)
    page = root.find('page')
    caption_map = caption_map or {}
    condition_map = condition_map or {}
    for value in (gap,label_gap):
        if not math.isfinite(value) or value < 4:
            raise ValueError('Gaps must be finite and at least 4 pt')
    if width is not None and (not math.isfinite(width) or width <= 0):
        raise ValueError('Invalid width')
    objects = {e.get('id'):e for e in page if e.get('id')}
    assigned = list(caption_map.values()) + [i for ids in condition_map.values() for i in ids]
    if len(set(assigned)) != len(assigned):
        raise ValueError('A label cannot have multiple owners')
    for fid,tid in caption_map.items():
        if fid not in objects or objects[fid].tag!='fragment' or tid not in objects or objects[tid].tag!='t':
            raise ValueError('Caption map must link current fragment IDs to current text IDs')
    condition_side = {}
    for aid,tids in condition_map.items():
        if aid not in objects or objects[aid].tag!='arrow':
            raise ValueError('Condition owner must be a native arrow ID')
        a = objects[aid];head=numbers(a.get('Head3D'),3);tail=numbers(a.get('Tail3D'),3)
        if abs(head[1]-tail[1]) > .1 or head[0] <= tail[0]:
            raise ValueError('Unsupported: row layout requires rightward horizontal arrows')
        sides = set()
        for tid in tids:
            if tid not in objects or objects[tid].tag!='t':
                raise ValueError('Condition text ID is absent')
            side = 'above' if bounds(objects[tid]).center[1] < head[1] else 'below'
            if side in sides:
                raise ValueError('Use one multiline condition text object per arrow side')
            sides.add(side);condition_side[tid]=side
    components=[]
    for e in page:
        eid=e.get('id')
        if eid in assigned or e.tag=='scheme' or e.get('SupersededBy'):
            continue
        if e.tag=='t' and ''.join(e.itertext()).strip()!='+':
            raise ValueError(f'Unassigned text {eid}; supply caption_map or condition_map explicitly')
        if e.tag not in ('fragment','t','arrow'):
            raise ValueError(f'Unsupported row object: {e.tag} {eid}')
        if e.tag=='arrow':
            h=numbers(e.get('Head3D'),3);t=numbers(e.get('Tail3D'),3)
            if abs(h[1]-t[1])>.1 or h[0]<=t[0] or e.get('AngularSize'):
                raise ValueError('Unsupported non-horizontal or curved arrow')
        components.append(e)
    components.sort(key=lambda e:bounds(e).center[0])
    boxes=[bounds(e) for e in components]
    widths=[b.width for b in boxes]
    total=sum(widths)+gap*(len(widths)-1)
    if width is not None and total > width:
        raise ValueError(f'Row needs {total:.2f} pt width; requested {width:.2f}. No molecular shrinking performed.')
    row_y=36+max(b.height for b in boxes)/2
    cursor=36.
    for e,b,w in zip(components,boxes,widths):
        dx=cursor+w/2-b.center[0]
        dy=row_y-b.center[1]
        if e.tag=='arrow':
            dy=row_y-numbers(e.get('Tail3D'),3)[1]
        transform(e,dx=dx,dy=dy)
        for legacy in page.findall('graphic'):
            if legacy.get('SupersededBy')==e.get('id'):
                transform(legacy,dx=dx,dy=dy)
        cursor+=w+gap
    baseline=max(bounds(e).bottom for e in components)+label_gap
    for fid,tid in caption_map.items():
        place_text(objects[tid],bounds(objects[fid]).center[0],baseline)
    for aid,tids in condition_map.items():
        a=objects[aid];h=numbers(a.get('Head3D'),3);t=numbers(a.get('Tail3D'),3)
        for tid in tids:
            tb=bounds(objects[tid]);ty=numbers(objects[tid].get('p'),2)[1]
            y=h[1]-label_gap-(tb.bottom-ty) if condition_side[tid]=='above' else h[1]+label_gap+(ty-tb.top)
            place_text(objects[tid],(h[0]+t[0])/2,y)
    result=ET.tostring(root,encoding='unicode')
    if chemical_signature(result)!=original:
        raise ValueError('Chemistry changed during row layout')
    overlaps=find_overlaps([bounds(e) for e in components])
    if overlaps:
        raise ValueError(f'Unexpected component overlap: {overlaps}')
    return result,{'row_width_pt':total,'gap_pt':gap,'caption_baseline_pt':baseline,
                   'caption_map':caption_map,'condition_map':condition_map,
                   'checks':{'chemistry_preserved':True,'no_component_overlaps':True}}
