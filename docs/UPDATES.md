# Updating ChemDraw MCP

## Terminal installation

For a persistent `uv tool` installation tracking the development branch, close
the clients using that server, then explicitly reinstall from the current branch:

```sh
uv tool install --force --refresh-package chemdraw-mcp-macos \
  'chemdraw-mcp-macos[chemistry] @ git+https://github.com/glebo309/chemdraw-mcp-macos@main'
chemdraw-mac doctor
```

For repeatable versions, substitute a published tag or reviewed commit for
`main`. Returning to a previous reviewed revision uses the same command with
that revision. The configured tool executable path stays stable. Restart the
assistant after updating; running Python processes keep the old loaded code.
This is package replacement, not a tested transactional rollback service.

For a clean source checkout:

```sh
git pull --ff-only
uv sync --locked --extra chemistry
uv run --locked --extra chemistry chemdraw-mac doctor
```

Do not discard local modifications to make a pull succeed. Keep add-in
credentials and client settings; ordinary package updates do not require a new
private credential or deleting the add-in. Follow release-specific migration
instructions when provided.

## Graphical installation

There is no automatic update checker yet. Obtain a newer experimental DMG from
the project's Releases page, close assistants using the server, and run its
setup. The helper stores versioned app copies and uses a stable launcher for
selected client settings. A same-name entry pointing elsewhere is refused.
Keep the old download until the new version passes its connection test.

Versioned storage is already implemented. A complete graphical upgrade and
rollback acceptance test across released versions is still pending; retained
versions alone are not a verified one-click rollback feature. Do not delete the
ChemDraw add-in or other assistants' configurations to force an update.

The planned update UI will show installed/available versions, preserve private
credentials and client settings, replace the shared runtime safely, and explain
required client restarts. It will need a tested recovery path before being
advertised as automatic updating. [Roadmap](ROADMAP.md)
