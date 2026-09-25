# Drawing performance

## Complete framed tables (development)

Explicit grouped tables with plain charges now use two whole-document native
opens: one hidden measuring document, then one complete final document. There
is no molecule-by-molecule import, cleanup loop or second decoration workflow.
The measured table selects A4 portrait, A4 landscape or A3 landscape without
shrinking bonds. Chemical identity, native style, cell layout and frame geometry
are checked before delivery. Returned results include stage timings and a white
preview ready for visual review.

A serial native component test on ChemDraw 23.0.1.11 rendered a 15-member,
three-column, five-row framed table in 6.735 seconds, including measurement,
native checks, SVG, 600-DPI transparent PNG and a white preview. It left one
final document. The existing document inventory was unchanged, and guarded
selection/restoration was exercised. This is one component measurement, not a
median, prompt-to-answer benchmark or complete preservation acceptance. An
already-connected installed runtime prevented testing the development runtime's
desktop-API preservation reads in that run. The image was visually reviewed on
white for orientation, spacing, labels, charges, frame and clipping.

Use `chemdraw_draw_structures` with `groups`, `frame=true` and
`presentation="interactive"` when one new framed document is wanted. Do not add
a subsequent decoration or import call. `presentation="background"` closes the
owned final document after delivery. Explicit same-document requests remain
same-document requests; this optimization does not silently redirect them.

Most delay in a failed multi-call interaction can be outside actual rendering.
An uncertain result now returns its retained document ID, artifacts and audit
with `retry_safe=false`. Inspect these read-only; do not recreate the figure or
start another CLI connection to bypass the failure. Successful previews are
already white, so they do not need a separate image-conversion command.

Measurements from 2026-09-23, macOS 15.6 on Apple Silicon, ChemDraw 23.0.1.11,
Python 3.13.2, RDKit 2026.3.6 and resvg-py 0.5.0. These are server workflow times,
not prompt-to-answer times. Model reasoning, client startup, tool selection and
image review are outside the measurement.

## Native caffeine comparison

Each run used the same explicit caffeine graph in a fresh private document.
The existing document inventory and contents were checked unchanged. The
baseline retains full 3200-pixel transparent exports and the previous native
read sequence. The optimized modes use a combined post-read document-state
call, retaining the active-document checks. Each warm row is the median of
three runs in a single process; creation and closure of test documents are
outside the timer.

| Delivery | Median seconds | Native process calls | Files |
| --- | ---: | ---: | --- |
| Full export with previous read sequence | 2.952 | 13 | CDXML, SVG, transparent 3200-pixel PNG |
| Default preview | 2.067 | 10 | CDXML, SVG, white 1200-pixel review PNG |
| Explicit canvas-only | 1.401 | 7 | CDXML; no image exports |

In this fixture, default preview reduced server time by about 30%; canvas-only
reduced it by about 53% while omitting image delivery. The first preview call
took 2.595 seconds and is excluded from the warm medians. These small samples
are not a latency guarantee for larger tables, reactions or another Mac.
Name lookup is excluded because the comparison supplies an explicit graph.

## What changed

The rc17 frozen executable completed an explicit four-participant glycoside
hydrolysis in 5.758 seconds, including native measurement, layout, all exports
and preservation checks. It retained the full labels and conditions on A4
landscape. This is one measured run, not a median or a speedup factor against
the older failing workflow. Name lookup was excluded by supplying explicit
graphs. Reproduce with `tests/test_reaction_batch_live.py`; the packaged MCP
case is in `tests/test_desktop_bundle.py`. Both require `CHEMDRAW_LIVE_TEST=1`;
the packaged case also requires `CHEMDRAW_DESKTOP_RUNTIME`.

- Post-read document identity and metadata share one native process invocation.
  Before/after target checks remain, including a document switch during metadata
  collection. Current document snapshots are never cached.
- Shared `chemdraw_draw` requests default to a small white review image. Full
  transparent exports remain explicit, and physical-scale publication exports
  use the existing export tool without redrawing.
- Validated name/CAS lookup results can be reused in process memory for five
  minutes. Permission, ambiguity, truncation and provenance rules remain.
  No network failures or rejected candidate sets are cached.
- Results report actual stage timings so native work can be distinguished from
  model/client time. The cache and export choices do not skip chemistry, stereo,
  source preservation, measured table layout or style checks.

## Reproduce

Use the locked environment and disconnect other native editing clients first.
The tests only close their own successful private documents; uncertain writes
stop without retry or automatic closure.

```sh
CHEMDRAW_ADDIN_LIVE_TEST=1 uv run --locked --extra chemistry pytest -q -s tests/test_drawing_speed_live.py
```

The test prints the path to `benchmark.json`, with environment records, each
run's timings, native operation counts and artifact locations. Native previews
still require visual inspection. Use [delivery choices](DRAWING_HARNESS.md#drawing-speed-and-export-choices)
for the matching MCP and CLI request fields.
