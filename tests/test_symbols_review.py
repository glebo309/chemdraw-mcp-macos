"""Independent review regressions. All native activity is mocked."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import annotate_document, annotate_file
from chemdraw_macos.batch import NativeUncertain
from chemdraw_macos.editing import source_token
from chemdraw_macos.symbols import symbols_document
from test_annotations import ARROWS, SOURCE
from test_batch import BatchBridge
from test_symbols import REQUESTS, source


@pytest.mark.parametrize('workflow', ['symbols', 'annotations'])
def test_final_render_mutation_cannot_receive_checks_passed(tmp_path, workflow):
    bridge = BatchBridge(tmp_path / 'work')
    original = source() if workflow == 'symbols' else SOURCE
    bridge.docs[1] = original
    export = bridge.export

    def change_during_render(did, path, format, pixels=3200):
        if Path(path).name == 'figure.png':
            root = ET.fromstring(bridge.docs[did])
            atom = root.find('page/fragment/n')
            x, y = map(float, atom.get('p').split())
            atom.set('p', f'{x + 5} {y}')
            bridge.docs[did] = ET.tostring(root, encoding='unicode')
        return export(did, path, format, pixels)

    bridge.export = change_during_render
    operation = symbols_document if workflow == 'symbols' else annotate_document
    requests = REQUESTS if workflow == 'symbols' else ARROWS
    with pytest.raises(ValueError):
        operation(bridge, 1, str(tmp_path / 'out'), requests, source_token(original))
    assert bridge.docs[1] == original
    assert json.loads((tmp_path / 'out/audit.json').read_text())['status'] == 'failed'


def test_annotation_uncertain_failed_copy_close_stops_outer_cleanup(tmp_path):
    source_path = tmp_path / 'source.cdxml'
    source_path.write_text(SOURCE)
    bridge = BatchBridge(tmp_path / 'work')
    create = bridge.create
    close_attempts = []

    def change_created_curve(text):
        root = ET.fromstring(text)
        curve = root.find('page/curve')
        if curve is not None:
            curve.set('ArrowheadHead', 'HalfLeft')
        return create(ET.tostring(root, encoding='unicode'))

    def uncertain_close(did):
        close_attempts.append(did)
        raise RuntimeError('Native close timed out; completion unknown')

    bridge.create = change_created_curve
    bridge.close = uncertain_close
    with pytest.raises(NativeUncertain):
        annotate_file(bridge, str(source_path), str(tmp_path / 'out'), ARROWS)
    assert len(close_attempts) == 1, 'An uncertain close must prevent the outer imported-copy close'
    assert source_path.read_text() == SOURCE
    assert json.loads((tmp_path / 'out/audit.json').read_text())['status'] == 'uncertain'
