"""Explicit compound-ID grouping for any supported drawn molecule panel."""
from pathlib import Path
from .batch import _native, NativeUncertain
from .editing import source_token
from .scope import verify_scope
from .scope_decoration import decorate_scope_document
from .workflow import _write_json


def validate_draw_groups(groups, compound_ids):
    if not isinstance(groups, list) or not 1 <= len(groups) <= 20:
        raise ValueError('Supply 1 through 20 groups')
    seen = []; labels = set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {'label', 'compound_ids'}:
            raise ValueError('Groups require label and compound_ids')
        label = group['label']; ids = group['compound_ids']
        if (not isinstance(label, str) or not label.strip() or len(label) > 80 or
                any(ord(c) < 32 or ord(c) == 127 for c in label) or label in labels):
            raise ValueError('Group labels must be unique nonblank single-line text')
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise ValueError('Groups require a nonempty list of compound IDs')
        labels.add(label); seen.extend(ids)
    if len(seen) != len(set(seen)) or set(seen) != set(compound_ids):
        raise ValueError('Groups must own every compound exactly once')


def group_drawn_structures(bridge, document_id, text, cells, groups, output_dir,
                           columns=3, layout=None, frame=True, separators=True, pixels=3200):
    from .scope_job import arrange_scope_groups
    validate_draw_groups(groups, [c['compound_id'] for c in cells])
    out = Path(output_dir); out.mkdir()
    arranged, plan = arrange_scope_groups(text, cells, groups, columns, layout, frame, separators)
    (out/'planned.cdxml').write_text(arranged)
    _write_json(out/'group-layout.json', plan)
    gid = None
    try:
        grouped = _native(bridge.create, arranged); gid = grouped['document']['document_id']
        path = out/'grouped-native.cdxml'; _native(bridge.export, gid, str(path), 'cdxml')
        native = path.read_text()
        verification = verify_scope(arranged, native, plan['layout'])
        native_cells = {c['compound_id']: c for c in verification['cells']}
        decorated_groups = [{'label': g['label'],
            'fragment_ids': [fid for cid in g['compound_ids'] for fid in native_cells[cid]['fragment_ids']],
            'caption_ids': [tid for cid in g['compound_ids'] for tid in
                           (native_cells[cid].get('caption_id'), native_cells[cid].get('metadata_id')) if tid]}
                           for g in groups]
        result = decorate_scope_document(bridge, gid, str(out/'figure'), decorated_groups,
                                        source_token(native), frame=frame, separators=separators, pixels=pixels)
        _native(bridge.close, gid); gid = None
        result['group_plan'] = plan
        result['group_verification'] = verification
        result['artifacts'] = {fmt: str(out/'figure'/f'figure.{fmt}') for fmt in ('cdxml','svg','png')}
        return result
    except NativeUncertain:
        raise
    except Exception:
        if gid is not None: _native(bridge.close, gid)
        raise
