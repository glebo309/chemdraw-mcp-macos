# Product roadmap

Working plan, updated 2026-09-15. The repository is public and experimental, not a stable release. The current README and test results describe implemented support.

## Current molecule-first priorities

Reliable editable molecules and reactions take precedence over charts, presentation panels or decorative graphics. Per-user cross-process coordination is implemented. Opt-in native circled charges now require safe owner geometry and final native graph/association checks. Independent-Mac acceptance and remaining crowded-symbol limitations are next. Original project code is now licensed under AGPL-3.0-only.

The next chemistry expansion is explicit metal coordination: distinguish coordinate bonds, formal charges and oxidation-state labels; preserve supplied spatial geometry; test bounded square-planar, tetrahedral and octahedral depictions. Do not infer cis/trans, fac/mer or absolute metal stereochemistry from an ambiguous name or flat sketch. General metal-complex creation and 3D geometry are not implemented.

Visual references include the [Baran lab seminar collection](https://baranlab.org/seminars/), Yuzuru Kanda's [Classics in Semisynthesis](https://baranlab.org/wp-content/uploads/2017/06/Classics_in_Semisynthesis-Kanda2017.pdf), and Tian Qin's [Bimetallic Complex in Organic Synthesis](https://baranlab.org/wp-content/uploads/2026/08/Qin_Sept_15.pdf). Inspected pages illustrate conserved scaffold orientations, clear wedges/hashes, compact substituent labels and explicit metal coordination. These are design references, not copied repository artwork or proof of implementation support.

## Product promise

Describe a change, inspect a preview, and receive an editable native ChemDraw figure with an explicit record of what changed and what was verified. The first audience is Mac chemists who already use ChemDraw, not users seeking another generic molecular image generator.

## v0.9 approved production layer

All four approved increments are implemented through CLI and MCP: complete explicitly accepted scope jobs, bounded explicit reaction series, ownership-aware copy movement with selected route suggestions, and portable versioned numerical lab styles. Current native evidence and exact acceptance results are recorded in PROJECT_PROGRESS.md, not inferred from portable tests.

The scope job produces actual category bands. Reaction series retain supplied components and coefficients without balance or mechanism prediction. Ownership sidecars govern tool-controlled moves, not manual dragging; reaction schemes reject vertical movement because native role inference can discard reactants. Route proposals require explicit anchors and selection. Style packages lock actual supported workflow settings and retain their hash with each result.

The remaining broad capabilities below are not silently included: arbitrary nested/multipage editing, native manual-drag arrow attachment, automatic scaffold/chemistry inference and an additional naming provider. Independent-Mac acceptance and package publication remain pending. Use the [demo](DEMO_WALKTHROUGH.md), [release checklist](RELEASE_CHECKLIST.md), and [report template](BUG_REPORT_TEMPLATE.md) for handoff preparation.

## First deliverable: repair an existing figure safely

The current implementation target is deliberately narrower than arbitrary document editing:

- Diagnose the local ChemDraw connection from the terminal or MCP.
- Inspect a supported flat, single-page CDXML figure.
- Normalize physical molecular scale and typography without changing chemical attributes or reflecting structures.
- Preserve existing placement by default; allow an explicitly requested row layout with caller-owned captions/arrow conditions.
- Write a new working copy, obtain a real native preview and exports, and compare the saved chemistry with the input when the optional validator supports it.
- Return a change report with limitations, paths and measurable checks. Never report an unavailable check as passed.

Acceptance is a user-visible before/after artifact, not merely a collection of internal functions. Tests must include rejection cases and demonstrate that the original file and unrelated open documents were not modified. No broad cleanup fallback when the safe parser rejects a document.

## Next: finish the preservation contract

| Capability | Acceptance gate |
|---|---|
| Persistent annotation ownership | v0.9 sidecars provide bounded explicit tool moves; manual-drag coupling and independent cross-owner rerouting remain unimplemented |
| Native bounding-box feedback | Final caption gaps and condition centering measured after native rendering; no atom-only box reported as the visible molecular extent |
| Chemistry-aware fixtures | Sugars, bridgeheads, E/Z, unspecified stereo, isotopes, charged fragments, enhanced stereo and explicit H survive native save or return a precise unsupported result |
| Nested groups and multipage figures | Complete object/reference inventory; parent transforms tested; no lost page content |
| Cross-process coordination | Two clients cannot race on the same ChemDraw document; stale snapshots are detected before writes |
| Recovery after timeout | Do not retry uncertain native writes automatically; reconcile document state and expose recovery artifact |
| Reproducible recipe | Replaying on the same source and supported environment yields the same planned geometry and documented native differences |

## Then: chemistry-aware editing people will use daily

The first bounded copy-and-modify increment is implemented in 0.3.0: explicit neutral atom/H changes and ordinary bond-order edits on one fragment, with native mapped-chemistry/coordinate checks and caption decisions. Version 0.4.0 adds explicitly owned scope grids with native measured cell sizes, caller-supplied compound IDs/yields, disconnected components and saved-page fit. Current additions expose offline graph identifiers, standard aromatic candidate proposals and explicit-SMILES native drawing through CLI and MCP. Implemented boundaries and remaining extensions are distinguished below. See [naming research](NAME_CONVERSION_RESEARCH.md) and [layout/workflow research](LAYOUT_WORKFLOW_RESEARCH.md) for evidence and candidate implementation order.

1. **Copy and modify a scaffold.** Resolve atom mappings explicitly, preserve unaffected coordinates, and return a chemical diff. Start with a small, tested substitution API rather than arbitrary executable scripts.
2. **Expand reaction layout and scope grids.** The bounded row and grid workflows retain existing orientation, normalize bond scale and align owned labels. Grids additionally keep logical salt components together after normalization and enforce measured page fit without shrinking. Version 0.5.0 adds sequential native batch export and a contact sheet for explicit supported CDXML files. Version 0.7.0 adds opt-in rigid alignment to an explicit common scaffold during new drawings. Automatic scaffold inference and nested/multipage layout remain future work.
3. **Name/identifier input.** Offline inspection accepts strict SMILES or canonical Standard InChI. Explicit supported SMILES produce native drawings through checked MOL seeds, native cleanup and measured composition. Version 0.8 adds an explicitly opted-in PubChem name/CAS resolver returning candidate provenance, ambiguity and graph validation with no automatic selection. Labels and provider associations are not name-verified by graph parsing. OPSIN, additional providers and native ChemDraw Name-to-Structure remain future work. [Resolver contract](RESOLVER.md)
4. **Native charge and mechanism annotations.** Full and fishhook curves retain explicit endpoint/control geometry. Version 0.8 adds a separate atom-owned symbol-copy interface for graphical lone pairs/electrons and circled existing charges, with bounded conservative placement. Version 0.9 adds explicit ownership moves and bounded whole-curve route proposals requiring selection. Native evidence is reported per feature in the progress log. Chemical radical-state editing, native manual-drag attachment and inferred mechanism routing remain future work. [Symbol contract](SYMBOLS.md), [electron-flow conventions](MECHANISM_CONVENTIONS.md)
5. **Import a user's style file.** Version 0.8 extracts supported document settings from local CDX/CDS/CDXML with source hash, defaults and unapplied-property reporting. Custom preset dictionaries reach native drawing workflows, which preflight actual font families without silent substitutions. Template artwork, page layout, colours and font files are not imported or redistributed. [Style contract](STYLE_IMPORT.md)
6. **Design a substrate scope.** The standard isolated monosubstituted benzene profile remains unchanged. Version 0.8 adds explicit mapped-site scans on pre-substituted and isolated five/six-membered heteroaromatic rings, using ten curated groups and at most 100 requests before deduplication. Every candidate is a single addition with null yield; symmetry duplicates retain their requested variants. Fused rings, arbitrary fragments, inferred sites and automatic acceptance remain unsupported. Review/select map-free graph records before drawing. [Expanded contract](SCOPE_EXPANDED.md)
7. **Build explicit reaction rows.** Version 0.8 composes one through three compounds per side from supplied graphs and conditions. Version 0.9 expands this to up to three explicit rows on one page, supported salts/small species and coefficients, with measured native placement and role checks. It does not predict products or certify balance. Native save/visual evidence belongs in the progress log. [Reaction contract](REACTION_BUILDER.md), [expanded contract](REACTION_EXPANDED.md)

## Later adapters, not current scope

Version 0.8 also implements optional scope framing and group dividers as a separate native finishing pass. Explicit group ownership retains source positions; named headings require space and measured verification. It does not automatically classify or reorder compounds. PNG rasterization uses an offline resvg worker after native SVG creation, with an actual clipping/transparency regression for the shadow case.

- Keynote/PowerPoint handoff that retains an editable source, informed by keyClip and Windows Office workflows.
- Optional browser review/editing with Ketcher if users need a non-ChemDraw front end. It must be labelled as a different renderer/editor path.
- Photo/hand-drawing interpretation stays in the image-capable AI client. The MCP receives an explicit proposed graph for native creation and review. No separate image-recognition project or automatic recognizer dependency is planned. A specialist adapter is optional only if a later measured need justifies it; graph roundtrip checks do not prove image interpretation was correct.
- Chemical ELN and document extraction adapters only after the core figure workflow is reliable.

## Repository quality gates before publication

- Retain the project's AGPL-3.0-only licence and all upstream notices; audit each copied file and packaged dependency. Do not redistribute proprietary ChemDraw software, fonts, templates or third-party paper artwork without appropriate rights.
- Install from a clean supported Mac account with documented ChemDraw activation and Automation permission prerequisites.
- Publish a compatibility matrix separating tested macOS/ChemDraw combinations from untested ones.
- Provide CLI help, structured JSON examples, client-independent MCP setup and actionable diagnostics. Do not edit unrelated client configuration.
- Ship redistributable fixtures and a regression suite split into portable unit tests and opt-in native integration tests.
- Include a short reproducible demonstration: messy figure to polished working copy, explicit chemical preservation result, editable/vector output.
- Document local file retention, optional network lookups, and the separate privacy behavior of whichever AI client connects.
- Provide issue templates asking for versions, minimal redacted CDXML, diagnostic output and expected/actual preview. Never ask users to upload confidential unpublished structures by default.
- Keep tool descriptions honest about native versus optional-library work and supported object types.

## Collaboration direction

Propose shared fixtures, geometry contracts and compatible capability descriptions to Windows maintainers after the Mac implementation has reproducible evidence. Prefer contributing small portable improvements upstream over forking an entire tool suite. Contacts, commits, public releases and licensing are separate owner-approved actions; none are authorized by this roadmap itself.
