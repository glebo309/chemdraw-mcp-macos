from pathlib import Path
from types import SimpleNamespace

from chemdraw_macos import addin
from chemdraw_macos.batch import _document_content
from chemdraw_macos.core import Bridge


def test_untitled_preservation_reads_native_api_without_saving(tmp_path, monkeypatch):
    bridge = object.__new__(Bridge)
    bridge.inspect = lambda did: {'document': {'document_id': did, 'file': '', 'modified': True}}
    bridge._new_path = lambda suffix, category: tmp_path/('recovery'+suffix)
    def forbidden(*args):
        raise AssertionError('Untitled document must never be exported or renamed')
    bridge.export = forbidden
    content = '<CDXML><page id="1"><t id="2"><s>Unsaved content</s></t></page></CDXML>'
    calls = []
    def read(did):
        calls.append(did)
        return {'cdxml': content}
    monkeypatch.setattr(addin, 'get_backend', lambda b: SimpleNamespace(read=read))
    before = _document_content(bridge, 42)
    assert calls == [42]
    assert (tmp_path/'recovery.cdxml').read_text() == content
    assert _document_content(bridge, 42) == before
    content = content.replace('Unsaved content', 'Changed content')
    assert _document_content(bridge, 42) != before
