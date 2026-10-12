"""Windows COM implementation of the bounded native bridge (ChemDraw x64 automation).

Observed on ChemDraw 26.1 Windows (Phase 1 report of the Windows handoff):
- the running application is attached through the Running Object Table; documents have
  no numeric ID, so IDs are derived from the ChemDraw process and Name/FullName;
- Documents.Open()/Add() without Activate() is windowless and disappears when released
  (used for hidden measuring copies); Activate() makes a normal, persistent window;
- Objects.Data put appends CDXML but re-centres it; COM object IDs equal CDXML ids, so the
  inserted objects are isolated with Clone()/Remove() and moved back to supplied coordinates;
- Document.Close() is a no-op; File>Close is the native command that closes a document;
- automation writes do not set Modified, so visible targets are marked modified explicitly;
- PDF export is not offered by Windows ChemDraw.

Every COM object lives on one worker thread. Calls are bounded; a timeout poisons the
worker so that no later native write can follow an uncertain one.
"""
from __future__ import annotations

import gc
import hashlib
import math
import os
from pathlib import Path
import queue
import re
import struct
import threading
import xml.etree.ElementTree as ET

PROGID = 'ChemDraw_x64.Application'
APP_CLSID = '{C172F840-938F-4A55-A732-4A036E3FBF3D}'
CDXML = 'text/xml'
CDX = 'chemical/x-cdx'
SVG = 'image/svg+xml'
EMF = 'image/x-emf'
NAME = 'chemical/x-name'
EXPORTS = {'Scalable Vector Graphics (SVG)': SVG, 'ChemDraw XML': CDXML, 'ChemDraw': CDX}
MENU_COMMANDS = {
    'cleanStructure': ('Structure', 'Clean Up Structure'),
    'cleanReaction': ('Structure', 'Clean Up Reaction'),
    'expandLabel': ('Structure', 'Expand Label'),
    'contractLabel': ('Structure', 'Contract Label'),
}
# Align/Distribute are submenus; the COM menu API exposes no submenu items.
SUBMENU_ONLY = {'alignLeftEdges', 'alignRightEdges', 'alignTopEdges', 'alignBottomEdges',
                'alignLeftRightCenters', 'alignTopBottomCenters',
                'distributeObjectsHorizontally', 'distributeObjectsVertically'}


class NativeError(RuntimeError):
    """A bounded native refusal or failure, already explained for the user."""


# ---------------------------------------------------------------- installation

def app_location() -> Path:
    """ChemDraw.exe from CHEMDRAW_APP or the registered automation server, never a guess."""
    explicit = os.environ.get('CHEMDRAW_APP')
    if explicit:
        return Path(explicit).expanduser().resolve()
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf'CLSID\{APP_CLSID}\LocalServer32', 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            command = winreg.QueryValue(key, None)
    except OSError as exc:
        raise RuntimeError('ChemDraw automation (ChemDraw_x64.Application) is not registered; '
                           'set CHEMDRAW_APP to ChemDraw.exe') from exc
    return Path(server_executable(command))


def app_version(path) -> str:
    """Executable file version, e.g. '26.1.0.6327' (from the version resource, not the filename)."""
    import win32api
    info = win32api.GetFileVersionInfo(str(path), '\\')
    ms, ls = info['FileVersionMS'], info['FileVersionLS']
    return f'{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}'


def app_metadata(path) -> dict:
    """Version-resource strings of an executable (ProductName, CompanyName, OriginalFilename) and version."""
    import win32api
    result = {'version': app_version(path)}
    for language, codepage in win32api.GetFileVersionInfo(str(path), '\\VarFileInfo\\Translation')[:4]:
        for key in ('ProductName', 'CompanyName', 'OriginalFilename'):
            if key not in result:
                try:
                    result[key] = win32api.GetFileVersionInfo(
                        str(path), f'\\StringFileInfo\\{language:04x}{codepage:04x}\\{key}')
                except win32api.error:
                    continue
    return result


def server_executable(command: str) -> str:
    """'"C:\\...\\ChemDraw.exe" /Automation' or 'C:\\...\\ChemDraw.exe /Automation' -> exe path."""
    command = command.strip()
    if command.startswith('"'):
        return command[1:command.index('"', 1)]
    match = re.match(r'(.+?\.exe)\b', command, re.IGNORECASE)
    if not match:
        raise RuntimeError('Unrecognized ChemDraw automation server registration')
    return match.group(1)


# ---------------------------------------------------------------- worker thread

class _Worker:
    def __init__(self):
        self._jobs: queue.Queue = queue.Queue()
        self._thread = None
        self._start = threading.Lock()
        self.poisoned = None

    def _loop(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            while True:
                fn, box, done = self._jobs.get()
                try:
                    box['value'] = fn()
                except BaseException as exc:  # returned to the caller thread
                    box['error'] = exc
                finally:
                    done.set()
        finally:
            pythoncom.CoUninitialize()

    def call(self, fn, timeout):
        if self.poisoned:
            raise RuntimeError(self.poisoned)
        with self._start:
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, name='chemdraw-com', daemon=True)
                self._thread.start()
        box, done = {}, threading.Event()
        self._jobs.put((fn, box, done))
        if not done.wait(timeout):
            self.poisoned = ('A ChemDraw automation call timed out, possibly behind a dialog. Its outcome is '
                             'uncertain and it was not retried. Inspect ChemDraw, then restart this client.')
            raise RuntimeError(self.poisoned)
        if 'error' in box:
            raise box['error']
        return box['value']


_worker = _Worker()
_hidden: dict = {}       # document_id -> windowless COM document held by this process (worker thread only)


# ---------------------------------------------------------------- COM helpers (worker thread only)

def _com_error(exc):
    try:
        hr, msg, info, _ = exc.args
        detail = (info[2] if info and info[2] else msg) or 'COM error'
        return NativeError(f'ChemDraw automation failed: {detail} (HRESULT {hr & 0xFFFFFFFF:#010x})')
    except Exception:
        return NativeError('ChemDraw automation failed: ' + str(exc))


def _attach():
    import pythoncom
    import win32com.client
    try:
        return win32com.client.GetActiveObject(PROGID)
    except pythoncom.com_error:
        return None


def _app():
    app = _attach()
    if app is None:
        raise NativeError('ChemDraw is not running')
    return app


def _pid(app):
    import win32process
    return win32process.GetWindowThreadProcessId(int(app.MainWindow))[1]


def _key(doc):
    return doc.FullName if doc.Path else doc.Name


def document_id(pid, key):
    """Deterministic positive 31-bit ID per ChemDraw process and document identity."""
    digest = hashlib.sha256(f'{pid}\0{key}'.encode('utf-8')).digest()
    return (int.from_bytes(digest[:4], 'big') & 0x7FFFFFFF) or 1


def _docs(app):
    docs = app.Documents
    return [docs.Item(i) for i in range(1, docs.Count + 1)]


def _data(objects, mime):
    import pythoncom
    dispid = objects._oleobj_.GetIDsOfNames('Data')
    value = objects._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYGET, True, mime)
    if isinstance(value, (bytes, memoryview)):
        return bytes(value)
    return value


def _put_data(objects, mime, value):
    import pythoncom
    dispid = objects._oleobj_.GetIDsOfNames('Data')
    objects._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, False, mime, value)


def parse(text):
    """Parse ChemDraw CDXML (with its DOCTYPE and encoding-free declaration)."""
    body = re.sub(r'<!DOCTYPE[^>]*>', '', text, count=1)
    if body.lstrip().startswith('<?xml'):
        body = body.split('?>', 1)[1]
    return ET.fromstring(body.encode('utf-8'))


def top_fragments(root):
    """Molecules: fragments on the page or inside groups, not nicknames inside atoms."""
    found = []
    def walk(parent):
        for child in parent:
            if child.tag == 'fragment':
                found.append(child)
            elif child.tag == 'group':
                walk(child)
    for page in root.findall('page'):
        walk(page)
    return found


def _row(app, doc, pid=None, count=True):
    pid = _pid(app) if pid is None else pid
    molecules = len(top_fragments(parse(_data(doc.Objects, CDXML)))) if count else 0
    return [document_id(pid, _key(doc)), doc.Name, doc.FullName if doc.Path else '', bool(doc.Modified), molecules]


def _find(app, did, pid=None):
    pid = _pid(app) if pid is None else pid
    matches = [d for d in _docs(app) if document_id(pid, _key(d)) == did]
    if not matches:
        raise NativeError('Document ID is stale or absent; list documents again')
    if len(matches) > 1:
        raise NativeError('Document identity is ambiguous (two documents share a name/path); close one')
    return matches[0]


def _active_id(app, pid=None):
    if app.Documents.Count == 0:
        return None
    active = app.ActiveDocument
    return None if active is None else document_id(_pid(app) if pid is None else pid, _key(active))


def _require_active(app, did, message):
    if _active_id(app) != did:
        raise NativeError(message)


def _title_dirty(app):
    import win32gui
    return win32gui.GetWindowText(int(app.MainWindow)).rstrip().endswith('*]')


def _menu_item(app, menu_caption, item_caption):
    def plain(text):
        return text.replace('&', '').split('\t')[0].strip()
    for bar in app.MenuBars:
        for menu in bar.Menus:
            if plain(menu.caption) != menu_caption:
                continue
            for item in menu.MenuItems:
                if plain(item.caption) == item_caption and item.CommandID:
                    return item
    raise NativeError(f'ChemDraw menu command {menu_caption} > {item_caption} is not available')


def _raw_items(collection):
    """The collection's objects as raw IDispatch pointers, in collection order.

    pywin32's dynamic wrapper rebuilds type information for every enumerated object; measured on
    ChemDraw 26.1 the raw pointers return the same objects about four times faster (0.07 s instead
    of 0.27 s for a 406-object drawing), and each drawing walks the collection several times.
    """
    import pythoncom
    enum = collection._oleobj_.InvokeTypes(pythoncom.DISPID_NEWENUM, 0,
                                           pythoncom.DISPATCH_METHOD | pythoncom.DISPATCH_PROPERTYGET,
                                           (pythoncom.VT_UNKNOWN, 0), ()).QueryInterface(pythoncom.IID_IEnumVARIANT)
    while True:
        batch = enum.Next(256)
        if not batch:
            return
        for item in batch:
            yield item if hasattr(item, 'Invoke') else item.QueryInterface(pythoncom.IID_IDispatch)


def _raw_id(item):
    import pythoncom
    # The DISPID is looked up per object, never assumed across object types.
    return item.Invoke(item.GetIDsOfNames('ID'), 0, pythoncom.DISPATCH_PROPERTYGET, True)


def _ids(collection):
    return [_raw_id(item) for item in _raw_items(collection)]


def _isolate(doc, wanted, items=None):
    """A detached collection holding exactly the objects with the given native IDs.

    Measured on ChemDraw 26.1: Objects.Clone().Remove() can silently remove nothing, and Add()
    into a FilterByTag() result is ignored; Add() into a clone of an empty selection works and
    leaves the selection unchanged. COM insertion clears the selection, so after an insert the
    selection is empty; anywhere else a non-empty selection fails closed. Reading Count on the
    empty clone before Add() makes every later Add() a silent no-op, so only the live selection
    is counted. items: (ID, object) pairs from a pass over doc.Objects just made by the caller,
    with no change to the document since.
    """
    if doc.Selection.Objects.Count:
        raise NativeError('ChemDraw has a selection in this document; clear it, then retry. No change was made')
    collection = doc.Selection.Objects.Clone()
    for oid, item in items if items is not None else ((_raw_id(i), i) for i in _raw_items(doc.Objects)):
        if oid in wanted:
            collection.Add(item)
    held = set(_ids(collection))
    if held != set(wanted):
        raise NativeError(f'Native objects could not be isolated for this operation '
                          f'({len(set(wanted) - held)} missing, {len(held - set(wanted))} extra of {len(wanted)})')
    return collection


# ---------------------------------------------------------------- metadata annotations

METADATA_ANNOTATION_KEYS = {'id', 'Keyword', 'Content'}


def split_metadata(text):
    """Remove page-level document metadata annotations (template Keyword/Content pairs).

    They are not drawing objects. Anything else, including annotations with children or
    other attributes, is left in place and remains subject to the normal fail-closed checks.
    Returns (normalized CDXML, sorted metadata records).
    """
    root = parse(text)
    records = []
    for page in root.findall('page'):
        for e in list(page):
            if e.tag == 'annotation' and not len(e) and set(e.attrib) <= METADATA_ANNOTATION_KEYS:
                records.append((e.get('Keyword', ''), e.get('Content', '')))
                page.remove(e)
    if not records:
        return text, []
    return ET.tostring(root, encoding='unicode'), sorted(records)


# ---------------------------------------------------------------- placement

def _points(root, ids=None):
    """Geometric anchors of page objects: atom positions and page-level caption positions.

    Atom-label text inside atoms is excluded: ChemDraw re-lays it out with the target
    document's label font, so it is derived output, not supplied geometry.
    """
    out = []
    for page in root.findall('page'):
        for top in page:
            if ids is not None and top.get('id') not in ids:
                continue
            anchors = [top] if top.tag == 't' else list(top.iter('n'))
            for e in anchors:
                if e.get('p'):
                    x, y = map(float, e.get('p').split())
                    out.append((e.tag, x, y))
    return out


def rigid_offset(native_points, supplied_points, tolerance=0.05):
    """Translation that maps supplied points onto the native ones, or None if not rigid.

    Points are paired by proximity, each supplied point at most once. A sorted comparison is not
    used: rounding can swap two points with nearly equal x (observed for captions in one column).
    """
    if not supplied_points or len(native_points) != len(supplied_points):
        return None
    dx = min(p[1] for p in native_points) - min(p[1] for p in supplied_points)
    dy = min(p[2] for p in native_points) - min(p[2] for p in supplied_points)
    cells = {}
    for t, x, y in supplied_points:
        cells.setdefault((t, math.floor(x / tolerance), math.floor(y / tolerance)), []).append((x, y))

    def take(t, x, y):
        cx, cy = math.floor(x / tolerance), math.floor(y / tolerance)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                bucket = cells.get((t, cx + i, cy + j), [])
                for k, (sx, sy) in enumerate(bucket):
                    if abs(sx - x) <= tolerance and abs(sy - y) <= tolerance:
                        del bucket[k]
                        return True
        return False

    if not all(take(t, x - dx, y - dy) for t, x, y in native_points):
        return None
    return dx, dy


def _insert_exact(doc, payload):
    """Append payload at its supplied coordinates. Returns the native CDXML afterwards."""
    supplied = parse(payload)
    page = supplied.find('page')
    pages = int(page.get('HeightPages', '1')) if page is not None else 1
    if pages > int(doc.NumPagesHigh):
        doc.NumPagesHigh = pages
    # Objects present before come from the CDXML (COM IDs are its ids, unique document-wide; measured
    # on ChemDraw 26.1), not from a slow pass over every object. The object count, one cheap call,
    # guards that exactly the inserted objects are taken as new.
    known = {e.get('id') for page in parse(_data(doc.Objects, CDXML)).findall('page') for e in page.iter()
             if e is not page and e.get('id')}
    before_count = doc.Objects.Count
    _put_data(doc.Objects, CDXML, payload)
    after = [(_raw_id(item), item) for item in _raw_items(doc.Objects)]
    after_ids = [oid for oid, _ in after]
    new = {oid for oid in after_ids if str(oid) not in known}
    if not new or len(after_ids) != len(set(after_ids)) or len(new) != len(after_ids) - before_count:
        raise NativeError('Inserted objects could not be identified natively')
    native = parse(_data(doc.Objects, CDXML))
    offset = rigid_offset(_points(native, {str(i) for i in new}), _points(supplied))
    if offset is None:
        raise NativeError('Native insertion was not a rigid translation of the supplied objects')
    if abs(offset[0]) > 0.005 or abs(offset[1]) > 0.005:
        _isolate(doc, new, after).Move(-offset[0], -offset[1])
    return _data(doc.Objects, CDXML)


# ---------------------------------------------------------------- operations

def _arg_bool(value):
    return str(value).lower() == 'true'


def _op_list(app):
    pid = _pid(app)
    return [_row(app, d, pid) for d in _docs(app)]


def _op_active_document(app):
    return _active_id(app)


def _op_active_document_state(app):
    if app.Documents.Count == 0:
        return None
    did = _active_id(app)
    row = _row(app, _find(app, did))
    if _active_id(app) != row[0]:
        raise NativeError('Active document changed during read')
    return row


def _op_visible_documents(app):
    pid = _pid(app)
    return [document_id(pid, _key(d)) for d in _docs(app) if document_id(pid, _key(d)) not in _hidden]


def _op_open(app, path, visible='true'):
    target = os.path.normcase(os.path.abspath(path))
    doc = app.Documents.Open(str(path))
    matches = [d for d in _docs(app) if d.Path and os.path.normcase(os.path.abspath(d.FullName)) == target]
    if len(matches) != 1:
        raise NativeError('Could not identify the imported document uniquely')
    doc = matches[0]
    did = document_id(_pid(app), _key(doc))
    if _arg_bool(visible):
        doc.Activate()
    else:
        _hidden[did] = doc
    return _row(app, doc)


def _op_visibility(app, did, visible):
    did = int(did)
    doc = _find(app, did)
    if _arg_bool(visible) and did in _hidden:
        doc.Activate()
        del _hidden[did]
    return [_row(app, doc), did not in _hidden]


def _op_live_state(app, did):
    did = int(did)
    doc = _find(app, did)
    sel = doc.Selection
    objects = sel.Objects
    count = objects.Count
    bounds = [objects.Left, objects.Top, objects.Right, objects.Bottom] if count else [0.0, 0.0, 0.0, 0.0]
    molecules = len(top_fragments(parse(_data(objects, CDXML)))) if count else 0
    counts = [sel.Atoms.Count, sel.Bonds.Count, molecules, sel.Captions.Count]
    return [_row(app, doc), did not in _hidden, bounds, counts]


def _op_inspect(app, did):
    doc = _find(app, int(did))
    root = parse(_data(doc.Objects, CDXML))
    molecules = []
    for i, f in enumerate(top_fragments(root), 1):
        box = f.get('BoundingBox')
        molecules.append([i, [float(v) for v in box.split()] if box else None])
    s = doc.Settings
    settings = [round(s.BondLength * 20, 2), round(s.LineWidth * 20, 2), round(s.LabelSize * 20, 2),
                s.LabelFont, round(s.CaptionSize * 20, 2), s.CaptionFont]
    return [_row(app, doc), molecules, settings]


def _op_export(app, did, path, format_name):
    doc = _find(app, int(did))
    if format_name == 'PDF':
        raise NativeError('PDF export is not available from Windows ChemDraw; export SVG or CDXML instead')
    mime = EXPORTS.get(format_name)
    if mime is None:
        raise NativeError('Unsupported export format')
    value = _data(doc.Objects, mime)
    data = value if isinstance(value, bytes) else value.encode('utf-8')
    if not data:
        raise NativeError('ChemDraw returned an empty export')
    if mime == SVG:
        data = _record_faces(doc.Objects, data)
    with open(path, 'xb') as handle:
        handle.write(data)
    return _row(app, doc)


def _record_faces(objects, svg):
    """Record which installed faces ChemDraw measured, from its metafile of the same objects.

    ChemDraw names only a family and CSS weight in SVG; its metafile carries per-glyph advances
    that identify the face actually used (see native_faces). Stored as an SVG comment for later
    rasterization. Evidence is optional: without a usable metafile the native bytes are unchanged.
    """
    from . import native_faces
    try:
        emf = _data(objects, EMF)
        if not isinstance(emf, bytes) or not emf:
            return svg
        text = svg.decode('utf-8')
        mapping = native_faces.recorded_faces(text, emf, native_faces.system_faces, native_faces.gdi_substitute)
        return native_faces.annotate_faces(text, mapping).encode('utf-8')
    except (UnicodeDecodeError, ValueError, OSError, struct.error):
        return svg


def _op_clean(app, did, molecule=''):
    doc = _find(app, int(did))
    if str(molecule) == '':
        doc.Objects.Clean()
        return _row(app, doc)
    index = int(molecule)
    fragments = top_fragments(parse(_data(doc.Objects, CDXML)))
    if not 1 <= index <= len(fragments):
        raise NativeError('Molecule index is absent; inspect document again')
    wanted = {int(e.get('id')) for e in fragments[index - 1].iter() if e.get('id')}
    _isolate(doc, wanted).Clean()
    return _row(app, doc)


def _op_native_action(app, did, command, selection):
    did = int(did)
    doc = _find(app, did)
    _require_active(app, did, 'Native action requires the owned front document; no command dispatched')
    if did in _hidden:
        raise NativeError('Native action requires a visible document; no command dispatched')
    if command in SUBMENU_ONLY:
        raise NativeError('This ChemDraw command is only in a submenu, which Windows COM does not expose; '
                          'no command dispatched')
    if command not in MENU_COMMANDS:
        raise NativeError('Unsupported native command')
    if selection not in ('current', 'all'):
        raise NativeError('Unsupported native selection mode')
    item = _menu_item(app, *MENU_COMMANDS[command])
    if selection == 'all':
        doc.Objects.Select()
    if not item.Enabled:
        return [_row(app, doc), False]
    item.Execute()
    _require_active(app, did, 'Front document changed during native action; inspect ChemDraw')
    return [_row(app, doc), True]


def _op_convert_name(app, did):
    did = int(did)
    doc = _find(app, did)
    if did in _hidden:
        raise NativeError('Name conversion requires a visible owned document')
    _require_active(app, did, 'Name conversion requires the owned front document; no command dispatched')
    if top_fragments(parse(_data(doc.Objects, CDXML))):
        raise NativeError('Name conversion requires a caption-only document')
    captions = doc.Captions
    if captions.Count != 1:
        raise NativeError('Name conversion requires exactly one caption')
    caption = captions.Item(1)
    name = caption.Text
    before = set(_ids(doc.Objects))
    _put_data(doc.Objects, NAME, name)  # ChemDraw's own Name to Structure import
    added = set(_ids(doc.Objects)) - before
    if not added:
        raise NativeError('Native name conversion produced no structure')
    caption.Delete()
    doc.Modified = True
    return _row(app, doc)


def _op_close(app, did):
    did = int(did)
    doc = _find(app, did)
    if did in _hidden:
        del _hidden[did]
        doc = None
        gc.collect()
        try:
            _find(app, did)
        except NativeError:
            return [True]
        raise NativeError('Hidden working document is still open after release; inspect ChemDraw')
    # Callers close only owned documents and export a backup first (Bridge.close). Measured on
    # ChemDraw 26.1: Modified=False clears the unsaved marker and File>Close then closes titled
    # and untitled documents without a prompt. SaveAs is avoided: it can bind without writing.
    doc.Activate()
    _require_active(app, did, 'Could not bring the owned document to the front; no close command sent')
    doc.Modified = False  # Equivalent of 'close saving no' for this owned document.
    if _title_dirty(app):
        raise NativeError('Owned document still reports unsaved changes; no close command sent')
    item = _menu_item(app, 'File', 'Close')
    _require_active(app, did, 'Front document changed before close; no close command sent')
    item.Execute()
    doc = item = None
    gc.collect()
    try:
        _find(app, did)
    except NativeError:
        return [True]
    raise NativeError('Close command did not close the owned document; inspect ChemDraw')


def _op_select_document(app, did, expected_active):
    did = int(did)
    expected = None if expected_active in (None, '', 'None') else int(expected_active)  # no active document
    if _active_id(app) != expected:
        raise NativeError('Active document changed before preservation read')
    if did in _hidden:
        raise NativeError('Cannot activate a hidden working document')
    _find(app, did).Activate()
    if _active_id(app) != did:
        raise NativeError('Could not select preservation-read document')
    return True


def _op_clear_owned_scope(app, did, path):
    did = int(did)
    doc = _find(app, did)
    _require_active(app, did, 'Active scope changed; no clear dispatched')
    if (doc.FullName if doc.Path else '') != path:
        raise NativeError('Working scope file changed')
    if doc.Modified:
        raise NativeError('Working scope was edited; no clear dispatched')
    # Native Select All + Clear, as on macOS. Objects.Clear() is not used: on ChemDraw 26.1 it
    # also drops the document's file binding, which changes its identity.
    select_all, clear = _menu_item(app, 'Edit', 'Select All'), _menu_item(app, 'Edit', 'Clear')
    select_all.Execute()
    _require_active(app, did, 'Active scope changed before clear')
    if doc.Modified:
        raise NativeError('Working scope was edited before clear')
    clear.Execute()
    _require_active(app, did, 'Active scope changed during clear')
    if doc.Objects.Count:
        raise NativeError('Working scope clear incomplete')
    if (doc.FullName if doc.Path else '') != path:
        raise NativeError('Working scope lost its file binding during clear')
    return _row(app, doc)


def _op_empty_document_style(app, did, bond, line, bold, label, caption, font, spacing, angle, margin, hashing):
    did = int(did)
    doc = _find(app, did)
    _require_active(app, did, 'Active document changed before setting defaults')
    if doc.Objects.Count:
        raise NativeError('Document is no longer empty; defaults unchanged')
    s = doc.Settings
    s.BondLength = int(bond) / 20; s.LineWidth = int(line) / 20; s.BoldWidth = int(bold) / 20
    s.LabelSize = int(label) / 20; s.CaptionSize = int(caption) / 20
    s.LabelFont = font; s.CaptionFont = font
    s.BondSpacing = int(spacing); s.ChainAngle = int(angle)
    s.MarginWidth = int(margin) / 20; s.HashSpacing = int(hashing) / 20
    return True


def _op_single_page(app, did, wide, high):
    """Set an explicit document to one physical page; the caller re-reads and verifies its content."""
    doc = _find(app, int(did))
    if (doc.NumPagesWide, doc.NumPagesHigh) != (int(wide), int(high)):
        raise NativeError('Page layout changed since it was read; nothing changed')
    doc.NumPagesWide = 1
    doc.NumPagesHigh = 1
    return [doc.NumPagesWide, doc.NumPagesHigh]


def _op_addin_available(app, *_):
    return False


def _op_addin_open(app, *_):
    raise NativeError('The desktop add-in transport is not used on Windows; COM provides read and append')


def _op_read_document(app, did):
    """Fresh CDXML of an explicit document without activating it (no tab or focus change)."""
    did = int(did)
    doc = _find(app, did)
    text, metadata = split_metadata(_data(doc.Objects, CDXML))
    selection = None
    if doc.Selection.Objects.Count:
        selection = _data(doc.Selection.Objects, CDXML)
    return [_row(app, doc), text, selection, metadata]


def _op_channel_read(app):
    did = _active_id(app)
    if did is None:
        return {'error': 'no open document', 'error_stage': 'active_document', 'error_code': 'no_open_document',
                'write_attempted': False}
    doc = _find(app, did)
    text, _ = split_metadata(_data(doc.Objects, CDXML))
    selection = _data(doc.Selection.Objects, CDXML) if doc.Selection.Objects.Count else None
    return {'cdxml': text, 'selection': selection, 'selection_available': True,
            'version': 'COM ' + PROGID, 'write_attempted': False}


def _op_channel_append(app, expected, payload):
    did = _active_id(app)
    if did is None:
        return {'error': 'no open document', 'error_stage': 'active_document', 'error_code': 'no_open_document',
                'write_attempted': False}
    doc = _find(app, did)
    current, metadata = split_metadata(_data(doc.Objects, CDXML))
    if current != expected:
        return {'error': 'Document changed before append', 'error_stage': 'append',
                'error_code': 'native_api_error', 'write_attempted': False}
    try:
        after, metadata_after = split_metadata(_insert_exact(doc, payload))
        if metadata_after != metadata:
            raise NativeError('Document metadata annotations changed during append')
        if did not in _hidden:
            doc.Modified = True  # Automation writes are not marked; keep ChemDraw's save prompt.
        if _active_id(app) != did:
            raise NativeError('Active document changed during append')
    except Exception as exc:
        error = _com_error(exc) if type(exc).__name__ == 'com_error' else exc
        return {'error': str(error), 'error_stage': 'append', 'error_code': 'native_api_error',
                'write_attempted': True}
    return {'cdxml': after, 'write_attempted': True, 'version': 'COM ' + PROGID}


OPERATIONS = {name[4:]: fn for name, fn in globals().items() if name.startswith('_op_')}


# ---------------------------------------------------------------- public entry points

def _dispatch(operation, args):
    import pythoncom
    fn = OPERATIONS.get(operation)
    if fn is None:
        raise NativeError('Unsupported operation')
    try:
        return fn(_app(), *args)
    except pythoncom.com_error as exc:
        raise _com_error(exc) from None


def app_running(timeout=10):
    return _worker.call(lambda: _attach() is not None, timeout)


def ensure_running(app_path: Path, timeout=10):
    """Require a user-started ChemDraw; never launch it from this process.

    Unlike AppleScript on macOS, a process started here would belong to the MCP client's
    kill-on-close job object (observed with the MCP Python SDK) and be terminated together
    with the server, discarding unsaved drawings.
    """
    if not app_running(timeout):
        raise RuntimeError('ChemDraw is not running. Start ChemDraw, then retry. '
                           'No native operation was dispatched; this server never starts ChemDraw itself.')


def run(app_path: Path, operation, args, timeout=25):
    ensure_running(app_path, min(timeout, 10))
    try:
        return _worker.call(lambda: _dispatch(operation, args), timeout)
    except NativeError as exc:
        raise RuntimeError(str(exc)) from None


def poisoned():
    return _worker.poisoned
