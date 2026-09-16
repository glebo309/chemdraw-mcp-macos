# Terminal installation

Already used the graphical installer? Starting with rc13,
Finish also installs the terminal commands. Open a new macOS zsh Terminal window
and run `chemdraw-mac --help` or `chemdraw-mac first-run`. You do not need Git,
Python or uv for that route. It uses the same installed runtime, not a second
installation. See [graphical setup](DESKTOP_INSTALLER.md) for PATH details.
Earlier builds, including rc12, do not include these terminal launchers.

For Mac users who prefer the terminal. This route does not launch the graphical
installer. It uses the same native bridge, checks and molecular animation.

You need your own installed, activated ChemDraw, a logged-in macOS desktop,
[uv](https://docs.astral.sh/uv/getting-started/installation/), and Git for a Git
source URL. The tested native combination is in [compatibility](COMPATIBILITY.md).

## 1. Install the command-line tools

### Recommended Git route

```sh
git clone https://github.com/glebo309/chemdraw-mcp-macos.git
cd chemdraw-mcp-macos
./install.sh
```

The script installs the locked dependencies with uv and automatically launches
the themed setup. It accepts setup options, for example
`./install.sh --client claude --client codex`. Dependency installation is uv's
own progress display; the molecular screen starts when setup launches.
This route does not add commands to your shell PATH. Inside the checkout, use:

```sh
uv run --locked --extra chemistry chemdraw-mac first-run
```

### Alternative: a command on PATH

For users who prefer a persistent uv tool installation:

```sh
uv tool install 'chemdraw-mcp-macos[chemistry] @ git+https://github.com/glebo309/chemdraw-mcp-macos@main'
```

`uv` creates a persistent isolated environment and installs `chemdraw-mac` and
`chemdraw-mcp-macos`. Its own progress covers dependency installation; our
molecular animation begins when setup runs. If `uv` says its tool directory is
not on PATH, follow its displayed instruction or run `uv tool update-shell` and
open a new terminal. No `sudo` is needed for this project.

Use a published tag or reviewed commit instead of `main` for repeatable source
selection. A Git tool install resolves compatible dependencies from package
metadata. To use the repository lock instead:

```sh
git clone https://github.com/glebo309/chemdraw-mcp-macos.git
cd chemdraw-mcp-macos
uv sync --locked --extra chemistry
uv run --locked --extra chemistry chemdraw-mac setup
```

The remaining examples use the installed command. In a checkout, prefix it with
`uv run --locked --extra chemistry`.

## 2. Connect ChemDraw

```sh
chemdraw-mac setup
```

The terminal switches to the pink/lavender theme as soon as setup starts.
Molecules keep animating during checks and while you follow the instructions.
The final screen stays until you press Return. On exit or Ctrl-C, your previous
terminal screen, colours and cursor are restored; no Terminal profile is changed.
Small windows paginate instructions instead of silently dropping them.

Setup checks the software and creates this Mac's private add-in installer in a
uniquely named `ChemDraw-MCP-Setup-...` folder inside Downloads:

1. Open ChemDraw > Add-ins > Add-in Manager.
2. If **ChemDraw MCP Native API** is listed, enable it. Otherwise click **+ > Add
   from file**, open the displayed setup folder in Downloads, and select
   **ChemDraw MCP Native API.chemdrawaddin**.
3. Open a ChemDraw document, then press Return in the terminal.

Success reads **Document read: PASS**. Setup reads the document without adding
structures. It never launches the graphical helper. Permission prompts and
ChemDraw's Add-in Manager still belong to macOS/ChemDraw.

The `.chemdrawaddin` archive contains a private local credential. Do not share or
commit it. ChemDraw installs its own copy; after setup passes, you can delete the
Downloads setup folder. Re-running setup uses a new folder and retains existing
connection credentials. The archive basename stays fixed because ChemDraw uses
it as the installed add-in folder name. Older suffix-named installations are
recognized only when their metadata and local connection key match this setup.
It does not overwrite older Downloads files.

### Optional client registration

```sh
chemdraw-mac setup --client codex
chemdraw-mac setup --client claude --client codex
```

Only explicitly selected clients are registered, after the live read passes.
Their entries use the installed server's absolute path, without invoking `uv`
or downloading packages at client startup. Other settings are preserved, changed
files receive private backups, and a conflicting existing server entry is
refused. An existing Claude bundle registration is retained rather than duplicated.
Restart configured clients afterwards. Setup without `--client` edits no client
settings and prints the executable/arguments for another local stdio MCP client.

If you already installed the graphical route, you do not need this second route.
Do not overwrite its existing client entry to switch installations casually.
Only one running MCP server can own the native add-in connection at a time.

## 3. Try the animation and a drawing

Open a **blank** ChemDraw document, then run:

```sh
chemdraw-mac first-run
```

This appends the fixed caffeine/aspirin example, checks the native result, and
leaves it editable in ChemDraw. It reports the output files. Existing content
is preserved, but the active document receives the example. For read-only
verification, use `chemdraw-mac doctor` instead.

Animation requires an interactive terminal at least 72 columns wide with ANSI
color support. Use `--no-animation` for plain output. `first-run --json` is for
scripts. Setup deliberately requires an interactive terminal so it cannot skip
the manual enable step silently.

## Updates and troubleshooting

[Update guidance](UPDATES.md) distinguishes terminal installs from the bundled
Mac app. Do not delete working add-in credentials when updating Python code.

- **Busy:** disconnect the other assistant's ChemDraw server, then rerun setup.
  No process is killed automatically.
- **No document:** open a blank drawing and rerun setup.
- **Entry absent after restart:** check ChemDraw Preferences > Directories as
  described in [add-in recovery](DESKTOP_ADDIN.md).
- **Registration conflict:** inspect the existing `glecko_chemdraw` client entry.
  Setup preserves it rather than silently choosing a different runtime.
- **Automation denied:** grant access to the launching terminal/client in
  System Settings > Privacy & Security > Automation.
- **Uncertain drawing:** inspect ChemDraw and the retained audit before another
  write. Do not blindly repeat a timed-out drawing request.
