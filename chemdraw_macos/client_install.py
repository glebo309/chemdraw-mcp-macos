"""Explicit local client registration, with backups and no shell/PATH dependency."""
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import tempfile
import tomllib

SERVER_NAME = 'glecko_chemdraw'


def _regular(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Refusing symbolic links in client configuration paths')
    if path.exists() and not path.is_file():
        raise ValueError('Client configuration must be a regular file')


def _atomic(path, data, mode=0o600):
    _regular(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.chemdraw-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            os.fchmod(handle.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def connect_clients(clients, runtime, *, home=None, args=None):
    """Plan every selected config first; preserve other servers and original bytes."""
    if not isinstance(clients, list) or not clients:
        raise ValueError('Select at least one assistant')
    if any(c not in ('claude', 'codex', 'bundle') for c in clients) or len(set(clients)) != len(clients):
        raise ValueError('Unsupported assistant selection')
    home = Path(home) if home is not None else Path.home()
    command = str(Path(runtime).absolute())
    arguments = ['--desktop-serve'] if args is None else args
    if arguments not in (['--desktop-serve'], ['--profile', 'full']):
        raise ValueError('Unsupported server launch arguments')
    entry = {'command': command, 'args': arguments}
    plans, bundle_clients = [], []
    for client in clients:
        if client == 'bundle':
            continue  # The MCPB-capable host registered the bundle itself.
        manifest = home/'Library/Application Support/Claude/Claude Extensions/local.mcpb.glenn-bojanov.chemdraw-macos/manifest.json'
        if client == 'claude' and manifest.is_file():
            try:
                if json.loads(manifest.read_text()).get('name') == 'chemdraw-macos':
                    bundle_clients.append('claude')
                    continue
            except (ValueError, AttributeError):
                raise ValueError('Existing Claude extension metadata could not be checked')
        path = (home/'Library/Application Support/Claude/claude_desktop_config.json' if client == 'claude'
                else home/'.codex/config.toml')
        _regular(path)
        before = path.read_bytes() if path.exists() else None
        text = (before or b'').decode('utf-8')
        try:
            data = (json.loads(text or '{}') if client == 'claude' else tomllib.loads(text))
            key = 'mcpServers' if client == 'claude' else 'mcp_servers'
            servers = data.get(key, {})
            if not isinstance(servers, dict):
                raise ValueError('Server settings must be an object')
            wanted = entry if client == 'claude' else {**entry, 'tool_timeout_sec': 300}
            existing = servers.get(SERVER_NAME)
            if existing == wanted:
                continue
            if existing is not None:
                raise ValueError(f'{SERVER_NAME} is already configured differently in {client}. No settings changed.')
            if client == 'claude':
                data.setdefault(key, {})[SERVER_NAME] = wanted
                after = json.dumps(data, indent=2)+'\n'
            else:
                # Append only: preserve comments, order and all unrelated settings byte-for-byte.
                after = text + '\n\n# ChemDraw MCP setup\n' + f'[mcp_servers.{SERVER_NAME}]\n'
                after += f'command = {json.dumps(command)}\nargs = {json.dumps(arguments)}\ntool_timeout_sec = 300\n'
                tomllib.loads(after)  # Reject incompatible inline/sealed TOML tables before any write.
            plans.append((path, before, after.encode('utf-8')))
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, AttributeError) as exc:
            raise ValueError(f'{client} settings could not be safely read. No settings changed.') from exc
    backups, written = [], []
    try:
        for path, before, after in plans:
            _regular(path)
            if (path.read_bytes() if path.exists() else None) != before:
                raise ValueError('Assistant settings changed during setup. Please try setup again.')
            if before is not None:
                fd, name = tempfile.mkstemp(prefix=path.name+'.before-chemdraw-', dir=path.parent)
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(before)
                backups.append(name)
            _atomic(path, after)
            written.append((path, before, after))
    except Exception:
        for path, before, after in reversed(written):
            if path.read_bytes() == after:
                if before is None:
                    path.unlink()
                else:
                    _atomic(path, before)
        raise
    return {'clients': clients, 'bundle_clients': bundle_clients,
            'backups': backups, 'command': command, 'args': entry['args']}


def install_shared_app(source, *, home=None):
    """Keep immutable versioned copies; never remove an earlier installation."""
    home = Path(home) if home is not None else Path.home()
    source = Path(source).resolve()
    info = plistlib.loads((source/'Contents/Info.plist').read_bytes())
    version = str(info.get('CFBundleVersion', ''))
    if info.get('CFBundleIdentifier') != 'org.glebo309.chemdraw-mcp.setup' or not re.fullmatch(r'[0-9.]+', version):
        raise ValueError('Not a recognized ChemDraw MCP application')
    parent = home/'Library/Application Support/ChemDraw MCP/versions'/version
    target = parent/'ChemDraw MCP.app'
    if target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise ValueError('Refusing symbolic links in installation path')
    if target.exists():
        if (target/'Contents/Info.plist').read_bytes() != (source/'Contents/Info.plist').read_bytes():
            raise ValueError('An installation with this version already exists but differs')
        return target
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix='.install-', dir=parent))
    try:
        shutil.copytree(source, staging/target.name, symlinks=False)
        os.rename(staging/target.name, target)
    finally:
        shutil.rmtree(staging)
    return target


def install_and_connect(source_app, clients, *, home=None):
    import shlex
    home = Path(home) if home is not None else Path.home()
    app = install_shared_app(source_app, home=home)
    runtime = app/'Contents/Resources/backend/chemdraw-runtime'
    launcher = home/'Library/Application Support/ChemDraw MCP/bin/chemdraw-mcp'
    # Clients always reference this one path, independent of download/client folders.
    script = '#!/bin/sh\nexec '+shlex.quote(str(runtime))+' "$@"\n'
    _regular(launcher)
    previous = launcher.read_bytes() if launcher.exists() else None
    _atomic(launcher, script.encode(), 0o700)
    try:
        result = connect_clients(clients, launcher, home=home)
    except Exception:
        if previous is None:
            launcher.unlink()
        else:
            _atomic(launcher, previous, 0o700)
        raise
    return {**result, 'installed_app': str(app)}
