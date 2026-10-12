"""Windows COM adapter, exercised against a fake that reproduces observed ChemDraw 26.1 behaviour.

Observed natively (Phase 1 report of the Windows handoff): Objects.Data put appends but
re-centres; COM object IDs equal CDXML ids; Documents.Open()/Add() without Activate() is
windowless and disappears when released; automation writes leave Modified False.
"""
import gc
import sys
import threading
import time
import weakref
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows COM adapter (pywin32)')

if sys.platform == 'win32':
    from chemdraw_macos import windows_native as wn

BASE = ('<CDXML BondLength="18"><page id="100" BoundingBox="0 0 540 720">'
        '<fragment id="1"><n id="2" p="90 42"/><n id="3" p="105.6 51" Element="8"/><b id="4" B="2" E="3"/></fragment>'
        '<t id="5" p="90 80"><s>Base</s></t></page></CDXML>')
ADDITION = ('<CDXML BondLength="18"><page id="9" BoundingBox="0 0 540 720">'
            '<fragment id="1"><n id="2" p="300 40"/><n id="3" p="318 40" Element="7" Charge="1"/><b id="4" B="2" E="3"/></fragment>'
            '</page></CDXML>')
SHIFT = (37.25, -11.5)  # the fake's re-centring offset


class FakeRawObject:
    """A raw IDispatch pointer from the collection's enumerator; ChemDraw 26.1 gives ID DISPID 3."""
    def __init__(self, i):
        self.ID = i

    def GetIDsOfNames(self, name):
        assert name == 'ID'
        return 3

    def Invoke(self, dispid, lcid, flags, want):
        import pythoncom
        assert (dispid, flags) == (3, pythoncom.DISPATCH_PROPERTYGET)
        return self.ID


class FakeEnum:
    def __init__(self, ids):
        self.items = [FakeRawObject(i) for i in ids]

    def QueryInterface(self, iid):
        return self

    def Next(self, count):
        batch, self.items = self.items[:count], self.items[count:]
        return tuple(batch)


class FakeOle:
    def __init__(self, objects):
        self.objects = objects

    def GetIDsOfNames(self, name):
        assert name == 'Data'
        return 7

    def InvokeTypes(self, dispid, lcid, flags, result_type, arg_types):
        import pythoncom
        assert dispid == pythoncom.DISPID_NEWENUM
        return FakeEnum(self.objects.ids)

    def Invoke(self, dispid, lcid, flags, want, mime, *value):
        import pythoncom
        doc = self.objects.doc
        if flags == pythoncom.DISPATCH_PROPERTYGET:
            text = '<?xml version="1.0"  ?>\r\n<!DOCTYPE CDXML SYSTEM "x.dtd" >\r\n' + ET.tostring(doc.root, encoding='unicode')
            if mime == 'image/svg+xml':
                return memoryview(getattr(doc, 'svg', b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'))
            if mime == 'image/x-emf' and getattr(doc, 'emf', None) is not None:
                return memoryview(doc.emf)
            return text
        assert flags == pythoncom.DISPATCH_PROPERTYPUT and mime == 'text/xml'
        doc.append_recentred(value[0])


class FakeCollection:
    def __init__(self, doc, ids):
        self.doc, self.ids = doc, list(ids)
        self._oleobj_ = FakeOle(self)

    def __iter__(self):
        # pywin32's per-object dynamic wrapper rebuilds type information for every object
        # (measured ~4x slower than raw IDispatch on ChemDraw 26.1); production code must not use it.
        raise AssertionError('object collection iterated through the slow per-object wrapper')

    @property
    def Count(self):
        if not self.ids and type(self) is FakeCollection:
            self.frozen = True  # measured: Count on an empty clone makes later Add() a no-op
        return len(self.ids)

    def Remove(self, obj):
        pass  # measured on ChemDraw 26.1: Clone().Remove() can silently remove nothing

    def Add(self, obj):
        if not getattr(self, 'frozen', False):
            self.ids.append(obj.ID)

    def Move(self, dx, dy):
        self.doc.moves.append((dx, dy, tuple(self.ids)))
        for e in self.doc.root.iter():
            if e.get('id') and int(e.get('id')) in self.ids and e.get('p'):
                x, y = map(float, e.get('p').split())
                e.set('p', f'{x + dx:.4f} {y + dy:.4f}')

    def Clean(self):
        self.doc.cleaned.append(tuple(sorted(self.ids)))


class FakeObjects(FakeCollection):
    def __init__(self, doc):
        super().__init__(doc, [int(e.get('id')) for e in doc.root.iter() if e.get('id') and e.tag in ('fragment', 'n', 'b', 't')])
        self._oleobj_ = FakeOle(self)

    def Clone(self):
        return FakeCollection(self.doc, self.ids)

    def Clear(self):
        page = self.doc.root.find('page')
        for e in list(page):
            if e.tag != 'annotation':
                page.remove(e)
        # Observed on ChemDraw 26.1: Objects.Clear() also drops the document's file binding.
        self.doc.Path, self.doc.FullName = '', self.doc.Name


class FakeSettings:
    BondLength = 18.0; LineWidth = 1.58; BoldWidth = 2.0; LabelSize = 14.0; CaptionSize = 10.0
    LabelFont = CaptionFont = 'Arial'; BondSpacing = 18; ChainAngle = 120; MarginWidth = 1.6; HashSpacing = 2.5


class FakeSelection:
    def __init__(self, doc):
        self.Objects = FakeObjects.__new__(FakeObjects)
        FakeCollection.__init__(self.Objects, doc, [])
        self.Objects._oleobj_ = FakeOle(self.Objects)


class FakeDoc:
    def __init__(self, app, name, path='', text=BASE):
        self.app, self.Name, self.Path = app, name, path
        self.FullName = (path + '\\' + name) if path else name
        self.root = ET.fromstring(text)
        self.Modified = False
        self.moves, self.cleaned, self.activated = [], [], 0
        self.NumPagesHigh = 1
        self.NumPagesWide = 1
        self.Settings = FakeSettings()

    @property
    def Objects(self):
        return FakeObjects(self)

    @property
    def Selection(self):
        return FakeSelection(self)

    def Activate(self):
        self.activated += 1
        self.app.persist(self)
        self.app.active = self

    def append_recentred(self, text):
        payload = ET.fromstring(text.split('?>', 1)[-1] if text.startswith('<?xml') else text)
        start = max(int(e.get('id')) for e in self.root.iter() if e.get('id')) + 1
        mapping = {}
        for e in payload.find('page').iter():
            if e.get('id') and e.tag != 'page':
                mapping[e.get('id')] = str(start + len(mapping))
        page = self.root.find('page')
        for child in payload.find('page'):
            for e in child.iter():
                if e.get('id') in mapping:
                    e.set('id', mapping[e.get('id')])
                for key in ('B', 'E'):
                    if e.get(key) in mapping:
                        e.set(key, mapping[e.get(key)])
                if e.get('p'):
                    x, y = map(float, e.get('p').split())
                    e.set('p', f'{x + SHIFT[0]:.4f} {y + SHIFT[1]:.4f}')
            page.append(child)


class FakeDocuments:
    def __init__(self, app):
        self.app = app

    @property
    def Count(self):
        return len(self.app.all())

    def Item(self, i):
        return self.app.all()[i - 1]

    def Open(self, path):
        import os
        doc = FakeDoc(self.app, os.path.basename(path), os.path.dirname(path),
                      open(path, encoding='utf-8').read())
        self.app.windowless.append(weakref.ref(doc))
        return doc

    def Add(self):
        doc = FakeDoc(self.app, f'Untitled-{len(self.app.all()) + 1}')
        self.app.windowless.append(weakref.ref(doc))
        return doc


class FakeApp:
    MainWindow = 1234

    def __init__(self):
        self.windows, self.windowless, self.active = [], [], None
        self.Documents = FakeDocuments(self)

    def persist(self, doc):
        if doc not in self.windows:
            self.windows.append(doc)

    def all(self):
        alive = [r() for r in self.windowless if r() is not None and r() not in self.windows]
        return self.windows + alive

    @property
    def ActiveDocument(self):
        return self.active


@pytest.fixture
def app(monkeypatch):
    fake = FakeApp()
    user = FakeDoc(fake, 'mine.cdxml', 'C:\\private')
    fake.windows.append(user)
    fake.active = user
    monkeypatch.setattr(wn, '_pid', lambda app: 4242)
    monkeypatch.setattr(wn, '_hidden', {})
    monkeypatch.setattr(wn, '_title_dirty', lambda app: False)
    return fake


def did(doc):
    return wn.document_id(4242, wn._key(doc))


def test_registered_server_command_parsing():
    assert wn.server_executable('"C:\\Program Files\\X\\ChemDraw.exe" /Automation') == 'C:\\Program Files\\X\\ChemDraw.exe'
    assert wn.server_executable('C:\\Program Files\\X\\ChemDraw.exe /Automation') == 'C:\\Program Files\\X\\ChemDraw.exe'
    with pytest.raises(RuntimeError):
        wn.server_executable('notepad')


def test_document_ids_are_stable_positive_and_process_scoped():
    a = wn.document_id(10, 'C:\\x\\a.cdxml')
    assert a == wn.document_id(10, 'C:\\x\\a.cdxml')
    assert 0 < a <= 0x7FFFFFFF
    assert a != wn.document_id(11, 'C:\\x\\a.cdxml')  # ChemDraw restart invalidates IDs


def test_ambiguous_document_identity_fails_closed(app):
    twin = FakeDoc(app, 'Untitled-1')
    app.windows += [twin, FakeDoc(app, 'Untitled-1')]
    with pytest.raises(wn.NativeError, match='ambiguous'):
        wn._find(app, did(twin))


def test_metadata_annotations_are_split_but_others_kept():
    text = ('<CDXML><page id="1"><annotation Keyword="GUID" Content="x"/><t id="2" p="1 2"><s>a</s></t>'
            '<annotation Keyword="Name" Content="y" Extra="1"/></page></CDXML>')
    clean, records = wn.split_metadata(text)
    assert records == [('GUID', 'x')]
    page = ET.fromstring(clean).find('page')
    assert [e.tag for e in page] == ['t', 'annotation']


def test_rigid_offset_accepts_translation_only():
    supplied = [('n', 0, 0), ('n', 18, 0), ('t', 5, 30)]
    moved = [(t, x + 3.5, y - 2) for t, x, y in supplied]
    assert wn.rigid_offset(moved, supplied) == pytest.approx((3.5, -2))
    distorted = moved[:-1] + [('t', 5 + 3.5 + 1, 28)]
    assert wn.rigid_offset(distorted, supplied) is None
    assert wn.rigid_offset(moved[:2], supplied) is None


def test_rigid_offset_tolerates_rounding_ties_between_points_in_one_column():
    # Observed live (eight-analogue table): two captions in one column at x ~ 85.345 rounded to
    # 85.34 on one side and 85.35 on the other, which swapped them in a sorted comparison.
    supplied = [('n', 10, 10), ('t', 85.346, 258.43), ('t', 85.344, 389.85)]
    native = [('n', 10, 10), ('t', 85.344, 258.43), ('t', 85.346, 389.85)]
    assert wn.rigid_offset(native, supplied) == pytest.approx((0, 0))
    swapped = [('n', 10, 10), ('t', 85.344, 389.85), ('t', 85.346, 389.85)]
    assert wn.rigid_offset(swapped, supplied) is None  # each supplied point is matched once


def test_insert_exact_restores_supplied_coordinates_and_keeps_old_content(app):
    doc = app.active
    before = [(e.get('id'), e.get('p')) for e in doc.root.iter('n')]
    after = wn._insert_exact(doc, ADDITION)
    root = wn.parse(after)
    atoms = {e.get('id'): e.get('p') for e in root.iter('n')}
    for i, p in before:
        assert atoms[i] == p
    new = sorted(tuple(map(float, p.split())) for i, p in atoms.items() if i not in dict(before))
    assert new == pytest.approx([(300, 40), (318, 40)])
    assert doc.moves and doc.moves[0][:2] == pytest.approx((-SHIFT[0], -SHIFT[1]))
    assert len(doc.moves[0][2]) == 4  # fragment, two atoms, bond: exactly the inserted objects


def test_insert_walks_the_document_objects_once(app, monkeypatch):
    # Each pass over a large drawing costs a cross-process call per object. The objects present
    # before come from the document's CDXML (COM IDs are CDXML ids, unique document-wide), and
    # isolating the new objects reuses the single pass made after the insertion.
    walked = []
    original = FakeOle.InvokeTypes

    def counting(self, *args):
        if type(self.objects) is FakeObjects and self.objects.ids:
            walked.append(len(self.objects.ids))
        return original(self, *args)
    monkeypatch.setattr(FakeOle, 'InvokeTypes', counting)
    wn._insert_exact(app.active, ADDITION)
    assert walked == [9]
    assert len(app.active.moves) == 1 and len(app.active.moves[0][2]) == 4


def test_insert_fails_closed_if_a_new_object_reuses_an_existing_document_id(app, monkeypatch):
    doc = app.active
    doc.root.find('page').append(ET.fromstring('<annotation id="6" Keyword="note"/>'))  # not a COM object
    original = FakeDoc.append_recentred

    def reuse_id(self, text):
        original(self, text)
        self.root.find('page').remove(self.root.find('page/annotation'))
        fragment = self.root.findall('page/fragment')[-1]
        fragment.set('id', '6')  # a hypothetical ChemDraw reusing the annotation's id
    monkeypatch.setattr(FakeDoc, 'append_recentred', reuse_id)
    with pytest.raises(wn.NativeError):
        wn._insert_exact(doc, ADDITION)


def test_channel_append_checks_freshness_before_any_write(app):
    doc = app.active
    result = wn._op_channel_append(app, BASE.replace('Base', 'Stale'), ADDITION)
    assert result['write_attempted'] is False and 'changed' in result['error']
    assert doc.moves == [] and len(list(doc.root.iter('n'))) == 2


def test_channel_append_marks_visible_target_modified_and_preserves_metadata(app):
    doc = app.active
    ET.SubElement(doc.root.find('page'), 'annotation', Keyword='GUID', Content='keep')
    expected, _ = wn.split_metadata(wn._data(doc.Objects, wn.CDXML))
    result = wn._op_channel_append(app, expected, ADDITION)
    assert result['write_attempted'] is True and 'error' not in result
    assert doc.Modified is True
    assert 'annotation' not in result['cdxml']
    assert doc.root.find('page/annotation').get('Content') == 'keep'


def test_hidden_open_is_windowless_and_close_releases_it(app, tmp_path):
    path = tmp_path / 'measure.cdxml'
    path.write_text(ADDITION, encoding='utf-8', newline='')
    row = wn._op_open(app, str(path), 'false')
    assert row[0] in wn._hidden and wn._op_visible_documents(app) == [did(app.active)]
    assert app.Documents.Count == 2
    assert wn._op_close(app, row[0]) == [True]
    gc.collect()
    assert app.Documents.Count == 1 and row[0] not in wn._hidden


def test_visible_open_activates_and_persists(app, tmp_path):
    path = tmp_path / 'work.cdxml'
    path.write_text(ADDITION, encoding='utf-8', newline='')
    row = wn._op_open(app, str(path), 'true')
    doc = wn._find(app, row[0])
    assert doc.activated == 1 and row[0] not in wn._hidden
    assert row[2] == str(path) and row[3] is False


def test_submenu_actions_refused_before_dispatch(app):
    with pytest.raises(wn.NativeError, match='submenu'):
        wn._op_native_action(app, did(app.active), 'alignLeftEdges', 'all')


def test_pdf_export_refused_without_writing(app, tmp_path):
    target = tmp_path / 'x.pdf'
    with pytest.raises(wn.NativeError, match='PDF'):
        wn._op_export(app, did(app.active), str(target), 'PDF')
    assert not target.exists()


def test_svg_export_writes_native_bytes_and_never_overwrites(app, tmp_path):
    target = tmp_path / 'x.svg'
    wn._op_export(app, did(app.active), str(target), 'Scalable Vector Graphics (SVG)')
    assert target.read_bytes().startswith(b'<svg')
    with pytest.raises(FileExistsError):
        wn._op_export(app, did(app.active), str(target), 'Scalable Vector Graphics (SVG)')


def test_clean_molecule_isolates_exactly_that_fragment(app):
    wn._op_clean(app, did(app.active), '1')
    assert app.active.cleaned == [(1, 2, 3, 4)]


def test_list_reports_molecules_and_modified_flag(app):
    app.active.Modified = True
    rows = wn._op_list(app)
    assert rows == [[did(app.active), 'mine.cdxml', 'C:\\private\\mine.cdxml', True, 1]]


def test_worker_timeout_is_uncertain_not_retried_and_poisons(monkeypatch):
    worker = wn._Worker()
    release, calls = threading.Event(), []
    def slow():
        calls.append(1); release.wait(5)
    with pytest.raises(RuntimeError, match='not retried'):
        worker.call(slow, 0.2)
    with pytest.raises(RuntimeError, match='uncertain'):
        worker.call(lambda: calls.append(2), 1)
    release.set(); time.sleep(0.1)
    assert calls == [1]


def test_never_launches_chemdraw_from_the_server(monkeypatch, tmp_path):
    # MCP stdio clients run the server in a kill-on-close job object: a ChemDraw started
    # here would be terminated with the server, losing the user's unsaved drawings.
    import subprocess
    monkeypatch.setattr(wn, 'app_running', lambda timeout=10: False)
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('ChemDraw launched by the server'))
    dispatched = []
    monkeypatch.setattr(wn._worker, 'call', lambda fn, timeout: dispatched.append(fn))
    with pytest.raises(RuntimeError, match='Start ChemDraw'):
        wn.run(tmp_path / 'ChemDraw.exe', 'list', ())
    assert dispatched == []


def test_worker_returns_values_and_propagates_errors():
    worker = wn._Worker()
    assert worker.call(lambda: 5, 2) == 5
    with pytest.raises(ValueError):
        worker.call(lambda: (_ for _ in ()).throw(ValueError('x')), 2)


def test_preservation_read_uses_direct_com_read_without_tab_switch(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from chemdraw_macos import addin
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.windows_backend import ComBackend
    b = object.__new__(Bridge); b.lock = nullcontext(); calls = []
    def run(op, *args):
        calls.append(op)
        assert op == 'read_document'
        return [[args[0], 'u', '', True, 0], BASE, None, []]
    b._run = run
    b._desktop_addin = ComBackend(b)
    result = addin.read_preserving_active(b, 77)
    assert calls == ['read_document'] and result['transport'] == 'windows_com'
    assert result['document']['document_id'] == 77


def test_close_of_owned_untitled_document_discards_like_saving_no(app, monkeypatch):
    # Measured natively: Modified=False clears the unsaved marker and File>Close then closes an
    # untitled document without a prompt. SaveAs is not used (it can bind without writing).
    doc = FakeDoc(app, 'Untitled-9')
    doc.Activate(); doc.Modified = True
    doc.SaveAs = lambda path: pytest.fail('SaveAs must not be used to close')
    seen = []
    class Item:
        CommandID = 17
        Enabled = True
        def Execute(self):
            seen.append(doc.Modified)
            app.windows.remove(app.active); app.active = app.windows[0]
    monkeypatch.setattr(wn, '_menu_item', lambda a, m, i: Item())
    assert wn._op_close(app, did(doc)) == [True]
    assert seen == [False] and doc not in app.windows and app.active.Name == 'mine.cdxml'


def test_offset_uses_atoms_and_captions_not_relaid_atom_labels(app):
    # ChemDraw re-lays out atom label text with the target document's label font.
    payload = ('<CDXML><page id="9" BoundingBox="0 0 540 720"><fragment id="1">'
               '<n id="2" p="300 40" Element="8"><t p="296 44"><s>O</s></t></n><n id="3" p="318 40"/><b id="4" B="2" E="3"/>'
               '</fragment><t id="5" p="309 70"><s>cap</s></t></page></CDXML>')
    doc = app.active
    original = doc.append_recentred
    def relayout(text):
        original(text)
        for n in doc.root.iter('n'):
            for t in n.findall('t'):
                x, y = map(float, t.get('p').split()); t.set('p', f'{x + 2.7:.2f} {y - 1.1:.2f}')
    doc.append_recentred = relayout
    root = wn.parse(wn._insert_exact(doc, payload))
    atoms = sorted(tuple(map(float, e.get('p').split())) for e in root.iter('n') if int(e.get('id')) > 5)
    assert atoms == pytest.approx([(300, 40), (318, 40)])
    caption = [e for e in root.find('page') if e.tag == 't' and int(e.get('id')) > 5][0]
    assert tuple(map(float, caption.get('p').split())) == pytest.approx((309, 70))


def test_isolation_refuses_when_a_selection_exists(app):
    doc = app.active
    sel = FakeSelection(doc); sel.Objects.ids = [2]
    type(doc).Selection = property(lambda self: sel)
    try:
        with pytest.raises(wn.NativeError, match='selection'):
            wn._isolate(doc, {2, 3})
    finally:
        type(doc).Selection = property(lambda self: FakeSelection(self))


def test_svg_export_records_the_faces_chemdraw_measured(app, tmp_path, monkeypatch):
    from chemdraw_macos import native_faces
    from test_native_faces import emf, widths_faces
    app.active.emf = emf([('Helvetica Neue', 400, 100, 'abcab')])
    app.active.svg = (b'<svg xmlns="http://www.w3.org/2000/svg"><text transform="matrix(1 0 0 1 0 9)" '
                      b'font-family="Helvetica Neue" font-weight="normal" font-size="9px">\nabcab</text></svg>')
    monkeypatch.setattr(native_faces, 'system_faces', widths_faces)
    target = tmp_path / 'x.svg'
    wn._op_export(app, did(app.active), str(target), 'Scalable Vector Graphics (SVG)')
    text = target.read_text(encoding='utf-8')
    assert text.startswith('<svg') and 'chemdraw-mcp-faces' in text and '"Helvetica Neue", 200' in text


def test_svg_export_without_metafile_evidence_keeps_native_bytes(app, tmp_path):
    target = tmp_path / 'x.svg'  # the fake returns no metafile: nothing to record
    wn._op_export(app, did(app.active), str(target), 'Scalable Vector Graphics (SVG)')
    assert target.read_bytes() == b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'


def test_owned_scope_clear_uses_native_commands_and_keeps_the_file_binding(app, monkeypatch):
    owned = FakeDoc(app, 'scope.cdxml', r'C:\work')
    app.windows.append(owned)
    app.active = owned
    owned.Modified = False
    calls = []

    class Item:
        def __init__(self, caption):
            self.caption = caption

        def Execute(self):
            calls.append(self.caption)
            if self.caption == 'Clear':
                page = owned.root.find('page')
                for e in list(page):
                    if e.tag != 'annotation':
                        page.remove(e)
                owned.Modified = True

    monkeypatch.setattr(wn, '_menu_item', lambda a, menu, item: Item(item))
    before = did(owned)
    row = wn._op_clear_owned_scope(app, before, owned.FullName)
    assert calls == ['Select All', 'Clear']
    assert row[0] == before and row[2] == r'C:\work\scope.cdxml' and owned.Objects.Count == 0


def test_owned_scope_clear_refuses_an_inactive_or_rebound_document(app, monkeypatch):
    owned = FakeDoc(app, 'scope.cdxml', r'C:\work')
    app.windows.append(owned)
    owned.Modified = False
    monkeypatch.setattr(wn, '_menu_item', lambda a, menu, item: pytest.fail('command sent'))
    with pytest.raises(wn.NativeError, match='Active scope changed'):
        wn._op_clear_owned_scope(app, did(owned), owned.FullName)  # the user's document is active
    app.active = owned
    with pytest.raises(wn.NativeError, match='file changed'):
        wn._op_clear_owned_scope(app, did(owned), r'C:\elsewhere\scope.cdxml')


def test_single_page_sets_one_page_on_the_explicit_document(app):
    template = FakeDoc(app, 'Untitled template-1')
    app.windows.append(template)
    template.NumPagesWide, template.NumPagesHigh = 2, 3
    assert wn._op_single_page(app, did(template), 2, 3) == [1, 1]
    assert (template.NumPagesWide, template.NumPagesHigh) == (1, 1)
    assert (app.active.NumPagesWide, app.active.NumPagesHigh) == (1, 1)  # the active document is not touched


def test_single_page_refuses_a_layout_changed_since_the_read(app):
    doc = app.active
    doc.NumPagesWide, doc.NumPagesHigh = 2, 2
    with pytest.raises(wn.NativeError, match='changed'):
        wn._op_single_page(app, did(doc), 2, 3)
    assert (doc.NumPagesWide, doc.NumPagesHigh) == (2, 2)


def test_select_without_an_active_document_refuses_hidden_targets_cleanly(app, monkeypatch, tmp_path):
    app.windows.clear()
    app.active = None
    path = tmp_path / 'blank.cdxml'
    path.write_text(BASE, encoding='utf-8')
    row = wn._op_open(app, str(path), 'false')  # windowless working copy
    with pytest.raises(wn.NativeError, match='hidden working document'):
        wn._op_select_document(app, row[0], None)
