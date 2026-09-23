"""Desktop installers must tolerate extractors which do not preserve symlinks."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import json
import zipfile

import pytest


def test_runtime_stage_materializes_library_and_directory_links(tmp_path):
    spec = importlib.util.spec_from_file_location('desktop_builder', Path(__file__).parents[1]/'scripts/build_desktop.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = tmp_path/'frozen'
    (source/'libs').mkdir(parents=True)
    library = source/'libs/libchem.dylib'
    library.write_bytes(b'actual Mach-O fixture')
    library.chmod(0o755)
    (source/'libchem.dylib').symlink_to('libs/libchem.dylib')
    (source/'alias').symlink_to('libs', target_is_directory=True)
    target = tmp_path/'packaged'
    builder.stage_runtime(source, target)
    assert not any(path.is_symlink() for path in target.rglob('*'))
    assert (target/'libchem.dylib').read_bytes() == library.read_bytes()
    assert (target/'alias/libchem.dylib').read_bytes() == library.read_bytes()
    assert (target/'libchem.dylib').stat().st_mode & 0o111


@pytest.mark.skipif(not os.environ.get('CHEMDRAW_DESKTOP_ARCHIVE'), reason='Requires built MCPB')
def test_mcpb_works_with_plain_zip_extractor(tmp_path):
    with zipfile.ZipFile(os.environ['CHEMDRAW_DESKTOP_ARCHIVE']) as archive:
        assert not any(stat.S_ISLNK(item.external_attr >> 16) for item in archive.infolist()), 'ZIP library links break in Claude extraction'
        archive.extractall(tmp_path)
        for item in archive.infolist():
            mode = item.external_attr >> 16
            if mode & 0o111:
                (tmp_path/item.filename).chmod(mode & 0o777)
    from chemdraw_macos.desktop_setup import APP_NAME
    runtime = tmp_path/APP_NAME/'Contents/Resources/backend/chemdraw-runtime'
    result = subprocess.run([runtime, '--self-check'], capture_output=True, text=True,
                            env={'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin'}, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['cdxml_writer_available'] is True


def test_builder_names_one_neutral_main_download_and_optional_mcpb():
    spec = importlib.util.spec_from_file_location('desktop_builder', Path(__file__).parents[1]/'scripts/build_desktop.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.product_names('arm64') == {
        'installer': 'ChemDraw-MCP-Apple-Silicon.dmg',
        'bundle': 'ChemDraw-MCP-Apple-Silicon.mcpb',
    }


def test_speed_candidate_package_versions_are_consistent():
    import tomllib
    root = Path(__file__).parents[1]
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    assert version == '0.10.0rc17'
    build = (root / 'scripts/build_desktop.py').read_text()
    assert "'CFBundleVersion': '17'" in build
    assert "extension_manifest('0.10.0-rc.17', arch)" in build
    lock = tomllib.loads((root / 'uv.lock').read_text())
    assert next(p['version'] for p in lock['package'] if p['name'] == 'chemdraw-mcp-macos') == version
