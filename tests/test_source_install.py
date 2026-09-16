"""The Git checkout entry point installs locked dependencies, then starts setup."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_git_installer_launches_setup_and_forwards_client_choice(tmp_path):
    commands = tmp_path/'commands'
    executable = tmp_path/'uv'
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$INSTALL_TEST_LOG"\n')
    executable.chmod(0o755)
    result = subprocess.run(['/bin/sh', str(ROOT/'install.sh'), '--client', 'codex'],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, 'PATH': str(tmp_path)+':/usr/bin:/bin', 'INSTALL_TEST_LOG': str(commands)})
    assert result.returncode == 0, result.stderr
    assert commands.read_text().splitlines() == [
        'sync --locked --extra chemistry',
        'run --locked --extra chemistry chemdraw-mac setup --client codex']


def test_git_installer_does_not_start_setup_after_failed_dependency_install(tmp_path):
    executable = tmp_path/'uv'
    executable.write_text('#!/bin/sh\n[ "$1" = sync ] && exit 17\nexit 99\n')
    executable.chmod(0o755)
    result = subprocess.run(['/bin/sh', str(ROOT/'install.sh')], cwd=tmp_path,
        env={**os.environ, 'PATH': str(tmp_path)+':/usr/bin:/bin'})
    assert result.returncode == 17
