"""ChemDraw's own named commands on an open document.

Commands are dispatched by name through ChemDraw's scripting interface, the
same ``do command`` the menus use. Nothing here reimplements a command. File,
clipboard, application and network commands are refused; commands that have a
dedicated tool with stronger checks are routed there.
"""
from __future__ import annotations

import re
import time

from .core import document_row

POLL_INTERVAL = .08
COUNT_KEYS = ('atoms', 'bonds', 'molecules', 'captions', 'arrows')

_EXACT = {
    'quit': 'application lifecycle command',
    'print': 'file command (printing)',
    'showApplicationPreferences': 'application preferences change every document; set them in ChemDraw',
    'convertNameToStructure': 'may send the name over the network; use chemdraw_draw_name with allow_network',
    'predict1H_NMR_Shifts': 'use chemdraw_predict_nmr, which returns the parsed shifts',
    'predict13C_NMR_Shifts': 'use chemdraw_predict_nmr, which returns the parsed shifts',
    'checkStructure': 'use chemdraw_check_structure, which reads warnings without a modal alert',
    'repeatLastAction': 'repeats an unknown earlier action',
    'disabledDummyCommand': 'internal command',
    'openInChemDrawPlus': 'file command (opens another application)',
    'Add-in Manager...': 'add-in manager',
    'ChemACXExplorerAddIn': 'add-in that can use the network',
}
_PREFIXES = (
    ('open', 'file command'), ('save', 'file command'), ('close', 'file command'),
    ('new', 'file command'), ('ask', 'file command (file chooser)'),
    ('available', 'file command (opens or applies a file)'), ('revert', 'file command'),
    ('copy', 'clipboard command; read the document with chemdraw_read_live_document'),
    ('cut', 'clipboard command'), ('paste', 'clipboard command'),
    ('fake', 'internal command'), ('showHelp', 'opens help'),
)


def command_policy(name: str) -> tuple[bool, str | None]:
    """Return (allowed, reason). Refusal reasons name the safer route."""
    if not isinstance(name, str) or not name or len(name) > 200:
        return False, 'invalid command name'
    if name in _EXACT:
        return False, _EXACT[name]
    if ' > ' in name:
        # Windows names a menu item directly as 'Menu > Item' (windows_commands.py).
        from .windows_commands import menu_policy, split_menu_name
        reason = menu_policy(*split_menu_name(name))
        return (reason is None), reason
    if '://' in name:
        return False, 'network add-in command'
    if '/' in name:
        return False, 'file command (path-based stationery, sample or add-in)'
    if name.endswith('...') or name.endswith('…'):
        return False, 'add-in or file chooser'
    for prefix, reason in _PREFIXES:
        if name.startswith(prefix) and (len(name) == len(prefix) or not name[len(prefix)].islower()):
            return False, reason
    return True, None


def list_commands(bridge, pattern: str | None = None, enabled_only: bool = False, limit: int = 100) -> dict:
    """List ChemDraw's named commands with enabled state for the front document."""
    if not isinstance(limit, int) or not 1 <= limit <= 2000:
        raise ValueError('limit must be 1 through 2000')
    try:
        matcher = re.compile(pattern, re.I) if pattern else None
    except re.error as exc:
        raise ValueError(f'Invalid pattern: {exc}') from exc
    names, enabled, descriptions = bridge._run('list_commands')
    rows = []
    for name, on, description in zip(names, enabled, descriptions):
        if matcher and not matcher.search(name):
            continue
        if enabled_only and not on:
            continue
        allowed, reason = command_policy(name)
        row = {'name': name, 'enabled': bool(on), 'description': description or '', 'allowed': allowed}
        if reason:
            row['refused_because'] = reason
        rows.append(row)
    return {'count': len(rows), 'shown': min(len(rows), limit), 'commands': rows[:limit],
            'note': 'enabled reflects the front document and its current selection.'}


def _counts(row):
    return dict(zip(COUNT_KEYS, row)) if row is not None else None


_DIALOG_NEXT = 'Read the dialog, then answer it with chemdraw_dialog (fill fields, choose, press a button).'


def execute(bridge, document_id, native_command: str, selection: str = 'current', wait_seconds: float = 15) -> dict:
    """Dispatch one command and check completion and dialogs in the same native call.

    ChemDraw handles events in order, so the state read in that call follows
    the command. Only a long command (state "busy") needs further polling.
    No policy check here: callers decide which commands they expose.
    """
    from . import dialogs as dialog_module
    did = bridge._id(document_id)
    if selection not in ('current', 'all'):
        raise ValueError('selection must be current or all')
    if isinstance(wait_seconds, bool) or not isinstance(wait_seconds, (int, float)) or not 0 < wait_seconds <= 120:
        raise ValueError('wait_seconds must be greater than 0 and at most 120')
    process = dialog_module._process_name(bridge)
    with bridge.lock:
        reply = bridge._run('dispatch_command', did, native_command, selection, process)
        row, enabled, before, ids_before, windows_before = reply[:5]
        result = {'command': native_command, 'selection': selection, 'document': document_row(row),
                  'counts_before': _counts(before), 'counts_after': None,
                  'new_documents': [], 'dialogs': [], 'chemical_preservation_verified': False}
        if not enabled:
            return {**result, 'status': 'not_enabled',
                    'message': 'ChemDraw has this command disabled for the current selection or document; nothing was dispatched.'}
        state, dialogs_open = reply[5], reply[6]
        start = time.monotonic()
        while state == 'busy' and dialogs_open <= 0:
            if time.monotonic() - start >= wait_seconds:
                return {**result, 'status': 'still_running',
                        'message': 'ChemDraw has not answered yet. Do not dispatch again; check with chemdraw_dialog or chemdraw_list_documents.'}
            time.sleep(POLL_INTERVAL)
            state, dialogs_open = bridge._run('command_state', did, process)
        if state != 'busy':
            state_row, after, ids_after, windows_after = state
            result['document'] = document_row(state_row)
            result['counts_after'] = _counts(after)
            new_ids = [i for i in ids_after if i not in ids_before]
            if new_ids:
                rows = [document_row(r) for r in bridge._run('list')]
                result['new_documents'] = [r for r in rows if r['document_id'] in new_ids]
        if dialogs_open > 0:
            return {**result, 'status': 'dialog_open', 'dialogs': dialog_module.read_dialogs(bridge), 'next': _DIALOG_NEXT}
        if dialogs_open < 0:
            result['dialog_check'] = 'unavailable: grant Accessibility to the app running this server to detect ChemDraw dialogs'
        return {**result, 'status': 'completed'}


def run_command(bridge, document_id, command: str, selection: str = 'current', wait_seconds: float = 15) -> dict:
    allowed, reason = command_policy(command)
    if not allowed:
        raise ValueError(f'Refused ChemDraw command {command!r}: {reason}')
    if selection not in ('current', 'all'):
        raise ValueError('selection must be current or all')
    result = execute(bridge, document_id, command, selection, wait_seconds)
    result['undo'] = 'chemdraw_run_command(command="undo") reverts this in ChemDraw.'
    return result
