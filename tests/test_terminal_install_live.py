"""Acceptance of installed CLI outside the checkout, with a real terminal."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import time

import pytest

CLI = os.environ.get('CHEMDRAW_INSTALLED_CLI')
pytestmark = pytest.mark.skipif(not CLI or os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST') != '1',
                                reason='Needs installed CLI and explicit native opt-in')


def test_installed_terminal_animation_draws_only_in_owned_document(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.addin import get_backend
    from test_api_drawing import EMPTY
    bridge = Bridge()
    baseline = bridge.documents()['documents']
    target = bridge.create(EMPTY)['document']['document_id']
    out = tmp_path/'first-run'
    master, slave = pty.openpty()
    process = subprocess.Popen([CLI, 'first-run', '--output', str(out)], cwd='/tmp',
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, 'TERM': 'xterm-256color', 'COLUMNS': '100', 'LINES': '32'})
    os.close(slave)
    chunks = []
    deadline = time.monotonic()+90
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], .2)[0]:
                try: data = os.read(master, 65536)
                except OSError: break
                if not data: break
                chunks.append(data)
            elif process.poll() is not None:
                break
        assert process.wait(timeout=3) == 0, b''.join(chunks)[-3000:]
        terminal = b''.join(chunks)
        (tmp_path/'terminal.ansi').write_bytes(terminal)
        assert b'\x1b[?1049h' in terminal and b'\x1b[?1049l' in terminal
        assert b'38;5;218m' in terminal
        report = json.loads((out/'first-run.json').read_text())
        assert report['status'] == 'checks_passed'
        assert report['document']['document_id'] == target
        assert report['document']['molecule_count'] == 2
        assert not list(out.rglob('*.html'))
        current = bridge.documents()['documents']
        assert {d['document_id'] for d in current} == {target, *[d['document_id'] for d in baseline]}
        backend = get_backend(bridge)
        try:
            assert backend.read(target)['document']['molecule_count'] == 2
        finally:
            backend.close()
        bridge.close(target)
        assert bridge.documents()['documents'] == baseline
    finally:
        os.close(master)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
