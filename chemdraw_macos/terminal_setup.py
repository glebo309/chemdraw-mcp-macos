"""Interactive, terminal-only add-in setup with explicit client registration."""
import os
from pathlib import Path
import shutil
import shlex
import sys
import tempfile
import json
from datetime import datetime, timezone

from .desktop_setup import SetupSession, diagnostic_details
from .terminal_screen import SetupScreen


def run_setup(args, *, session=None, home=None, input_fn=None, stream=None, executable=None):
    stream = stream or sys.stdout
    if input_fn is None and not sys.stdin.isatty():
        print('Run setup in an interactive terminal. For diagnostics use doctor.', file=sys.stderr)
        return 1
    input_fn = input_fn or input
    home = Path(home) if home is not None else Path.home()
    frozen = getattr(sys, 'frozen', False)
    installed_bin = home/'Library/Application Support/ChemDraw MCP/bin' if frozen else Path(sys.executable).parent
    executable = Path(executable) if executable else installed_bin/'chemdraw-mcp-macos'
    source = Path(__file__).resolve().parents[1]
    if not frozen and (source/'uv.lock').is_file() and (source/'pyproject.toml').is_file():
        project = [] if Path.cwd().resolve() == source else ['--project', str(source)]
        demo = shlex.join(['uv', 'run', *project, '--locked', '--extra', 'chemistry', 'chemdraw-mac', 'first-run'])
    else:
        demo = shlex.join([str(executable.with_name('chemdraw-mac')), 'first-run'])
    animate = (not args.no_animation and stream.isatty() and
               os.environ.get('TERM') != 'dumb' and not os.environ.get('CI') and
               shutil.get_terminal_size().columns >= 72)

    screen = SetupScreen(stream, enabled=animate)
    outcome = ''
    events = []
    action = 'startup'

    def record(status, details):
        events.append({'timestamp': datetime.now(timezone.utc).isoformat(),
                       'action': action, 'status': status, 'details': details})

    def dispatch(request):
        nonlocal action
        action = request['action']
        value = session.dispatch(request)
        # SetupSession supplies shareable details; never record request paths,
        # exported add-in contents, raw messages or private credentials.
        record(value.get('status', 'error'), value.get('details', {}))
        return value

    def stage(action, label, phase):
        screen.show(label)
        return dispatch({'action': action})

    try:
        screen.__enter__()
        session = session or SetupSession()
        if not animate:
            print('CHEMDRAW / MCP\nTerminal setup\nCreated by Glenn Bojanov\n', file=stream)
        if args.app:
            dispatch({'action': 'choose_app', 'path': args.app})
        checked = stage('check', 'Checking installed software', 'installation')
        if checked['status'] != 'local_ready':
            raise ValueError(checked.get('message', 'Software check failed. Run doctor --no-connect.'))
        prepared = stage('prepare', 'Preparing the private add-in', 'connection')
        if prepared['status'] != 'prepared':
            raise ValueError(prepared.get('message', 'Add-in preparation failed.'))
        downloads = home/'Downloads'
        downloads.mkdir(exist_ok=True)
        # ChemDraw derives the installed folder from the archive's basename.
        # Make the enclosing folder unique, not the add-in's installation name.
        folder = Path(tempfile.mkdtemp(prefix='ChemDraw-MCP-Setup-', dir=downloads))
        target = folder/'ChemDraw MCP Native API.chemdrawaddin'
        with target.open('xb'):
            target.chmod(0o600)
        dispatch({'action': 'export_installer', 'path': str(target)})
        screen.show('Connect ChemDraw', [
            '1. Open ChemDraw > Add-ins > Add-in Manager.',
            'Enable ChemDraw MCP Native API if listed.',
            'If absent: + > Add from file.',
            '', 'In Downloads, open:', folder.name + '/', target.name, '',
            '2. Open a drawing. A blank one is fine.',
            'The connection test reads it without changing it.', '',
            'This add-in file contains your local connection key. Do not share it.',
            'After setup, you can delete this Downloads copy. The installed add-in stays.',
        ])
        screen.wait(input_fn, 'Return to test connection  /  Ctrl-C to stop')
        tested = stage('test', 'Testing the native document read', 'connection')
        if not tested.get('ready'):
            raise ValueError(tested.get('message', 'Connection not ready.'))
        session.close()  # Release the single-owner endpoint before another client starts.
        if args.client:
            if not executable.is_file():
                raise ValueError('Installed MCP executable is missing; install the package before registering clients')
            from .client_install import connect_clients
            result = connect_clients(args.client, executable, home=home, args=['--profile', 'full'])
            if result['bundle_clients']:
                screen.show('Existing Claude registration retained')
        screen.show('Installation finished', ['Connected. Document read: PASS.', '',
            'Selected client settings saved. Restart those clients.' if args.client else
            'ChemDraw is ready for a local MCP client.', '',
            'MCP server:', str(executable), 'Arguments: --profile full', '',
            'Optional drawing demo:', demo,
            'Only one assistant can connect at a time.'])
        if animate: screen.wait(input_fn, 'Return to finish and restore your terminal')
        outcome = ('Connected. Document read: PASS. Terminal setup is finished.\n'
                   'Optional drawing demo (open a blank drawing first):\n' + demo)
        return 0
    except (KeyboardInterrupt, EOFError):
        outcome = 'Setup stopped. No drawing was changed.'
        return 130
    except Exception as exc:
        outcome = f'Setup needs attention: {exc}'
        record('error', diagnostic_details({'status': 'error'}, exception=exc))
        report = 'ChemDraw MCP terminal setup diagnostics\nNo drawings or connection keys are included.\n\n'
        report += json.dumps({'schema_version': 1, 'route': 'terminal', 'events': events}, indent=2)+'\n'
        try:
            logs = home/'Library/Logs/ChemDraw MCP'
            if logs.is_symlink() or any(p.is_symlink() for p in logs.parents if p != home.parent):
                raise ValueError('Diagnostic folder must not be a symbolic link')
            logs.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, name = tempfile.mkstemp(prefix='setup-', suffix='.txt', dir=logs)
            with os.fdopen(fd, 'w') as handle:
                handle.write(report)
            outcome += '\nDiagnostics saved. Share this report:\n'+name
        except (OSError, ValueError):
            outcome += '\nCould not save diagnostics. Copy the report below instead.\n'
            outcome += 'BEGIN CHEMDRAW DIAGNOSTICS\n'+report+'END CHEMDRAW DIAGNOSTICS'
        return 1
    finally:
        screen.__exit__()
        if session is not None: session.close()
        if outcome: print(outcome, file=stream, flush=True)
