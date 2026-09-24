"""Opt-in acceptance against an actual self-contained desktop executable."""
import json
import os
from pathlib import Path
import subprocess

import pytest

RUNTIME = os.environ.get('CHEMDRAW_DESKTOP_RUNTIME')
pytestmark = pytest.mark.skipif(not RUNTIME, reason='Set CHEMDRAW_DESKTOP_RUNTIME to the frozen executable')


@pytest.mark.skipif(not os.environ.get('CHEMDRAW_PREVIOUS_RUNTIME'), reason='Requires two released build runtimes')
def test_frozen_upgrade_keeps_configs_and_switches_executed_version(tmp_path):
    from chemdraw_macos.client_install import install_and_connect
    old_runtime = os.environ['CHEMDRAW_PREVIOUS_RUNTIME']
    configs = None
    versions = []
    for runtime in (old_runtime, RUNTIME):
        result = install_and_connect(Path(runtime).resolve().parents[3], ['claude', 'codex'], home=tmp_path)
        current = [(tmp_path/p).read_bytes() for p in (
            '.codex/config.toml', 'Library/Application Support/Claude/claude_desktop_config.json')]
        if configs is not None: assert configs == current
        configs = current
        run = subprocess.run([result['terminal_command'], 'doctor', '--no-connect'],
            env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr
        report = json.loads(run.stdout)
        versions.append(report['package_version'])
        assert report['cdxml_writer_available'] and report['rasterizer_available']
    assert versions[0] != versions[1]
    assert versions[1] == __import__('importlib.metadata').metadata.version('chemdraw-mcp-macos')


def test_frozen_app_has_native_finder_icon():
    import plistlib
    app = Path(RUNTIME).resolve().parents[3]
    info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert info['CFBundleDisplayName'] == 'ChemDraw MCP'
    icon = app/'Contents/Resources'/info['CFBundleIconFile']
    assert icon.read_bytes().startswith(b'icns')


def test_frozen_terminal_cli_needs_no_python_uv_or_source_checkout(tmp_path):
    result = subprocess.run([RUNTIME, '--cli', 'identify', '--value', 'CCO'],
                            capture_output=True, text=True, cwd=tmp_path,
                            env={'PATH': '/usr/bin:/bin'}, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['formula'] == 'C2H6O'
    help_result = subprocess.run([RUNTIME, '--cli', 'first-run', '--help'],
                                capture_output=True, text=True, cwd=tmp_path,
                                env={'PATH': '/usr/bin:/bin'}, timeout=30)
    assert help_result.returncode == 0, help_result.stderr
    assert '--no-animation' in help_result.stdout
    from chemdraw_macos.client_install import install_and_connect
    installed = install_and_connect(Path(RUNTIME).resolve().parents[3], ['bundle'], home=tmp_path)
    terminal = subprocess.run(['/bin/zsh', '-ic', 'chemdraw-mac identify --value CCO'],
                              capture_output=True, text=True, cwd=tmp_path,
                              env={'ZDOTDIR': str(tmp_path), 'PATH': '/usr/bin:/bin'}, timeout=30)
    assert terminal.returncode == 0, terminal.stderr
    assert json.loads(terminal.stdout)['formula'] == 'C2H6O'
    assert Path(installed['terminal_command']).is_file()


def test_frozen_runtime_needs_no_system_python_or_shell_profile(tmp_path):
    result = subprocess.run([RUNTIME, '--self-check'], capture_output=True, text=True,
                            cwd=tmp_path, env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'}, timeout=30)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value['cdxml_writer_available'] and value['raster_ok']


def test_frozen_setup_protocol_stays_machine_readable(tmp_path):
    result = subprocess.run([RUNTIME, '--setup-service'], input='{"action":"welcome"}\n{"action":"check"}\n',
                            capture_output=True, text=True, cwd=tmp_path,
                            env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'}, timeout=30)
    assert result.returncode == 0, result.stderr
    welcome, checked = map(json.loads, result.stdout.splitlines())
    assert len(welcome['molecules']) == 9
    assert welcome['credit'] == 'Created by Glenn Bojanov'
    assert checked['ready'] is False
    assert checked['details']['cdxml_writer_available']


@pytest.mark.asyncio
async def test_frozen_real_mcp_initialize_discovery_and_offline_chemistry(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    # A test-only home suppresses GUI onboarding. No actual installation state changes.
    settings = tmp_path/'Library/Application Support/ChemDraw MCP/desktop-setup.json'
    settings.parent.mkdir(parents=True)
    settings.write_text('{"setup_complete":true}')
    params = StdioServerParameters(command=RUNTIME, args=['--desktop-serve'],
        cwd=str(tmp_path), env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {'chemdraw_draw', 'chemdraw_read_live_document', 'chemdraw_doctor',
                    'chemdraw_export_figure'} <= {t.name for t in tools.tools}
            draw = next(t for t in tools.tools if t.name == 'chemdraw_draw')
            assert 'page_policy' in str(draw.inputSchema)
            assert 'exports' in str(draw.inputSchema)
            assert 'refresh_identifiers' in str(draw.inputSchema)
            assert 'reaction_paper' in str(draw.inputSchema)
            result = await session.call_tool('chemdraw_identify', {'value': 'CCO', 'input_format': 'smiles'})
            assert not result.isError
            assert 'C2H6O' in str(result)


@pytest.mark.asyncio
async def test_shared_install_and_both_client_configs_launch_real_mcp(tmp_path):
    import shutil
    import tomllib
    from chemdraw_macos.client_install import install_and_connect, SERVER_NAME
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    result = install_and_connect(Path(RUNTIME).resolve().parents[3], ['claude', 'codex'], home=tmp_path)
    # Isolated test home, no user client settings or installation are changed.
    settings = tmp_path/'Library/Application Support/ChemDraw MCP/desktop-setup.json'
    settings.write_text(json.dumps({'setup_complete': True, 'installed_app': result['installed_app']}))
    config = tomllib.loads((tmp_path/'.codex/config.toml').read_text())['mcp_servers'][SERVER_NAME]
    claude = json.loads((tmp_path/'Library/Application Support/Claude/claude_desktop_config.json').read_text())
    assert claude['mcpServers'][SERVER_NAME]['command'] == config['command'] == result['command']
    if codex := shutil.which('codex'):
        checked = subprocess.run([codex, 'mcp', 'get', SERVER_NAME, '--json'],
            env={**os.environ, 'CODEX_HOME': str(tmp_path/'.codex')},
            capture_output=True, text=True, timeout=30)
        assert checked.returncode == 0, checked.stderr
        assert json.loads(checked.stdout)['transport']['command'] == result['command']
    for command in (config['command'], RUNTIME):
        params = StdioServerParameters(command=command, args=config['args'],
            cwd=str(tmp_path), env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                response = await session.call_tool('chemdraw_identify', {'value': 'CCO', 'input_format': 'smiles'})
                assert not response.isError and 'C2H6O' in str(response)


def test_frozen_native_svg_raster_worker_dispatch(tmp_path):
    svg = tmp_path/'fixture.svg'
    png = tmp_path/'fixture.png'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M1 1L9 9" stroke="black"/></svg>')
    result = subprocess.run([RUNTIME, '-m', 'chemdraw_macos.raster', str(svg), str(png), '256'],
                            capture_output=True, text=True, cwd=tmp_path, timeout=30)
    assert result.returncode == 0, result.stderr
    assert png.read_bytes().startswith(b'\x89PNG')


def test_frozen_fresh_setup_exports_zip_without_preinstalling(tmp_path):
    from chemdraw_macos.core import app_location
    from zipfile import ZipFile
    exported = tmp_path/'Downloads/ChemDraw MCP Native API.chemdrawaddin'
    exported.parent.mkdir()
    requests = [{'action': 'choose_app', 'path': str(app_location())},
                {'action': 'prepare'}, {'action': 'export_installer', 'path': str(exported)}]
    result = subprocess.run([RUNTIME, '--setup-service'],
        input=''.join(json.dumps(request)+'\n' for request in requests), capture_output=True,
        text=True, cwd=tmp_path, env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'}, timeout=30)
    assert result.returncode == 0, result.stderr
    selected, prepared, saved = map(json.loads, result.stdout.splitlines())
    assert selected['status'] == 'selected'
    assert prepared['status'] == 'prepared', prepared
    assert prepared['existing_files'] is False
    assert saved['status'] == 'exported', saved
    assert not (tmp_path/'Library/Application Support/com.revvity.ChemDraw/Add-ins/ChemDraw MCP Native API').exists()
    with ZipFile(exported) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 2
    assert exported.stat().st_mode & 0o077 == 0


@pytest.mark.skipif(os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST') != '1', reason='Opt-in read of an existing live ChemDraw document')
def test_frozen_setup_live_read_without_drawing_writes():
    result = subprocess.run([RUNTIME, '--setup-service'], input='{"action":"test"}\n',
                            capture_output=True, text=True, cwd='/tmp', timeout=60)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value['ready'] is True, value


@pytest.mark.skipif(os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST') != '1', reason='Requires exclusive native connection')
@pytest.mark.asyncio
async def test_frozen_drawing_preview_and_upright_caffeine(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from chemdraw_macos.core import Bridge
    from test_api_drawing import EMPTY
    from PIL import Image
    from rdkit import Chem
    owner = Bridge()
    baseline = owner.documents()
    did = owner.create(EMPTY)['document']['document_id']
    # Execute this candidate directly. --desktop-serve deliberately delegates to
    # the user's selected shared install, which can still be an older release.
    # Shared-launcher installation is covered separately in an isolated home.
    params = StdioServerParameters(command=RUNTIME, args=['--cli', 'serve', '--profile', 'full'], env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            response = await session.call_tool('chemdraw_draw', {
                'document_id': did, 'output_dir': str(tmp_path / 'caffeine'),
                'request': {'molecules': [{'format': 'smiles', 'value': 'Cn1c(=O)c2c(ncn2C)n(C)c1=O', 'label': 'Caffeine'}]}})
            assert not response.isError, response
            result = response.structuredContent or json.loads(response.content[0].text)
            assert result['status'] == 'completed', result
            assert result['delivery']['mode'] == 'preview'
            assert result['planning']['orientations'][0]['policy'] == 'axis_aligned_six_ring'
            assert result['timings']['total_seconds'] > 0
            assert all(result['checks'].values())
            image = Image.open(result['artifacts']['preview'])
            assert max(image.size) == 1200 and image.getpixel((0, 0)) == (255, 255, 255, 255)
            mol = Chem.MolsFromCDXML(Path(result['artifacts']['cdxml']).read_text())[0]
            rings = mol.GetRingInfo().AtomRings()
            a, b = set(next(r for r in rings if len(r) == 6)) & set(next(r for r in rings if len(r) == 5))
            conf = mol.GetConformer()
            assert abs(conf.GetAtomPosition(a).x - conf.GetAtomPosition(b).x) < .002
    owner.close(did)
    assert owner.documents() == baseline


@pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires exclusive native ChemDraw')
@pytest.mark.asyncio
async def test_frozen_complete_reaction_through_mcp(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from test_reaction_batch import glycoside_reaction
    from PIL import Image
    from chemdraw_macos.core import Bridge
    step=glycoside_reaction()[0];owner=Bridge();baseline=owner.documents()
    request={'molecules':[{'format':'smiles','value':p['smiles'],'label':p['label']} for p in step['reactants']],
             'products':[{'format':'smiles','value':p['smiles'],'label':p['label']} for p in step['products']],
             'conditions_above':step['conditions_above'],'conditions_below':step['conditions_below']}
    params=StdioServerParameters(command=RUNTIME,args=['--cli','serve','--profile','full'],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            response=await session.call_tool('chemdraw_draw',{'request':request,'output_dir':str(tmp_path/'reaction'),'presentation':'background'})
            assert not response.isError,response
            result=response.structuredContent or json.loads(response.content[0].text)
            assert result['status']=='completed',result
            assert result['planning']['paper']['name']=='A4 landscape'
            assert all(result['checks'].values()) and len(result['plan']['provenance'])==4
            assert result['checks']['native_charge_clearance']
            assert result['checks']['native_charge_ownership']
            import xml.etree.ElementTree as ET
            assert len(ET.parse(result['artifacts']['cdxml']).findall('page/fragment/graphic'))==4
            assert Image.open(result['artifacts']['png']).info['dpi']==pytest.approx((600,600),abs=.02)
    assert owner.documents()==baseline
