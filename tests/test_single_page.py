"""Multi-page documents (for example from a poster-sized template) are switched to one page
before a shared drawing, but only when nothing lies outside the first physical page."""
from contextlib import nullcontext
from pathlib import Path

import pytest

from chemdraw_macos import core
from chemdraw_macos.addin import source_token
from chemdraw_macos.batch import NativeUncertain
from chemdraw_macos.core import Bridge
from chemdraw_macos.page_layout import first_page_fit
from test_api_drawing import EMPTY

TEXT = '<t id="2" BoundingBox="40 40 90 60" p="40 55"><s>keep</s></t>'
FAR = '<t id="3" BoundingBox="900 40 950 60" p="900 55"><s>page two</s></t>'


def page(wide, high, box='0 0 1440 1620', content=''):
    return EMPTY.replace('<page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"/>',
                         f'<page id="1" BoundingBox="{box}" WidthPages="{wide}" HeightPages="{high}">{content}</page>')


ONE = page(1, 1, '0 0 720 540')


def doc(text):
    return {'cdxml': text, 'source_token': source_token(text), 'document': {'file': ''}}


def bridge(calls, windows, monkeypatch):
    monkeypatch.setattr(core, 'WINDOWS', windows)
    b = object.__new__(Bridge); b.lock = nullcontext()
    b._run = lambda *args: calls.append(args)
    return b


class Reread:
    def __init__(self, text): self.text = text
    def read(self, did):
        assert did == 42
        return doc(self.text)


def test_single_page_document_is_left_alone():
    assert first_page_fit(ONE) is None
    assert first_page_fit(page(1, 3, '0 0 720 1620')) is None  # downward pages are added by design


def test_downward_pages_need_one_page_when_expansion_is_off():
    assert first_page_fit(page(1, 3, '0 0 720 1620'), allow_page_expansion=False) == {
        'pages': (1, 3), 'first_page': (0.0, 0.0, 720.0, 540.0)}


def test_empty_multi_page_document_fits_its_first_page():
    assert first_page_fit(page(2, 3)) == {'pages': (2, 3), 'first_page': (0.0, 0.0, 720.0, 540.0)}


def test_content_on_the_first_page_fits():
    assert first_page_fit(page(2, 3, content=TEXT))['first_page'] == (0.0, 0.0, 720.0, 540.0)


def test_content_beyond_the_first_page_is_refused_with_steps():
    with pytest.raises(ValueError, match='2 pages wide and 3 pages tall.*Nothing was changed'):
        first_page_fit(page(2, 3, content=TEXT + FAR))


def test_content_without_measured_bounds_is_refused():
    with pytest.raises(ValueError, match='Nothing was changed'):
        first_page_fit(page(2, 3, content='<t id="2" p="40 55"><s>x</s></t>'))


def test_windows_switches_an_empty_template_page_and_rereads(monkeypatch):
    calls = []
    result = bridge(calls, True, monkeypatch).fit_single_page(42, doc(page(2, 3)), Reread(ONE))
    assert calls == [('single_page', 42, 2, 3)]
    assert result['cdxml'] == ONE
    assert result['page_layout'] == {'before': '2 x 3 pages', 'after': '1 x 1 page'}


def test_windows_switch_keeps_first_page_content(monkeypatch):
    calls = []
    after = page(1, 1, '0 0 720 540', TEXT)
    result = bridge(calls, True, monkeypatch).fit_single_page(42, doc(page(2, 3, content=TEXT)), Reread(after))
    assert result['cdxml'] == after and len(calls) == 1


def test_switch_that_moves_content_is_uncertain(monkeypatch):
    moved = page(1, 1, '0 0 720 540', TEXT.replace('40 40 90 60', '50 40 100 60'))
    with pytest.raises(NativeUncertain, match='nothing was drawn'):
        bridge([], True, monkeypatch).fit_single_page(42, doc(page(2, 3, content=TEXT)), Reread(moved))


def test_switch_that_leaves_several_pages_is_uncertain(monkeypatch):
    with pytest.raises(NativeUncertain):
        bridge([], True, monkeypatch).fit_single_page(42, doc(page(2, 3)), Reread(page(2, 3)))


def test_mac_explains_the_manual_fix_without_a_native_call(monkeypatch):
    calls = []
    with pytest.raises(ValueError, match='Document Settings'):
        bridge(calls, False, monkeypatch).fit_single_page(42, doc(page(2, 3)), Reread(ONE))
    assert calls == []


def test_single_page_document_needs_no_native_call(monkeypatch):
    calls = []
    initial = doc(ONE)
    assert bridge(calls, True, monkeypatch).fit_single_page(42, initial, Reread(ONE)) is initial
    assert calls == []


def test_shared_drawing_into_a_multi_page_template_switches_the_page_first(tmp_path, monkeypatch):
    from chemdraw_macos import api_drawing
    monkeypatch.setattr(core, 'WINDOWS', True)
    ops = []

    class Backend:
        current = page(2, 3)
        def read(self, did): return doc(self.current)
        def append(self, did, text, token):
            ops.append('append')
            self.current = text
            path = tmp_path / 'native.cdxml'; path.write_text(text, encoding='utf-8', newline='')
            return {'status': 'completed', 'document': {'document_id': did}, 'after_snapshot': str(path),
                    'source_token': source_token(text), 'checks': {'page_unchanged': True}}
    backend = Backend()

    class FakeBridge:
        lock = nullcontext()
        fit_single_page = Bridge.fit_single_page
        def _id(self, did): return did
        def documents(self): return {'documents': [{'document_id': 42}]}
        def _run(self, *args):
            ops.append(args)
            backend.current = ONE

    monkeypatch.setattr(api_drawing, 'get_backend', lambda b: backend, raising=False)
    result = api_drawing.run_api_drawing(
        FakeBridge(), {'workflow': 'molecules', 'structures': [{'compound_id': '1', 'label': 'Test', 'smiles': 'CCO'}]},
        tmp_path / 'out', 42)
    assert result['status'] == 'completed'
    assert ops == [('single_page', 42, 2, 3), 'append']
    assert result['page_layout'] == {'before': '2 x 3 pages', 'after': '1 x 1 page'}
    assert 'single page' in result['note']
