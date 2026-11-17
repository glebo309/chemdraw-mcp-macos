"""Windows side of named commands, dialogs and document settings.

UNVERIFIED ON WINDOWS. Written on macOS from the published ChemDraw COM model,
the Win32 dialog API and the behaviour of windows_native.py. Every COM call
here follows the patterns already measured there; the menu captions in
COMMAND_ALIASES and the dialog reading have not been run against a real
Windows ChemDraw yet. See docs/WINDOWS_NATIVE_COMMANDS_CHECKLIST.md.

Design, mirroring macOS:
- A command is a top-level menu item (COM exposes no submenu items). macOS
  command names that the shared tools use are mapped to menu captions; any
  item can also be named directly as "Menu > Item".
- Menu items are executed on a separate COM thread. A command that opens a
  modal dialog blocks that thread until the dialog closes, and never the
  bridge worker, which would otherwise be poisoned by its timeout.
- Dialogs are standard Win32 dialogs (#32770) of the ChemDraw process, read
  and answered through their controls with window messages. No keystrokes,
  no mouse, no other process.

The pure helpers at the top import nothing Windows-specific, so their tests
run on every platform.
"""
from __future__ import annotations

import re
import threading
import time

# macOS command name -> (menu caption, item caption). A trailing '*' matches a
# prefix (Undo/Redo captions name the action, e.g. "Undo Clean Up Structure").
# Captions are compared after normalize(); unverified ones are corrected from
# chemdraw_list_commands on Windows.
COMMAND_ALIASES = {
    'undo': ('Edit', 'Undo*'),
    'redo': ('Edit', 'Redo*'),
    'clear': ('Edit', 'Clear'),
    'selectAll': ('Edit', 'Select All'),
    'cleanStructure': ('Structure', 'Clean Up Structure'),
    'cleanReaction': ('Structure', 'Clean Up Reaction'),
    'expandLabel': ('Structure', 'Expand Label'),
    'contractLabel': ('Structure', 'Contract Label'),
    'checkStructure': ('Structure', 'Check Structure'),
    'convertStructureToName': ('Structure', 'Convert Structure to Name'),
    'predict1H_NMR_Shifts': ('Structure', 'Predict 1H-NMR Shifts'),
    'predict13C_NMR_Shifts': ('Structure', 'Predict 13C-NMR Shifts'),
    'mapReactionAtoms': ('Structure', 'Map Reaction Atoms'),
    'clearReactionMap': ('Structure', 'Clear Reaction Map'),
    'analyzeStoichiometry': ('Structure', 'Analyze Stoichiometry'),
    'group': ('Object', 'Group'),
    'ungroup': ('Object', 'Ungroup'),
    'bringToFront': ('Object', 'Bring to Front'),
    'sendToBack': ('Object', 'Send to Back'),
    'flipObjectsHorizontal': ('Object', 'Flip Horizontal'),
    'flipObjectsVertical': ('Object', 'Flip Vertical'),
    'showScaleDialog': ('Object', 'Scale'),
    'showRotationDialog': ('Object', 'Rotate'),
    'zoomToFit': ('View', 'Fit to Window'),
}

_SUPERSCRIPTS = str.maketrans({'¹': '1', '²': '2', '³': '3'})


def normalize(caption: str) -> str:
    """Menu caption without accelerator, shortcut, ellipsis, hyphens or case."""
    text = caption.replace('&', '').split('\t')[0].translate(_SUPERSCRIPTS)
    text = text.replace('…', '').replace('...', '').replace('-', ' ')
    return re.sub(r'\s+', ' ', text).strip().lower()


def split_menu_name(name: str):
    """'Structure > Clean Up Structure' -> ('Structure', 'Clean Up Structure'), else None."""
    if ' > ' not in name:
        return None
    menu, item = name.split(' > ', 1)
    return menu.strip(), item.strip()


def resolve(name: str):
    """(menu, item pattern) for a macOS alias or an explicit 'Menu > Item' name."""
    if name in COMMAND_ALIASES:
        return COMMAND_ALIASES[name]
    explicit = split_menu_name(name)
    if explicit:
        return explicit
    raise ValueError(f'No Windows menu item is known for {name!r}. List them with chemdraw_list_commands '
                     'and pass "Menu > Item" exactly as listed.')


def caption_matches(pattern: str, caption: str) -> bool:
    if pattern.endswith('*'):
        return normalize(caption).startswith(normalize(pattern[:-1]))
    return normalize(caption) == normalize(pattern)


def menu_policy(menu: str, item: str):
    """Refusals for 'Menu > Item' names, matching the macOS command policy."""
    m, i = normalize(menu), normalize(item)
    if m == 'file':
        return 'file command'
    if m == 'help' or m == 'online':
        return 'help or network command'
    if i.startswith(('copy', 'cut', 'paste')):
        return 'clipboard command'
    if i.startswith(('preferences', 'exit', 'quit', 'options')):
        return 'application preferences or lifecycle command'
    if i.startswith('predict 1h') or i.startswith('predict 13c'):
        return 'use chemdraw_predict_nmr, which returns the parsed shifts'
    if i.startswith('check structure'):
        return 'use chemdraw_check_structure, which reads warnings without a modal alert'
    if i.startswith('convert name to structure'):
        return 'may send the name over the network; use chemdraw_draw_name with allow_network'
    return None


# Win32 button styles (BS_TYPEMASK = 0x0F).
_BUTTON_KINDS = {0: 'button', 1: 'button', 2: 'checkbox', 3: 'checkbox', 5: 'checkbox', 6: 'checkbox',
                 4: 'radio', 9: 'radio', 7: 'group'}


def button_kind(style: int) -> str:
    return _BUTTON_KINDS.get(style & 0x0F, 'button')


def plain_label(text: str) -> str:
    return text.replace('&&', '\0').replace('&', '').replace('\0', '&').strip()


def describe_controls(title: str, controls: list) -> dict:
    """Dialog record from (class, style, text, checked) tuples in tab order."""
    d = {'kind': 'dialog', 'window': title, 'text': [], 'buttons': [], 'fields': [],
         'radio_buttons': [], 'checkboxes': []}
    for cls, style, text, checked in controls:
        cls = cls.lower()
        if cls == 'static':
            if text.strip():
                d['text'].append(text.strip())
        elif cls == 'edit' or cls.startswith('combobox'):
            d['fields'].append({'index': len(d['fields']) + 1, 'value': text})
        elif cls == 'button':
            kind, label = button_kind(style), plain_label(text)
            if kind == 'button' and label:
                d['buttons'].append(label)
            elif kind == 'radio':
                d['radio_buttons'].append({'name': label, 'selected': bool(checked)})
            elif kind == 'checkbox':
                d['checkboxes'].append({'name': label, 'checked': bool(checked)})
    return d


# ---------------------------------------------------------------- Win32 dialogs (no COM)

WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT = 0x000D, 0x000E, 0x000C
BM_GETCHECK, BM_CLICK = 0x00F0, 0x00F5
GWL_STYLE = -16
SMTO_ABORTIFHUNG = 0x0002


def _user32():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                           wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    return user32


def _send(hwnd, message, wparam=0, lparam=0, timeout_ms=2000):
    import ctypes
    result = ctypes.c_size_t()
    if not _user32().SendMessageTimeoutW(hwnd, message, wparam, lparam, SMTO_ABORTIFHUNG, timeout_ms,
                                         ctypes.byref(result)):
        raise RuntimeError('ChemDraw did not answer a dialog message in time; nothing was retried')
    return result.value


def _text(hwnd) -> str:
    import ctypes
    length = _send(hwnd, WM_GETTEXTLENGTH)
    buffer = ctypes.create_unicode_buffer(length + 1)
    _send(hwnd, WM_GETTEXT, length + 1, ctypes.addressof(buffer))
    return buffer.value


def _chemdraw_pids() -> set:
    """Process IDs whose executable is ChemDraw.exe (no COM call)."""
    import ctypes
    import win32gui
    import win32process
    pids, kernel = set(), ctypes.WinDLL('kernel32')
    def visit(hwnd, _):
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        if pid in pids:
            return True
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            try:
                size = ctypes.c_ulong(1024)
                name = ctypes.create_unicode_buffer(1024)
                if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                    if name.value.lower().endswith('\\chemdraw.exe'):
                        pids.add(pid)
            finally:
                kernel.CloseHandle(handle)
        return True
    win32gui.EnumWindows(visit, None)
    return pids


def _dialog_windows() -> list:
    import win32gui
    import win32process
    pids = _chemdraw_pids()
    found = []
    def visit(hwnd, _):
        if (win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == '#32770'
                and win32process.GetWindowThreadProcessId(hwnd)[1] in pids):
            found.append(hwnd)
        return True
    win32gui.EnumWindows(visit, None)
    return found


def _controls(dialog) -> list:
    import win32gui
    handles = []
    win32gui.EnumChildWindows(dialog, lambda h, _: handles.append(h) or True, None)
    rows = []
    for h in handles:
        if not win32gui.IsWindowVisible(h):
            continue
        cls = win32gui.GetClassName(h)
        style = win32gui.GetWindowLong(h, GWL_STYLE)
        checked = cls.lower() == 'button' and button_kind(style) in ('radio', 'checkbox') and _send(h, BM_GETCHECK) == 1
        rows.append((h, cls, style, _text(h), checked))
    return rows


def dialog_count() -> int:
    return len(_dialog_windows())


def read_dialogs() -> list:
    out = []
    for index, dialog in enumerate(_dialog_windows()):
        rows = _controls(dialog)
        record = describe_controls(_text(dialog), [(c, s, t, k) for _, c, s, t, k in rows])
        out.append({'index': index, **record})
    return out


def act_dialog(request: dict) -> None:
    import ctypes
    dialogs = _dialog_windows()
    if not 0 <= request['dialog'] < len(dialogs):
        raise RuntimeError('The dialog closed before it could be answered; read it again')
    dialog = dialogs[request['dialog']]
    if _text(dialog) != request['window']:
        raise RuntimeError('The dialog changed before it could be answered; read it again')
    rows = _controls(dialog)
    fields = [h for h, c, *_ in rows if c.lower() == 'edit' or c.lower().startswith('combobox')]
    def named(kind, name):
        for h, c, s, t, _ in rows:
            if c.lower() == 'button' and button_kind(s) == kind and plain_label(t) == name:
                return h
        raise RuntimeError(f'{kind} {name!r} is absent from the dialog')
    for key, value in (request.get('fields') or {}).items():
        index = int(key) - 1
        if not 0 <= index < len(fields):
            raise RuntimeError(f'Dialog field {key} is absent')
        text = ctypes.create_unicode_buffer(str(value))
        _send(fields[index], WM_SETTEXT, 0, ctypes.addressof(text))
    if request.get('choose'):
        _send(named('radio', request['choose']), BM_CLICK)
    for name, wanted in (request.get('check') or {}).items():
        box = named('checkbox', name)
        if (_send(box, BM_GETCHECK) == 1) != wanted:
            _send(box, BM_CLICK)
    _send(named('button', request['button']), BM_CLICK)


# ---------------------------------------------------------------- COM command execution

class _Pending:
    def __init__(self):
        self.done = threading.Event()
        self.error = None


_pending: _Pending | None = None


def find_menu_item(app, menu_caption, item_pattern):
    """Top-level menu item by caption pattern (see caption_matches); COM objects of this thread."""
    available = []
    for bar in app.MenuBars:
        for menu in bar.Menus:
            if normalize(menu.caption) != normalize(menu_caption):
                continue
            for item in menu.MenuItems:
                if not item.CommandID:
                    continue
                available.append(item.caption.replace('&', '').split('\t')[0].strip())
                if caption_matches(item_pattern, item.caption):
                    return item
    raise ValueError(f'ChemDraw menu item {menu_caption} > {item_pattern.rstrip("*")} was not found; '
                     f'{menu_caption} has: {available}')


def list_menu_commands(app):
    """[names, enabled, descriptions]: macOS aliases that resolve, then every 'Menu > Item'."""
    items = []
    for bar in app.MenuBars:
        for menu in bar.Menus:
            for item in menu.MenuItems:
                if item.CommandID:
                    items.append((menu.caption.replace('&', '').strip(),
                                  item.caption.replace('&', '').split('\t')[0].strip(), bool(item.Enabled)))
    names, enabled, descriptions = [], [], []
    for alias, (menu, pattern) in COMMAND_ALIASES.items():
        for m, i, on in items:
            if normalize(m) == normalize(menu) and caption_matches(pattern, i):
                names.append(alias); enabled.append(on); descriptions.append(f'{m} > {i}')
                break
    for m, i, on in items:
        names.append(f'{m} > {i}'); enabled.append(on); descriptions.append('')
    return [names, enabled, descriptions]


def start_command(menu_caption, item_pattern):
    """Execute a menu item on its own COM thread; the caller polls pending_done()."""
    global _pending
    if _pending is not None and not _pending.done.is_set():
        raise RuntimeError('A previous ChemDraw command is still running or waiting for its dialog; '
                           'answer the dialog first. Nothing was dispatched.')
    pending = _Pending()
    def work():
        import pythoncom
        from .windows_native import _attach
        pythoncom.CoInitialize()
        try:
            app = _attach()
            if app is None:
                raise RuntimeError('ChemDraw is not running')
            find_menu_item(app, menu_caption, item_pattern).Execute()
        except BaseException as exc:
            pending.error = exc
        finally:
            pending.done.set()
            pythoncom.CoUninitialize()
    _pending = pending
    threading.Thread(target=work, name='chemdraw-command', daemon=True).start()
    return pending


def pending_busy() -> bool:
    return _pending is not None and not _pending.done.is_set()


def wait_for(pending: _Pending, seconds: float) -> str:
    """'done', 'dialog' or 'busy' after at most `seconds`."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if pending.done.wait(.05):
            return 'done'
        if dialog_count():
            return 'dialog'
    return 'busy'


# Document.Settings property -> settings order used by the shared code (twentieths of a point).
SETTINGS = (('BondLength', 20), ('LineWidth', 20), ('BoldWidth', 20), ('LabelSize', 20), ('CaptionSize', 20),
            ('LabelFont', None), ('CaptionFont', None), ('BondSpacing', 1), ('ChainAngle', 1),
            ('MarginWidth', 20), ('HashSpacing', 20))
SETTING_NAMES = {'fixed length': 'BondLength', 'line width': 'LineWidth', 'bold width': 'BoldWidth',
                 'label size': 'LabelSize', 'caption size': 'CaptionSize', 'label font': 'LabelFont',
                 'caption font': 'CaptionFont', 'bond spacing': 'BondSpacing', 'chain angle': 'ChainAngle',
                 'margin width': 'MarginWidth', 'hash spacing': 'HashSpacing'}


def read_settings(settings) -> list:
    values = []
    for prop, scale in SETTINGS:
        value = getattr(settings, prop)
        values.append(value if scale is None else round(float(value) * scale))
    return values + [None]  # magnification: not part of COM Settings


def write_settings(settings, pairs) -> None:
    for name, value in pairs:
        if name == 'magnification':
            raise RuntimeError('Magnification is not available through Windows ChemDraw automation')
        prop = SETTING_NAMES.get(name)
        if prop is None:
            raise RuntimeError('Unsupported document setting')
        scale = dict(SETTINGS)[prop]
        setattr(settings, prop, value if scale is None else int(value) / scale)


def object_counts(root, top_fragments) -> list:
    """[atoms, bonds, molecules, captions, arrows] from native CDXML, like the macOS counts."""
    fragments = top_fragments(root)
    atoms = sum(1 for f in fragments for n in f.iter('n'))
    bonds = sum(1 for f in fragments for b in f.iter('b'))
    captions = sum(1 for page in root.findall('page') for e in page if e.tag == 't')
    arrows = sum(1 for e in root.iter() if e.tag == 'arrow')
    return [atoms, bonds, len(fragments), captions, arrows]
