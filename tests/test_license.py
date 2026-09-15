"""Keep the public licensing declaration and packaged notices consistent."""
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_project_license_is_explicit_agpl_v3_only():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project.get('license') == 'AGPL-3.0-only'
    assert {'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md', 'licenses/*.txt'} <= set(project['license-files'])
    provenance = json.loads((ROOT / 'upstream-sources.json').read_text())
    assert provenance['own_project_public_license'] == 'AGPL-3.0-only'


def test_full_license_and_project_notice_are_present():
    text = (ROOT / 'LICENSE').read_text()
    assert 'GNU AFFERO GENERAL PUBLIC LICENSE' in text
    assert '13. Remote Network Interaction' in text
    assert 'How to Apply These Terms to Your New Programs' in text
    notice = (ROOT / 'NOTICE').read_text()
    assert 'Copyright (c) 2026 Glenn Bojanov' in notice
    assert 'AGPL-3.0-only' in notice
    assert 'WITHOUT ANY WARRANTY' in notice


def test_upstream_mit_notice_is_retained():
    text = (ROOT / 'licenses/live-chemdraw-mcp.txt').read_text()
    assert 'Copyright (c) 2026 Michael Leitch' in text
    assert 'Permission is hereby granted' in text
