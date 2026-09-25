import json
from pathlib import Path
import subprocess

import pytest


def test_checkout_launchers_follow_source_without_reinstall_and_backup_old(tmp_path):
    from chemdraw_macos.client_install import connect_checkout
    checkout=tmp_path/'source with spaces';checkout.mkdir()
    (checkout/'pyproject.toml').write_text('[project]\nname="chemdraw-mcp-macos"\n')
    (checkout/'uv.lock').write_text('fixture')
    (checkout/'chemdraw_macos').mkdir()
    (checkout/'chemdraw_macos/development.py').write_text('')
    uv=tmp_path/'fake uv'
    uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');uv.chmod(0o700)
    home=tmp_path/'user';bin=home/'Library/Application Support/ChemDraw MCP/bin';bin.mkdir(parents=True)
    (bin/'chemdraw-mcp').write_text('old runtime')
    result=connect_checkout(checkout,uv=uv,home=home)
    assert any(Path(p).read_text()=='old runtime' for p in result['backups'])
    assert not (home/'.codex/config.toml').exists()
    for name,args in [('chemdraw-mcp',['--desktop-serve']),('chemdraw-mac',['doctor','--no-connect']),('chemdraw-mcp-macos',[])]:
        output=subprocess.check_output([bin/name,*args],text=True).splitlines()
        assert output[:8]==['run','--quiet','--locked','--extra','chemistry','--project',str(checkout),'python']
        assert output[8:10]==['-m','chemdraw_macos.development']
    assert connect_checkout(checkout,uv=uv,home=home)['backups']==[]


def test_checkout_entry_does_not_redirect_to_old_bundle(monkeypatch):
    from chemdraw_macos import development,server,desktop_setup
    calls=[]
    monkeypatch.setenv('CHEMDRAW_APP','test-only previous app')
    monkeypatch.delenv('CHEMDRAW_DESKTOP_EXTENSION',raising=False)
    monkeypatch.setattr(desktop_setup,'read_settings',lambda:{'installed_app':'old app','chemdraw_app':'chosen app'})
    monkeypatch.setattr(desktop_setup,'validate_app',lambda x:x)
    monkeypatch.setattr(server,'main',lambda args:calls.append(args))
    development.main(['--desktop-serve'])
    assert calls==[['--profile','full']]


def test_checkout_refuses_unrelated_source(tmp_path):
    from chemdraw_macos.client_install import connect_checkout
    with pytest.raises(ValueError):connect_checkout(tmp_path,uv='/usr/bin/true',home=tmp_path/'user')
    assert not (tmp_path/'user').exists()


def test_doctor_exposes_loaded_checkout_and_detects_changed_code(monkeypatch):
    from chemdraw_macos import diagnostics
    monkeypatch.setattr(diagnostics,'_source_digest',lambda:'new source')
    monkeypatch.setattr(diagnostics,'_LOADED_SOURCE_DIGEST','loaded source')
    result=diagnostics.doctor(connect=False)['runtime']
    assert result['mode']=='checkout'
    assert result['loaded_source_digest']=='loaded source'
    assert result['restart_required'] is True
    assert result['source_directory']==str(Path(diagnostics.__file__).resolve().parent.parent)
