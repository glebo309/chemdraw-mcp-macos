# Guarded drawing entry point

The client supplies chemical intent. The server owns the drawing procedure.
Use `chemdraw_draw` for new molecules, related panels and explicit reactions.
There is no embedded language model and no natural-language parser on the server.

The default molecule path now uses the [desktop API](DESKTOP_ADDIN.md): one
preplanned insertion into the active canvas, including untitled drawings. It
validates native chemistry, coordinates, typography/strokes, object ink bounds,
page fit and exports. It does not run per-molecule native imports or cleanup.
The separate background/reaction pipelines retain their original gates below.

For clients that should not choose among low-level tools:

```sh
chemdraw-mcp-macos --profile drawing
```

This profile exposes drawing, diagnostics and physical export. The existing
`full` profile also exposes the harness and recommends it for new drawings.
`core` remains the direct native API. Existing client processes must restart
to load the new code and tool schema. No client configuration is changed silently.

## Request

```json
{
  "molecules": [
    {"value": "C[C@H](O)C(=O)O", "format": "smiles", "label": "Explicit stereoisomer"}
  ]
}
```

Call `chemdraw_draw(request=..., output_dir="/absolute/new-folder")` or save the
request as JSON and use the same implementation through the CLI:

```sh
chemdraw-mac produce --request /absolute/request.json --output /absolute/new-folder
```

Each molecule needs `value` and `format` (`name`, `cas`, `smiles` or `inchi`).
Labels are optional; explicit graph inputs without labels display compact compound
numbers, not formulas or guessed names. Explicit labels are retained as text.
Names/CAS require `allow_network=true` (CLI: `--allow-network`) to query PubChem.
A sole locally validated match is recorded as the selected source; ambiguous or
truncated results require an explicit `selected_cid` or a more specific input.
PubChem matching is not authoritative CAS Registry validation. Unspecified stereo
is retained as unspecified, not invented.

Add `products` in the same format for a reaction. All products must be supplied;
conditions may be placed in `conditions_above` and `conditions_below`.
Products, yields, activity and reaction balance are not predicted.

## Drawing speed and export choices

Shared molecule requests accept `exports`:

| Value | Delivered files |
| --- | --- |
| `auto` (default) or `preview` | Editable CDXML, unchanged native SVG and a white-background 1200-pixel `artifacts.preview` PNG for direct visual review |
| `full` | Editable CDXML, native SVG and the previous transparent 3200-pixel `artifacts.png` bundle |
| `canvas` | Editable CDXML and checked native insertion only; inspect the drawing in ChemDraw |

The preview is not a publication export and is not advertised as a transparent
PNG. Do not convert it again just to inspect it on white. Use
`chemdraw_export_figure` or CLI `export-figure` afterwards for physical-scale
SVG/PNG and optional PDF, without redrawing. Chemistry, stereo, source preservation,
style, page fit and table alignment checks remain mandatory in every mode.
Canvas mode does not claim that an SVG export or image review occurred.
Background/reaction workflows keep full exports; explicit `preview` and `canvas`
requests on those paths are rejected before native changes. The advanced
`chemdraw_draw_structures` interface keeps its existing full-export default.

Repeated name/CAS lookups reuse locally validated results for up to five minutes
in the same process. The cache has at most 128 entries, never writes queries to
disk, retains retrieval provenance and never removes ambiguity or truncation.
Set `refresh_identifiers: true` to bypass it. Every name/CAS request still needs
explicit network permission, including cache hits. Separate CLI invocations do
not share memory; repeated inputs within one request can benefit.

Results include `timings.total_seconds` and `timings.stages_seconds` for input
resolution/planning, native reads, layout, insertion/verification and requested
exports. Timings exclude model reasoning, tool selection and client image review.
Native stage timings are retained in the audit; the overall timing is in
`result.json`. These measurements are evidence, not an estimated progress bar.

## Enforced gates

1. Strict typed request; unknown fields and attempts to skip checks are rejected.
2. Identifier resolution with provenance, local graph validation and support checks.
3. Native-readiness check, including preservation of existing user documents.
4. House-scale native drawing, measured layout and bounded document ownership.
5. Native saved-graph, layout and source-preservation checks.
6. Independent comparison of delivered graphs, conservative measured collision
   screening and requested artifacts. Shared `canvas` delivery omits images, not
   the graph/layout checks; background delivery retains CDXML/SVG/PNG requirements.
7. Structured result with artifact paths, plan, audit location and presentation state.

Related panels of at least four molecules use a common core only when an entire
ring-containing molecule supplied in the request matches every structure with
stereochemistry respected. This is not unrestricted scaffold inference. New
coordinate seeds are constrained to the native reference; existing drawings are
not reflected to force a fit. Exact supported substituent motifs produce group
bands, headings, dotted dividers and a native rounded shadow frame. Electronic
group labels describe motifs, not measured electronic properties or reactivity.
Unrecognized substitutions remain explicitly in `Other substitutions`.
This decoration policy applies to the separate background workflow. On the shared
canvas, `panel="auto"` selects a plain aligned grid before native execution while
retaining the common core. No initial rejection or retry with `plain` is needed.
Explicit decorations supplied through the advanced drawing tool remain unsupported
in shared mode; they are not silently removed.

In both auto and plain shared batches, a unique matching live molecular graph
supplies orientation. If replacing its substituent prevents a whole-parent match,
the planner tries the same conservative whole-supplied-ring-core rule and anchors
that core to the unique matching live drawing. If no live reference matches, a
verified supplied core aligns the batch to its first requested structure. This
also considers whole ring/linker frameworks derived from supplied graphs, only
when the entire framework matches every requested molecule. It does not infer a
maximum common substructure or chemical correspondence outside
the matched core. Requests without a verified core retain independent depictions;
use the advanced `scaffold_smiles` option for an explicit common core.

Fresh coordinate seeds with a regular six-membered ring use the smallest proper
rotation that makes a ring edge vertical. This removes arbitrary global tilt,
including the caffeine fused-ring example. It does not change relative atom
positions, bond length, stereochemistry or label orientation. Irregular rings,
chair/cage depictions and molecules without a qualifying ring keep their seed
orientation. A live reference always takes precedence; it is never straightened
behind the user's back. The planning report records each orientation policy and
rotation. This is a bounded depiction convention, not universal layout repair.

Columns are selected from measured widths. Failed alignment is not silently
dropped; overflow is not hidden by shrinking molecules independently. This
shared path can add identical vertical physical pages in the same document, up
to 20 pages, when the complete table needs more space. Set `page_policy="keep"`
to require the current page extent. Unsupported layouts fail without retry loops.

## Result states

| State | Meaning |
| --- | --- |
| `completed` | Mandatory gates passed; final artifact paths are usable. |
| `needs_input` | Specific ambiguity, missing network permission or unsaved-document requirement. No production write dispatched. |
| `rejected` | A schema, support, layout or delivery gate failed. No renderer fallback. |
| `uncertain` | A dispatched native operation has uncertain state. No automatic retry or close. |

`completed` is not a universal chemical or pixel-perfect appearance certificate.
Native measured bounds and conservative bond envelopes can flag intentional
crossings; unsupported cases stop for inspection. Human visual review remains
explicitly required. The server cannot make an incorrect caller-supplied SMILES
correct merely by rendering it accurately.

`presentation="auto"` and `interactive` use the active canvas for molecules,
creating one working document only if none exists. `shared` with `document_id`
binds an explicit active document. Multi-molecule tables use one hidden native
measuring copy, closed after successful measurement; no second final document
is created for overflow.
Explicit `background` retains separate exports and native temporary imports.
All modes require a licensed logged-in desktop, not a display-free engine.

The chosen shared document may be untitled: the desktop API reads it without
assigning a filename, and checked insertion leaves it unsaved and open. Shared
reads and writes do not select all objects or use the clipboard. Background/separate-document
production still blocks on other untitled documents because its preservation
snapshot path has not been converted. It does not save or close them implicitly.

## Current acceptance scope

Portable tests exercise typed routing, chemistry breadth, strict rejection,
ambiguity, missing verification, collisions, presentation and uncertainty.
Native end-to-end tests are in `tests/test_harness_native.py`, using a mixed
chemistry panel, an automatically grouped unrelated scaffold family and an
explicit reaction through the reduced MCP profile. On 2026-09-15 all three
positive cases passed in 52.37 seconds on the development Mac. The untitled-document
guard was skipped because there was no untitled document; it passed separately
before the user saved the document. Each successful background job closed its own
documents and preserved the baseline inventory. Native PNGs were inspected on white.
The portable confirmation passed 961 tests with 70 native skips in 8.20 seconds.
These are bounded acceptance results, not a stable-release or cross-machine claim.
It does not support every
possible molecule: metals, exotic bond types and polymer semantics still use
separate bounded interfaces or are rejected.

Visual inspection also identifies the next layout-policy work: automatic columns
currently maximize width, so five unrelated molecules can occupy a sparse four-plus-one
grid. Group bands can likewise leave substantial unused space. Collision-free is
not equivalent to compact or well-balanced; bounded layout candidate selection
and broader native corpus coverage remain pending.
