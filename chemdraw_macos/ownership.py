"""Explicit sidecar ownership and verified, translation-only working copies."""
from contextlib import nullcontext
import copy
import hashlib
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from . import annotations as ann
from .batch import _native, NativeUncertain
from .editing import source_token
from .polish import bounds, encode, numbers, transform
from .symbols import verify_symbols, symbol_primitives, _destination
from .workflow import _file_hash, _write_json


def _owner_for_ref(root, owners, ref):
    if not isinstance(ref, dict) or set(ref) != {'kind','id'} or ref['kind'] not in ('atom','bond','symbol') or not isinstance(ref['id'],str):
        raise ValueError('Curve ownership references require explicit kind and id')
    tag = {'atom':'n','bond':'b','symbol':'graphic'}[ref['kind']]
    for fragment in root.findall('page/fragment'):
        if any(e.get('id') == ref['id'] for e in fragment.findall(tag)):
            return next(owner['key'] for owner in owners if fragment.get('id') in owner['fragment_ids'])
    raise ValueError('Curve ownership reference does not identify an existing object of that kind')


def build_ownership(cdxml, owners, curves=None):
    root = ann._root(cdxml); verify_symbols(cdxml, cdxml)
    if not isinstance(owners,list) or not 1 <= len(owners) <= 100:
        raise ValueError('Supply 1 through 100 explicit owners')
    fragments = {f.get('id') for f in root.findall('page/fragment')}
    captions = {t.get('id') for t in root.findall('page/t')}
    seen_fragments, seen_captions, keys = set(), set(), set()
    for owner in owners:
        if not isinstance(owner,dict) or set(owner) != {'key','fragment_ids','caption_ids'}:
            raise ValueError('Each owner requires key, fragment_ids and caption_ids')
        key = owner['key']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',key) or key in keys:
            raise ValueError('Owner keys must be unique safe identifiers')
        keys.add(key)
        for field, available, seen in [('fragment_ids',fragments,seen_fragments), ('caption_ids',captions,seen_captions)]:
            ids = owner[field]
            if not isinstance(ids,list) or (field == 'fragment_ids' and not ids) or any(not isinstance(i,str) for i in ids):
                raise ValueError('Ownership IDs must be explicit lists; each owner needs a fragment')
            if len(set(ids)) != len(ids) or set(ids)-available or set(ids)&seen:
                raise ValueError('Unknown or multiply owned fragment/caption')
            seen.update(ids)
    if seen_fragments != fragments:
        raise ValueError('Every fragment requires exactly one explicit owner')
    curves = [] if curves is None else curves
    if not isinstance(curves,list) or len(curves) > 100:
        raise ValueError('At most 100 explicit curve ownership records are supported')
    seen_curves = set()
    for curve in curves:
        if not isinstance(curve,dict) or set(curve) != {'curve_id','source','target'} or not isinstance(curve['curve_id'],str) or curve['curve_id'] in seen_curves:
            raise ValueError('Each curve needs a unique curve_id and explicit source/target ownership')
        seen_curves.add(curve['curve_id'])
        for end in ('source','target'): _owner_for_ref(root,owners,curve[end])
        if curve['target']['kind'] == 'symbol':
            raise ValueError('Symbol targets are unsupported')
    if seen_curves != {c.get('id') for c in root.findall('page/curve')}:
        raise ValueError('Every existing curve requires explicit ownership; unknown curves are rejected')
    return {'schema_version':1,'source_token':source_token(cdxml), 'owners':copy.deepcopy(owners),
            'curves':copy.deepcopy(curves),'stationary_caption_ids':sorted(captions-seen_captions)}


def _validate_state(text, state):
    if not isinstance(state,dict) or set(state) != {'schema_version','source_token','owners','curves','stationary_caption_ids'} or type(state['schema_version']) is not int or state['schema_version'] != 1:
        raise ValueError('Unsupported ownership sidecar schema')
    if state['source_token'] != source_token(text):
        raise ValueError('Ownership sidecar is stale; rebuild explicit ownership from a current snapshot')
    rebuilt = build_ownership(text,state['owners'],state['curves'])
    if state != rebuilt:
        raise ValueError('Ownership sidecar contains inconsistent stationary captions')
    return ann._root(text)


def _move_objects(root, state, deltas):
    page = root.find('page')
    for owner in state['owners']:
        dx,dy = deltas.get(owner['key'],(0,0))
        for element in page:
            if element.get('id') in owner['fragment_ids'] + owner['caption_ids']:
                transform(element,dx=dx,dy=dy)
    for record in state['curves']:
        a,b = (_owner_for_ref(root,state['owners'],record[end]) for end in ('source','target'))
        da,db = deltas.get(a,(0,0)),deltas.get(b,(0,0))
        if da != db:
            raise ValueError('Cross-owner curve movement requires equal owner translations; select a new route before moving one owner independently')
        curve = next(c for c in page.findall('curve') if c.get('id') == record['curve_id'])
        curve.set('CurvePoints',encode([v+da[i%2] for i,v in enumerate(numbers(curve.get('CurvePoints'),12))]))


def _page_fit(root):
    page = root.find('page'); left,top,right,bottom = numbers(page.get('BoundingBox'),4)
    if right <= left or bottom <= top: raise ValueError('Invalid native page bounds')
    boxes = []
    for e in page:
        if e.tag in ('fragment','t'): boxes.append(tuple(vars(bounds(e)).values()))
        if e.tag == 'curve':
            pts = numbers(e.get('CurvePoints'),12)
            boxes.append((min(pts[::2]),min(pts[1::2]),max(pts[::2]),max(pts[1::2])))
    for t in root.findall('page/fragment/n/t'):
        boxes.append(tuple(vars(bounds(t)).values()))
    for graphic in root.findall('page/fragment/graphic'):
        boxes.extend((x-r,y-r,x+r,y+r) for x,y,r in symbol_primitives(graphic,root.get('LineWidth','.6')))
    if any(x < left or y < top or xx > right or yy > bottom for x,y,xx,yy in boxes):
        raise ValueError('Moved owned geometry does not fit the native page bounds')


def plan_move(cdxml, ownership, moves):
    root = _validate_state(cdxml,ownership)
    if not isinstance(moves,list) or not 1 <= len(moves) <= 100:
        raise ValueError('Supply 1 through 100 explicit owner translations')
    keys = {owner['key'] for owner in ownership['owners']}; deltas = {}
    for move in moves:
        if not isinstance(move,dict) or set(move) != {'owner_key','delta'} or not isinstance(move['owner_key'],str) or move['owner_key'] not in keys or move['owner_key'] in deltas:
            raise ValueError('Each move requires one known, unique owner_key and delta')
        delta = ann._vec(move['delta'],500)
        if delta == (0,0): raise ValueError('No-op owner translation')
        deltas[move['owner_key']] = delta
    if root.findall('page/scheme') and any(delta[1] != 0 for delta in deltas.values()):
        raise ValueError('Unsupported vertical movement in a reaction scheme: ChemDraw can reassign or remove explicit reaction roles. Only horizontal owner moves are supported here; native role preservation is still required.')
    _move_objects(root,ownership,deltas); _page_fit(root)
    planned = ET.tostring(root,encoding='unicode')
    # Reverse only the requested translations and reuse strict mapped graph,
    # atom/text/symbol/curve preservation, rather than comparing formula alone.
    undo = copy.deepcopy(root)
    _move_objects(undo,ownership,{key:(-d[0],-d[1]) for key,d in deltas.items()})
    verify_symbols(cdxml,ET.tostring(undo,encoding='unicode'))
    state = build_ownership(planned,ownership['owners'],ownership['curves'])
    return planned,state,{'moves':copy.deepcopy(moves),'checks':{'planned_chemistry_preserved':True,'planned_page_bounds':True},
        'native_manual_drag_attachment':'not_verified','collision_review':'Not checked; explicit translations can overlap existing content',
        'cross_owner_curves':'Only equal translations of both anchor owners are supported'}


def _remap_state(state, text, mapping):
    owners = copy.deepcopy(state['owners']); curves = copy.deepcopy(state['curves'])
    for owner in owners:
        for field in ('fragment_ids','caption_ids'): owner[field] = [mapping[i] for i in owner[field]]
    for curve in curves:
        curve['curve_id'] = mapping[curve['curve_id']]
        for end in ('source','target'): curve[end]['id'] = mapping[curve[end]['id']]
    return build_ownership(text,owners,curves)


def move_document(bridge,document_id,output_dir,ownership,moves,expected_source_token,pixels=3200):
    out = _destination(output_dir,pixels); created = None
    audit = {'status':'in_progress','checks':{},'visual_review':'required'}
    with getattr(bridge,'lock',nullcontext()):
        baseline = _native(bridge.inspect,document_id)['document']; disk_hash = _file_hash(baseline)
        snapshot = bridge._new_path('.cdxml','backups'); _native(bridge.export,document_id,str(snapshot),'cdxml')
        source = snapshot.read_text()
        if source_token(source) != expected_source_token: raise ValueError('Source snapshot is stale')
        planned,state,plan = plan_move(source,ownership,moves)
        out.mkdir(); (out/'before.cdxml').write_text(source)
        _write_json(out/'recipe.json',{'schema_version':1,'ownership':ownership,'moves':moves,'expected_source_token':expected_source_token,'pixels':pixels})
        audit['plan'] = plan; _write_json(out/'audit.json',audit)
        try:
            for fmt in ('svg','png'): _native(bridge.export,document_id,str(out/f'before.{fmt}'),fmt,pixels)
            result = _native(bridge.create,planned); created = result['document']['document_id']
            audit['working_document_id'] = created; _write_json(out/'audit.json',audit)
            for fmt in ('svg','png','cdxml'): _native(bridge.export,created,str(out/f'figure.{fmt}'),fmt,pixels)
            final = (out/'figure.cdxml').read_text(); verification = verify_symbols(planned,final)
            _page_fit(ann._root(final))
            final_state = _remap_state(state,final,verification['id_map'])
            after = bridge._new_path('.cdxml','backups'); _native(bridge.export,document_id,str(after),'cdxml')
            if source_token(after.read_text()) != expected_source_token or _native(bridge.inspect,document_id)['document'] != baseline or _file_hash(baseline) != disk_hash:
                raise ValueError('Source changed during owned movement')
            audit.update(status='checks_passed',native_verification=verification,limitations=plan['collision_review'],native_manual_drag_attachment='not_verified')
            audit['checks'].update(verification['checks'],source_document_unchanged=True,ownership_remapped=True,native_page_bounds=True)
            _write_json(out/'ownership.json',final_state); _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Owned movement</title><h1>Owned movement copy</h1><p>Visual collision review required. Ownership sidecar controls future tool moves, not manual ChemDraw attachment.</p><img width="48%" src="before.png"><img width="48%" src="figure.png"><p><a href="figure.cdxml">Editable figure</a> <a href="ownership.json">Ownership</a> <a href="audit.json">Audit</a></p>')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'ownership':final_state,'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),recovery='No retry or automatic close; inspect owned copies and snapshots')
            _write_json(out/'audit.json',audit); raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            if created is not None:
                try: _native(bridge.close,created)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing)); _write_json(out/'audit.json',audit); raise
            _write_json(out/'audit.json',audit); raise


def move_file(bridge,path,output_dir,ownership,moves,expected_source_token=None,pixels=3200):
    out = _destination(output_dir,pixels); path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower() != '.cdxml': raise ValueError('Owned movement file input requires CDXML')
    with path.open('rb') as handle: data = handle.read(10_000_001)
    if len(data) > 10_000_000: raise ValueError('Source exceeds 10 MB')
    source = data.decode('utf-8'); plan_move(source,ownership,moves)
    if expected_source_token is not None and source_token(source) != expected_source_token: raise ValueError('Source file snapshot is stale')
    with getattr(bridge,'lock',nullcontext()):
        result = _native(bridge.create,source); did = result['document']['document_id']; uncertain = False; completed = None
        try:
            snapshot = bridge._new_path('.cdxml','backups'); _native(bridge.export,did,str(snapshot),'cdxml'); native = snapshot.read_text()
            mapped = _remap_state(ownership,native,verify_symbols(source,native)['id_map'])
            if path.read_bytes() != data: raise ValueError('Source file changed during import')
            completed = move_document(bridge,did,output_dir,mapped,moves,source_token(native),pixels)
            try: preserved = path.read_bytes() == data
            except OSError: preserved = False
            completed['audit'].update(source_file=str(path),source_file_sha256=hashlib.sha256(data).hexdigest())
            completed['audit']['checks']['source_file_unchanged'] = preserved
            if not preserved: completed['audit'].update(status='failed',error='Source file changed during owned movement')
            _write_json(out/'audit.json',completed['audit'])
            if not preserved:
                _native(bridge.close,completed['document']['document_id']); raise ValueError('Source file changed during owned movement')
            return completed
        except NativeUncertain: uncertain = True; raise
        finally:
            if not uncertain:
                try: _native(bridge.close,did)
                except NativeUncertain as exc:
                    if completed:
                        completed['audit'].update(status='uncertain',close_error=str(exc)); _write_json(out/'audit.json',completed['audit'])
                    raise


def plan_native_groups(cdxml,ownership):
    """Prepare integral native groups for an explicit serial compatibility probe.

    This is not enabled in move_document. No generic grouped-input parsing or
    manual-drag attachment guarantee is introduced by this format-only plan.
    """
    root = _validate_state(cdxml,ownership); page = root.find('page')
    next_id = max(int(e.get('id')) for e in root.iter() if e.get('id')) + 1
    records = []; cross = []
    curve_owners = {curve['curve_id']:[_owner_for_ref(root,ownership['owners'],curve[end])
                    for end in ('source','target')] for curve in ownership['curves']}
    for owner in ownership['owners']:
        ids = owner['fragment_ids'] + owner['caption_ids']
        for curve in ownership['curves']:
            owners = curve_owners[curve['curve_id']]
            if owners == [owner['key']]*2: ids.append(curve['curve_id'])
            elif owner['key'] == owners[0]: cross.append(curve['curve_id'])
        selected = [element for element in page if element.get('id') in ids]
        rectangles = []
        for element in selected:
            if element.tag == 'curve':
                pts = numbers(element.get('CurvePoints'),12); rectangles.append((min(pts[::2]),min(pts[1::2]),max(pts[::2]),max(pts[1::2])))
            else: rectangles.append(tuple(vars(bounds(element)).values()))
        box = (min(b[0] for b in rectangles),min(b[1] for b in rectangles),max(b[2] for b in rectangles),max(b[3] for b in rectangles))
        group = ET.Element('group',{'id':str(next_id),'BoundingBox':encode(box),'Integral':'yes'}); next_id += 1
        for element in selected: page.remove(element); group.append(element)
        page.append(group); records.append({'owner_key':owner['key'],'group_id':group.get('id'),'member_ids':[e.get('id') for e in group]})
    return ET.tostring(root,encoding='unicode'),{'groups':records,'ungrouped_cross_owner_curve_ids':cross,
        'native_manual_drag_attachment':'not_verified','status':'native_probe_required'}
