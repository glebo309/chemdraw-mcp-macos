# First native drawing

`first-run` and MCP `chemdraw_first_run` run the same fixed smoke test. They do not modify client settings, install ChemDraw, activate a licence or change macOS permissions.

## One command

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

uv handles dependency installation first, showing its own progress. Once Python starts, an ASCII ring animates beside the actual native workflow stage. There is no invented percentage or claim that an uncompleted check has passed.

## What happens

1. Check application discovery, RDKit and the SVG rasterizer without contacting ChemDraw.
2. Acquire the cooperative native-operation lock and check the application connection.
3. Draw the fixed caffeine/aspirin graphs through the existing native import, cleanup, grid and validation workflow.
4. Verify that the drawing audit passed and that editable CDXML, native SVG, PNG and HTML review files exist inside the output bundle.
5. Save `first-run.json`, report the paths and leave the final working drawing open. In an interactive CLI only, open the review in the default browser.

The graphs are explicit software-test fixtures, not online name-resolution results. RDKit validates and supplies coordinate seeds; ChemDraw imports, cleans and renders. PNG is rasterized from that native SVG. Passing this fixture does not certify arbitrary chemistry, another application version or a human visual review.

Default output is a unique child of `~/ChemDraw-MCP-Output/first-runs/`, or of the workspace selected by `CHEMDRAW_MCP_WORKSPACE`. Supply `--output /absolute/existing/parent/new-folder` for another destination. An existing destination is rejected before native work. Source snapshots and audit data remain local; do not attach unreviewed bundles containing private drawings to public issues.

## Terminal and automation

| Option or environment | Behavior |
| --- | --- |
| `--json` | JSON on stdout; no animation or browser launch, including errors |
| Redirected/non-terminal stdout | Same machine-readable mode automatically |
| `--no-open` | Keep interactive output but do not open the browser |
| `--no-animation` | Plain stage messages in an interactive terminal |
| Narrow terminal, `TERM=dumb` or `CI` | No animation |

Exit status is 0 for passed checks, 1 for failure/busy/uncertain results and 130 for interruption. Browser launch failure is a warning, not a failed drawing. Errors retain the failing stage and available output path. The combined drawing/validation stage is intentionally not split into fake substeps.

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
