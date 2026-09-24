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

No uninstall is needed for an ordinary update from the graphical installer.

1. Save your ChemDraw work, quit ChemDraw, and quit assistants using its MCP connection.
2. Download and open the new DMG, then open **ChemDraw MCP** inside it.
3. Select your installed ChemDraw and assistants. Setup refreshes the existing
   add-in in place, retaining its local key. Do not import another copy when the
   add-in is already listed.
4. Open a drawing, test the connection, then choose **Finish setup**. Restart
   your assistants. New terminal commands use the same updated runtime.

The helper stores versioned app copies and switches stable launchers after the
connection test. Existing assistant settings are not duplicated, and previous
app versions are retained. A same-name server entry pointing to a different,
manually configured installation is deliberately refused rather than overwritten.
Setup saves diagnostic reports automatically; **Show saved report** locates one
after a failure. Keep the old download until the new version passes its test.

Regression tests exercise repeated upgrades, stable client and terminal paths,
preserved credentials and suffixed add-in folders. Independent-Mac acceptance
is still pending. Retained versions are not a one-click rollback service.
Do not delete the ChemDraw add-in or assistant configurations to force an update.

There is no automatic update checker yet. The planned update UI will show installed/available versions, preserve private
credentials and client settings, replace the shared runtime safely, and explain
required client restarts. It will need a tested recovery path before being
advertised as automatic updating. [Roadmap](ROADMAP.md)
