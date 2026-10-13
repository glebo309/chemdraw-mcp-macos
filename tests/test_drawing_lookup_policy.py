"""A supplied drawing name permits lookup; explicit offline requests do not."""
import asyncio

import pytest

from chemdraw_macos import server


@pytest.mark.parametrize('profile', ['full', 'drawing'])
@pytest.mark.parametrize('permission,expected', [(None, True), (False, False), (True, True)])
def test_drawing_lookup_default_and_explicit_override(monkeypatch, tmp_path, profile, permission, expected):
    calls = []
    monkeypatch.setattr(server, 'bridge', lambda: object())
    def capture(bridge, request, output_dir, allow_network, presentation, **kwargs):
        calls.append((request['molecules'][0]['value'], allow_network))
        return {'status': 'captured'}
    monkeypatch.setattr(server, 'run_drawing', capture)
    arguments = {'request': {'molecules': [{'format': 'name', 'value': 'caffeine'}]},
                 'output_dir': str(tmp_path / 'drawing')}
    if permission is not None:
        arguments['allow_network'] = permission
    asyncio.run(server.get_server(profile).call_tool('chemdraw_draw', arguments))
    assert calls == [('caffeine', expected)]


def test_explicit_offline_name_stops_before_lookup_or_native(monkeypatch, tmp_path):
    from chemdraw_macos import harness
    monkeypatch.setattr(server, 'bridge', lambda: object())
    monkeypatch.setattr(harness, 'resolve_identifier', lambda *a, **kw: pytest.fail('Network forbidden'))
    result = server.chemdraw_draw(
        server.DrawingRequest(molecules=[{'format': 'name', 'value': 'unlisted-private-name'}]),
        str(tmp_path / 'offline'), allow_network=False)
    assert result['status'] == 'needs_input'
    assert result['code'] == 'network_permission_required'
    assert not (tmp_path / 'offline').exists()
