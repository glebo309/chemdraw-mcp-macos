# Optional scope frame and grouped separators

This workflow decorates an existing supported scope drawing with a rounded box and
drop shadow, dotted horizontal separators and optional explicit group headings.
It preserves the existing molecule positions, chemical graphs and captions.
Groups are supplied by the caller; the workflow does not classify electronics,
invent group names, rearrange compounds or insert experimental results.

## API

CLI: `chemdraw-mac decorate-scope --input /absolute/scope.cdxml --recipe groups.json --output /absolute/new-directory`. For a live document, replace `--input` with `--document ACTUAL_ID` and include the current analysis token in the recipe.

The JSON recipe contains `schema_version: 1`, `groups` and optional `frame`, `separators`, `pixels`, `expected_source_token`. MCP `chemdraw_decorate_scope` takes the same workflow arguments plus `document_id` and `output_dir`; `schema_version` belongs only to the CLI recipe.

Reproducible example:

```sh
chemdraw-mac decorate-scope --input examples/scope-decoration-input.cdxml --recipe examples/scope-decoration-recipe.json --output /absolute/new-framed-scope
```

This example preserves the fourteen-candidate acetophenone figure and separates the first two rows from the remaining rows, matching the supplied visual reference. These bands deliberately have no chemical headings: the pre-existing order mixes electronic categories, so calling an entire band donating or withdrawing would be incorrect. For named electronic groups, arrange selected compounds into the intended bands first.

```python
from chemdraw_macos.scope_decoration import (
    decorate_scope_document, decorate_scope_file,
    plan_scope_decoration, verify_scope_decoration,
)

result = decorate_scope_document(
    bridge, document_id, '/absolute/existing/parent/decorated-scope',
    groups=[
        {'label': 'Donating', 'fragment_ids': ['ACTUAL_FRAGMENT_ID'],
         'caption_ids': ['ACTUAL_NAME_ID', 'ACTUAL_METADATA_ID']},
        {'label': 'Withdrawing', 'fragment_ids': ['OTHER_FRAGMENT_ID'],
         'caption_ids': ['OTHER_NAME_ID', 'OTHER_METADATA_ID']},
    ],
    expected_source_token=current_analysis['source_token'],
    frame=True,
    separators=True,
    pixels=3200,
)
```

Replace placeholder IDs with the actual source object's IDs from analysis.
The file API is `decorate_scope_file(bridge, path, output_dir, groups,
expected_source_token=None, frame=True, separators=True, pixels=3200)`.
It accepts explicit CDXML input and matches source IDs to its private native copy.
The live API requires a current source token; a stale source fails before creation.

The pure planner `plan_scope_decoration(text, groups, frame=True, separators=True)`
returns planned CDXML and an ownership/geometry plan. The verifier
`verify_scope_decoration(source, native, plan)` strips only decorations matching
that plan before applying the existing source-preservation checks. Neither helper
calls ChemDraw. Native rendering evidence belongs to the serial integration run,
not to the existence of these helpers or passing portable tests.

## Ownership and existing layout

The source must contain one flat physical page with ordinary molecular fragments
and page text only. Existing decorations, arrows, schemes, nested objects and
unsupported graphical chemistry are rejected. Every fragment and every page-text
object must belong to exactly one group. This includes both compound names and
any existing ID/yield labels. Fragment-internal atom labels remain part of their
fragment and are not listed separately.

Supply 1 through 20 groups. Each group has exactly `label`, `fragment_ids` and
`caption_ids`. Fragment lists are nonempty; caption lists may be empty if the group
has no page text. IDs are existing strings, with no duplicates within or across
groups. Labels are empty or nonblank single-line text of at most 80 characters.
Use an empty label to add frame/separators without reserving heading space.

Groups must already occupy disjoint top-to-bottom bands in the supplied order.
The union of each group's native-measured fragment/caption bounds defines its band.
Every listed object requires a measured bounding box; overlapping source objects
or group bands fail explicitly. There is no automatic row sorting or chemical
classification. An existing grid must be arranged into the intended bands first.

## Frame, dots and headings

`frame` and `separators` are independent booleans, both default true. Both may be
false; nonempty labels can still create explicit headings.

- The frame extends 12 pt beyond the union of content and heading bounds. It is a
  native Rectangle graphic with `RectangleType="RoundEdge Shadow"`,
  `CornerRadius="600"` and `ShadowSize="400"`, including native centre/axis geometry.
  The planner conservatively reserves an additional 8 pt at the right/bottom for
  the shadow and requires page fit. It does not claim that this reservation is a
  measured shadow-glyph extent for every ChemDraw version.
- A separator lies halfway between successive displayed bands. Each separator is
  a row of actual native filled-circle Oval graphics with radius 0.55 pt and
  centre spacing at most 5 pt. These are dots, not a dashed line called dotted.
  Decoration is capped at 1,500 graphics; exceeding the cap is an error.
- Nonempty headings are left-aligned to the overall content's left edge, in the
  existing caption font/size with bold face. Their baseline is 6 pt above the first
  content in that group. The planner reserves conservative heading bounds and
  requires space in the existing gaps; it never moves source objects. After native
  saving, actual heading bounds must clear content/separators and remain within
  the page/frame. A long heading or crowded band is rejected rather than covered,
  clipped or silently shrunk.

Frame width inherits the document `LineWidth` and must be 0.2 through 3 pt.
Heading size inherits `CaptionSize`, falling back to `LabelSize`, and must be
4 through 72 pt. Named headings require an explicit resolved caption/label font
table entry. These fixed decoration choices are recorded in the plan; arbitrary
colours, border patterns, custom artwork and frame geometry are outside this API.

## Native preservation and recovery

The working copy receives the new objects; the original is never an editing target.
The final editable CDXML is exported after SVG and PNG, so verification sees any
state changes caused by those renders. Native object renumbering is allowed only
through unambiguous matching. Every new graphic's supported type, numerical
attributes and geometry must survive saving. Extra or changed graphics are not
silently stripped. Heading content, typography and position are verified separately
from actual measured heading bounds.

Once precisely matched decorations/headings are removed from a verification copy,
the existing validator checks source chemistry, atom coordinates, object coverage
and captions. Original page/atom-label typography is also checked. Source document
inventory, retained unsaved content and available source-file hash are compared.
Native dimensions are compared with the existing 0.03 pt numerical tolerance;
native visual review remains required for border/shadow appearance and glyphs.

File input is read and validated before native creation. Its exact bytes are retained
as `source-input.cdxml`, with source path and SHA-256 in the audit. The native import
uses those frozen bytes. Detected source mutation or disappearance fails production.
The successful temporary source copy is closed; the final decorated copy stays open.
An uncertain native operation, including close, stops without retry or automatic
closure of another uncertain copy. Determinate failures close only owned copies.

The new absolute output directory must not already exist and its parent must exist.
PNG longest-side size is an integer from 256 through 8192, default 3200. The bundle
contains `before.cdxml/svg/png`, `planned.cdxml`, `figure.cdxml/svg/png`, `recipe.json`,
`audit.json` and `review.html`, plus `source-input.cdxml` for file input.
`checks_passed` means the implemented checks passed; `failed` and `uncertain`
artifacts remain diagnostic. Group labels and experimental interpretation are
caller supplied and not chemically certified.

## Format evidence

Before implementation, the installed ChemDraw 23.0.1 factory sample
`Human Insulin.cdxml` was inspected read-only. Graphic 6853 contains the exact
`RoundEdge Shadow` rectangle flags, corner/shadow settings and centre/axis format
used by the planner. Only the graphic vocabulary and geometry contract were used;
the sample's artwork, text and template were not copied or redistributed.
The dotted rows use the native filled-circle representation already exercised by
the project's graphical-electron probes. A combined decorated-scope native run
and visual inspection are separate acceptance gates.

Both native MCP decoration cases, with and without headings, passed in the full
v0.8.0 native gate. The fourteen-candidate CLI example passed preservation checks
and visual inspection in native SVG and transparent PNG. PNG uses offline resvg
because sips mishandled the native evenodd shadow clip hole. Details and exact
complete-suite counts are in PROJECT_PROGRESS.md and KNOWN_ISSUES.md.
