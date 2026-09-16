# ChemDraw MCP 0.10.0rc3: another-Mac test

This is an experimental test candidate, not a stable release or another-Mac
compatibility certification. It requires a Mac with the user's own licensed,
activated ChemDraw and an MCP client that can launch a local stdio server.
Dependencies are downloaded during installation. No ChemDraw, fonts, proprietary
templates, credentials or virtual environment are distributed in this bundle.

## Install the exact candidate

1. Extract the handoff ZIP. Keep its wheel, source archive and SHA256SUMS together.
2. In Terminal, enter that extracted directory and verify `shasum -a 256 -c SHA256SUMS`.
3. Extract the source archive and enter its directory:

```sh
tar -xzf chemdraw_mcp_macos-0.10.0rc3.tar.gz
cd chemdraw_mcp_macos-0.10.0rc3
uv sync --locked --extra chemistry
uv run --locked --extra chemistry chemdraw-mac doctor --no-connect
```

Install uv first if it is unavailable: https://docs.astral.sh/uv/getting-started/installation/
Use the source installation above for the locked dependency set and acceptance
tests. The wheel is an alternative package artifact, not an additional install
step. Do not transfer the sender's `.venv` or installed add-in directory.

Offline diagnostics should report `local_ready`, the candidate version, macOS,
architecture, ChemDraw build, RDKit version and `cdxml_writer_available: true`.
`shared_drawing_ready: false` is expected until a live API read is tested.
If app discovery is ambiguous, set `CHEMDRAW_APP` to the absolute installed .app
path, including it in the MCP client's environment as well.

## Install this Mac's add-in once

Open and activate ChemDraw, then run:

```sh
uv run --locked --extra chemistry chemdraw-mac addin-connect
```

On a fresh Mac this generates a private `.chemdrawaddin` and reports its path.
In ChemDraw, use Add-ins > Add-in Manager > Add from file to install that package
and enable **ChemDraw MCP Native API**. In Preferences > Directories, ensure the
ChemDraw Items search list includes `~/Library/Application Support/com.revvity.ChemDraw/`.
Resolve macOS Automation prompts deliberately. Do not automate licence activation.

The generated add-in contains a machine-local credential. Do not share it or add
it to the handoff archive. Do not expose this desktop bridge through a public tunnel.

Open a blank ChemDraw document and run:

```sh
uv run --locked --extra chemistry chemdraw-mac doctor
uv run --locked --extra chemistry chemdraw-mac first-run --no-animation
```

Doctor `ready` means required local capabilities and a live read passed; it is not
a write test. First-run should add caffeine and aspirin to that canvas with no
temporary molecule windows. Inspect their appearance in ChemDraw. Output includes
CDXML, SVG, PNG and JSON, no HTML. The CLI releases its connection panel on exit;
the document remains open. A persistent MCP client reuses its connection panel.

## Connect an assistant

Use the absolute executable path printed by:

```sh
uv run --locked --extra chemistry python -c 'import shutil; print(shutil.which("chemdraw-mcp-macos"))'
```

Configure it as the local stdio server command, with arguments `--profile full`.
See `docs/MCP_CLIENTS.md` for JSON/TOML examples. The drawing-only profile lacks
the live-read tools needed for the manual-edit comparison below.

Only one client can own this add-in connection at a time. Fully stop its ChemDraw
MCP server before switching clients or running standalone diagnostics/native tests.
`endpoint_in_use` means another owner, not a missing installation. Restart the
client after changing server code. No add-in reinstall is needed for Python-only
updates. Keep the modeless connection panel open during MCP work.

## Compare clients consistently

Record the exact client app/version and model ID, candidate version, macOS,
architecture, ChemDraw build and RDKit version. Use identical prompts and fresh
test documents. Give every client the same instructions:

> Use the ChemDraw MCP, house style and the shared canvas. Read the live molecular
> graph after my edits; do not identify it from its caption. Keep all additions
> in that document, with labelled, centred and equally spaced structures. Do not
> retry uncertain writes or open a separate final document as a fallback.

Run these cases in order, one client at a time:

1. Draw caffeine in an untitled document. Note elapsed time and any extra windows.
2. Manually change the graph without saving. Leave the old caption in place.
3. Ask the assistant to read and identify the edited graph before adding anything.
4. Ask for ten explicit analogues of that scaffold with labels and common
   orientation. Record the actual structures/tool request, not just the prose.
5. Inspect count, chemistry, orientation, row/column centres, caption baselines,
   bond scale and stroke/font style. Note all additional windows and manual fixes.
6. Repeat a read/addition while another application has OS focus, without switching
   the active document inside ChemDraw. Do not manually edit during a write.
7. Restart the client and ChemDraw, then repeat a simple draw to test add-in discovery.

Separate model/client mistakes (wrong graph interpretation, tool choice, omitted
labels, retrying an uncertain result) from MCP failures (rejected valid input,
bad placement, extra windows, stale live reads). For a model-only comparison, use
one host with interchangeable models; comparing different apps tests the whole stack.

Use test data only. Captions are caller-supplied labels, not verified chemical
names. Machine checks do not certify synthetic feasibility or biological activity.

## Developer acceptance

Close other clients' MCP servers and run the portable suite:

```sh
.venv/bin/pytest -q
```

The opt-in shared API/native first-run suite on the development ChemDraw 23.0.1
installation is:

```sh
CHEMDRAW_ADDIN_LIVE_TEST=1 CHEMDRAW_LIVE_TEST=1 .venv/bin/pytest tests/test_addin_live.py tests/test_first_run_live.py -q
```

These native fixtures currently address the application by the development build's
name, `ChemDraw 23.0.1`. On another named build, use the manual checklist above and
record it as a separate compatibility test rather than claiming this fixture ran.
Tests create their own untitled documents and close only successful test-owned
documents. An uncertain test canvas remains for inspection; do not blindly retry.
Keep detailed CDXML snapshots and private paths out of public issue reports.

## Known limits

- Only the development Mac/ChemDraw build has been natively accepted so far.
- Same-document insertion supports flat molecules and text, plain charges, house
  or ACS presets, and a single physical page. Full pages fail without expansion.
- Explicit decorated groups, arbitrary graphics, custom layouts/styles and reactions
  still require separate workflows. Legacy copy-based workflows may retain HTML reviews.
- Automatic orientation uses a unique live whole parent, or a whole supplied common
  ring core for batches of at least four. It is not general maximum-common-substructure
  inference. Use advanced `scaffold_smiles` when an explicit core is required.
- The add-in panel is required. This is a logged-in desktop integration, not headless.

Record results in the included TEST-RESULTS.md; skipped checks are not passes.
