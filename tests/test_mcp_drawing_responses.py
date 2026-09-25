"""Keep successful MCP delivery small without losing retained diagnostic evidence."""
import asyncio
import copy
import json

import pytest

from chemdraw_macos import server


def completed(tmp_path):
    result = {
        'status': 'completed', 'document': {'document_id': 42, 'modified': True},
        'source_token': 'fresh-token', 'checks': {'chemistry': True},
        'artifacts': {'cdxml': str(tmp_path / 'figure.cdxml')},
        'output_dir': str(tmp_path), 'visual_review': 'required',
        'delivery': {'mode': 'canvas', 'export_tool': 'chemdraw_export_figure'},
        'timings': {'total_seconds': 7.4},
        'presentation': {'same_working_document': True},
        'note': 'Do not import again.', 'warnings': ['Caller-supplied chemistry.'],
        'plan': {'provenance': [{'provider_payload': 'x' * 20000}]},
        'planning': {'seeds': ['x' * 1000] * 16},
        'group_plan': {'cells': ['x' * 1000] * 16},
        'audit': {'status': 'checks_passed', 'checks': {'chemistry': True},
                  'visual_review': 'required', 'limitations': 'Not chemical truth.',
                  'warnings': ['Review stereochemistry.'],
                  'planning': {'seeds': ['x' * 1000] * 16}},
    }
    (tmp_path / 'result.json').write_text(json.dumps(result))
    return result


@pytest.mark.parametrize('name', ['chemdraw_draw', 'chemdraw_draw_structures'])
def test_mcp_success_compact_but_full_result_retained(tmp_path, monkeypatch, name):
    full = completed(tmp_path)
    before = copy.deepcopy(full)
    calls = []
    def draw(*args, **kwargs):
        calls.append((args, kwargs))
        return full
    monkeypatch.setattr(server, 'bridge', lambda: object())
    monkeypatch.setattr(server, 'run_drawing', draw)
    monkeypatch.setattr(server, 'draw_structures', draw)
    arguments = {'output_dir': str(tmp_path)}
    if name == 'chemdraw_draw':
        arguments['request'] = {'molecules': [{'value': 'CCO', 'format': 'smiles'}]}
    else:
        arguments['structures'] = [{'compound_id': '1', 'label': '1', 'smiles': 'CCO'}]
    response = asyncio.run(server.mcp.call_tool(name, arguments))
    result = json.loads(response[0].text)
    assert len(calls) == 1
    assert not {'plan', 'planning', 'group_plan'} & result.keys()
    assert result['details'] == str(tmp_path / 'result.json')
    for key in before.keys() - {'plan', 'planning', 'group_plan', 'audit'}:
        assert result[key] == before[key]
    assert result['audit'] == {k: v for k, v in before['audit'].items() if k != 'planning'}
    assert len(json.dumps(result)) < len(json.dumps(full)) / 10
    assert full == before
    assert json.loads((tmp_path / 'result.json').read_text()) == before


@pytest.mark.parametrize('status', ['needs_input', 'rejected', 'uncertain', 'failed'])
def test_failure_response_not_compacted(tmp_path, monkeypatch, status):
    result = completed(tmp_path)
    result.update(status=status, retry_safe=False, recovery={'document_id': 42})
    monkeypatch.setattr(server, 'bridge', lambda: object())
    monkeypatch.setattr(server, 'run_drawing', lambda *a, **kw: result)
    assert server.chemdraw_draw(server.DrawingRequest(molecules=[{'value': 'CCO', 'format': 'smiles'}]), str(tmp_path)) == result


def test_without_retained_details_return_full_result(tmp_path, monkeypatch):
    result = completed(tmp_path)
    (tmp_path / 'result.json').unlink()
    monkeypatch.setattr(server, 'bridge', lambda: object())
    monkeypatch.setattr(server, 'run_drawing', lambda *a, **kw: result)
    assert server.chemdraw_draw(server.DrawingRequest(molecules=[{'value': 'CCO', 'format': 'smiles'}]), str(tmp_path)) == result
