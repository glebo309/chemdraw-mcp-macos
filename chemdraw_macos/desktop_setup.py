"""Bounded setup protocol for the native macOS welcome window.

No HTTP setup server or drawing writes. Client configuration changes require an
explicit selection and successful read, and preserve recoverable originals.
"""
import json
import errno
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys


APP_NAME = 'ChemDraw MCP.app'


def export_installer(package, target, installation_directory):
    import io
    import tempfile
    import zipfile
    target = Path(target)
    if target.resolve().is_relative_to(Path(installation_directory).resolve()):
        raise ValueError('Save outside the ChemDraw installation folder, for example in Downloads')
    if target.suffix != '.chemdrawaddin' or target.is_symlink():
        raise ValueError('Choose a regular .chemdrawaddin file in Downloads')
    try:
        data = Path(package).read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != {'main.html', 'chemdraw-addin-metadata.json'}:
                raise ValueError('Invalid add-in package contents')
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError('The add-in package failed validation. Prepare it again before saving.') from exc
    fd, temporary = tempfile.mkstemp(prefix='.chemdraw-installer-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as handle: handle.write(data)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return target


def settings_path():
    return Path.home()/'Library/Application Support/ChemDraw MCP/desktop-setup.json'


def read_settings(path=None):
    path = path or settings_path()
    if path.is_symlink():
        raise ValueError('Setup settings must not be a symbolic link')
    return json.loads(path.read_text()) if path.exists() else {}


def validate_app(value):
    app = Path(value).expanduser().resolve()
    try:
        metadata = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    except (OSError, plistlib.InvalidFileException) as exc:
        raise ValueError('Choose the installed ChemDraw application') from exc
    if app.suffix != '.app' or metadata.get('CFBundleIdentifier') not in (
            'com.revvity.ChemDraw', 'com.perkinelmer.ChemDraw', 'com.cambridgesoft.ChemDraw'):
        raise ValueError('The selected application is not a recognized ChemDraw installation')
    return app


def welcome_data():
    from .welcome import load_molecules
    return {'status': 'welcome', 'renderer': 'native ChemDraw',
            'credit': 'Created by Glenn Bojanov', 'molecules': load_molecules()}


def diagnostic_details(report, exception=None):
    """Shareable allowlist. Never export exception text, paths or document data."""
    details = {key: report.get(key) for key in (
        'package_version', 'macos', 'architecture', 'version', 'rdkit_version',
        'cdxml_writer_available', 'rasterizer_available', 'status',
        'native_connection', 'shared_drawing_ready') if key in report}
    api = report.get('desktop_api', {})
    details['desktop_api'] = {key: api[key] for key in (
        'status', 'code', 'api_version', 'read_verified', 'write_tested') if key in api}
    error = str(exception) if exception is not None else report.get('error', '')
    if error:
        match = re.search(r'\((-\d+)\)', error) if error.startswith('ChemDraw automation failed:') else None
        code = int(match[1]) if match else None
        kind = ('automation_denied' if code == -1743 else
                'addin_timeout' if error.startswith('Add-in response timed out') else
                'automation_timeout' if error.startswith('ChemDraw automation timed out') else
                'native_error' if code is not None else 'unclassified_error')
        details['failure'] = {'kind': kind, 'native_error_code': code}
        if exception is not None:
            details['failure']['exception_type'] = type(exception).__name__
            if isinstance(exception, OSError):
                details['failure']['os_error_code'] = exception.errno
    return details


def present_diagnostic(report):
    ready = report.get('status') == 'ready' and report.get('shared_drawing_ready') is True
    messages = {
        'local_ready': ('Software checked', 'Click Next to prepare the ChemDraw add-in.'),
        'needs_setup': ('Enable the ChemDraw add-in', 'Follow the add-in steps below, then click Next.'),
        'needs_document': ('Open a drawing', 'In ChemDraw, choose File > New. Then click Next again.'),
        'busy': ('Another assistant is connected', 'Disconnect the ChemDraw extension in your other assistant, then test again. Nothing needs reinstalling.'),
        'unavailable': ('Connection needs attention', 'The connection check failed. Choose Save diagnostics or Copy diagnostics to share the failure details.'),
        'basic_only': ('Bundled software needs attention', 'A bundled chemistry component could not load. Choose Save diagnostics and share the report so the installer can be corrected.'),
    }
    title, message = ('Connected to ChemDraw', 'The live document read passed. Finish setup to connect your selected assistants.') if ready else messages.get(report.get('status'), ('Not connected yet', 'Prepare the add-in, open a ChemDraw document, then test the connection.'))
    details = diagnostic_details(report)
    failure = details.get('failure', {}).get('kind')
    if report.get('status') == 'unavailable' and failure == 'automation_denied':
        title = 'ChemDraw control was denied'
        message = 'macOS reported an Automation denial. Check System Settings > Privacy & Security > Automation for the launching app. If no entry appears, choose Save diagnostics.'
    elif report.get('status') == 'unavailable' and failure == 'addin_timeout':
        title = 'The ChemDraw add-in did not respond'
        message = 'The local add-in did not return the document read. Choose Save diagnostics and share the report; this does not establish a permissions problem.'
    # Never return drawings, document names, private credentials or raw XML to the UI.
    return {'status': report.get('status', 'unavailable'), 'ready': ready,
            'title': title, 'message': message,
            'details': details}


class SetupSession:
    def __init__(self, *, settings_path=None):
        self.path = settings_path or globals()['settings_path']()
        self.settings = read_settings(self.path)
        self.bridge = None
        self.last_diagnostic = {}

    def close(self):
        backend = getattr(self.bridge, '_desktop_addin', None)
        if backend is not None:
            backend.close()
        self.bridge = None

    def _bridge(self):
        if self.bridge is None:
            from .core import Bridge
            selected = self.settings.get('chemdraw_app')
            self.bridge = Bridge(app_path=validate_app(selected) if selected else None)
        return self.bridge

    def install_clients(self, clients):
        from .client_install import install_and_connect
        if not getattr(sys, 'frozen', False):
            raise ValueError('Use the bundled Mac application for graphical client installation')
        app = Path(sys.executable).resolve().parents[3]
        return install_and_connect(app, clients)

    def dispatch(self, request):
        action = request.get('action')
        if action == 'welcome':
            return welcome_data()
        if action == 'choose_app':
            app = validate_app(request['path'])
            self.close()
            self.last_diagnostic = {}
            self.settings['chemdraw_app'] = str(app)
            return {'status': 'selected', 'app': str(app)}
        if action in ('check', 'test'):
            from .diagnostics import doctor
            selected = self.settings.get('chemdraw_app')
            previous = os.environ.get('CHEMDRAW_APP')
            try:
                if selected:
                    os.environ['CHEMDRAW_APP'] = str(validate_app(selected))
                self.last_diagnostic = doctor(connect=action == 'test',
                                              bridge=self._bridge() if action == 'test' else None)
            finally:
                if previous is None:
                    os.environ.pop('CHEMDRAW_APP', None)
                else:
                    os.environ['CHEMDRAW_APP'] = previous
            return present_diagnostic(self.last_diagnostic)
        if action == 'prepare':
            from .addin import get_backend
            self.last_diagnostic = {}
            try:
                backend = get_backend(self._bridge(), setup=True)
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                self.last_diagnostic = {'status': 'busy', 'shared_drawing_ready': False}
                return present_diagnostic(self.last_diagnostic)
            return {'status': 'prepared', 'package': str(backend.package),
                    'existing_files': all((backend.directory/name).is_file() for name in ('main.html', 'chemdraw-addin-metadata.json')),
                    'search_directory': str(backend.directory.parent.parent)}
        if action == 'export_installer':
            backend = getattr(self.bridge, '_desktop_addin', None)
            if backend is None or backend.closed:
                raise ValueError('Prepare the add-in before saving its installer')
            path = export_installer(backend.package, request['path'], backend.directory)
            return {'status': 'exported', 'path': str(path)}
        if action == 'finish':
            if not present_diagnostic(self.last_diagnostic)['ready']:
                raise ValueError('Test the live connection successfully before finishing setup')
            self.close()
            if 'clients' in request:
                result = self.install_clients(request['clients'])
                self.settings['clients'] = result['clients']
                self.settings['installed_app'] = result.get('installed_app')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise ValueError('Refusing symbolic link for setup settings')
            import tempfile
            fd, name = tempfile.mkstemp(prefix='.setup-', dir=self.path.parent)
            try:
                with os.fdopen(fd, 'w') as handle:
                    json.dump({**self.settings, 'setup_complete': True}, handle)
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return {'status': 'finished'}
        raise ValueError('Unknown setup action')


def serve_setup(source=None, sink=None, *, session=None):
    source, sink = source or sys.stdin, sink or sys.stdout
    session = session or SetupSession()
    try:
        for line in source:
            try:
                if len(line) > 16384:
                    raise ValueError('Setup request too large')
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Expected a setup request')
                value = session.dispatch(request)
            except Exception as exc:
                # Local UI only; no upload. Do not serialize private connection objects.
                value = {'status': 'error', 'title': 'Setup needs attention', 'message': str(exc),
                         'details': diagnostic_details({'status': 'error'}, exception=exc)}
            sink.write(json.dumps(value, ensure_ascii=True)+'\n')
            sink.flush()
    finally:
        session.close()


def extension_manifest(version, architecture):
    if architecture not in ('arm64', 'x86_64'):
        raise ValueError('Build a separate bundle for each supported Mac architecture')
    machine = 'Apple Silicon' if architecture == 'arm64' else 'Intel'
    executable = APP_NAME+'/Contents/Resources/backend/chemdraw-runtime'
    return {'manifest_version': '0.3', 'name': 'chemdraw-macos',
            'display_name': 'ChemDraw MCP', 'version': version,
            'description': f'Native, same-document ChemDraw drawing on {machine} Macs. Includes graphical setup.',
            'long_description': 'Requires your own licensed ChemDraw. Reads unsaved edits and draws editable molecules in the same canvas. Bundled Python and chemistry tools; no terminal setup. Experimental: ChemDraw 23.0.1 is the tested build. On first launch the setup window guides add-in installation. Drawing stays local; explicitly approved name resolution uses PubChem. Your assistant has its own data policies.',
            'author': {'name': 'Glenn Bojanov'}, 'license': 'AGPL-3.0-only', 'icon': 'icon.png',
            'server': {'type': 'binary', 'entry_point': executable,
                       'mcp_config': {'command': '${__dirname}/'+executable,
                                      'args': ['--desktop-serve']}},
            'tools_generated': True, 'compatibility': {'platforms': ['darwin']}}


def runtime_main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    # Existing native export launches this exact restricted worker command.
    if args[:2] == ['-m', 'chemdraw_macos.raster']:
        from .raster import main
        return main(args[2:])
    if args[:1] == ['--cli']:
        settings = read_settings()
        if settings.get('chemdraw_app'):
            os.environ['CHEMDRAW_APP'] = str(validate_app(settings['chemdraw_app']))
        os.environ.pop('CHEMDRAW_DESKTOP_EXTENSION', None)
        from .cli import main
        return main(args[1:])
    if args == ['--setup-service']:
        os.environ.pop('CHEMDRAW_DESKTOP_EXTENSION', None)
        serve_setup()
        return 0
    if args == ['--desktop-serve']:
        settings = read_settings()
        if settings.get('setup_complete') and settings.get('installed_app'):
            installed = Path(settings['installed_app'])
            base = Path.home()/'Library/Application Support/ChemDraw MCP/versions'
            if installed.name != APP_NAME or not installed.resolve().is_relative_to(base.resolve()):
                raise ValueError('Shared installation path is outside the ChemDraw MCP directory')
            runtime = installed/'Contents/Resources/backend/chemdraw-runtime'
            if not runtime.is_file():
                raise ValueError('Shared ChemDraw MCP runtime is missing. Reopen the installer to repair it.')
            if runtime.resolve() != Path(sys.executable).resolve():
                # MCPB hosts and all configured local clients use the same installed build.
                os.execv(str(runtime), [str(runtime), '--desktop-serve'])
        if settings.get('chemdraw_app'):
            os.environ['CHEMDRAW_APP'] = str(validate_app(settings['chemdraw_app']))
        if not settings.get('setup_complete'):
            # Frozen executable lives inside the extension's signed helper app.
            app = Path(sys.executable).resolve().parents[3]
            if app.name == APP_NAME:
                subprocess.run(['/usr/bin/open', str(app)], check=True, timeout=15,
                               stdout=subprocess.DEVNULL, stderr=sys.stderr)
        os.environ['CHEMDRAW_DESKTOP_EXTENSION'] = '1'
        from .server import main
        main(['--profile', 'full'])
        return 0
    if args == ['--self-check']:
        from .diagnostics import _chemistry
        from .raster import rasterize_svg
        result = _chemistry()
        result['raster_ok'] = rasterize_svg('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M1 1L9 9" stroke="black"/></svg>', 256).startswith(b'\x89PNG')
        print(json.dumps(result))
        return 0 if result['cdxml_writer_available'] and result['raster_ok'] else 1
    raise ValueError('Unsupported desktop runtime invocation')
