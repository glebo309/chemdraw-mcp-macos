import json
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import annotate_file, plan_annotations, verify_annotations
from test_annotations import SOURCE, ARROWS
from test_batch import BatchBridge


def test_native_changed_charge_background_rejected():
    planned, _ = plan_annotations(SOURCE, ARROWS)
    native = ET.fromstring(planned)
    native.find('.//graphic[@SymbolType="CircleMinus"]').set('bgcolor', '0')
    with pytest.raises(ValueError, match='charge'):
        verify_annotations(planned, ET.tostring(native, encoding='unicode'))


def test_deleted_source_after_export_marks_audit_failed(tmp_path):
    source = tmp_path / 'source.cdxml'
    source.write_text(SOURCE)
    bridge = BatchBridge(tmp_path / 'work')
    original = bridge.export
    def export(did, path, format, pixels=3200):
        result = original(did, path, format, pixels)
        if str(path).endswith('figure.png'):
            source.unlink()
        return result
    bridge.export = export
    with pytest.raises(ValueError, match='Source file'):
        annotate_file(bridge, source, str(tmp_path / 'out'), ARROWS)
    audit = json.loads((tmp_path / 'out' / 'audit.json').read_text())
    assert audit['status'] == 'failed'
    assert audit['checks']['source_file_unchanged'] is False
    assert not bridge.managed
