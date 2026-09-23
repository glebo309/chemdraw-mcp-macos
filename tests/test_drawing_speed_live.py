"""Serial opt-in timing comparison on private native documents, never user drawings."""
import json
import os
import platform
import plistlib
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST') != '1',
                                reason='Requires the installed native add-in and exclusive connection')


def _previous_read(bridge, channel, document_id):
    """Pre-optimization read sequence, retained only as a measured baseline."""
    from chemdraw_macos.core import validate_cdxml
    from chemdraw_macos.addin import source_token
    did = bridge._id(document_id)
    with bridge.lock:
        if bridge._run('active_document') != did:
            raise ValueError('Choose the active ChemDraw document')
        result = channel.request('read')
        if result.get('error'):
            raise RuntimeError(result['error'])
        validate_cdxml(result['cdxml'])
        if bridge._run('active_document') != did:
            raise RuntimeError('Active document changed during read')
        doc = next(d for d in bridge.documents()['documents'] if d['document_id'] == did)
        return {'document': doc, 'cdxml': result['cdxml'], 'source_token': source_token(result['cdxml'])}


def test_native_delivery_modes_and_timing_comparison(tmp_path, monkeypatch):
    from chemdraw_macos import addin
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.batch import _document_content
    from chemdraw_macos.harness import run_drawing
    from test_api_drawing import EMPTY
    from PIL import Image

    bridge = Bridge()
    backend = addin.get_backend(bridge)
    baseline = bridge.documents()
    before = {d['document_id']: _document_content(bridge, d['document_id']) for d in baseline['documents']}
    report = {'environment': {'macos': platform.mac_ver()[0], 'architecture': platform.machine(),
                              'python': platform.python_version(), 'rdkit': version('rdkit'),
                              'resvg-py': version('resvg-py')}, 'runs': []}
    with (bridge.app / 'Contents/Info.plist').open('rb') as handle:
        report['environment']['chemdraw'] = plistlib.load(handle)['CFBundleShortVersionString']
    request = {'molecules': [{'format': 'smiles', 'value': 'Cn1c(=O)c2c(ncn2C)n(C)c1=O', 'label': 'Caffeine'}]}
    try:
        # First call is reported separately, not pooled into the warm comparison.
        for index, mode in enumerate(['cold_preview'] + ['baseline', 'preview', 'canvas'] * 3):
            did = bridge.create(EMPTY)['document']['document_id']
            operations = Counter()
            original = bridge._run
            def counted(operation, *args):
                operations[operation] += 1
                return original(operation, *args)
            with monkeypatch.context() as patch:
                patch.setattr(bridge, '_run', counted)
                if mode == 'baseline':
                    patch.setattr(addin, 'read_document', _previous_read)
                started = perf_counter()
                result = run_drawing(bridge, {**request, 'exports': 'full' if mode == 'baseline' else
                                     'preview' if mode == 'cold_preview' else mode},
                                     str(tmp_path / f'{index}-{mode}'), presentation='shared', document_id=did)
                elapsed = perf_counter() - started
            report['runs'].append({'mode': mode, 'seconds': elapsed, 'native_calls': dict(operations), 'result': result})
            (tmp_path / 'benchmark.json').write_text(json.dumps(report, indent=2))
            assert result['status'] == 'completed', result
            assert result['document']['molecule_count'] == 1
            assert all(result['checks'].values())
            from rdkit import Chem
            mol = Chem.MolsFromCDXML(Path(result['artifacts']['cdxml']).read_text())[0]
            rings = mol.GetRingInfo().AtomRings()
            six, five = next(r for r in rings if len(r) == 6), next(r for r in rings if len(r) == 5)
            a, b = set(six) & set(five)
            conf = mol.GetConformer()
            assert abs(conf.GetAtomPosition(a).x - conf.GetAtomPosition(b).x) < .002
            assert sum(conf.GetAtomPosition(i).x for i in six) / 6 > sum(conf.GetAtomPosition(i).x for i in five) / 5
            if mode in ('preview', 'cold_preview'):
                image = Image.open(result['artifacts']['preview'])
                assert max(image.size) == 1200
                assert image.getpixel((0, 0)) == (255, 255, 255, 255)
            if mode == 'canvas':
                assert set(result['artifacts']) == {'cdxml'}
                assert not operations['export']
            bridge.close(did)  # Only this successful, owned test copy.
        assert bridge.documents() == baseline
        assert {did: _document_content(bridge, did) for did in before} == before
        report['preexisting_documents_unchanged'] = True
        (tmp_path / 'benchmark.json').write_text(json.dumps(report, indent=2))
        print('DRAWING_BENCHMARK=' + str(tmp_path / 'benchmark.json'))
    finally:
        backend.close()
