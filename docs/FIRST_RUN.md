# First native drawing

`first-run` and MCP `chemdraw_first_run` run the same fixed smoke test. They do not modify client settings, install ChemDraw, activate a licence or change macOS permissions.

## One command

New installation? Complete [terminal setup](TERMINAL_INSTALL.md) first.
`chemdraw-mac setup` prepares the private add-in and verifies a read without
drawing. `first-run` below is the optional drawing demonstration.

Prerequisites: macOS, your own installed and activated ChemDraw, and [uv](https://docs.astral.sh/uv/getting-started/installation/). The direct Git command also needs Git and network access to download source and dependencies.

Without a checkout:

```sh
uvx --from 'chemdraw-mcp-macos[chemistry] @ git+https://github.com/glebo309/chemdraw-mcp-macos@main' chemdraw-mac first-run
```

This executes the public experimental development branch, not a stable package release. Replace `main` with a reviewed commit for source pinning. uv resolves a tool environment from package metadata; this route does not enforce the repository's dependency lock. No PyPI publication is needed. See [uv tool environments and Git sources](https://docs.astral.sh/uv/guides/tools/).

From an existing checkout, use the committed dependency lock:

```sh
uv run --locked --extra chemistry chemdraw-mac first-run
```

uv handles dependency installation first, showing its own progress. Once Python starts, an interactive terminal cycles through bundled silhouettes from native ChemDraw exports with the tagline “Natural language → ChemDraw.” Structures stay geometrically fixed while a gold reveal passes across them, with pink and lavender accents matching graphical setup. Names are hidden. The continuous bar uses weighted workflow phases, approaches the current phase ceiling while work is pending, and reaches completion only after all native checks pass. It is not an elapsed-time estimate or a download percentage. The actual phase is always shown beneath it.

The sequence is caffeine, azulene, saccharin, 5-MeO-DMT, urea, aspirin, vanillin, alizarin and dopamine. These are precomputed decorative silhouettes, not additional compounds drawn during setup. No name lookup, image library, installed font or extra network request is needed to animate them. Provenance and native SVG hashes are in `chemdraw_macos/data/welcome.json`. Unicode braille cells represent rasterized native strokes; they are not the scientific output.

The animation runs only during interactive `first-run`, never ordinary drawing commands or MCP calls. It stops with the actual workflow, restores the cursor/screen on failure, and never adds a minimum artificial delay. Re-running `first-run` deliberately replays onboarding and creates another smoke-test drawing.

## What happens

1. Check application discovery, RDKit and the SVG rasterizer without contacting ChemDraw.
2. Acquire the cooperative native-operation lock and check the application connection.
3. Append the fixed caffeine/aspirin graphs once to the active canvas through the desktop API, with house style, grid and validation. Open a blank document first for an isolated test.
4. Verify the drawing audit and editable CDXML, native SVG and PNG files inside the output bundle.
5. Save `first-run.json`, report the paths and leave the drawing open in ChemDraw. No HTML review is generated or required, and no browser is launched.

The graphs are explicit software-test fixtures, not online name-resolution results. RDKit validates and supplies editable coordinates; ChemDraw renders the single API addition. PNG is rasterized from that native SVG. Passing this fixture does not certify arbitrary chemistry, another application version or a human visual review. Install and enable the locally generated desktop add-in first, following [the add-in guide](DESKTOP_ADDIN.md).

Default output is a unique child of `~/ChemDraw-MCP-Output/first-runs/`, or of the workspace selected by `CHEMDRAW_MCP_WORKSPACE`. Supply `--output /absolute/existing/parent/new-folder` for another destination. An existing destination is rejected before native work. Source snapshots and audit data remain local; do not attach unreviewed bundles containing private drawings to public issues.

## Terminal and automation

| Option or environment | Behavior |
| --- | --- |
| `--json` | JSON on stdout; no animation or browser launch, including errors |
| Redirected/non-terminal stdout | Same machine-readable mode automatically |
| `--no-open` | Accepted for compatibility; browser launch has been removed |
| `--no-animation` | Plain stage messages in an interactive terminal |
| Narrow terminal, `TERM=dumb` or `CI` | No animation |

Exit status is 0 for passed checks, 1 for failure/busy/uncertain results and 130 for interruption. Errors retain the failing stage and available output path. The combined drawing/validation stage is intentionally not split into fake substeps.

## From an assistant app

Configure the local server once using [desktop client setup](MCP_CLIENTS.md). Then ask:

> Run the ChemDraw first-run check. Draw the built-in example and show me the editable file, native preview and audit.

The tool takes only optional `output_dir`; omitting it creates a unique folder. It returns paths and checks without terminal escape sequences, browser launch or a configuration change. The client decides how to present files. A successful result keeps `visual_review: "required"`. Failures are MCP tool errors whose text includes the structured report.

## If a check fails

- Installation: inspect the reported application/dependency error. From a checkout, `uv sync --locked --extra chemistry` installs the optional chemistry dependencies. Set `CHEMDRAW_APP` to the actual absolute app path if discovery is ambiguous.
- Connection: open and activate ChemDraw, dismiss application dialogs, and check macOS Automation permission for the app that launched this server. Permission granted to a terminal may not cover a desktop client.
- Busy: let the other cooperating client finish. This command does not retry automatically.
- Uncertain or interrupted: inspect ChemDraw and retained audits/backups before another write. An already dispatched operation may have completed. The wrapper does not retry or issue extra close operations.
- Drawing or exports: retain the diagnostic bundle. Partial artifacts are not accepted output. Inspect the exact native error; do not bypass chemistry or ownership checks.

Native evidence is recorded in [project progress](../PROJECT_PROGRESS.md). Another-Mac acceptance remains outstanding.
