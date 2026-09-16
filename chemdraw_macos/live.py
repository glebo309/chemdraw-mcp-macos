"""Existing-document operations and background native rendering, without previews.

This is not an arbitrary native atom setter or an atomic human/agent edit lock.
"""
import hashlib
import json
from pathlib import Path

from .core import document_row, validate_cdxml
from .native_actions import ACTIONS
from .native_lock import native_transaction


def _state(bridge, did):
    row, visible, bounds, counts = bridge._run('live_state', did)
    return {'document': document_row(row), 'visible': visible,
            'selection': {'bounds_pt': bounds,
                          'counts': dict(zip(('atoms','bonds','molecules','captions'), counts))}}


def _content(text):
    root = validate_cdxml(text)
    for key in ('Name','CreationProgram','WindowPosition','WindowSize'):
        root.attrib.pop(key, None)
    def record(e):
        return (e.tag, sorted(e.attrib.items()), e.text if e.tag=='s' else (e.text or '').strip(),
                [record(c) for c in e])
    return root, record(root)


@native_transaction
def read_live_document(bridge, document_id):
    """Fresh native content; no new window, ownership change or chemical parsing."""
    did = bridge._id(document_id)
    before = _state(bridge, did)
    snapshot = bridge._new_path('.cdxml', 'backups')
    method='export'
    from .core import Bridge
    if isinstance(bridge,Bridge):
        from .addin import get_backend
        snapshot.write_text(get_backend(bridge).read(did)['cdxml'])
        method='desktop_addin'
    elif not before['document']['file']:
        from .shared import clipboard
        snapshot.write_text(clipboard(bridge,did)['cdxml'])
        method='clipboard'
    else:
        bridge.export(did, str(snapshot), 'cdxml')
    after = _state(bridge, did)
    for key in ('document_id','file'):
        if before['document'][key] != after['document'][key]:
            raise RuntimeError('Document binding changed while reading; no edit dispatched')
    if method in ('export','desktop_addin') and before['selection'] != after['selection']:
        raise RuntimeError('Selection changed while reading; no edit dispatched')
    root, content = _content(snapshot.read_text())
    if method in ('clipboard','desktop_addin'):
        from .shared import fingerprint
        content=fingerprint(snapshot.read_text())
    binding = [did, after['document']['file'], content, after['selection']]
    token = hashlib.sha256(json.dumps(binding, ensure_ascii=False).encode()).hexdigest()
    objects = []
    for e in root.iter():
        if e.tag not in ('CDXML','page','s','font','color','fonttable','colortable'):
            item = {'kind': e.tag, 'id': e.get('id'), 'attributes': dict(e.attrib)}
            if e.tag == 't':item['text'] = ''.join(e.itertext())
            objects.append(item)
    from .api_drawing import inspect_graphs
    return {**after, 'snapshot': str(snapshot), 'source_token': token, 'objects': objects,
            'molecular_graphs':inspect_graphs(snapshot.read_text()),
            'snapshot_method':method,'selection_changed':before['selection']!=after['selection'],
            'note': 'Fresh live graph, including unsaved edits. Molecular identity comes from molecular_graphs, never from captions, which may be stale. IDs belong to this snapshot.'}


@native_transaction
def live_action(bridge, document_id, action, expected_source_token, selection='current'):
    if action not in ACTIONS:raise ValueError('Unsupported native live action')
    if selection not in ('current','all'):raise ValueError('Selection must be current or all')
    if not isinstance(expected_source_token,str) or len(expected_source_token)!=64:
        raise ValueError('Expected a source token from read_live_document')
    did = bridge._id(document_id)
    before = read_live_document(bridge, did)
    if selection=='current' and before.get('selection_changed'):
        raise ValueError('Selection changed during snapshot; no action dispatched. Use an explicit all-object action or a saved document for current-selection editing.')
    if before['source_token'] != expected_source_token:
        raise ValueError('Document or selection changed; read the live document again before editing')
    # No ownership promotion: an attached user document must never become eligible
    # for close_working_document. Native script checks the front document itself.
    row, applied = bridge._run('native_action', did, ACTIONS[action], selection)
    after = read_live_document(bridge, did)
    if after['document']['file'] != before['document']['file']:
        raise RuntimeError(f'Document file changed during action; recovery snapshot: {before["snapshot"]}')
    return {'document': document_row(row), 'backup': before['snapshot'], 'current': after,
            'action': action, 'status': 'native_action_applied_review_required' if applied else 'unavailable_for_selection',
            'chemical_preservation_verified': False,
            'warning': 'Edits the existing document. Manual edits during dispatch are not locked; avoid drawing during this short operation. No automatic save to the original file, rollback or retry.'}


@native_transaction
def render_cdxml(bridge, cdxml, output_dir, background=True):
    """Render supplied CDXML, not a replacement high-level chemistry workflow."""
    if type(background) is not bool:raise ValueError('background must be a boolean')
    validate_cdxml(cdxml)
    out = Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output must be absolute with an existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output directory already exists')
    out.mkdir()
    result = bridge.create(cdxml, visible=not background)
    did = result['document']['document_id']
    artifacts = {}
    for fmt in ('cdxml','svg','png','pdf'):
        path = out / ('figure.' + fmt)
        bridge.export(did,str(path),fmt)
        artifacts[fmt] = str(path)
    # Never close on an uncertain export. A failed job leaves its only document
    # and available artifacts for recovery, even if the window is hidden.
    closed = bridge.close(did) if background else None
    report = {'document': result['document'], 'artifacts': artifacts,
              'document_closed': background, 'recovery': closed,
              'background': background, 'chemical_preservation_verified': False,
              'note': 'Native export of supplied CDXML. No preview page. Background means a hidden window in a logged-in licensed desktop session, not display-free server support. Opening may briefly show a window.'}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
