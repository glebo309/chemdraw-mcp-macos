"""Tool profiles are exercised over real stdio, without requiring ChemDraw."""
import asyncio
import json
import os
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from chemdraw_macos import cli, server


CORE = {
    'chemdraw_list_documents', 'chemdraw_inspect_document',
    'chemdraw_import_file', 'chemdraw_create_document', 'chemdraw_clean',
    'chemdraw_apply_style', 'chemdraw_export', 'chemdraw_close_working_document',
    'chemdraw_list_styles', 'chemdraw_doctor',
}


def test_core_profile_keeps_existing_schemas_and_full_server(monkeypatch):
    def forbidden():
        raise AssertionError('Tool discovery must not connect to ChemDraw')
    monkeypatch.setattr(server, 'bridge', forbidden)
    original = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    core = server.get_server('core')
    actual = {t.name: t for t in asyncio.run(core.list_tools())}
    assert set(actual) == CORE
    for name in CORE:
        assert actual[name].model_dump() == original[name].model_dump()
    assert server.get_server() is server.mcp
    assert server.get_server('full') is server.mcp
    assert {t.name for t in asyncio.run(server.mcp.list_tools())} == set(original)
    with pytest.raises(ValueError, match='profile'):
        server.get_server('unknown')


def test_core_dispatch_uses_same_bridge(monkeypatch):
    calls = []
    class Native:
        def inspect(self, document_id):
            calls.append(document_id)
            return {'document_id': document_id}
    monkeypatch.setattr(server, 'bridge', Native)
    result = asyncio.run(server.get_server('core').call_tool(
        'chemdraw_inspect_document', {'document_id': 42}))
    assert calls == [42]
    assert json.loads(result[0].text) == {'document_id': 42}


@pytest.mark.parametrize('profile', ['core', 'full'])
def test_cli_serve_forwards_profile(monkeypatch, profile):
    calls = []
    monkeypatch.setattr(server, 'main', lambda argv: calls.append(argv))
    assert cli.main(['serve', '--profile', profile]) == 0
    assert calls == [['--profile', profile]]


@pytest.mark.asyncio
@pytest.mark.parametrize('entry,profile', [
    ('chemdraw_macos.server', 'core'),
    ('chemdraw_macos.server', 'full'),
    ('chemdraw_macos.cli', 'core'),
])
async def test_profile_discovery_and_call_over_stdio(entry, profile):
    args = ['-m', entry]
    if entry.endswith('.cli'):
        args.append('serve')
    args += ['--profile', profile]
    params = StdioServerParameters(command=sys.executable, args=args, env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert 'natural-language' in initialized.instructions.lower()
            names = {t.name for t in (await session.list_tools()).tools}
            assert CORE <= names
            if profile == 'core':
                assert names == CORE
                denied = await session.call_tool('chemdraw_draw_structures', {})
                assert denied.isError
            else:
                assert 'chemdraw_draw_structures' in names
            styles = await session.call_tool('chemdraw_list_styles', {})
            assert not styles.isError
            payload = styles.structuredContent or json.loads(styles.content[0].text)
            assert 'house' in payload['presets']


def test_core_discovery_without_optional_rdkit():
    code = '''
import asyncio, importlib.abc, json, sys
class NoChemistry(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'rdkit' or fullname.startswith('rdkit.'):
            raise AssertionError('Core must not import optional RDKit')
sys.meta_path.insert(0, NoChemistry())
from chemdraw_macos.server import get_server
core = get_server('core')
print(json.dumps([t.name for t in asyncio.run(core.list_tools())]))
assert not any(n == 'rdkit' or n.startswith('rdkit.') for n in sys.modules)
'''
    result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == CORE
