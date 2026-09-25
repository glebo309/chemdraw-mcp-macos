"""Delivery policy and timings must not weaken native verification."""
import json
from pathlib import Path

import pytest

from test_api_drawing import EMPTY


@pytest.fixture
def drawing_backend(tmp_path, monkeypatch):
    from chemdraw_macos import api_drawing
    from chemdraw_macos.addin import source_token
    events = []

    class Backend:
        current = EMPTY

        def read(self, did):
            events.append('read')
            return {'cdxml': self.current, 'source_token': source_token(self.current)}

        def append(self, did, text, token):
            assert token == source_token(self.current)
            events.append('append')
            self.current = text
            path = tmp_path / 'after.cdxml'
            path.write_text(text)
            return {'status': 'completed', 'document': {'document_id': did},
                    'after_snapshot': str(path), 'checks': {'existing_content_preserved': True}}

    class Bridge:
        def documents(self):
            return {'documents': [{'document_id': 42}]}

        def _id(self, did):
            return did

        def export(self, did, path, fmt):
            events.append('export')
            assert fmt == 'svg'
            Path(path).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><path d="M10 10 L90 40" stroke="black"/></svg>')

    backend = Backend()
    monkeypatch.setattr(api_drawing, 'get_backend', lambda b: backend)
    return Bridge(), backend, events


def plan(mode):
    return {'workflow': 'molecules', 'exports': mode,
            'structures': [{'compound_id': '1', 'label': 'Test', 'smiles': 'CCO'}]}


def test_preview_is_small_white_native_derived_image_with_timings(drawing_backend, tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    from PIL import Image
    bridge, _, events = drawing_backend
    result = run_api_drawing(bridge, plan('preview'), tmp_path / 'out', 42)
    assert set(result['artifacts']) == {'cdxml', 'svg', 'preview'}
    picture = Image.open(result['artifacts']['preview'])
    assert picture.size == (1200, 600)
    assert picture.getpixel((0, 0)) == (255, 255, 255, 255)
    assert events == ['read', 'append', 'export', 'read']
    assert all(result['checks'].values())
    assert result['delivery']['mode'] == 'preview'
    stages = result['timings']['stages_seconds']
    assert {'document_read', 'layout', 'append_and_verify', 'style_and_layout_verify',
            'native_svg_export', 'rasterize', 'export_verify'} <= stages.keys()
    assert all(value >= 0 for value in stages.values())
    assert result['timings']['total_seconds'] >= sum(stages.values()) - .001
    assert json.loads((tmp_path / 'out/audit.json').read_text())['timings'] == result['timings']


def test_canvas_delivery_omits_rendering_but_retains_native_checks(drawing_backend, tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    bridge, _, events = drawing_backend
    result = run_api_drawing(bridge, plan('canvas'), tmp_path / 'out', 42)
    assert set(result['artifacts']) == {'cdxml'}
    assert events == ['read', 'append']
    assert result['checks']['new_object_style_verified'] is True
    assert 'native_svg_export' not in result['checks']
    assert result['delivery']['mode'] == 'canvas'
    assert result['visual_review'] == 'required'
    assert 'chemdraw_export_figure' in result['delivery']['export_tool']


def test_full_delivery_keeps_transparent_3200_png(drawing_backend, tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    from PIL import Image
    bridge, _, events = drawing_backend
    result = run_api_drawing(bridge, plan('full'), tmp_path / 'out', 42)
    assert set(result['artifacts']) == {'cdxml', 'svg', 'png'}
    image = Image.open(result['artifacts']['png'])
    assert image.size == (3200, 1600) and image.getpixel((0, 0))[3] == 0
    assert result['delivery']['mode'] == 'full'


def test_export_policy_is_validated_before_native_calls(tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    with pytest.raises(ValueError, match='exports'):
        run_api_drawing(object(), plan('fastish'), tmp_path / 'out', 42)
    assert not (tmp_path / 'out').exists()


def test_preview_export_failure_is_uncertain_and_never_reinserts(drawing_backend, tmp_path, monkeypatch):
    from chemdraw_macos.api_drawing import run_api_drawing
    from chemdraw_macos.batch import NativeUncertain
    bridge, _, events = drawing_backend
    def fail(*args):
        events.append('export_failed')
        raise RuntimeError('lost response')
    monkeypatch.setattr(bridge, 'export', fail)
    with pytest.raises(NativeUncertain):
        run_api_drawing(bridge, plan('preview'), tmp_path / 'out', 42)
    assert events == ['read', 'append', 'export_failed']


def test_canvas_cannot_bypass_style_checks(drawing_backend, tmp_path, monkeypatch):
    from chemdraw_macos import api_drawing
    from chemdraw_macos.batch import NativeUncertain
    bridge, _, events = drawing_backend
    def fail(*args):
        raise ValueError('style failed')
    monkeypatch.setattr(api_drawing, 'verify_style', fail)
    with pytest.raises(NativeUncertain):
        api_drawing.run_api_drawing(bridge, plan('canvas'), tmp_path / 'out', 42)
    assert events == ['read', 'append']


def test_harness_auto_canvas_on_shared_path():
    from chemdraw_macos.harness import plan_request
    request = {'molecules': [{'format': 'smiles', 'value': 'CCO'}]}
    assert plan_request(request, shared=True)['exports'] == 'canvas'
    assert 'exports' not in plan_request(request)
    assert plan_request({**request, 'exports': 'canvas'}, shared=True)['exports'] == 'canvas'
    with pytest.raises(ValueError, match='shared'):
        plan_request({**request, 'exports': 'canvas'})
    with pytest.raises(ValueError, match='shared'):
        plan_request({**request, 'products': request['molecules'], 'exports': 'canvas'}, shared=True)


def test_harness_has_total_and_input_timings_on_success_and_rejection(tmp_path, monkeypatch):
    from chemdraw_macos import harness, shared
    monkeypatch.setattr(shared, 'run_shared', lambda *a, **kw: {'status': 'completed'})
    result = harness.run_drawing(object(), {'molecules': [{'format': 'smiles', 'value': 'CCO'}]},
                                 str(tmp_path / 'out'), presentation='shared', document_id=42)
    assert result['timings']['total_seconds'] >= result['timings']['stages_seconds']['input_resolution_and_planning'] >= 0
    failed = harness.run_drawing(object(), {'molecules': []}, str(tmp_path / 'rejected'))
    assert failed['timings']['total_seconds'] >= 0
    assert failed['status'] == 'rejected'


def test_mcp_schema_exposes_delivery_and_fresh_lookup():
    import asyncio
    from chemdraw_macos.server import get_server
    tools = asyncio.run(get_server('drawing').list_tools())
    schema = next(t.inputSchema for t in tools if t.name == 'chemdraw_draw')
    assert 'exports' in str(schema) and 'refresh_identifiers' in str(schema)
