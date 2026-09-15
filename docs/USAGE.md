# Usage

CLI and MCP share the same workflow implementations. Natural-language interpretation comes from a connected assistant; the server itself is not an LLM. The separate `resolve` interface contacts PubChem only when the caller explicitly enables network access; other workflows do not perform name lookup.

## Complete production jobs

| CLI | MCP | Contract |
| --- | --- | --- |
| `scope-job --plan-only` / `scope-job` | `chemdraw_plan_scope_job` / `chemdraw_build_scope_job` | [Accepted candidates to a native grouped scope](SCOPE_JOB.md) |
| `reaction-series` | `chemdraw_build_reaction_series` | [Explicit rows, salts, small species and coefficients](REACTION_EXPANDED.md) |
| `build-ownership` / `move-owned` | `chemdraw_build_ownership` / `chemdraw_move_owned` | [Snapshot-bound molecule/annotation ownership](OWNERSHIP.md) |
| `suggest-routes` / `apply-route` | `chemdraw_suggest_routes` / `chemdraw_apply_route` | [Explicitly selected geometric arrow proposals](OWNERSHIP.md#geometry-only-route-suggestions) |
| `make-lab-style` / `inspect-lab-style` / `styled-job` | `chemdraw_create_lab_style` / `chemdraw_inspect_lab_style` / `chemdraw_run_styled_job` | [Portable locked numerical settings](LAB_STYLE.md) |

The [demo walkthrough](DEMO_WALKTHROUGH.md) connects these to actual examples. CLI subcommand `--help` lists required input/recipe/output arguments. Offline ownership and route commands read a supplied CDXML snapshot and write a new JSON sidecar/report; MCP equivalents snapshot an explicit live document. Native operations create working copies. None of these commands publishes a package or installs files on another machine.

## Install and diagnose

From the project directory, with `uv` installed:

```sh
uv sync --locked --extra chemistry
uv run --extra chemistry chemdraw-mac doctor
```

The optional chemistry extra supplies RDKit for offline identifiers and scope proposals, molecular coordinate seeds for `draw`, and polish, analogue-edit, scope-grid, annotation and batch-export validation. RDKit does not render the exported figure. The low-level native bridge works without it. Retain `--extra chemistry` in `uv run` commands that need these workflows, or run the installed `.venv/bin/chemdraw-mac` directly after syncing that extra.

`doctor` reports application path/version, whether the native connection responded, rasterizer availability and RDKit import availability. It does not test a chemical fixture or certify an unfamiliar application version.

| Status | Meaning |
|---|---|
| `ready` | App discovery succeeded and RDKit is present; check `native_connection` to see whether connection was tested |
| `basic_only` | App discovery succeeded but RDKit is absent; identifiers, proposals, drawing, polish, editing, grids, annotations and batch export require the chemistry extra |
| `unavailable` | A platform, application or connection check failed; inspect the returned error |

`doctor --no-connect` skips contacting ChemDraw. Diagnostic exit status is zero for `ready` and `basic_only`, nonzero for `unavailable`.

Set `CHEMDRAW_APP` to an absolute `.app` path if discovery is ambiguous or the app is outside `/Applications`. Default discovery expects exactly one `/Applications/ChemDraw*.app`. `CHEMDRAW_MCP_WORKSPACE` overrides `~/ChemDraw-MCP-Output`, where scratch files and backups are retained. The launching process needs macOS Automation permission. The server does not change permissions or activate licenses.

## Inspect identifiers offline

```sh
uv run --extra chemistry chemdraw-mac identify --value '[13CH3][C@H](O)C(=O)[O-].[Na+]' --format smiles
uv run --extra chemistry chemdraw-mac identify --value 'InChI=1S/CH4/h1H4' --format inchi
```

`--format` is `smiles` by default or `inchi`; neither command contacts ChemDraw or an external provider. MCP `chemdraw_identify(value, input_format='smiles')` calls the same offline implementation. There is no format autodetection, chemical-name lookup or CAS resolution.

The JSON result includes canonical isomeric SMILES, formula, formal charge, disconnected-component and explicit-atom counts, isotope/stereo summaries and nested `inchi` availability/normalization information. Explicit ordinary/isotopic H and specified supported stereo are retained in the graph output. Unspecified potential stereo is reported, not invented. Standard InChI has separate normalization semantics, so check `inchi.warnings` and `inchi.graph_roundtrip_equivalent`; a matching InChIKey is not a guarantee of the same drawn tautomer or ionic depiction.

Inputs are bounded, ASCII and whitespace-free. Trailing names, CX/query/dummy/map syntax, exotic bonds/stereo and silently discarded stereo are rejected. InChI input is restricted to canonical Standard InChI with exact regeneration, including repeated-component notation. Unsupported/malformed input fails explicitly. If InChI generation is unavailable, supported SMILES inspection still returns with an explicit unavailable result. See [the full identifier contract](IDENTIFIERS.md) for fields and limits. Identifier indices are not ChemDraw atom IDs.

## Resolve an explicit name or CAS query

```sh
uv run --extra chemistry chemdraw-mac resolve --query caffeine --kind name --allow-network
uv run --extra chemistry chemdraw-mac resolve --query 58-08-2 --kind cas --allow-network
```

MCP `chemdraw_resolve(query, input_kind='name', allow_network=False)` calls the same resolver. Every request requires `allow_network=True` to send the query to PubChem over HTTPS. There is no provider fallback, automatic retry or silent selection. Up to 20 records are returned with provider fields, local strict chemistry validation, provenance, total match count, ambiguity and truncation. `selected_candidate` remains null and `selection_required` remains true even for a single match. Unsupported candidate chemistry is retained with its rejection reason.

CAS syntax and checksum are checked, but PubChem associations are not authoritative CAS Registry certification. Resolver validation does not establish name correctness, reaction compatibility or native drawing support. Review an explicit candidate before passing its validated graph to `draw` or `reaction`. See [resolver input, errors and network limits](RESOLVER.md).

## Import a local document style

```sh
uv run chemdraw-mac import-style --input /absolute/path/my-style.cds \
  --output /absolute/existing/parent/style-report.json
```

The optional report path must be new and absolute; JSON is also printed. MCP `chemdraw_import_style(path)` returns the same report without opening ChemDraw. Supported `.cds`/`.cdx` binary document settings and `.cdxml` root settings become a validated `preset` dictionary. The report records source path/hash, defaults and unapplied properties, while font availability remains unchecked until production. Duplicate font tables/IDs, unresolved fonts, incomplete core settings and malformed input fail explicitly.

Pass the report's `preset` object to the `preset` argument of supported drawing, reaction, polish, grid or style-copy workflows. CLI `draw --style PATH` and `reaction --style PATH` extract and apply a style directly, overriding the manifest preset. Custom font families are checked against the rendering Mac's installed families before native production. Missing fonts are not substituted. Page settings, artwork, palette and font files are not imported. Retain the separate report when source-template provenance matters; drawing requests retain the resolved preset. [Exact settings and limits](STYLE_IMPORT.md)

## Propose an aromatic substrate scope

```sh
uv run --extra chemistry chemdraw-mac propose-scope \
  --parent 'O=C[c:1]1ccccc1' \
  --handle-map 1
```

This is an offline candidate proposal, not a native drawing command. The example supplies an aldehyde-bearing parent. Its `[c:1]` map marks the benzene carbon bonded to the existing reaction handle, not the carbonyl carbon and not an inferred reactive atom. Use the actual parent relevant to the task; the server does not choose one or guess the intended reaction.

MCP `chemdraw_propose_scope(parent_smiles, handle_atom_map, profile='standard')` returns the same proposal. The CLI exposes the sole `standard` profile without a profile flag. The parent must be one connected supported molecule of at most 200 atoms, containing an isolated, neutral, non-isotopic, monosubstituted aromatic carbon six-membered ring. The mapped anchor has exactly one outside handle bond; the other five ring atoms are H-bearing. Atom maps must be unique, and the supplied handle map must exist. A fused, heteroaromatic or pre-substituted selected ring, radicals, explicit H atoms, queries, unsupported elements and unassigned/non-tetrahedral or directional-bond parent stereo fail closed. The supported element set here is C, N, O, F, P, S, Cl, Br and I. Supported existing fully assigned tetrahedral stereo is preserved and checked.

The initial standard profile contains fourteen distinct graphs:

| Purpose | Proposed relative substitutions |
|---|---|
| Reference | Unchanged parent |
| Positional series | 2-Me, 3-Me, 4-Me |
| Donating comparisons | 4-Me, 4-OMe |
| Withdrawing comparisons | 4-CF3, 4-CN, 4-NO2 |
| Halogen comparisons | 4-F, 4-Cl, 4-Br |
| Steric comparisons | 2-Me, 2-iPr, 2-tBu, 2,6-Me2 |

The repeated methyl entries are deduplicated by graph, retaining all their category/rationale memberships. Positions are relative to the selected handle, not claimed systematic IUPAC numbering. These fixed categories explain why a candidate is included; they do not predict compatibility, yield or an isolated steric effect independent of electronics.

The result has `status: "proposal"`, mapped/unmapped parent and candidate SMILES, relative display labels, graph-derived candidate IDs, substitution records, rationale, compatibility questions and preservation checks. Every `yield_percent` is null. There is no candidate availability lookup, chemical-name generation or experimental result generation. IDs depend on canonical graph serialization and are not registry identifiers.

Review and select candidates before drawing. Convert each selected candidate explicitly to a `draw` record: `compound_id` from an assigned ID or `candidate_id`, `label` from a reviewed label, and `smiles` from `canonical_smiles`. Do not pass `mapped_smiles` into `draw`, whose strict graph interface rejects atom-map annotations. No implicit proposal-to-production side effect runs.

### Explicit scans on substituted and heteroaromatic rings

```sh
uv run --extra chemistry chemdraw-mac scan-scope --manifest examples/scope-custom.json
```

The manifest has `schema_version: 1`, `parent_smiles`, `site_atom_maps`, `substituents` and optional `include_parent` (default true). MCP `chemdraw_scan_scope(parent_smiles, site_atom_maps, substituents, include_parent=True)` uses the same offline implementation.

Each map must identify a unique H-bearing aromatic carbon. Supported selected rings are isolated neutral non-isotopic five/six-membered aromatic C/N/O/S rings; existing substituents remain present. Sites can span independently isolated rings in the connected parent. Choose a nonempty unique list from `Me`, `OMe`, `CF3`, `CN`, `NO2`, `F`, `Cl`, `Br`, `iPr`, `tBu`. Each site/group pair produces one single-substitution candidate. At most 100 combinations including the optional parent are accepted before deduplication.

Labels identify parent atom maps, never inferred systematic positions. Symmetry-equivalent graphs retain `requested_variants`; graph IDs ignore map tags. Parent graph/stereo checks and null yields remain mandatory. Fused rings, arbitrary substituent SMILES and automatically chosen sites are unsupported. [Full expanded scope contract](SCOPE_EXPANDED.md)

## Draw native structures from SMILES

Create a manifest such as:

```json
{
  "schema_version": 1,
  "preset": "house",
  "columns": 2,
  "pixels": 3200,
  "structures": [
    {"compound_id": "a", "label": "Ethanol", "smiles": "CCO"},
    {"compound_id": "b", "label": "Acetone", "smiles": "CC(=O)C"}
  ]
}
```

Then run:

```sh
uv run --extra chemistry chemdraw-mac draw \
  --manifest /absolute/path/structures.json \
  --output /absolute/existing/parent/structures-review
```

MCP `chemdraw_draw_structures(structures, output_dir, preset='house', columns=None, pixels=3200, scaffold_smiles=None, layout=None, charge_style='plain')` calls the same workflow. CLI `schema_version` must be `1` when supplied. Unknown manifest/record fields are rejected; the output directory must be new and absolute with an existing parent.

Optional `charge_style: "circled"` adds native symbols for existing +1/-1 atom charges after the measured grid. At most 50 charge symbols are accepted. Geometry, charge ownership and chemistry are verified after native saving; crowded arrangements fail without silently changing charge style or molecular scale. [Ionic example](../examples/ions-circled.json), [placement limits](SYMBOLS.md). `styled-job` draw recipes accept the same option. Follow returned `artifacts.cdxml`, `artifacts.svg` and `artifacts.png` paths: plain outputs live under `figure/`, while a successful added-charge pass lives under `charged/`. The `grid_audit` describes the pre-charge layout, not a current atom-ID inventory; inspect the final document for current IDs.

| Input | Limit |
|---|---|
| `structures` | 1 through 24 explicit records in requested order |
| Each record | Exactly `compound_id`, `label`, `smiles`; no yield field |
| `compound_id` | Case-insensitively unique; 1 through 32 ASCII letters/digits/periods/underscores/hyphens, starting with a letter/digit |
| `label` | Caller-supplied nonblank text, at most 120 characters, no control characters |
| `smiles` | Strict identifier syntax; one connected nonradical graph with 2 through 150 atoms |
| Elements | H, B, C, N, O, F, Si, P, S, Cl, Br and I |
| `preset` | `house` by default, `acs-1996`, or a validated custom style object |
| `columns` | Null/omitted for measured automatic selection, or integer 1 through structure count |
| `pixels` | Integer longest PNG side, 256 through 8192; default 3200 |
| `scaffold_smiles` | Null/omitted, or an explicit connected nonradical core with 3 through 150 heavy atoms and no explicit H nodes; strict SMILES syntax, not SMARTS |

Labels are not checked against molecule names. Isotope, explicit-H and supported tetrahedral/E/Z identity must survive the MOL/native roundtrips or production fails. Disconnected salts and radical graphs are outside `draw`, even though `identify` can inspect them and `grid` can accept some pre-existing disconnected drawings. Plain formal-charge atoms are permitted if the remaining native parser and preservation checks accept them; this is not support for creating arbitrary circled-charge graphics or organometallic drawings.

### What produces the drawing

1. Strictly parse every supplied SMILES and check the supported creation subset. If a scaffold is supplied, check its presence and supported stereochemical compatibility in every structure before any native call.
2. Write a validated MOL coordinate seed using RDKit, retaining supported identity.
3. Import a private seed copy into ChemDraw and verify its saved identity.
4. Run native Clean Up Structure on that private document and verify identity again.
5. Positively normalize the saved native fragments; optionally rigidly align the explicit scaffold to the first structure. Stage the molecules in nonoverlapping uniform cells with explicit owned labels, remapping object IDs and applying the requested style.
6. Use the existing native-measured grid workflow for scale, label placement and page-fit checks, then export the native result.

RDKit is not merely a validator in this workflow: it supplies the coordinate seed. It is still not the exported figure renderer. Cleanup and output rendering happen in desktop ChemDraw. Without `scaffold_smiles`, native cleanup can choose different orientations for related molecules. There is no automatic common-core inference or prescribed sugar orientation. Once measured native structures enter the grid stage, the grid preserves their orientations while normalizing scale and placing them.

The composition retains page settings from the first native import instead of asserting a custom paper size from a CDXML bounding box. Positive preset-scale normalization precedes initial fit calculations. Native molecular bounds and conservative label-width estimates determine nonoverlapping uniform staging cells before composition import; structures are not overlaid at the page centre. Native saved page bounds determine final measured grid-fit acceptance. Long labels or large layouts can fail instead of being silently shrunk. This conservative preflight may reject a label that a manually arranged drawing could accommodate. Page resizing, name wrapping, reaction arrows and yield labels are not part of this command. Molecular identity, bounded atom-label checks and grid bounds do not certify every rendered glyph or intramolecular collision.

For an included proposal-to-drawing example, use `examples/acetophenone-scope-draw.json` as the manifest. Its fourteen explicit structures use short labels relative to the acetophenone parent, three columns, `"scaffold_smiles": "CC(=O)c1ccccc1"` and no yields. The source is an illustrative candidate selection, not a dataset of tested substrates or outcomes.

### Optional explicit-scaffold orientation

Add `scaffold_smiles` as a top-level manifest field, or pass the same MCP argument. Choose a core present in every record, including any substituent or reaction handle whose correspondence matters. The ethanol/acetone example above does not provide a suitable common core; the acetophenone manifest does.

The first structure's cleaned, preset-normalized native coordinates define the reference. Alignment uses only proper rigid rotation and translation, never reflection, internal-coordinate changes or scaling. Preset scale normalization is a separate earlier step. Native scaffold coordinates must be noncollinear, and the best rigid fit must have RMSD at most 0.25 pt. A geometrically incompatible core fails instead of being distorted. Native reimport/save supplies fresh label measurements before final grid acceptance; visual review is still required.

Scaffold matching respects supported specified chirality and rejects inputs reaching the 1,000-match limit. The reference uses the first lexicographic decoded atom-index match. Target matches minimize RMSD; ties within 0.000001 pt prefer the smallest absolute rotation, then signed angle and atom-index tuple. These are deterministic drawing choices for symmetric cores, not inferred chemical correspondence for substituents outside the explicit core. A more specific core can reduce ambiguity. No atom mapping is guessed, and no collision-free layout or canonical ring orientation is promised.

The draw audit records matched native atom IDs, rotations, translations, scaffold RMSDs and internal-distance preservation under `alignment`. The alignment-enabled path passed two live draw/MCP tests and the fourteen-candidate CLI example on the development Mac. The latter was visually inspected; median bond lengths ranged from 18.0 to 18.001336 pt, and the largest normalized scaffold-fit RMSD was 0.0026354 pt. This is fixture-specific native evidence, not a general collision or cross-version certification. See the progress log for run details.

### Output and recovery

The bundle includes `request.json`, `audit.json`, `review.html`, retained input MOL/native snapshots under `seeds/`, `combined.cdxml`, `combined-native.cdxml`, and the normal grid bundle under `figure/`. Final files are `figure/figure.cdxml`, `figure/figure.svg` and `figure/figure.png`. The nested grid audit reports native scale, ownership, alignment and page-fit checks.

Successful intermediate private documents are closed with backups; the final document remains open. Pre-existing document inventory, metadata and exported unsaved contents are compared before acceptance. Native-operation errors stop without retrying or automatically closing an uncertain copy. Failed/uncertain artifacts remain diagnostic, and `visual_review` stays required. The audit verifies supplied graph preservation, not chemical-name correctness, experimental yields or reaction feasibility. See [project progress](../PROJECT_PROGRESS.md) for actual native test evidence, rather than inferring compatibility from the presence of a command.

### Images and hand sketches

The server has no image-recognition or OCR endpoint. An image-capable connected assistant can interpret a supplied photograph or hand sketch and prepare explicit SMILES after resolving uncertain atoms, bonds, charges and stereo with the user. The same strict graph/native drawing workflow then applies. A valid molecular graph does not establish that the transcription matches the image; that correspondence remains a separate visual/chemical review. No new image service, model or provider is installed by these commands.

## Build an explicit one-step reaction

```sh
uv run --extra chemistry chemdraw-mac reaction \
  --manifest examples/reaction-build.json \
  --output /absolute/existing/parent/reaction-review
```

Add optional `--style /absolute/path/my-style.cds` to override the manifest preset. The example explicitly supplies ethanol, ethanal and `oxidation` above the arrow; it is a composition example with no reagents, experimental conditions or yields inferred.

The manifest contains `schema_version: 1`, `reactants`, `products`, optional `conditions_above`, `conditions_below`, `preset`, `pixels` and `scaffold_smiles`. Each side has one through three exact `{compound_id, label, smiles}` records, with IDs unique across both sides. Each structure uses `draw`'s connected nonradical 2 through 150-atom subset. Standalone one-atom participants and disconnected salts are outside this creation path. Each condition is empty or nonblank single-line text of at most 120 characters.

MCP `chemdraw_build_reaction(reactants, products, output_dir, conditions_above='', conditions_below='', preset='house', pixels=3200, scaffold_smiles=None)` creates the same native row. The explicit core, if supplied, must match every participant. ChemDraw cleans/renders private structures; composition adds one rightward arrow, plus signs, owned captions and conditions. Native measured gaps, role bindings, caption baselines, condition alignment and page fit are checked. No product prediction, balancing, stoichiometry, name verification or inferred experimental outcome runs.

Output includes native `figure.cdxml/svg/png`, `request.json`, `recipe.json`, `audit.json`, `review.html` and retained seeds/snapshots. The final working document stays open. Native uncertainty stops without retry or automatic closure; visual review remains required. [Full reaction contract and evidence boundary](REACTION_BUILDER.md)

## Included example

```sh
uv run --extra chemistry chemdraw-mac polish \
  --input examples/messy-oxidation.cdxml \
  --recipe examples/oxidation-recipe.json \
  --output /absolute/existing/parent/oxidation-review
```

Choose a new absolute output directory with an existing parent; do not create the output directory first. The example illustrates ethanol-to-ethanal oxidation with `[O]`, not an experimental protocol. Its inconsistent presentation is a layout fixture, not research data.

The CLI validates CDXML input before native import, opens a private copy, matches source-file IDs to native IDs if required, and produces a new final document. Its temporary imported source copy is closed, while the final document remains open. File-input polish currently accepts CDXML only. The separate low-level MCP import tool also accepts CDX, MOL and SDF.

## An existing open document

```sh
uv run --extra chemistry chemdraw-mac documents
uv run --extra chemistry chemdraw-mac analyze DOCUMENT_ID
uv run --extra chemistry chemdraw-mac polish \
  --document DOCUMENT_ID \
  --preset house \
  --layout preserve \
  --output /absolute/existing/parent/figure-review
```

Replace `DOCUMENT_ID` with a current listed integer, which may be negative. `analyze` exports a snapshot without editing the source. Its fragment/text/arrow IDs differ from the 1-based molecule indices returned by low-level native inspection. Refresh analysis after manual edits rather than reusing a remembered mapping. Analysis supports the same bounded drawing subset as polish.

## Recipe

`examples/oxidation-recipe.json` matches its included source CDXML:

```json
{
  "schema_version": 1,
  "preset": "house",
  "layout": "row",
  "caption_map": {"1": "10", "20": "30"},
  "condition_map": {"50": ["51"]},
  "gap": 24,
  "label_gap": 14,
  "pixels": 2400
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Currently `1` |
| `preset` | `house`, `acs-1996`, or a validated custom style object in the recipe |
| `layout` | `preserve` or `row` |
| `caption_map` | Fragment ID to its caption text ID |
| `condition_map` | Native arrow ID to condition text IDs, at most one multiline text per side |
| `gap` | Equal gap between main component boxes, in points; minimum 4 |
| `label_gap` | Caption baseline offset below the lowest main component; visible clearance for arrow conditions, in points; minimum 4 |
| `width` | Optional maximum main-row width in points; oversized rows are rejected, not shrunk |
| `pixels` | PNG longest side, 256 through 8192; default 3200 |

Unknown fields and unsupported schema versions are rejected. Recipe `preset`/`layout` take precedence over CLI flags; flags supply defaults only when absent from the recipe. Geometry is in points, not pixels.

Ownership rules:

- For `--input file.cdxml`, recipe IDs belong to that file. Matching accommodates native renumbering; ambiguous matches are rejected.
- For `--document`, use the current `analyze` snapshot IDs. In MCP, use IDs returned by `chemdraw_analyze_document`.
- A label cannot have multiple owners. `preserve` rejects ownership maps; use `row` for annotation movement.
- Row layout retains current left-to-right component order. It does not infer reaction roles or optimize multistep schemes.
- A standalone `+` is a row component. Other free text must be assigned; unassigned captions/conditions are rejected rather than guessed.
- Conditions retain their above/below-arrow side. Only rightward horizontal, noncurved arrows are supported.

The saved `recipe.json` uses the IDs in its accompanying `before.cdxml`; keep them together. A recipe is not portable to arbitrary files that happen to use the same ID numbers.

`width` limits main components and gaps, not every caption or the printed page. Long labels, conditions and page edges need review. Arrow length is preserved rather than automatically expanded to fit condition text.

## What polish does

1. Snapshot and check the supported source chemistry.
2. Apply numerical font/stroke settings and positively scale each fragment to the preset median bond length.
3. Open the normalized copy in ChemDraw, export it and verify its molecular graph.
4. Optionally arrange measured objects into a row with explicitly owned captions and conditions.
5. Export native final artifacts, recheck chemistry and scale, check source preservation and report inter-object box overlaps.

No native cleanup runs automatically. Orientation is not rotated/reflected, and explicit H atoms are retained. Median scale normalization does not straighten distorted individual bonds. Native Clean Up Structure is a separate explicit operation that can change depiction.

Low-level `chemdraw_apply_style` is different: it makes a styled copy without rescaling existing coordinates. A document's bond-length setting alone does not normalize a figure.

## Outputs and acceptance

| Files | Purpose |
|---|---|
| `before.cdxml`, `before.svg`, `before.png` | Native source snapshot and renders |
| `figure.cdxml`, `figure.svg`, `figure.png` | Final editable source and native-derived renders |
| `recipe.json`, `audit.json` | Settings/ownership and verification report |
| `review.html` | Local before/after review and artifact links |

PDF and binary CDX are available through separate low-level `chemdraw_export`, not included in the polish bundle. PNG uses unchanged native SVG rasterized offline with `resvg`, not RDKit. Transparent RGBA dimensions are checked; external SVG resources and unsupported features fail explicitly. Inspect the export on the intended slide/document background.

Audit status:

- `checks_passed`: implemented preservation/scale checks passed and checked inter-object boxes do not overlap.
- `needs_review`: operation completed but box overlaps were detected.
- `failed`: production was interrupted; retained files are diagnostic, not an accepted final figure.

Every audit retains `visual_review: "required"`. A graph match establishes preservation of supported input chemistry, not correctness of names, mechanisms or reactions. Polish's coarse boxes do not comprehensively detect glyph/charge/bond collisions or page overflow. Scope grids additionally check native ink against the saved page region, as described below.

The CLI exits nonzero on exceptions. A completed `needs_review` operation exits zero, so automation must read the audit rather than treating exit status as approval. Failures can leave a partial output directory and backups; use a new output directory for a reviewed retry.

## Analogue editing

`edit` changes an owned copy of one supported molecular fragment. It manipulates CDXML, then uses desktop ChemDraw to save and render the result. It does not call a native atom-setter API, generate fresh coordinates, resolve names or run cleanup. The optional chemistry extra is required.

```sh
uv run --extra chemistry chemdraw-mac edit \
  --input examples/chlorobenzoic-acid.cdxml \
  --recipe examples/bromo-analogue-recipe.json \
  --output /absolute/existing/parent/bromo-analogue-review
```

Use a new absolute output directory whose parent exists. File input accepts CDXML only. The included recipe identifies objects in the included source file:

```json
{
  "schema_version": 1,
  "operations": [{"kind": "atom", "id": "8", "element": "Br", "hydrogens": 0}],
  "captions": {"30": "4-Bromobenzoic acid"},
  "pixels": 2400
}
```

The original file is preflighted before import; source IDs are matched to ChemDraw's imported IDs. The temporary imported copy is closed, while the final analogue stays open. This recipe is not portable to an unrelated document that happens to reuse the same IDs.

### Editing a live document

First run `chemdraw-mac analyze DOCUMENT_ID`, or call `chemdraw_analyze_document`. A supported single molecule receives an `editing` object with atoms, bonds, captions and `source_token`. An `editing.unsupported` result means this editor cannot safely handle the drawing even if other analysis succeeded.

Construct a recipe using those exact atom/bond IDs and add `"expected_source_token": "the returned token"`. Then invoke:

```sh
uv run --extra chemistry chemdraw-mac edit \
  --document DOCUMENT_ID \
  --recipe /absolute/path/live-edit-recipe.json \
  --output /absolute/existing/parent/live-analogue-review
```

MCP tool `chemdraw_edit_document` takes `document_id`, `output_dir`, `operations`, `captions`, `expected_source_token` and optional `pixels`. The token is required for live edits. A changed source is rejected; analyze again and rebuild the selection rather than reusing stale IDs. For file inputs a token is optional and, when supplied, must match the original file snapshot.

### Explicit operations

| Operation | Required fields | Limits |
|---|---|---|
| Atom/H change | `kind: "atom"`, existing string `id`, integer `hydrogens` | H count 0 through 4; optional `element` retains the current element when omitted |
| Bond order | `kind: "bond"`, existing string `id`, integer `order` | Order 1, 2 or 3; existing plain nonaromatic, nonstereo bond only |

Supported atom-edit elements are C, N, O, F, P, S, Cl, Br and I. Both the old and requested elements must be in this set. Charged or isotope-labelled target atoms, radicals, no-op operations and duplicate edit IDs are rejected. Supply 1 through 50 operations. This is not atom insertion/deletion, substituent attachment or an arbitrary reaction engine.

Atom edits always require an explicit attached-hydrogen decision. A bond-order change with stored explicit hydrogen counts on an endpoint also requires an atom/H edit for that endpoint. The validator checks the resulting valence and reports observed hydrogen changes on all atoms. Do not assume that changing a bond label alone expresses a chemically complete transformation.

Existing tetrahedral configuration is mapped by atom identity. Editing a stereocentre or creating/removing potential tetrahedral or alkene stereo is refused. Retained stereo elsewhere is checked, not newly inferred. Coordinates are retained and verified after native export within the documented native rounding tolerance. Changed heteroatom label bounds may be remeasured by ChemDraw, so preserving coordinates does not promise an identical ink bounding box.

Every page caption must occur in `captions`: a string replaces its text, the identical string explicitly retains it, and `null` removes it. Use `{}` only when there are no captions. The editor does not infer the new compound name or preserve a stale parent name automatically. Caption text must be nonempty, at most 500 characters and contain no control characters.

### Edit outputs and verification

The bundle has the same before/after CDXML, SVG, PNG, recipe, audit and HTML filenames as polish. `pixels` defaults to 2400 and allows 256 through 8192. The saved recipe addresses its accompanying `before.cdxml`, including the source token.

The edit audit adds `chemical_diff`, with atom/bond changes, observed hydrogen changes and caption decisions, plus native atom ID mapping and maximum coordinate displacement. Checks distinguish:

- Supported mapped molecular graph and stereochemistry in native saved CDXML.
- Atom coordinates in native saved CDXML.
- Chemical atom-label tokens and caption text in native saved CDXML.
- Preservation of the source document metadata, available disk hash and exported unsaved content.

`native_labels_verified` refers to CDXML label content, not OCR or glyph validation of SVG/PNG. Correct graph and CDXML labels do not establish that every rendered label is correct. The resolved input-label orientation case and its procedural fix are documented in [known issues](KNOWN_ISSUES.md). Inspect before/after exports. No general collision check or automatic label/charge repair runs in this edit workflow. `checks_passed` remains a machine-check result with `visual_review: "required"`; failure outputs are diagnostic.

Offline identifier conversion is available through `identify`; the separate `resolve` command supports opted-in PubChem name/CAS candidates. See [the identifier contract](IDENTIFIERS.md), [resolver semantics](RESOLVER.md) and [upstream research](UPSTREAM_RESEARCH.md).

## Scope grids

`grid` places explicitly assigned compounds in equal-sized cells. It retains molecular orientation, normalizes median bond scale to the chosen preset, preserves existing name captions, and adds caller-supplied compound IDs and optional yields. It does not resolve names, infer compound numbering, align common scaffolds by rotation, or generate experimental results. The optional chemistry extra is required.

```sh
uv run --extra chemistry chemdraw-mac grid \
  --input examples/scope-input.cdxml \
  --recipe examples/scope-recipe.json \
  --output /absolute/existing/parent/scope-review
```

Choose a new absolute output directory whose parent exists. File input accepts CDXML only. It validates and freezes the original bytes before native creation, creates a private document from that frozen text rather than reopening a mutable source pathname, and remaps source-file IDs to the native copy. The final grid stays open; intermediate working documents are closed with backups after determinate outcomes. **The included eight-compound recipe contains invented percentage values for software testing, not research data.**

### Grid recipe

The minimal shape below illustrates a two-cell recipe. IDs must belong to your actual input; it is not a recipe for the eight-compound example:

```json
{
  "schema_version": 1,
  "preset": "house",
  "columns": 2,
  "cells": [
    {"compound_id": "3a", "fragment_ids": ["1"], "caption_id": "10", "yield_percent": 0},
    {"compound_id": "3b", "fragment_ids": ["20"], "caption_id": "30", "yield_percent": null}
  ]
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Currently `1` |
| `cells` | 1 through 100 compounds in requested row-major order |
| `preset` | `house` by default, `acs-1996`, or a validated custom style object |
| `columns` | Integer from 1 through compound count; omitted or `null` selects the maximum fitting column count from measured cell width |
| `width`, `height` | Optional layout-region limits in points, within the saved page and margins; default is available saved-page size |
| `margin` | Inset from saved page bounds, default 36 pt; nonnegative |
| `h_gap`, `v_gap` | Gaps between uniform cells, default 18 and 24 pt; minimum 4 pt |
| `label_gap` | Visible clearance below the common molecular region, default 10 pt; minimum 4 pt |
| `pixels` | PNG longest side, default 3200; 256 through 8192 |
| `expected_source_token` | Required for live-document grids; optional for file input, where it must match the original file snapshot if supplied |

Each cell has a unique `compound_id` of 1 through 32 characters, beginning with an ASCII letter or digit and otherwise using letters, digits, periods, underscores or hyphens. `fragment_ids` is a nonempty list of string IDs. Every molecular fragment must belong to exactly one cell.

`caption_id` is an existing page-text ID or `null` if the compound has no existing name caption. Every page-text object must belong to exactly one cell. At most one existing caption belongs to a cell. Free headings, standalone plus signs and unrelated annotations are not guessed or dropped; remove them from a working source or use another workflow. Existing caption text is retained, not regenerated from the structure.

`yield_percent` is a finite numeric percentage from 0 through 100, or `null`/omitted. Zero remains visible as `0%`; a missing value displays only the compound ID. Strings such as `"82%"`, booleans and out-of-range values are rejected. These values are caller-supplied labels and are not experimentally validated.

Multiple fragments may belong to one compound, for example disconnected counterions. Each fragment is normalized first; subsequent grid placement applies one shared translation to all fragments of that compound. This is not a salt-layout optimizer and does not promise to preserve pre-normalization fragment separation exactly.

### Gridding a live document

Run `chemdraw-mac analyze DOCUMENT_ID` or `chemdraw_analyze_document`. Use the current fragment/text IDs and the report's **top-level `source_token`** to construct the recipe, including `expected_source_token`:

```sh
uv run --extra chemistry chemdraw-mac grid \
  --document DOCUMENT_ID \
  --recipe /absolute/path/live-grid-recipe.json \
  --output /absolute/existing/parent/live-scope-review
```

The top-level token is available for supported multimolecule analysis. The analogue editor's older `editing.source_token` field may also exist for a supported single molecule and has the same value, but grids do not require the `editing` object. Changed snapshots fail before production; analyze again rather than reusing stale IDs.

MCP `chemdraw_grid_document` takes `document_id`, `output_dir`, `cells`, `expected_source_token` and the optional preset/geometry/export fields above. `schema_version` belongs to the CLI recipe, not the MCP tool arguments. Saved `recipe.json` addresses its accompanying `before.cdxml`, including the snapshot token. Keep those artifacts together.

### Measurement and acceptance

The workflow styles and normalizes a private copy, asks desktop ChemDraw to save native bounds, then computes cell dimensions from molecular ink, existing caption ink and newly generated metadata ink. All cells use the same width and height. Within each row, molecular regions share a centre line, name captions share a baseline, and compound/yield labels share another baseline. Positions preserve recipe order rather than sorting names or yields.

Automatic columns use measured cell width; they do not change page size or shrink molecules. If the requested grid does not fit the available width and height, production fails. Long names count toward cell width. Use a suitable page, fewer or more columns as appropriate, or shorter captions; the tool does not wrap names automatically to force a fit.

The bundle contains the same before/after CDXML, SVG, PNG, recipe, audit and HTML files as polish. The grid audit checks mapped molecular chemistry and stereo, normalized bond scale, native atom coordinates against the planned transformation, compound/yield bindings, caption anchors and visible horizontal ink centres, inter-object overlaps, saved-page fit and source preservation. Native coordinate matching tolerates rounding; visible caption centring has a 0.75 pt tolerance.

File-input grids additionally retain the exact frozen original as `source-input.cdxml`. The audit records `source_file`, `source_file_sha256`, `source_snapshot` and `checks.source_file_unchanged`. The original filename and file bytes are not rewritten. Mutation or disappearance detected during production fails the result and retains a diagnostic audit/snapshot. Native-operation uncertainty stops without retries or automatic closure of the imported source; an uncertain source-close result also downgrades the audit to `uncertain` instead of leaving an apparent success.

Grid acceptance is stricter than polish's optional row layout: an overlap, unowned native object, changed binding or ink outside the requested saved-page region fails production. Successful results report `checks_passed`; failed artifacts are diagnostic. `visual_review` remains `required`. Native bounding boxes do not establish that every intramolecular glyph, bond or charge is collision-free, nor do they certify printer margins or experimental correctness.

Supported input is one flat, single physical page containing molecules and owned captions only. Reactions, nested groups, page graphics and native symbol graphics inside molecules are rejected. Plain formal-charge atom attributes are supported, including a live-tested disconnected sodium/chloride example; native circled-charge symbol graphics are a different, unsupported object type for this workflow. No cleanup or automatic reorientation runs.

## Scope frames and grouped separators

After arranging the intended compound groups into horizontal bands, add an editable frame and dotted dividers to a new copy:

```sh
chemdraw-mac decorate-scope --input /absolute/scope.cdxml --recipe groups.json --output /absolute/new-framed-scope
```

The recipe supplies `groups`, each with `label`, `fragment_ids` and `caption_ids`, assigning every molecule and page caption exactly once. Empty labels add only the visual framing; nonempty headings need free space above their bands. `frame` and `separators` default to true and can be disabled independently. MCP exposes the same operation as `chemdraw_decorate_scope` using an explicit document ID and current source token.

This is an optional finishing pass, not automatic electronic classification, rearrangement or experimental annotation. The existing structures, labels and positions are preserved. Frame, shadow, actual round dots and headings are native editable objects. Details, page-fit checks and limits: [scope decoration](SCOPE_DECORATION.md).

## Batch export

`batch` exports existing, supported CDXML drawings sequentially through desktop ChemDraw. It makes no requested style, layout or chemistry changes. The optional chemistry extra is required for preservation checks; it does not render the output.

```sh
uv run --extra chemistry chemdraw-mac batch \
  --manifest /absolute/path/figures.json \
  --output /absolute/existing/parent/manuscript-figures
```

Choose a new absolute output directory with an existing parent. A manifest contains explicit sources rather than a folder glob:

```json
{
  "schema_version": 1,
  "pixels": 3200,
  "items": [
    {"key": "scheme-01", "source": "/absolute/path/reaction.cdxml", "formats": ["pdf", "cdx"]},
    {"key": "figure-02", "source": "/absolute/path/compounds.cdxml"}
  ]
}
```

Supply 1 through 100 items in the requested export order. Each `key` is 1 through 64 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit; uniqueness is case-insensitive. Each `source` must be an absolute path to an existing UTF-8 CDXML file of at most 10 MB. Relative sources, globs and arbitrary output filenames are not accepted. Sources are resolved and read before native import.

Native CDXML/SVG and native-derived PNG are always included. `formats` optionally adds `pdf` and/or `cdx`; listing any default format again is harmless and duplicates are removed. Unsupported formats and unknown fields are rejected. `pixels` controls PNG longest side, default 3200 and range 256 through 8192. Manifest `schema_version` defaults to `1` when omitted; other versions are rejected.

MCP `chemdraw_batch_export` takes `items`, `output_dir` and optional `pixels` with the same behavior. `schema_version` is a CLI manifest field, not an MCP argument. This tool accepts file paths, not live-document IDs.

### Batch artifacts and status

```text
manuscript-figures/
  manifest.json
  audit.json
  review.html
  scheme-01/
    scheme-01.cdxml
    scheme-01.svg
    scheme-01.png
    scheme-01.pdf
    scheme-01.cdx
    audit.json
    snapshots/
      source.cdxml
      post-export.cdxml
```

The item snapshot directory keeps the frozen input separate from named exports, including a figure whose key is `source`. PDF/CDX files appear only when requested. Failed items can have partial artifacts; rejected or not-run items may have no item directory. The top-level audit records every input and its status. `review.html` shows available previews, artifact links and errors; it is not an approval certificate.

| Item status | Meaning |
|---|---|
| `rejected` | Input missing or unsupported during preflight; valid other items can still run |
| `failed` | A deterministic preservation or local processing check failed; later items can run |
| `exported` | Requested exports and implemented checks completed |
| `uncertain` | A native operation errored, including an uncertain close; inspect the application and retained artifacts |
| `not_run` | A previous uncertain native operation stopped further items |

An in-progress audit can also contain `pending` and `in_progress`. Batch status is `completed` only if every item exported and final pre-existing-document checks passed; otherwise it is `partial_failure` or `interrupted`. The CLI exits zero only for `completed`. Read the audit even on success: every output still requires visual review.

Any native-operation exception is treated conservatively as uncertain. The operation is not retried, later items are stopped, and the uncertain working document is not automatically closed. Other successful or deterministically failed private working copies are closed with recovery backups. Never interpret a partial PNG or PDF as an approved result.

### Batch preservation boundary

Before production, source bytes are frozen and hashed. Hashes are checked before and after each item's exports. Native saved CDXML is checked for mapped supported chemistry/stereo, atom positions, caption text/anchors, arrow endpoints and supplied arrow properties. Explicit source reaction-scheme roles/references must survive native renumbering. ChemDraw may infer scheme metadata when none was supplied; that inferred chemistry is not certified. Native working-document content is compared before and after rendering.

The workflow also snapshots pre-existing open documents and compares their metadata, exact document-ID inventory and exported unsaved content at the end. Window/export-only metadata is excluded from content comparison. These recovery snapshots stay in the bridge workspace backups, not in the batch contact sheet. The feature does not prevent another process or user from making concurrent changes, and an interrupted run may leave preservation unverified.

Batch supports the bounded flat, single-page CDXML subset with molecular fragments, text, arrows, specifically supported native arrow-fallback graphics and reaction-scheme metadata. It also accepts the annotation workflow's restricted single-cubic full/left-half/right-half curves and circled plus/minus graphics with explicit matching atom-charge references. These objects are checked with the existing annotation verifier as well as the ordinary batch graph/position/reaction checks. Supported SN2 annotation output can therefore be included in a batch manifest. Unknown curve shapes, symbols or unsupported properties, groups, nested abbreviations, polymers, queries and other molecular/atom annotations remain rejected. Plain formal-charge attributes and graphical circled symbols are distinct checks. Successful low-level import alone is not evidence that arbitrary graphics are supported.

No restyling, collision repair, automatic mechanism validation, source-name verification or exhaustive glyph/font/stroke comparison runs. Inspect final exports at their intended display size. This workflow packages existing supported figures; use polish or grid first when those transformations are explicitly wanted.

## Electron-flow annotations

`annotate` adds native editable cubic curves to a new working copy, with either full two-electron heads or one-electron fishhooks. Each tail requires an explicitly selected displayed donor symbol or donor bond; bare atom sources are rejected. It does not alter molecular graphs, charges, radical states, existing atom positions or existing charge placement. There is no automatic mechanism interpretation, curve routing or new lone-pair/radical-dot creation. The optional chemistry extra validates preservation; desktop ChemDraw saves and renders the copied CDXML.

Reproduce the included SN2 annotation example:

```sh
uv run --extra chemistry chemdraw-mac annotate \
  --input examples/sn2-annotation-input.cdxml \
  --recipe examples/sn2-annotation-recipe.json \
  --output /absolute/existing/parent/sn2-review
```

The input and recipe are a matched pair from the native house-style SN2 reference. The file path is CDXML only. The new absolute output directory must have an existing parent and must not already exist. Source bytes, output arguments, recipe and supported geometry are validated before native creation. Labelled atom targets require measured `BoundingBox` data in the source file; if absent, inspect a native document and use the live-document route below. The file workflow does not invent label bounds.

### Inspect and annotate a live drawing

```sh
uv run --extra chemistry chemdraw-mac inspect-annotations DOCUMENT_ID
uv run --extra chemistry chemdraw-mac annotate \
  --document DOCUMENT_ID \
  --recipe /absolute/path/annotation-recipe.json \
  --output /absolute/existing/parent/mechanism-review
```

Use `chemdraw_inspect_annotations` in MCP for the same inventory: atom IDs, elements, positions, chemical labels and available native label bounds; bond IDs with their endpoints; existing curve IDs, heads and points; and a `source_token`. This specialized inspector accepts the supported existing curves and circled-charge graphics that the ordinary `analyze` workflow does not accept. It exports a snapshot without editing the source.

Build the recipe using those current IDs and set `expected_source_token` to the returned token. The live route requires the token and rejects stale snapshots. File input optionally accepts a token for its original source; native IDs are mapped after import. Do not reuse IDs from an unrelated drawing or after manual edits. The saved recipe addresses its accompanying `before.cdxml`, which may use ChemDraw-renumbered IDs.

MCP `chemdraw_annotate_document` takes `document_id`, `output_dir`, `arrows`, `expected_source_token`, optional `line_width` and optional `pixels`. CLI `schema_version` is not an MCP argument.

### Annotation recipe

This example uses IDs from the included SN2 source and adds its attack arrow:

```json
{
  "schema_version": 1,
  "line_width": 0.9,
  "pixels": 3200,
  "arrows": [
    {
      "key": "nucleophilic-attack",
      "electrons": 2,
      "source": {"kind": "symbol", "id": "1500"},
      "target": {"kind": "atom", "id": "2103", "offset": [0, -14]},
      "controls": [[0, -33], [0, -28]]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `schema_version` | CLI recipe version, currently `1`; unknown versions/fields are rejected |
| `arrows` | 1 through 50 explicit curves, appended while retaining supported existing curves |
| `key` | Unique per request; 1 through 64 ASCII letters, digits, underscores or hyphens, starting with a letter/digit |
| `electrons` | Integer `2` for a full head or `1` for a fishhook |
| `fishhook_side` | `left` by default or `right`; may be supplied only when `electrons` is `1` |
| `source`, `target` | A source is a bond with exactly `kind`, `id` and `offset`, or a displayed donor with exactly `kind: "symbol"` and an existing symbol `id`, with no offset. A target is an atom or bond with exactly `kind`, `id` and `offset`. Atom sources and symbol targets are rejected |
| `offset` | Finite `[dx, dy]` in page points, each coordinate from -36 through 36; relative to the target atom position or source/target bond midpoint |
| `controls` | Two finite `[dx, dy]` control offsets, each coordinate from -200 through 200; first relative to the curve start, second relative to the curve end |
| `line_width` | Width for the new curves, default 0.9 pt; finite 0.2 through 3 pt |
| `pixels` | PNG longest side, default 3200; integer 256 through 8192 |
| `expected_source_token` | Required for live input, optional for file input |

These are page coordinates: positive x goes right, positive y goes down. Endpoints must be at least 1 pt apart and control tangents cannot be degenerate. Half-head sides select native `HalfLeft`/`HalfRight` rendering; they do not assert a chemically valid radical mechanism. The half-head regression fixtures use explicitly selected bonds to test rendering, not alternative SN2 chemistry. A negative-charge donor cannot be converted to a fishhook by changing the electron count.

An atom target must lie outside its own measured label box expanded by 1 pt on all sides. An unlabelled atom target instead requires at least 1 pt endpoint displacement from its position. A bond endpoint is computed from its midpoint plus the supplied offset. This is not a general collision check: the whole curve and arrowhead can still intersect bonds, charge symbols, unrelated labels, other curves or page edges. Offsets and controls are explicit inputs requiring visual review.

For a displayed donor symbol, `source` must be exactly `{"kind": "symbol", "id": "ACTUAL_SYMBOL_ID"}` with no offset. `CircleMinus` and `LonePair` require `electrons: 2`; `Electron`, including the graphical filled-circle form, requires `electrons: 1`. A neutral atom donor needs an explicitly displayed lone pair first; there is no atom-label fallback. Positive charges and symbol targets are rejected. The first control vector must be nonzero and determines departure direction. The tail starts at the visible edge calibrated from ChemDraw 23.0.1 SVG exports; for a lone pair it selects the outward dot, not the gap between dots. Native source-arrow integration cases passed on the development Mac, but each complete path and its optical appearance still require visual review. A negative charge is a donor source only when explicitly selected; bond donation still uses a bond source. [Symbol-source contract](SYMBOLS.md), [mechanism conventions](MECHANISM_CONVENTIONS.md)

### Supported annotations and output

Supported existing curves are single cubic segments with full, left-half or right-half heads and the implemented solid-head/no-fill style. Molecular graphics accept circled plus/minus symbols with an explicit matching atom-charge reference, native lone pairs, and the bounded graphical electron subset. A lone pair may own a native `represent attribute="Radical"` reference only to its same-fragment nonradical atom, without changing atom Radical state. New electron dots use strict native black `Oval` / `Circle Filled` graphics, not radical-state Electron Symbols; existing unassociated Electron Symbols are accepted only without chemistry changes. Unknown properties, unsupported associations and nonfinite/nonpositive dimensions fail closed. Annotation retains these objects; new symbols use the separate symbol-copy workflow. Other supported page content includes text, reaction arrows, their native fallback graphics and reaction-scheme metadata.

The bundle contains `before.cdxml/svg/png`, `figure.cdxml/svg/png`, `recipe.json`, `audit.json` and `review.html`. Native saved verification checks mapped chemistry/stereo and atom coordinates, existing charge-symbol counts/associations/geometry and supported styling, and curve counts/head types/control points and supported styling. The audit records the explicit source/target IDs and geometry. These recipe associations do **not** establish native moving attachment: moving an atom later in ChemDraw is not guaranteed to move its curve.

The original document is checked through its exported content token, metadata and available on-disk hash. File input also records and rechecks the original byte hash. Its private imported source is closed after a determinate result; the final annotated copy remains open. Unknown native-operation outcomes stop without retries or automatic closure of the uncertain copy. Audits distinguish `checks_passed`, `failed` and `uncertain`; partial artifacts are diagnostic. `visual_review` always remains `required`, and no check certifies chemical plausibility, radical states, all glyphs or complete collision avoidance.

Batch export reuses this restricted annotation-preservation support, so a supported annotation result can be exported through a normal explicit batch manifest. Batch does not add arrows, reroute them or repair collisions. Scope grids, `draw` and polish do not gain support for these graphical objects; use only workflows whose documented subset includes the actual drawing.

## Electron and charge symbols

```sh
uv run --extra chemistry chemdraw-mac inspect-symbols DOCUMENT_ID
uv run --extra chemistry chemdraw-mac symbols \
  --document DOCUMENT_ID --recipe /absolute/path/symbols.json \
  --output /absolute/existing/parent/symbol-review
```

Alternatively use `--input /absolute/path/source.cdxml` instead of `--document`. MCP `chemdraw_inspect_symbols(document_id)` supplies supported atom/symbol geometry and a current source token. `chemdraw_add_symbols(document_id, output_dir, symbols, expected_source_token, span=None, line_width=None, clearance=2, pixels=3200)` makes the corresponding copy.

A recipe contains `schema_version: 1`, a `symbols` list and the live `expected_source_token`; optional fields are `span`, `line_width`, `clearance` and `pixels`. Each of 1 through 50 records is exactly `{key, kind, atom_id}`, using an existing string atom ID, a unique safe key and `kind` of `charge`, `lone_pair` or `electron`. A charge request requires an existing formal +1 or -1 and rejects an already-associated charge symbol. A canonical elemental/H label's redundant terminal charge suffix is transferred to the circle so ChemDraw does not double-count it; atom charge stays unchanged. Lone pairs use native LonePair symbols with a checked nonradical-atom association. Electron requests use native filled-circle annotations, explicitly reported as `native_representation: "filled_circle_annotation"`, because ChemDraw's nearby Electron Symbol would set Radical state. Neither path authorizes chemical radical-state edits.

Placement uses native-measured label bounds and calibrated visible circles against atom positions, bond centre-line segments with a configured stroke allowance, labels, page-object bounds and existing symbols. Search is bounded at 36 pt from the target atom. It does not test every rendered wedge/double-bond outline or certify a whole arrow path. `span` is charge-equivalent size, default 0.75 times label size, permitted 2 through 24 pt; lone-pair handle span is `span/3` and graphical electron radius is `2*span/27`, giving matching dot sizes. `line_width` is requested visible charge stroke, default document width, permitted 0.2 through 3 pt; native graphic LineWidth is divided by 0.8 to compensate for measured ChemDraw 23.0.1 rendering. Clearance is 1 through 12 pt, default 2, with an additional 0.05 pt native-quantization allowance. No valid bounded placement is an error, not permission to overlap a label. Geometry/styling and source chemistry are checked after native saving; chemical intent and every glyph collision are not certified.

The output contains before/after CDXML/SVG/PNG, recipe, audit and HTML review. File input retains source evidence and detects source changes; live input requires a fresh token. No retry or automatic close follows an uncertain native operation. Four native MCP integration cases passed on the development Mac: negative-charge creation, lone-pair creation plus a source arrow, graphical-electron creation plus a fishhook, and an existing negative-charge source arrow. These are ChemDraw 23.0.1 results, not a cross-version or universal-molecule guarantee. Consult [symbol support](SYMBOLS.md), [electron-flow conventions](MECHANISM_CONVENTIONS.md) and the progress log. Symbol insertion itself does not infer or add mechanism arrows, and native moving attachment is not promised.

## Recovery and concurrency

Existing outputs are refused. Imports are private copies because ChemDraw can autosave opened files. Draw creates private structures; polish, edits, grids, annotations and batch export preserve the original. Low-level cleanup explicitly edits its target after backup, while `draw` cleans only its own private imports. Only documents opened by the current bridge session can be managed-closed, and another CLI process does not inherit that registry.

Updated clients share a per-user process lock across workspaces. A competing call waits at most two seconds, then returns busy without dispatching its native command. Do not edit concurrently by hand or through older/uncooperative clients. A native timeout is different from lock contention: an AppleEvent write may have completed without returning its result. Inspect the application and refresh document state first. See [coordination](NATIVE_COORDINATION.md).
