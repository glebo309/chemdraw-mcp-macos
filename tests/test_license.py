"""Keep the public licensing declaration and packaged notices consistent."""
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_project_license_is_explicit_mit():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project.get('license') == 'MIT'
    assert {'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md', 'licenses/*.txt'} <= set(project['license-files'])
    provenance = json.loads((ROOT / 'upstream-sources.json').read_text())
    assert provenance['own_project_public_license'] == 'MIT'


def test_full_license_and_project_notice_are_present():
    text = (ROOT / 'LICENSE').read_text()
    assert text.startswith('MIT License')
    assert 'Copyright (c) 2026 Glenn Bojanov' in text
    assert 'Permission is hereby granted' in text
    notice = (ROOT / 'NOTICE').read_text()
    assert 'Copyright (c) 2026 Glenn Bojanov' in notice
    assert 'SPDX-License-Identifier: MIT' in notice
    assert 'WITHOUT WARRANTY' in notice


def test_upstream_mit_notice_is_retained():
    text = (ROOT / 'licenses/live-chemdraw-mcp.txt').read_text()
    assert 'Copyright (c) 2026 Michael Leitch' in text
    assert 'Permission is hereby granted' in text
