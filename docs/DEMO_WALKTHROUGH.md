# Reproducible native demo

Run these commands from the project directory on a supported Mac with a licensed, activated ChemDraw installation. This walkthrough uses checked-in illustrative examples, not research results. It neither publishes files nor sends chemistry to an external service.

```sh
uv sync --locked --extra chemistry
uv run --extra chemistry chemdraw-mac doctor
DEMO_ROOT=$(mktemp -d "${TMPDIR%/}/chemdraw-demo.XXXXXX")
export DEMO_ROOT
```

Keep this shell open. `DEMO_ROOT` is a newly created absolute parent directory; every workflow below creates its own new child directory. Do not reuse an existing output child when rerunning a command. Only one native editing client should operate at a time. The diagnostic does not substitute for the actual native exports below.

## 1. Inspect a complete scope plan offline

```sh
uv run --extra chemistry chemdraw-mac scope-job \
  --manifest examples/scope-job.json --plan-only
```

The example provides mapped acetophenone, explicit ordered categories and `accept_all: true`. Inspect the candidate graphs, category memberships and `selection` record. `accept_all` is the example's explicit approval to draw the proposal; `--plan-only` itself creates no native document. For an unapproved planning session, remove that field in your own recipe. To approve only particular compounds, replace it with `selected_candidate_ids` copied from the proposal. Do not provide both keys.

The three supplied bands are Reference / donors, Withdrawers, and Bulky / positional. Each graph is assigned once to its first matching band; secondary memberships remain in the plan. Relative labels are not systematic chemical names. No experimental yields are supplied or generated.

## 2. Build and inspect the native grouped figure

```sh
uv run --extra chemistry chemdraw-mac scope-job \
  --manifest examples/scope-job.json \
  --output "$DEMO_ROOT/scope"
open "$DEMO_ROOT/scope/review.html"
```

Inspect the actual grouped rows, common scaffold orientation, captions, headings, dotted dividers and rounded shadow frame. The editable file is `scope/figure/figure.cdxml`, with SVG and transparent PNG beside it. The frame interior should show the page background, with the shadow outside the border; inspect transparency on white as well as the preview background.

`scope/plan.json` retains candidate-to-compound bindings and group assignment. `scope/group-layout.json` records measured rows. `scope/audit.json` and child audits separate chemistry, native geometry, source preservation and visual review. A successful run leaves the final working document open in ChemDraw and closes only its intermediate copies. The complete scope job has passed native checks and visual inspection on the development Mac; receiving-machine acceptance remains separate.

See [scope jobs](SCOPE_JOB.md) for exact layout options and limits. Page overflow is an error, not permission to shrink molecules or relabel a mixed row as a category.

## 3. Reuse the numerical style as a versioned package

This step extracts settings from the native output you just produced, not from a proprietary template. First create two small JSON inputs in the demo directory: a copy of the accepted scope recipe with style/layout delegated to the package, and package spacing matching that recipe.

```sh
.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ['DEMO_ROOT'])
job = json.loads(Path('examples/scope-job.json').read_text())
settings = {'grid': job.pop('layout')}
job.pop('preset')
for name, value in [('style-settings.json', settings), ('styled-scope.json', job)]:
    with (root / name).open('x') as handle:
        json.dump(value, handle, indent=2)
PY

uv run chemdraw-mac make-lab-style \
  --name demo-lab --version 1.0.0 \
  --style "$DEMO_ROOT/scope/figure/figure.cdxml" \
  --settings "$DEMO_ROOT/style-settings.json" \
  --output "$DEMO_ROOT/demo-lab.json"

uv run chemdraw-mac inspect-lab-style \
  --input "$DEMO_ROOT/demo-lab.json"

uv run --extra chemistry chemdraw-mac styled-job \
  --lab-style "$DEMO_ROOT/demo-lab.json" --workflow scope-job \
  --recipe "$DEMO_ROOT/styled-scope.json" \
  --output "$DEMO_ROOT/styled-scope"
open "$DEMO_ROOT/styled-scope/review.html"
```

Inspect the package name, version and content hash, and the `lab_style` audit record in the second output. The package locks numerical style and spacing; it does not silently override conflicting recipe values. Font families must exist on the rendering Mac. This packages numerical settings and conventions, not template artwork, pages, palettes or fonts. It does not automatically add charges or mechanism arrows to an unrelated workflow.

## 4. Build an explicitly supplied reaction

```sh
uv run --extra chemistry chemdraw-mac reaction \
  --manifest examples/reaction-build.json \
  --output "$DEMO_ROOT/reaction"
open "$DEMO_ROOT/reaction/review.html"
```

The existing example supplies ethanol, ethanal and the text `oxidation`. It provides no experimental reagent specification, conditions or yield. Check the native arrow, role placement, captions and graph-preservation audit. This demonstrates explicit composition, not reaction prediction or balancing.

## Additional bounded workflows

The current `reaction-series` interface accepts explicitly ordered reaction steps, coefficients and supported ionic components. `build-ownership` and `move-owned` keep explicitly owned molecules and annotations together during tool-controlled translations. `suggest-routes` proposes bounded curves from explicit anchors, and `apply-route` requires a selected candidate from the unchanged source snapshot. These interfaces need their own correctly bound recipes; do not reuse object IDs from another document or assume the single-reaction manifest is a series manifest.

Ownership sidecars do not promise that manually dragging an atom in ChemDraw will move its curve. A route's geometric checks do not prove a mechanism or every possible rendered collision. Review the workflow-specific audits and native preview before using either result.

## Finish the review

Keep source inputs and the final editable CDXML with their recipe, audit and native exports. Review SVG/PNG glyphs and the actual ChemDraw page, not only the JSON status. `visual_review` remains `required` even after machine checks pass. If a native operation becomes uncertain, stop: do not rerun the write or close an unknown working document automatically. Read the audit and inspect the current document inventory before choosing recovery.

The output directories remain in `DEMO_ROOT`; retain or remove them deliberately after review. No cleanup command here closes user documents or deletes the evidence. See the [release checklist](RELEASE_CHECKLIST.md) for the still-pending independent-Mac and licence/publication gates.
