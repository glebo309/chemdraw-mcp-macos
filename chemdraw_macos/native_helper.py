"""One long-lived osascript process that keeps the native script compiled.

Starting osascript and loading the Foundation framework cost about 0.26 s per
native call. The helper pays that once; a call then costs only ChemDraw's own
work (about 8 ms per question asked of ChemDraw). Semantics are those of the
one-shot path: a call is sent once, a timeout leaves its outcome uncertain and
is never retried, and the next call starts a fresh helper.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time

_SOURCE = Path(__file__).with_name('native_helper.js')
_helpers: dict[str, 'NativeHelper'] = {}
_guard = threading.Lock()


def wrap(script: str) -> str:
    """Rename the run handler and catch its errors, so they return as text."""
    start, end = script.index('on run argv'), script.rindex('end run')
    body = script[:start] + 'on cdmcp_run(argv)' + script[start + len('on run argv'):end] \
        + 'end cdmcp_run' + script[end + len('end run'):]
    return body + ('\non run argv\n    try\n        return "R" & cdmcp_run(argv)\n'
                   '    on error msg number num\n        return "E" & num & ":" & msg\n'
                   '    end try\nend run\n')


class NativeHelper:
    def __init__(self, script: str):
        self.script = wrap(script)
        self.process = None
        self._buffer = b''
        self._lock = threading.Lock()

    @property
    def pid(self):
        return self.process.pid if self.process else None

    def _start(self):
        self.process = subprocess.Popen(['/usr/bin/osascript', '-l', 'JavaScript', str(_SOURCE)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, bufsize=0)
        self._buffer = b''
        loaded = self._exchange({'script': self.script}, 30)
        if not loaded.get('ok'):
            self._stop()
            raise RuntimeError('Native helper could not load its script: ' + str(loaded.get('error')))

    def _stop(self):
        if self.process is not None:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.process = None

    def _exchange(self, request: dict, timeout: float) -> dict:
        self.process.stdin.write((json.dumps(request) + '\n').encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        fd = self.process.stdout.fileno()
        with selectors.DefaultSelector() as selector:
            selector.register(fd, selectors.EVENT_READ)
            while b'\n' not in self._buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError()
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    raise EOFError()
                self._buffer += chunk
        line, self._buffer = self._buffer.split(b'\n', 1)
        return json.loads(line)

    def call(self, args: list, timeout: float):
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                self._start()
            try:
                reply = self._exchange({'args': [str(a) for a in args]}, timeout)
            except TimeoutError as exc:
                self._stop()
                raise RuntimeError('ChemDraw automation timed out, possibly due to a dialog. Operation was not '
                                   'retried; its outcome is uncertain. Inspect ChemDraw before retrying.') from exc
            except (EOFError, OSError, ValueError) as exc:
                self._stop()
                raise RuntimeError('Native helper stopped during a ChemDraw call; its outcome is uncertain and '
                                   'it was not retried. Inspect ChemDraw before retrying.') from exc
        if not reply.get('ok'):
            raise RuntimeError('ChemDraw automation failed: ' + str(reply.get('error')))
        text = reply['result']
        if text.startswith('E'):
            number, _, message = text[1:].partition(':')
            raise RuntimeError(f'ChemDraw automation failed: {message} ({number})')
        try:
            return json.loads(text[1:])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'Invalid native response: {text[1:501]}') from exc

    def close(self):
        with self._lock:
            if self.process is not None and self.process.stdin:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            self._stop()


def helper_for(script: str) -> NativeHelper:
    with _guard:
        helper = _helpers.get(script)
        if helper is None:
            helper = _helpers[script] = NativeHelper(script)
        return helper


@atexit.register
def _close_all():
    for helper in list(_helpers.values()):
        helper.close()
