"""Build a local architecture-specific MCPB, including native graphical setup.

Run using the build environment with the locked project and PyInstaller installed.
No publication, signing-identity creation, client install or credential copying.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chemdraw_macos.desktop_setup import APP_NAME, extension_manifest


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def stage_runtime(source, destination):
    # Claude's MCPB extractor can materialize ZIP symlinks as link-target text.
    # Ship actual library bytes at every loader path, including framework aliases.
    shutil.copytree(source, destination, symlinks=False)


def product_names(architecture):
    machine = {'arm64': 'Apple-Silicon', 'x86_64': 'Intel'}[architecture]
    return {'installer': f'ChemDraw-MCP-{machine}.dmg', 'bundle': f'ChemDraw-MCP-{machine}.mcpb'}


def build(destination):
    if platform.system() != 'Darwin':
        raise RuntimeError('Build on macOS for the target architecture')
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    stage = destination/'extension'
    app = stage/APP_NAME
    resources = app/'Contents/Resources'
    executable = app/'Contents/MacOS/ChemDrawWelcome'
    resources.mkdir(parents=True)
    executable.parent.mkdir()
    arch = platform.machine()
    swift_flags = []
    if os.environ.get('CHEMDRAW_BUILD_SWIFT_OVERLAY'):
        overlay = str(Path(os.environ['CHEMDRAW_BUILD_SWIFT_OVERLAY']).resolve())
        swift_flags = ['-vfsoverlay', overlay, '-Xcc', '-ivfsoverlay', '-Xcc', overlay]
    run(['swiftc', '-parse-as-library', '-O', *swift_flags, '-target', arch+'-apple-macosx13.0',
         ROOT/'packaging/SetupPresentation.swift', ROOT/'packaging/Welcome.swift', '-o', executable])
    info = {'CFBundleExecutable': executable.name, 'CFBundleIdentifier': 'org.glebo309.chemdraw-mcp.setup',
            'CFBundleName': 'ChemDraw MCP', 'CFBundleDisplayName': 'ChemDraw MCP',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '18', 'CFBundleShortVersionString': '0.10.0',
            'CFBundleIconFile': 'ChemDraw.icns',
            'LSMinimumSystemVersion': '13.0', 'NSHighResolutionCapable': True,
            'NSAppleEventsUsageDescription': 'Connect to ChemDraw to verify your local drawing setup.'}
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    shutil.copy2(ROOT/'chemdraw_macos/data/welcome.json', resources/'welcome.json')
    from chemdraw_macos.raster import rasterize_svg
    (stage/'icon.png').write_bytes(rasterize_svg((ROOT/'packaging/icon.svg').read_text(), 512))
    iconset = destination/'ChemDraw.iconset'
    iconset.mkdir()
    import resvg_py
    for size in (16, 32, 128, 256, 512):
        for factor in (1, 2):
            suffix = '@2x' if factor == 2 else ''
            (iconset/f'icon_{size}x{size}{suffix}.png').write_bytes(
                resvg_py.svg_to_bytes(svg_string=(ROOT/'packaging/icon.svg').read_text(),
                                      width=size*factor, height=size*factor))
    run(['/usr/bin/iconutil', '-c', 'icns', iconset, '-o', resources/'ChemDraw.icns'])
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--name', 'chemdraw-runtime',
         '--distpath', destination/'frozen', '--workpath', destination/'work', '--specpath', destination,
         '--paths', ROOT, '--collect-all', 'chemdraw_macos', '--collect-all', 'rdkit',
         '--collect-all', 'resvg_py', '--collect-submodules', 'mcp.server', '--collect-data', 'mcp', '--copy-metadata', 'chemdraw-mcp-macos',
         ROOT/'packaging/desktop_runtime.py'], cwd=ROOT)
    stage_runtime(destination/'frozen/chemdraw-runtime', resources/'backend')
    notices = resources/'Licenses'
    notices.mkdir()
    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name, notices/name)
    shutil.copytree(ROOT/'licenses', notices/'project-upstream')
    for dist in importlib.metadata.distributions():
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ('license', 'copying', 'notice')) and '.dist-info/' in str(file):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = notices/dist.metadata['Name']/Path(*Path(str(file)).parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    # CPython's bundled license covers the redistributed interpreter and stdlib.
    python_license = Path(sys.base_prefix)/f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Locate the bundled interpreter license before distribution')
    shutil.copy2(python_license, notices/'Python-LICENSE.txt')
    # The same corresponding source accompanies both distribution formats.
    run(['uv', 'build', '--sdist', '--out-dir', resources/'Source', ROOT])
    run(['codesign', '--force', '--deep', '--sign', '-', app])
    run(['codesign', '--verify', '--deep', '--strict', app])
    run([resources/'backend/chemdraw-runtime', '--self-check'], cwd='/tmp', env={
        'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8'})
    manifest = extension_manifest('0.10.0-rc.18', arch)
    (stage/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    output = destination/product_names(arch)['bundle']
    # No symbolic links: do not rely on a client's ZIP link extraction semantics.
    if any(path.is_symlink() for path in stage.rglob('*')):
        raise RuntimeError('Desktop bundle must contain real files, not symbolic links')
    run(['/usr/bin/ditto', '-c', '-k', '--norsrc', stage, output])
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Extension archive CRC check failed')
        if any('.connection.json' in name or name.endswith('.chemdrawaddin') for name in archive.namelist()):
            raise RuntimeError('Private add-in must never be distributed')
    print(output)
    installer_stage = destination/'installer'
    installer_stage.mkdir()
    shutil.copytree(app, installer_stage/APP_NAME)
    installer = destination/product_names(arch)['installer']
    run(['/usr/bin/hdiutil', 'create', '-volname', 'ChemDraw MCP', '-srcfolder', installer_stage,
         '-format', 'UDZO', installer])
    run(['/usr/bin/hdiutil', 'verify', installer])
    print(installer)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path, help='New build directory')
    build(parser.parse_args().destination)
