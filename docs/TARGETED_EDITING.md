# Precise targets and copied drawing edits

The full MCP profile exposes `chemdraw_inspect_targets`,
`chemdraw_prepare_selection` and `chemdraw_edit_targets`. The CLI equivalents are
`inspect-targets`, `prepare-selection` and `edit-targets`. The chemistry extra is
required. Core remains the direct native command interface.

## What a selection means

The inventory describes a molecular graph with two-dimensional page coordinates:
atom IDs, element, position, formal charge, isotope, hydrogen count and stereo;
bond IDs, endpoint IDs, order and display; molecule IDs and their member objects.
IDs are paired with a source token. Changed source content invalidates a selection.
These IDs are not native AppleScript indices. Ambiguous informal requests must be
resolved by the connected assistant before submitting exact IDs.

Selections are logical target records, **not ChemDraw UI highlighting**. Live
probes on ChemDraw 23.0.1 rejected individual atom/bond references and reference
lists assigned to the documented selection property. JavaScript for Automation
returned the same coercion failure. Native select-next-structure works but does
not provide arbitrary atom/bond targeting. There is no simulated-click fallback.

## Use

```sh
chemdraw-mac inspect-targets DOCUMENT_ID
chemdraw-mac prepare-selection DOCUMENT_ID --kind atom --ids ATOM_ID --source-token TOKEN
chemdraw-mac edit-targets --document DOCUMENT_ID --recipe /absolute/recipe.json \
  --output /absolute/existing/parent/new-edit
```

The recipe contains `selection` from prepare-selection, `operation` below, and
optional `pixels` (256 through 8192, default 2400). MCP accepts these fields as
arguments to `chemdraw_edit_targets`. Only the logical selector fields are trusted;
object details are resolved again from the fresh source.

| Operation | Target | Required additional fields |
| --- | --- | --- |
| `bond_display` | One single bond | `display`: `hashed_wedge` or `solid_wedge`; `from_atom_id`: narrow endpoint; `allow_stereo_change`: `true` |
| `set_atom` | One nonisotopic atom without assigned stereo | `element`: C/N/O/F/P/S/Cl/Br/I; `hydrogens`: integer 0 through 4; `charge`: -1, 0 or +1 |
| `set_bond_order` | One plain nonaromatic, nonstereo bond | `order`: integer 1 through 3; `hydrogens`: mapping of BOTH endpoint IDs to explicit counts |
| `attach_ring` | One neutral, nonisotopic H-bearing C/N/O | `size`: integer 3 through 8; `angle_degrees`: direction -360 through 360, or `"auto"` |
| `attach_fragment` | One neutral, nonisotopic H-bearing C/N/O/S | `fragment_cdxml`: one supplied molecular fragment without captions; `attachment_atom_id`: its H-bearing endpoint; `angle_degrees`: number or `"auto"` |
| `remove_substituent` | One plain single connecting bond | `keep_atom_id`: retained endpoint; `hydrogens`: explicit count on that endpoint after removal |
| `native_align` | Two or more molecule IDs (three for distribution) | `action`: one of the native alignment/distribution action names |

Angles are in the page plane: zero points right, positive angles turn toward
positive y (downward). Ring attachment adds a saturated carbon ring and one
connecting single bond, replacing one implicit hydrogen. It does not fuse a ring,
make a spiro centre, infer aromaticity or invent stereochemistry. Existing atom
coordinates remain fixed. Target stereocentres, explicit H-atom replacement,
new potential stereo on retained source atoms and introduced collisions are rejected.
An `"auto"` angle tests twelve directions in deterministic 30-degree steps. It picks
the first passing preflight, never moves the original scaffold and fails if all
candidates are blocked. This is bounded geometry search, not universal layout repair.

Fragment attachment accepts 1 through 100 supplied atoms, including a one-carbon
methyl fragment. It rescales the supplied fragment to the destination's median bond
length and applies rotation/translation only. A terminal fragment atom uses a
120-degree join so skeletal carbon does not disappear inside a straight line.
Both endpoints lose one implicit H. Explicit-H replacement and isotope-labelled
attachment fragments are refused. Existing supported fragment tetrahedral stereo
is compared after ID remapping; creating/changing potential alkene stereo is refused.
This does not perform name lookup or invent a fragment from a label.

Removal cuts the selected connecting bond and deletes only the component on the
opposite side from `keep_atom_id`. It refuses ring cuts, dangling crossing references
and retained molecules smaller than two atoms. Retained atom coordinates stay fixed.
Explicit requested hydrogen/charge values must match the decoded result; invalid
valence is an error, not permission to silently adjust the chemistry.

## Placement and styling

Chemical edits check newly introduced atom/label collisions, bond crossings and
conservative bond envelopes, including multiple-bond spacing and wedge width.
Preflight uses native text bounds where present and estimates only missing bounds.
After rendering, the check runs again using native-measured label bounds. Existing
collision pairs are reported, not silently repaired. Collinear single-bond joins
that hide an unlabelled carbon are refused. These checks are not exact pixel-ink
analysis or a guarantee that an already crowded input will become well laid out.

Target editing preserves the original layout and does not globally restyle it.
For uniform production, use the existing draw/grid/reaction or explicit polish
workflows. Built-in and custom presets now replace supported local style overrides
and share native font/size/stroke verification. Reaction and molecule-grid defaults
use 10 pt visible caption clearance; the simple reaction path no longer measures
that gap to the text baseline. Explicit lab-style packages retain their own settings.

The separate symbol workflow uses actual local bond widths and conservative
multiple-bond/wedge envelopes when placing charges, then verifies new symbol
clearance again against native labels after saving. It never shrinks a requested
symbol to force a fit. Circled symbols remain outside this editor's input subset.

Bond display is a chemical edit, not merely typography. Its explicitly designated
endpoint may gain or change stereo; other assigned tetrahedral centres must remain
unchanged. The native saved graph and the requested wedge direction are checked.
No name or absolute stereochemical identity is inferred from the user's words.

Alignment invokes the existing ChemDraw command on an isolated copy of the chosen
molecules. Only the verified rigid translations return to a copy of the complete
source. Unselected molecules and all captions remain fixed. No caption ownership
or automatic grouping is inferred. Native bounds determine alignment, not centres
estimated from atom positions. This is not a GUI multiselection API.

## Results and limits

Each job keeps before/planned/final CDXML, native SVG and PNG, recipe, audit and
white-background HTML review. It creates a new editable final document and leaves
the source unchanged. New output directories are required. A native failure
retains diagnostic copies without retry or automatic uncertain-document closure.

Current input is a supported flat single-page molecular sheet with captions, not
reactions, nested abbreviations, groups or molecular graphics. Captions remain
verbatim and are not renamed after a chemical edit. Native diagnostic warnings
are retained and exposed in the target inventory. Live MCP fixtures cover atom and
charge changes, carbonyl formation, ring/fragment attachment, substituent removal,
a directed hashed wedge and three-of-four molecule alignment. Exact run boundaries
are recorded in PROJECT_PROGRESS.md. This is not universal molecule or cross-version
certification.

The native serializer may renumber objects. The final verification matches
molecules/atoms by supported chemistry and coordinates, checks mapped stereo and
explicit wedge endpoints, and rejects ambiguous matches. Visual review remains
required; a passing graph check does not certify every glyph or collision.
