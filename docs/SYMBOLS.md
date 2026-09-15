# Native chemical symbol graphics

Implementation date: 2026-09-15. Native ChemDraw 23.0.1 glyph calibration and five end-to-end MCP integration cases passed on the development Mac: negative-charge symbol creation; positive-charge creation on ammonium; lone-pair creation followed by a source arrow; graphical-electron creation followed by a fishhook; and an existing negative-charge source arrow. These fixtures establish the tested workflows, not universal molecule or cross-version compatibility. Current complete-run evidence is in PROJECT_PROGRESS.md.

## API

```python
from chemdraw_macos.symbols import (
    inspect_symbols_document, symbols_document, symbols_file,
    plan_symbols, verify_symbols,
)

report = inspect_symbols_document(bridge, document_id)
result = symbols_document(
    bridge, document_id, '/absolute/existing/parent/new-symbol-review',
    symbols=[
        {'key': 'oxygen-charge', 'kind': 'charge', 'atom_id': '123'},
        {'key': 'oxygen-pair', 'kind': 'lone_pair', 'atom_id': '456'},
    ],
    expected_source_token=report['source_token'],
)
```

Atom IDs above are placeholders. Use the IDs returned for the actual source. The file entry point has the same arguments after `path`, with an optional source token. Both entry points require a new absolute output directory whose parent exists. They leave the successful final copy open, preserve the original, and export native CDXML/SVG plus PNG, a recipe, audit and before/after HTML review.

Each request has exactly `key`, `kind` and `atom_id`. Keys are unique safe identifiers. Accept 1 through 50 requests; kinds are `charge`, `lone_pair` and `electron`. The optional numerical controls are `span`, `line_width`, `clearance` and `pixels`.

## Chemistry and representation

- `charge` uses `CirclePlus` or `CircleMinus` according to the existing atom `Charge` of exactly +1 or -1. It creates a native `graphic` with `GraphicType="Symbol"` and an explicit `represent attribute="Charge"` atom association. It neither changes charge nor invents a charge from a label. An atom that already owns a charge graphic is rejected. A redundant terminal +/- suffix in a canonical elemental label, optionally including explicit H, is removed when transferring its display to the circle. This is required because ChemDraw otherwise counts both displays and doubles the charge. Noncanonical signed label text is rejected rather than rewritten.
- `lone_pair` uses native `SymbolType="LonePair"` with an explicit `represent attribute="Radical"` reference to the requested nonradical atom. Despite that native attribute name, the observed lone-pair association does not add an atom Radical state. The verifier requires this association to remain on the same mapped atom and requires chemistry to remain unchanged. This does not infer or certify a chemically correct lone-pair population.
- `electron` uses a native filled-circle graphic, **not ChemDraw's Radical Electron Symbol**. The native Electron Symbol automatically adds `Radical="Doublet"` near an atom, which would violate this graph-preserving workflow. A controlled native probe verified that an unassociated `GraphicType="Oval"`, `OvalType="Circle Filled"` circle preserves the chemistry. Inventory exposes `kind="Electron"` and `native_graphic_type="Oval"`; the plan explicitly records `native_representation="filled_circle_annotation"`. No radical-state creation, valence-electron count, oxidation-state inference or mechanism validation is provided.
- These are not Unicode symbols, text superscripts or circles drawn around a typed charge.
- Existing native charge associations remain strict. Unsupported symbol kinds, styling, Electron radical associations or atom radical states fail closed. Existing unassociated native Electron Symbols can be preserved only when they do not change chemistry; new electron requests use the filled-circle form. The bounded LonePair association and exact black circular annotation do not make radical chemistry, general ovals or arbitrary ChemDraw graphics supported.

## Placement and appearance

Charge centers must be closer to their owning atom than to any other atom, with a 0.25 pt margin. Actual native testing showed ChemDraw reassociating an explicitly linked CirclePlus to a nearby carbon and removing the nitrogen's formal charge. Circle clearance alone was insufficient. Candidates outside the owner's nearest-atom region are now rejected before creating the charged copy. The saved graph and association are still checked; this geometric guard is not a universal native-association guarantee.

This can reject dense arrangements such as the current house-style tetramethylammonium and nitrobenzene examples. The workflow does not silently reduce symbol size, stretch bonds or switch to plain charges. Request plain-charge drawing explicitly when circled placement is infeasible. The `draw` and `styled-job` draw entry points accept `charge_style: "circled"` to run this bounded pass after native layout; `plain` remains the default.

The planner requires native measured text boxes for atom labels and page captions. It preserves all atom coordinates, bonds, stereochemistry and existing object geometry. New symbol positions are chosen near their explicit atom, prioritizing the direction away from its bonded neighbours and searching a bounded range of alternatives. For isolated atoms, the deterministic starting direction is upper right.

The `span` parameter is a common charge-equivalent size, defaulting to 0.75 times the document LabelSize. Native handle spans are `span` for circled charges and `span/3` for lone pairs. New graphical electrons have radius `2*span/27`, matching the visible radius of each lone-pair dot. The `line_width` parameter is the requested visible charge-symbol stroke, defaulting to the document LineWidth. Native charge strokes render at approximately 0.8 times their numerical graphic LineWidth, so the writer divides by 0.8. Native rounding introduces small differences; exact pixel-level equality is not asserted. The filled circle has no rendered border; its native LineWidth is explicitly 0.20 pt, but dot size comes from its radius. Existing symbols are retained, not restyled.

The native Symbol BoundingBox contains a centre and a size/orientation handle. It is not an ordinary rectangular ink box. Native 23.0.1 SVG probes at several sizes established these visible primitives, within approximately 0.03 pt of quantized output:

- Circled charge: outer radius `4*handle_span/9 + 0.8*graphic_LineWidth`.
- Electron: one filled circle at the first handle point, radius `handle_span/9`.
- Lone pair: two filled circles at the two handle endpoints, each radius `2*handle_span/9`.
- Graphical electron created by this workflow: native Circle Filled oval whose major/minor axis lengths are its visible radius. Its numeric LineWidth does not add a rendered border.

The planner reserves these calibrated circles with an additional 0.05 pt quantization margin. It checks them against atom positions, measured atom/caption labels, bond centre-line segments with the configured stroke allowance, existing/new symbols, curve-control bounding rectangles, reaction-arrow bounds and the physical page box. This is not a check against every rendered bond outline, double-bond stroke or wedge polygon, and it does not route or certify an entire arrow path. New pair dots straddle the chosen position, with the pair axis perpendicular to the outward direction. It rejects a drawing when no candidate fits instead of moving or shrinking its molecules. These are version-specific empirical calibration rules, not an assertion about every ChemDraw release.

The clearance defaults to 2 pt. Allowed charge-equivalent spans are 2 through 24 pt; requested visible line widths 0.2 through 3 pt; clearance 1 through 12 pt. Symbol-search distances from the target atom are bounded at 36 pt. Remote charge symbols can cause ChemDraw to drop their association and even their atom's formal Charge on import; native graph/association verification rejects such changes. This conservative method can reject a visually feasible crowded arrangement. It is not a general typography/layout solver. Native saved graph, coordinates, symbol count, type, association, geometry and style are verified separately from human visual approval. Actual exported glyph overlap and optical stroke matching still need native visual review.

## Explicit electron-flow sources

Annotation inspection now reports existing symbol IDs. A donation arrow can use an explicit source:

```json
{
  "key": "donation",
  "electrons": 2,
  "source": {"kind": "symbol", "id": "ACTUAL_SYMBOL_ID"},
  "target": {"kind": "atom", "id": "ACTUAL_TARGET_ID", "offset": [0, -14]},
  "controls": [[0, -33], [0, -28]]
}
```

`CircleMinus` and `LonePair` require two-electron arrows; `Electron`, including the explicitly graphical filled-circle form, requires one-electron arrows. Positive charges cannot be donation sources. Symbol targets and source-symbol offsets are rejected. The first control vector supplies the departure direction; it must be nonzero. Donating bonds remain supported sources; atoms and bonds remain supported targets. Atom-label sources are rejected. Add an explicit donor symbol first if needed.

The implementation starts a symbol-source curve at the calibrated visible edge in the departure direction. For a lone pair, it chooses the dot furthest in that direction, never the empty space between the two dots. The native glyph-size calibration is tested against exported SVG, and negative-charge, lone-pair and graphical-electron source arrows passed native integration checks. Human inspection of each rendered figure remains required; those tests do not certify every curve's full path or optical appearance.

An explicit negative-charge source means the caller intends that charge to stand for the donated pair. It is not a general rule that every negative charge is a donation origin. Bond donation, such as from a B-H bond, still uses a bond source. Curves are not mechanistic inference, and recipe ownership does not promise native moving attachment when an atom is edited later.

## Safety and outputs

Live-document calls require a current source token. File calls validate the input before importing, map IDs against the native copy, and recheck source bytes. Successful verification retains the final working copy and closes only an owned temporary source copy. An uncertain native operation stops immediately without retry or cleanup of uncertain documents. Audit state is `uncertain`, not passed. Determinate verification failures close only owned working copies.

Files retained: `before.cdxml`, `before.svg`, `before.png`, `figure.cdxml`, `figure.svg`, `figure.png`, `recipe.json`, `audit.json`, `review.html`. Chemical and geometric machine checks do not approve the source chemistry or certify that an electron-flow mechanism is correct.

## Format evidence and provenance

The native symbol vocabulary and centre/handle syntax were inspected read-only in the installed ChemDraw 23.0.1 samples `Nucleophilic Substitution Sn2.cdxml` and `Stereoisomerism.cdxml`. Those samples contain `CirclePlus`, `CircleMinus`, `LonePair` and `Electron`, including Radical associations. Independent minimal native probes in local-validation/symbol-geometry-v1 and symbol-geometry-v2 established rendering geometry and confirmed that distant standalone dots can remain graphical without a Radical association. Subsequent nearby-atom tests distinguished the nonradical LonePair attachment from an Electron attachment that changes the atom to Doublet. The independent local-validation/electron-oval-v1 probe confirmed a filled black circle can remain adjacent to bromide without changing its charge or adding radical state. No sample artwork was copied.

The documentation model is ChemDraw's [CDXML format reference](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/). Local source tests and actual native round trips remain the compatibility evidence for this application version.

Electron-flow reference: Clayden, Greeves and Warren, *Organic Chemistry*, second edition, chapter 5, printed pages 113, 117 and 120, inspected in the user's local textbook by the coordinating agent. This informs the distinction between a lone-pair/negative-charge donor and a donating bond. No textbook artwork or prose is redistributed here.
