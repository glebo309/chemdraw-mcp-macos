"""Read-only release review regressions for native batch preservation."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.batch import _verify, batch_export
from test_batch import BatchBridge, entries
from test_polish import SAMPLE


def test_native_dropped_reaction_scheme_is_not_accepted():
    root = ET.fromstring(SAMPLE)
    scheme = ET.SubElement(root.find('page'), 'scheme', {'id': '80'})
    ET.SubElement(scheme, 'step', {
        'id': '81', 'ReactionStepReactants': '1', 'ReactionStepProducts': '20',
    })
    with pytest.raises(ValueError):
        _verify(ET.tostring(root, encoding='unicode'), SAMPLE)


def test_native_arrowhead_size_change_is_not_accepted():
    root = ET.fromstring(SAMPLE)
    arrow = ET.SubElement(root.find('page'), 'arrow', {
        'id': '50', 'Head3D': '220 80 0', 'Tail3D': '150 80 0',
        'ArrowheadHead': 'Full', 'ArrowheadType': 'Solid', 'HeadSize': '1000',
    })
    before = ET.tostring(root, encoding='unicode')
    arrow.set('HeadSize', '50')
    with pytest.raises(ValueError):
        _verify(before, ET.tostring(root, encoding='unicode'))


def test_unexpected_open_document_prevents_completed_status(tmp_path):
    items = entries(tmp_path, 1)
    bridge = BatchBridge(tmp_path / 'work')
    create = bridge.create

    def extra_document(text):
        result = create(text)
        create(text)
        return result

    bridge.create = extra_document
    report = batch_export(bridge, items, str(tmp_path / 'out'))
    assert report['status'] != 'completed'
    assert not report['checks']['preexisting_documents_unchanged']


def test_preexisting_unsaved_content_mutation_is_not_certified(tmp_path):
    items = entries(tmp_path, 1)
    bridge = BatchBridge(tmp_path / 'work')
    export = bridge.export

    def mutate_original(did, path, format, pixels=3200):
        if format == 'png':
            bridge.docs[1] = SAMPLE.replace('Methanol', 'Changed caption')
        return export(did, path, format, pixels)

    bridge.export = mutate_original
    report = batch_export(bridge, items, str(tmp_path / 'out'))
    assert report['status'] != 'completed'
    assert not report['checks']['preexisting_documents_unchanged']


def test_reserved_source_key_cannot_overwrite_frozen_source_backup(tmp_path):
    items = entries(tmp_path, 1)
    items[0]['key'] = 'source'
    bridge = BatchBridge(tmp_path / 'work')
    create = bridge.create
    bridge.create = lambda text: create(ET.tostring(ET.fromstring(text), encoding='unicode'))
    report = batch_export(bridge, items, str(tmp_path / 'out'))
    assert report['status'] == 'completed'
    folder = tmp_path / 'out' / 'source'
    assert (folder / 'source.cdxml').is_file()
    assert any(path.read_text() == SAMPLE for path in folder.rglob('*.cdxml'))
