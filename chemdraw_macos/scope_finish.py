"""Finish a newly owned scope in its existing window, never a user original."""
from .core import validate_cdxml
from .batch import NativeUncertain
from .polish import chemical_signature
from .scope_decoration import verify_scope_decoration
from .shared import fingerprint


def finish_scope(bridge, document_id, expected, arranged, decorated, decoration):
    from .addin import get_backend
    did=bridge._id(document_id)
    if did not in bridge.managed:
        raise ValueError('Scope finishing requires a session-owned document')
    verify_scope_decoration(arranged,decorated,decoration)
    if chemical_signature(expected)!=chemical_signature(arranged):
        raise ValueError('Scope finishing must preserve every molecular graph')
    with bridge.lock:
        backend=get_backend(bridge)
        initial=backend.read(did);doc=initial['document']
        if (doc.get('modified') or not doc.get('file') or
                fingerprint(initial['cdxml'])!=fingerprint(expected)):
            raise NativeUncertain('Working scope changed; retained untouched, no finishing write sent')
        if bridge._run('active_document')!=did:
            raise NativeUncertain('Working scope is no longer active; retained untouched')
        backup=bridge._new_path('.cdxml','backups');backup.write_text(initial['cdxml'])
        planned=bridge._new_path('.cdxml','backups');planned.write_text(decorated)
        try:
            # Native guards run again immediately before selection/clear. This
            # command is private, owned-only and never exposed as an MCP tool.
            bridge._run('clear_owned_scope',did,doc['file'])
            blank=backend.read(did)
            root=validate_cdxml(blank['cdxml']);pages=root.findall('page')
            if (blank['document']['file']!=doc['file'] or len(pages)!=1 or len(pages[0])):
                raise ValueError('Working scope was not empty after clear')
            reply=backend.channel.request('append',expected=blank['cdxml'],cdxml=decorated)
            if reply.get('error'):raise ValueError(reply['error'])
            after=reply['cdxml']
            snapshot=bridge._new_path('.cdxml','backups');snapshot.write_text(after)
            if bridge._run('active_document')!=did:raise ValueError('Active document changed')
            verify_scope_decoration(arranged,after,decoration)
            row=next(d for d in bridge.documents()['documents'] if d['document_id']==did)
            if row['file']!=doc['file']:raise ValueError('Working file binding changed')
            return {'document':row,'before_snapshot':str(backup),'after_snapshot':str(snapshot)}
        except Exception as exc:
            raise NativeUncertain('Scope finishing stopped; retain this document and do not retry. '
                f'Recovery: {backup}; planned table: {planned}. '+str(exc)) from exc
