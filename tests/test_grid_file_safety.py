"""File-input grid preservation and uncertain-operation regression tests."""
import hashlib
import json
from pathlib import Path

import pytest

from chemdraw_macos.batch import NativeUncertain
from chemdraw_macos.scope import grid_file
from test_scope import MeasuredBridge, CELLS
from test_polish import SAMPLE


def fixture(tmp_path):
    source = tmp_path / 'My original compounds.cdxml'
    source.write_bytes(SAMPLE.encode('utf-8'))
    bridge = MeasuredBridge(tmp_path / 'work')
    def mutable_import(path):
        bridge.events.append(('import_file', path))
        return bridge.create(Path(path).read_text())
    bridge.import_file = mutable_import
    return source, bridge, tmp_path / 'out'


def test_existing_output_rejected_before_native_import(tmp_path):
    source, bridge, out = fixture(tmp_path)
    out.mkdir()
    with pytest.raises(FileExistsError):
        grid_file(bridge, source, str(out), CELLS)
    assert bridge.events == []


def test_file_source_is_frozen_and_original_filename_and_bytes_preserved(tmp_path):
    source, bridge, out = fixture(tmp_path)
    original = source.read_bytes()
    result = grid_file(bridge, source, str(out), CELLS, columns=2)
    assert not any(e[0] == 'import_file' for e in bridge.events)
    assert source.name == 'My original compounds.cdxml' and source.read_bytes() == original
    assert result['audit']['source_file'] == str(source)
    assert result['audit']['source_file_sha256'] == hashlib.sha256(original).hexdigest()
    assert result['audit']['checks']['source_file_unchanged'] is True
    assert Path(result['audit']['source_snapshot']).read_bytes() == original
    assert bridge.managed == {result['document']['document_id']}


def test_source_mutation_during_import_fails_with_retained_audit(tmp_path):
    source, bridge, out = fixture(tmp_path)
    original_create = bridge.create
    def mutate(text):
        result = original_create(text)
        source.write_text(SAMPLE + '\n')
        return result
    bridge.create = mutate
    with pytest.raises(ValueError, match='Source file changed'):
        grid_file(bridge, source, str(out), CELLS)
    audit = json.loads((out / 'audit.json').read_text())
    assert audit['status'] == 'failed'
    assert audit['checks']['source_file_unchanged'] is False
    assert Path(audit['source_snapshot']).read_bytes() == SAMPLE.encode()
    assert not bridge.managed


@pytest.mark.parametrize('remove', [False, True])
def test_source_mutation_or_disappearance_during_export_never_claimed_success(tmp_path, remove):
    source, bridge, out = fixture(tmp_path)
    original_export = bridge.export
    def change(did, path, format, pixels=3200):
        result = original_export(did, path, format, pixels)
        if Path(path).name == 'figure.png':
            if remove:
                source.unlink()
            else:
                source.write_text(SAMPLE + '\n')
        return result
    bridge.export = change
    with pytest.raises(ValueError, match='Source file changed'):
        grid_file(bridge, source, str(out), CELLS, columns=2)
    audit = json.loads((out / 'audit.json').read_text())
    assert audit['status'] == 'failed'
    assert audit['checks']['source_file_unchanged'] is False
    assert not bridge.managed


def test_uncertain_grid_workflow_does_not_close_imported_source(tmp_path):
    source, bridge, out = fixture(tmp_path)
    original_export = bridge.export
    def timeout(did, path, format, pixels=3200):
        if Path(path).name == 'figure.svg':
            raise RuntimeError('native export timeout')
        return original_export(did, path, format, pixels)
    bridge.export = timeout
    with pytest.raises(NativeUncertain, match='timeout'):
        grid_file(bridge, source, str(out), CELLS, columns=2)
    assert not any(e[0] == 'close' for e in bridge.events)
    assert json.loads((out / 'audit.json').read_text())['status'] == 'uncertain'


def test_uncertain_source_close_updates_completed_audit(tmp_path):
    source, bridge, out = fixture(tmp_path)
    original_create = bridge.create
    original_close = bridge.close
    imported = []
    def remember(text):
        result = original_create(text)
        if not imported:
            imported.append(result['document']['document_id'])
        return result
    def timeout(did):
        if did == imported[0]:
            bridge.events.append(('uncertain_close', did))
            raise RuntimeError('source close timeout')
        return original_close(did)
    bridge.create, bridge.close = remember, timeout
    with pytest.raises(NativeUncertain, match='source close timeout'):
        grid_file(bridge, source, str(out), CELLS, columns=2)
    audit = json.loads((out / 'audit.json').read_text())
    assert audit['status'] == 'uncertain'
    assert 'source close timeout' in audit['close_error']
    assert len([e for e in bridge.events if e[0] == 'uncertain_close']) == 1


def test_uncertain_initial_creation_retains_audit_without_retry_or_close(tmp_path):
    source, bridge, out = fixture(tmp_path)
    def timeout(text):
        bridge.events.append(('uncertain_create',))
        raise RuntimeError('initial create timeout')
    bridge.create = timeout
    with pytest.raises(NativeUncertain, match='initial create timeout'):
        grid_file(bridge, source, str(out), CELLS)
    assert json.loads((out / 'audit.json').read_text())['status'] == 'uncertain'
    assert len([e for e in bridge.events if e[0] == 'uncertain_create']) == 1
    assert not any(e[0] == 'close' for e in bridge.events)
