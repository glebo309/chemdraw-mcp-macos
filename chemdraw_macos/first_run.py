"""One-call native smoke test, with optional terminal-only progress."""
from contextlib import nullcontext
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid

from .batch import NativeUncertain
from .core import Bridge
from .diagnostics import doctor
from .draw import draw_structures
from .native_lock import NativeBusy


DEMO_STRUCTURES = (
    {'compound_id': '1', 'label': 'Caffeine', 'smiles': 'Cn1c(=O)c2c(ncn2C)n(C)c1=O'},
    {'compound_id': '2', 'label': 'Aspirin', 'smiles': 'CC(=O)Oc1ccccc1C(=O)O'},
)


class FirstRunError(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report, ensure_ascii=True))


def run_first_run(output_dir=None, *, bridge_factory=None, progress=None):
    """Check locally, draw a fixed fixture once, retain the final working copy.

    No browser, terminal output, package installation or client configuration
    mutation happens here. CLI and MCP share this exact native workflow.
    """
    stage = 'installation'
    environment = None
    out = None
    def phase(name, label):
        nonlocal stage
        stage = name
        if progress is not None:
            progress(name, label)
    try:
        phase('installation', 'Checking installation')
        if output_dir is not None:
            out = Path(output_dir).expanduser()
            if not out.is_absolute() or not out.parent.is_dir():
                raise ValueError('Output must be a new absolute directory with an existing parent')
            if out.exists() or out.is_symlink():
                raise FileExistsError('Output already exists; choose a new directory')
        environment = doctor(connect=False)
        if environment['status'] not in ('ready', 'basic_only'):
            raise RuntimeError(environment.get('error', 'ChemDraw installation unavailable'))
        if not environment.get('chemistry_validator_available'):
            raise RuntimeError('RDKit is missing. From the checkout run: uv sync --locked --extra chemistry')
        if not environment.get('rasterizer_available'):
            raise RuntimeError('SVG rasterizer is missing. From the checkout run: uv sync --locked --extra chemistry')
        b = bridge_factory() if bridge_factory is not None else Bridge(app_path=Path(environment['app']))
        phase('connection', 'Connecting to ChemDraw')
        with getattr(b, 'lock', nullcontext()):
            b.documents()
            environment['native_connection'] = 'responding'
            if out is None:
                parent = Path(b.workspace).expanduser().absolute() / 'first-runs'
                parent.mkdir(parents=True, exist_ok=True)
                out = parent / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
            phase('drawing', 'Drawing + native validation')
            drawing = draw_structures(b, [dict(s) for s in DEMO_STRUCTURES], str(out),
                                      columns=2, pixels=2400, preset='house')
            phase('exports', 'Checking editable and preview files')
            audit = drawing['audit']
            checks = audit.get('checks', {})
            if audit.get('status') != 'checks_passed' or not checks or any(v is not True for v in checks.values()):
                raise ValueError('Native drawing checks did not all pass; inspect the drawing audit')
            for name in ('cdxml', 'svg', 'png'):
                _require_artifact(drawing['artifacts'][name], out)
            _require_artifact(drawing['review'], out)
            result = {'status': 'checks_passed', 'environment': environment,
                      'output_dir': str(out), 'report': str(out / 'first-run.json'),
                      'document': drawing['document'], 'review': drawing['review'],
                      'artifacts': drawing['artifacts'], 'checks': checks,
                      'audit': str(out / 'audit.json'), 'visual_review': 'required',
                      'scope': 'Fixed caffeine/aspirin smoke test, not general compatibility certification.'}
            with (out / 'first-run.json').open('x') as handle:
                json.dump(result, handle, indent=2, ensure_ascii=True)
            return result
    except (Exception, KeyboardInterrupt) as exc:
        status = ('interrupted' if isinstance(exc, KeyboardInterrupt) else 'busy' if isinstance(exc, NativeBusy)
                  else 'uncertain' if isinstance(exc, NativeUncertain) else 'failed')
        if status in ('uncertain', 'interrupted'):
            hint = 'Inspect ChemDraw and retained audits/backups before another write. No retry or extra close was attempted.'
        elif status == 'busy':
            hint = 'Another cooperating client is using ChemDraw. Wait for it to finish; no automatic retry was attempted.'
        elif stage == 'installation':
            hint = 'Check the reported path/dependency. Install and activate your own ChemDraw; use CHEMDRAW_APP for an explicit app path.'
        elif stage == 'connection':
            hint = 'Open and activate ChemDraw, dismiss its dialogs, and check Automation permission for the launching app. No permission was changed.'
        else:
            hint = 'Inspect the native error and retained output. Failed or partial files are diagnostic, not an accepted drawing.'
        message = 'Interrupted; a dispatched native operation may still have completed.' if status == 'interrupted' else str(exc)
        raise FirstRunError({'status': status, 'stage': stage, 'error': message,
                             'help': hint, 'output_dir': str(out) if out else None,
                             'environment': environment}) from exc


def _require_artifact(path, output_dir):
    p = Path(path)
    if not p.is_absolute() or not p.resolve().is_relative_to(output_dir.resolve()) or not p.is_file() or p.stat().st_size == 0:
        raise ValueError('Missing, empty or out-of-bundle artifact: ' + str(p))


def ring_frame(index, label):
    rows = [list('   o---o   '), list('  /     \\  '), list(' o       o '),
            list('  \\     /  '), list('   o---o   ')]
    row, column = ((0, 3), (0, 7), (2, 9), (4, 7), (4, 3), (2, 1))[index % 6]
    rows[row][column] = '*'
    lines = [''.join(r) for r in rows]
    lines[2] += '  ' + _terminal_text(label)[:52]
    return '\n'.join(lines)


def _terminal_text(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


class TerminalProgress:
    """Animation only; all native work remains in the calling thread."""
    def __init__(self, stream, enabled=False):
        self.stream = stream
        self.enabled = enabled
        self.label = 'Starting'
        self.stop = threading.Event()
        self.guard = threading.Lock()
        self.thread = None

    def __enter__(self):
        if self.enabled:
            self.stream.write('\n' * 5)
            self.stream.flush()
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
        return self

    def update(self, stage, label):
        with self.guard:
            self.label = label

    def _animate(self):
        index = 0
        while not self.stop.is_set():
            with self.guard:
                frame = ring_frame(index, self.label)
                self.stream.write('\x1b[5A' + ''.join('\r\x1b[2K' + line + '\n' for line in frame.splitlines()))
                self.stream.flush()
            index += 1
            self.stop.wait(.16)

    def __exit__(self, *exc):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
            self.stream.write('\x1b[5A' + '\r\x1b[2K\n' * 5)
            self.stream.flush()


def open_review(path):
    p = Path(path)
    if not p.is_absolute() or not p.is_file():
        raise ValueError('Review must be an existing absolute file')
    subprocess.run(['/usr/bin/open', str(p)], check=True, capture_output=True, timeout=10)


def run_cli(args):
    machine = args.json or not sys.stdout.isatty()
    interactive = not machine and sys.stderr.isatty()
    animate = (interactive and not args.no_animation and os.environ.get('TERM') != 'dumb'
               and not os.environ.get('CI') and shutil.get_terminal_size().columns >= 72)
    try:
        with TerminalProgress(sys.stderr, enabled=animate) as progress:
            def update(stage, label):
                if animate:
                    progress.update(stage, label)
                elif interactive:
                    print(label + '...', file=sys.stderr, flush=True)
            result = run_first_run(args.output, progress=update)
    except FirstRunError as exc:
        result = exc.report
    except KeyboardInterrupt:
        result = {'status': 'interrupted', 'stage': 'unknown',
                  'error': 'First run interrupted; a native operation may still have completed.',
                  'help': 'Inspect ChemDraw and workspace backups before another write. No retry or extra close attempted.'}
    passed = result['status'] == 'checks_passed'
    if passed and interactive and not args.no_open:
        try:
            open_review(result['review'])
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print('Drawing passed; browser launch failed. Open the review link below. ' + _terminal_text(exc), file=sys.stderr)
    if machine:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    elif passed:
        print('ChemDraw is ready. Native smoke test passed.\n')
        print('Review:   ' + _terminal_text(result['review']))
        print('Editable: ' + _terminal_text(result['artifacts']['cdxml']))
        print('Report:   ' + _terminal_text(result['report']))
        print('\nThe final drawing stays open in ChemDraw. Please inspect the visual result.')
    else:
        print('First run ' + result['status'] + ' at ' + result['stage'] + ': ' + _terminal_text(result['error']), file=sys.stderr)
        print(_terminal_text(result['help']), file=sys.stderr)
        if result.get('output_dir'):
            print('Diagnostic output: ' + _terminal_text(result['output_dir']), file=sys.stderr)
    return 0 if passed else 130 if result['status'] == 'interrupted' else 1
