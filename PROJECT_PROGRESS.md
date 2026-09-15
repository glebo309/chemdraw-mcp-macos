# Project progress

## 2026-09-15: v0.9.2 one-command native first run

Glenn approved a one-command onboarding workflow with a small molecular terminal animation and asked whether the same workflows work from desktop assistant apps. `first-run` and new MCP `chemdraw_first_run` now share one implementation: dependency discovery, native connection, explicit caffeine/aspirin drawing through cleanup and grid validation, required artifact checks and a retained `first-run.json` report. Default output is uniquely named. The final drawing stays open; pre-existing documents are preserved. Fresh server discovery reports 38 tools.

Interactive CLI uses a six-position ASCII ring with truthful stage labels and opens the local review on success. JSON/nonterminal output remains machine-readable, with no browser or escape sequences. MCP has neither presentation behavior. Missing dependencies, existing destinations, busy/uncertain operations, partial exports, interruption and browser-launch failures have regression coverage. Ctrl-C initially lost the native stage/output path; the failing regression now passes. There are no automatic write retries, extra uncertainty cleanup, permission changes or client-configuration edits.

Verification: full locked portable suite passed 733 tests with 35 native skips in 6.43 s, recorded in local-validation/first-run-portable-final.xml. Targeted serial native suite passed 5 tests in 117.38 s, recorded in local-validation/first-run-native.xml: the new actual stdio first-run plus four existing draw cases. The test closes only its own final copy and checks the original document inventory. This is not a repeat of the earlier full 34-test native acceptance.

The 0.9.2 wheel and source archive built offline. The installed wheel was exercised through uvx from outside the checkout, including interactive ring animation, successful browser launch and native output at local-validation/first-run-cli-v092/review.html. Its white-background native preview was visually inspected: readable structures, aligned captions/IDs and no apparent label overlap. The original transparent exports remain unchanged. Checks passed on ChemDraw 23.0.1.11 with Python 3.13.2; this remains same-Mac evidence. Wheel contents retain the native module and all AGPL/upstream notices, excluding local validation bundles.

README and docs/FIRST_RUN.md provide the Git-source uvx command and locked-checkout alternative. docs/MCP_CLIENTS.md documents Claude Desktop JSON and Codex local configuration, native-job timeout considerations and the local-versus-web boundary using official client documentation. Client settings were not changed. A native doctor call through the current connected assistant session also responded successfully. Another-Mac acceptance, crowded-charge refinement, metal complexes, desktop-extension packaging and package publication remain separate work.

## 2026-09-15: open-source licensing and collaboration

Glenn requested making the project open source after discussing permissive and copyleft options. Original project code is now licensed under GNU AGPL version 3 only (AGPL-3.0-only), preserving the stated preference for access to covered improvements while allowing commercial use. LICENSE is the unchanged official GNU text, verified byte-for-byte; NOTICE declares project copyright and warranty terms. Existing upstream MIT notices remain unchanged. No restriction on ordinary user drawings or research, no promise that all independent paid clients are covered, and no contributor copyright assignment were added.

README and CONTRIBUTING invite compatibility reports, reproducible drawing examples and focused pull requests. Current status, agent guidance, provenance and release checklist distinguish open-source availability from a tested stable release. Historical milestone entries retain their then-current licence status.

Packaging regression tests failed for missing licence metadata/text before the change and now pass. Full portable suite: 716 passed, 34 native tests skipped in 6.43 s. The locked dependency check and offline wheel/source builds passed. The wheel declares License-Expression AGPL-3.0-only and includes LICENSE, NOTICE, THIRD_PARTY_NOTICES.md and the upstream MIT text; the source archive includes the same notices and excludes local validation/environment files. Drawing behavior was not changed, so native tests were not rerun for this licence-only increment. Package publication, another-Mac acceptance and the onboarding/charge/metal-complex work remain separate.

## 2026-09-15: v0.9.1 coordination, charge ownership and readable previews

GitHub examples now use opaque white-background SVG copies. The original transparent exports and their native drawing elements are unchanged. This fix was published in commit a9809f8, with a regeneration script and structural regression test.

Native CLI and MCP workflows now share a per-user, cross-process gate with a bounded two-second wait. Nested workflows are reentrant; create/import/close and file wrappers hold the gate across their complete transactions. Busy contention is reported separately from uncertain native outcomes. The protocol does not coordinate manual GUI changes, other automation or separate Macs. Process exit releases the lock, but does not prove an already dispatched AppleEvent completed. See docs/NATIVE_COORDINATION.md.

The earlier circled-charge failure was a genuine native reassignment from nitrogen to a nearby carbon. Candidate positions now require the intended atom to be uniquely nearest, in addition to existing clearance checks; final native chemistry and ownership remain checked. The original four charged structures pass in plain mode. Opt-in circled mode passes for glycine zwitterion and benzoate, with three uniform native symbols. Crowded tetramethylammonium and nitrobenzene remain refused in circled mode at the current house style. No validator was weakened, charge silently changed, or molecule distorted to force acceptance.

Final portable acceptance: 713 passed, 34 native tests skipped in 6.32 s, recorded in local-validation/portable-v091-final.xml. Full serial native acceptance: 34 passed in 441.91 s, recorded in local-validation/native-coordination-v2.xml, with retained artifacts under local-validation/native-coordination-v2/. Interrupted runs are not counted as passes. Native tests and the CLI demo preserved pre-existing documents.

The actual CLI draw command with examples/ions-circled.json produced local-validation/ions-circled-v091/review.html and charged/figure.cdxml, SVG and PNG. Its final working copy remains open. The white-background preview was visually inspected: three matching circled charges are clear of atoms, bonds and captions, although the negative charges sit low beside the caption row and remain a visual-refinement opportunity. All saved chemistry, coordinate, symbol and page checks passed. Doctor reports ready with ChemDraw 23.0.1.11 and the shared gate.

Package metadata is 0.9.1. The dependency lock validates and wheel/source builds succeed locally; validation bundles and proprietary references remain excluded. Public source hosting is approved; package publication, original-code licensing and independent-Mac acceptance remain separate gates. Marco DeCorti's acknowledgment is retained.

## 2026-09-15: public experimental repository

Glenn explicitly approved making the repository public. GitHub visibility was changed and verified PUBLIC. Reviewed the sole existing commit's file inventory and scanned tracked text for credential patterns; no matches were found. Local validation outputs, environments, builds, proprietary templates and reference PDFs remain excluded. Marco DeCorti's acknowledgment is retained. Documentation now distinguishes public experimental source from a stable release and from an open-source licence grant. No code or test behavior changed in this publication step; the documented unfinished-work status remains current.

## 2026-09-15: private repository and contributor acknowledgment

Glenn approved private GitHub hosting. Repository: https://github.com/glebo309/chemdraw-mcp-macos, verified PRIVATE before the initial push. Marco DeCorti is acknowledged in the README for visual guidance, reference examples and checking generated drawings. No collaborators were invited, public release made or original-code licence granted.

The initial source snapshot deliberately retains current unfinished test-first work. Latest portable run: 683 passed, 32 skipped, 11 failed in 6.05 seconds, all failures in the new coordination tests. The experimental one-call circled-charge native demo stopped at chemistry validation and is not accepted. See docs/DEVELOPMENT_STATUS.md for the exact boundary and next steps. Local validation artifacts, environments, distributions and proprietary references remain excluded.

## 2026-09-15: local v0.9 complete jobs, ownership and portable styles

All four approved increments are exposed through the CLI and MCP, with 37 registered tools in a fresh server connection. The implementation follows test-first development; native clients run serially and preserve existing documents. Local package metadata is 0.9.0. Public release, licence selection and independent-Mac acceptance remain separate pending gates.

- Complete scope jobs combine an explicit mapped parent, candidate acceptance, deterministic category assignment with retained secondary memberships, native cleanup, conserved scaffold alignment, actual group bands, headings, optional frame/dividers and final exports. The full acetophenone example contains 14 candidates in 3/6/5-compound bands, with null yields. Native creation and white-background visual review passed.
- Expanded reactions accept explicit water/hydroxide/halide/Na+/K+ participants and bounded charge-balanced salts, positive supplied coefficients and up to three explicit rows on one physical page. Salt components retain ownership. Na/K use the narrowly checked native CDXML ion seed instead of deleting MOL-import AbnormalValence metadata. Native asymmetric arrow bounds and cross-row caption assignment produced retained regressions. A 120 pt row separation passed the unchanged native role/condition verifier; it is now the default, not a universal arbitrary-layout guarantee.
- Snapshot-bound ownership sidecars move explicit captions, native symbols and internal curves with their molecules. Horizontal reaction movement passed natively. Vertical movement within a reaction scheme fails preflight because an actual native test lost explicit reactant roles. A plain molecular sheet passed both-axis movement through MCP. One-sided cross-owner curve moves and native manual-drag attachment remain unsupported. Route suggestions evaluate 24 bounded cubic candidates against conservative measured obstacles and require explicit selection. Both charge-source attack and bond-source leaving arrows passed native rendering; arrowhead ink still requires visual review.
- Portable lab styles are numerical JSON packages, not the legacy draft skill or an alternate renderer. They contain supported settings, a version, hash and reference records, reject conflicting recipe overrides, check fonts on the rendering Mac and retain the exact package with successful native output. The native MCP style/drawing/ownership chain passed. No proprietary template, font or application resource is included.

Portable acceptance: 676 passed, 32 native tests skipped in 6.52 s, recorded in local-validation/portable-v09-release-candidate.xml. The full serial native gate passed 32 tests in 394.64 s, recorded in local-validation/native-v09-electron-final.xml. That process loaded the reaction-series module before the final coefficient-font correction, so the fresh-process typography regression is recorded separately below. Known issues and scope-specific limitations are retained in docs/KNOWN_ISSUES.md, docs/SCOPE_JOB.md, docs/REACTION_EXPANDED.md, docs/OWNERSHIP.md and docs/LAB_STYLE.md. Demo, release checklist and report template are prepared without publication.

Glenn caught a stale SN2 test fixture drawing from the Br label. New annotation and route APIs now reject atom-label sources. Explicit displayed negative-charge/lone-pair sources represent two electrons; graphical electron dots represent one; donating bonds remain supported sources. Atom/bond targets are unchanged. Neutral-donor tests add explicit lone pairs, and fishhook rendering fixtures use bond sources. Corrected native CLI bundle local-validation/sn2-sources-v09 was visually inspected at 3200 px and preserves the source. The final working copy remains open. The local review hub is local-validation/v0.9-review.html.

Independent inspection also found coefficients at 8.25 pt beside 14 pt atom labels: the general style pass had overwritten them with caption typography. Explicitly owned coefficient text is now restored to the atom family/size before native measurement, with regression coverage and native verification of both font and size. No global caption style was changed.

The fresh-process expanded-reaction regression passed in 30.28 s, recorded in local-validation/native-v09-coefficient-final.xml. All four saved coefficients are explicitly 14 pt Helvetica Neue, and coefficient_font_and_size is verified true. The native PNG was visually inspected. This output supersedes the smaller-coefficient previews retained in the earlier full-run directories; the review hub links the corrected version.

The 0.9.0 wheel and source distribution build successfully. Archive inspection confirms the five new workflow modules and portable style example are included, while local validation artifacts, the environment and proprietary CDS files are excluded. The dependency lock validates and a fresh server registers 37 tools. No publishing, original-code licence grant or Synology installation occurred.

## 2026-09-15: local v0.8 styles, reactions, symbols and scope finishing

Version 0.8.0 exposes twenty-seven MCP tools, with the same workflow implementation callable from the terminal. The five approved increments are implemented: numerical CDS/CDX/CDXML style import, explicit atom-owned charge/electron annotations, explicit reaction rows, opt-in PubChem name/CAS candidates, and mapped substitutions on supported pre-substituted/heteroaromatic parents. Glenn's additional scope-frame request is also implemented.

- The original Sharpless CDS was read without modification. Actual settings include 18 pt bonds, approximately 1.58 pt strokes, 14 pt Helvetica Neue atom labels and captions. The supported saved settings/font families are checked separately from molecular identity. The five-candidate pyridine scope at local-validation/pyridine-sharpless-v2 passed native checks and visual review. Template/font files are not redistributed.
- Explicit reaction construction accepts supported supplied participants and above/below conditions, not inferred products or conditions. The native Sharpless example at local-validation/reaction-sharpless-v1 passed role, graph/stereo, caption, gap, scale and page checks. It is an illustrative ethanol/ethanal layout, not a specified experimental oxidation protocol.
- PubChem is opt-in per call, returns candidates with provenance and ambiguity, and does not silently select a match. An actual caffeine lookup returned CID 2519 and the expected checked graph. Public query only; no research compounds were transmitted. Mapped aromatic proposals remain offline, with no yields or reactivity predictions.
- Native CirclePlus/Minus and LonePair geometry was calibrated against actual SVG. Graphical electron dots use a native filled-circle Oval because nearby Electron symbols can change Radical state. Charge signs derive from existing formal charge, never a guessed display glyph. Five native MCP fixtures cover positive/negative creation and charge/lone-pair/electron-source arrows. The corrected SN2 example starts at the circled charge and C-I bond midpoint; bundle local-validation/sn2-symbol-source-v1.
- Optional decorate-scope and chemdraw_decorate_scope add native rounded shadow frames, true dotted separators and optional explicit headings to existing nonoverlapping bands. Source positions and labels are retained. No automatic donating/withdrawing classification or group reordering. The complete fourteen-candidate example is local-validation/scope-framed-v2/review.html, with native CDXML/SVG and transparent PNG. Native SVG and corrected PNG were visually inspected. Reproducible source/recipe are examples/scope-decoration-input.cdxml and examples/scope-decoration-recipe.json.
- Independent review fixed export ordering, uncertain cleanup, actual caption bearings, inherited local width/colour and native font/number serialization. Native typography equivalences are narrow and evidence-backed, not broad font-substitution permission. Final symbol/annotation/decoration CDXML is exported after raster/vector rendering so render-time mutation cannot evade verification.
- The shadow example exposed a sips SVG rasterization bug: the native SVG clip hole rendered correctly in a browser and native PDF, while sips made the whole interior grey. PNG now uses pinned offline resvg-py 0.5.0 on the unchanged native SVG, in a timed worker with bounded local-only resources and checked RGBA dimensions. An actual pixel regression checks transparent interior and partially transparent shadow. No ChemDraw geometry was changed to conceal the conversion bug.

Portable acceptance: 558 passed, 26 native tests skipped in 3.68 s. The complete post-rasterizer native gate passed all 26 tests in 248.61 s, including frame-only and named-heading cases plus positive/negative charges and source arrows. Native clients ran serially and preserved pre-existing document state. Artifacts are retained in local-validation/native-v08-final and the stable summary in local-validation/validation-v0.8.0.json. The visually checked framed PNG is 2172 by 3200 RGBA, with sampled interior alpha zero. Supported native evidence is limited to this development Mac and ChemDraw 23.0.1.11.

The 0.8.0 wheel and source distribution build successfully; packaged modules include styles, resolver, reaction, symbols, scope decoration, raster worker, native AppleScript and retained adapted-source licence. Source examples are included; local-validation, private book/template files and the virtual environment are excluded. Runtime rasterizer attribution is in THIRD_PARTY_NOTICES.md and upstream-sources.json. No public release, remote, new original-code licence or shared-skill installation.

## 2026-09-15: explicit native electron-flow annotations

Version 0.6.0 adds inspect-annotations/annotate and two corresponding MCP tools, for seventeen tools at this milestone. Native full heads and both fishhook directions use explicit atom/bond endpoint offsets and cubic controls. Supported existing circled charges and molecular graphs are retained. No new electron dots, radical-state editing, automatic routing or native moving-attachment claim.

- The first native save-cycle failed because pretty-print whitespace outside text runs was treated as label content. Formatting-only whitespace is now excluded, with actual text-run content preserved.
- Reviewer regressions cover unsupported charge styles, nonfinite/negative dimensions, changed curve geometry and source mutation. Additional main-agent regressions cover changed charge backgrounds and source deletion during export.
- Full native annotation milestone: 13 tests passed in 88.08 s, including all previous workflows plus full/left-half/right-half curve saves. Half-head variants are rendering fixtures, not proposed SN2 chemistry.
- Actual CLI bundle: local-validation/sn2-annotations-v1/review.html. Native PNG was visually inspected on white; its two curves reproduce Glenn's approved reference. Original reference folder was not modified.
- Version 0.6.0 wheel and source distribution built locally before the subsequent input/scope expansion. Latest combined counts belong to the later milestone below.

## 2026-09-15: native input, standard scopes and alignment

Glenn authorized continued local development while unavailable, including subagent implementation/review, without confirmations. Publication, external services, licence changes and modification of pre-existing user drawings remain out of scope.

Version 0.7.0 exposes twenty MCP tools. Offline identifiers, a bounded standard aromatic scope proposer and explicit-input native drawing are callable through CLI/MCP. The proposer preserves an explicit monosubstituted benzene parent handle and produces fourteen unique electronic/positional/steric/reference candidates with relative labels and blank yields. It is not reaction prediction. Image interpretation remains in the image-capable client, with no recognizer project or dependency added.

- Identifier inspection accepts strict SMILES or canonical Standard InChI, retains explicit H/isotopes/stereo, and reports InChI normalization and graph-roundtrip equivalence separately. No name/CAS resolver or network provider.
- New drawings take explicit IDs, labels and SMILES. RDKit supplies a checked MOL coordinate seed; actual ChemDraw imports, runs native Clean Up Structure, saves, measures and renders. Source labels are caller supplied, not verified chemical names. All native work uses private copies.
- Optional explicit common-scaffold alignment rotates/translates normalized candidates to the first native structure without reflection or scaling. Chemistry, stereo, pairwise distances and fit RMSD are checked, then native saving remeasures labels. Symmetric matches are deterministic drawing choices, not inferred correspondence outside the supplied scaffold.
- Live integration caught incorrect MOL chiral-flag semantics, fake physical-page assumptions, overlapping initial assembly and unstable coordinate sorting after native rounding. All have regression coverage and are documented in KNOWN_ISSUES.md. The final matcher keeps its original 0.03 pt tolerance and ordered reaction-arrow endpoints.
- Batch now supports the bounded native annotation subset, including full and both fishhook heads plus supported existing circled charges. Three head variants exported through all five native/vector/raster formats in the dedicated native test. New symbol creation and arbitrary graphics remain unsupported.
- File-grid input is frozen before import and checked after final export, with its exact source snapshot/hash and uncertain-operation recovery recorded in the audit. No retry or automatic close follows an uncertain native outcome.
- Portable tests: 298 passed, 17 opt-in native tests skipped in 1.62 s. Full native suite: 17 passed in 154.12 s. It covers the bridge, polish, analogue edits, scope and frozen file-grid import, batch, full/left/right electron arrows, explicit new drawings including isotope/stereo and scaffold alignment, and all-format annotated batch export. Native clients ran serially and pre-existing document state was preserved. Run artifacts are under pytest-166 in the local pytest temporary directory; the stable validation summary is local-validation/validation-v0.7.0.json.

The three-column fourteen-candidate manifest is examples/acetophenone-scope-draw.json. Its graph set exactly matches the offline acetophenone proposal. The alignment-enabled final bundle is local-validation/standard-scope-v3/review.html, with native editable CDXML, SVG and transparent PNG under figure/. Its white-background review preview was visually inspected. All measured median bond lengths are 18.0000 through 18.0014 pt, largest normalized scaffold fit RMSD is 0.0026354 pt, and the previously tilted ortho-methyl candidate rotates 30.0003747 degrees. Labels and IDs align; no yields are supplied. assets/standard-scope.svg is the matching native export for the README. Earlier evidence was not overwritten.

Version 0.7.0 wheel and source distribution built successfully. The wheel includes the alignment/input/annotation modules, native AppleScript and upstream licence notice; the source distribution includes reproducible examples and the SVG, excluding local-validation and the development environment. Twenty MCP tools and the actual identify/propose-scope CLI paths were checked. User originals and the approved SN2 reference remain untouched. No publication, external name provider or original-code licence grant.

## 2026-09-15: batch export and existing electron-arrow reference

Version 0.5.0 adds CLI batch and MCP chemdraw_batch_export, bringing the server to fifteen tools. An explicit manifest of supported CDXML files produces consistently keyed CDXML/SVG/PNG plus requested PDF/CDX, source/post-export snapshots, per-item audits and an HTML contact sheet. No styling or layout transformation runs.

- Native access is sequential. Each item uses a private working copy, closed with a backup after a determinate result. Native exceptions stop subsequent items, retain uncertainty and never trigger a retry or a second close.
- Missing and unsupported inputs are preflight rejections, so valid siblings can still export. A partial or interrupted batch exits nonzero through the CLI. Failed artifacts remain diagnostic.
- Source bytes are frozen and hashed before native import. Mapped chemistry/stereo/coordinates, captions, supplied arrow properties and explicit reaction-scheme references are checked. Source hashes and unchanged working content are checked after export. Pre-existing open-document inventory, metadata and unsaved XML content are compared; those backups stay in the bridge workspace, not the contact sheet.
- Independent review produced five failing regressions: dropped scheme metadata, changed arrowhead size, leaked extra documents, changed unsaved source content and source-key backup collision. All five are fixed. Backup files now live in an item's snapshots subdirectory.
- Native validation initially failed because isolated fragments lost document settings. The fix follows the existing scope helper: retain the root/page settings while removing unrelated page children. Native scheme inference when none was supplied is documented separately from preserving explicit source roles.
- Final portable suite: 123 passed, 10 opt-in native tests skipped. Full native suite: 10 passed in 66.87 s, including two valid batch inputs, a rejected missing input and all five output formats. Pre-existing document state was preserved.
- Actual CLI demo: local-validation/batch-v1/review.html. Three previously generated figures each exported as CDXML, SVG, PNG, PDF and CDX. All checks passed. The HTML contact sheet was rendered in an isolated headless browser and visually inspected; screenshot retained as contact-sheet-preview.png. The example scope percentages remain invented software-test values, not research results.
- Version 0.5.0 wheel and source distribution built locally. No publication, remote, external resolver or original-code licence grant.

Glenn supplied /Users/glenn/Downloads/SN2_house_style as the desired mechanism reference. The actual preview, CDXML/native CDXML, recipe, audit and original generator at /Users/glenn/ChemDraw-Output/horgh1-v9/sn2_example.py were inspected. It already writes two native editable curved electron-pair arrows, without GUI mouse automation. Next mechanism work should reuse that proven curve planning with the new explicit-document bridge, not the legacy front-document exporter. The source/target association and clearance checks are not yet a generalized tool. Research and evidence are recorded in docs/ELECTRON_ANNOTATION_RESEARCH.md. Native lone-pair/radical symbols and fishhooks are format-supported; project-specific attachment/fishhook save-cycle tests remain future work. The reference folder was not modified.

High-level batch currently rejects curves and molecular symbol graphics, including that legacy SN2 drawing. The lower-level native bridge can import/export them, but batch preservation support must not be claimed before its validator and tests cover them.

## 2026-09-15: native scope grids

Version 0.4.0 adds the CLI grid command and MCP chemdraw_grid_document, bringing the server to fourteen tools. A recipe assigns every source fragment and caption to one explicitly ordered compound, with a compound ID and optional caller-supplied yield. Names are retained, not inferred. Zero and missing yields remain distinct.

- Native measured molecular/name/metadata bounds determine uniform cell dimensions. Captions and metadata share row baselines. Overflow fails instead of shrinking molecules or changing page size.
- Each fragment is normalized to the selected median bond scale, retaining orientation. Multiple fragments assigned to a compound receive one shared layout translation after normalization. This is not a salt-spacing optimizer or common-scaffold alignment engine.
- Exact source/native object coverage, per-atom mapped chemistry/stereo/coordinates, caption anchors and visible horizontal centring, compound/yield binding, inter-object overlaps and saved-page fit are checked. Native ink centring tolerance is 0.75 pt; planned caption anchors and compound centres use 0.05 pt.
- Supported flat single-physical-page molecules and captions only. Reactions, nested groups, page graphics and native molecular symbol graphics fail closed. Plain formal-charge atom attributes are supported.
- Analyze exposes a top-level source token for supported multimolecule drawings. CLI file import validates before native creation and remaps IDs. Working copies and available file/unsaved-content checks preserve the source.
- TDD cycle included independent reviewer regressions for extra native fragments, extra captions and misplaced visible caption bounds. All four failures were fixed; the final review found no blocker within the supported boundary.
- Full portable suite: 104 passed, 9 opt-in native tests skipped in 0.43 s. Full native suite: 9 passed in 61.61 s, including basic scope and disconnected sodium/chloride scope tests. Native clients were run serially and pre-existing document state was preserved.
- Actual eight-compound, four-column CLI demo: local-validation/scope-v1/review.html. Native output was visually inspected. All eight median bond lengths lie from 18.0000 to 18.0014 pt; all audit checks passed. Names and IDs are aligned, with invented test percentages including 0% and a missing yield. These are not experimental data.
- Reproducible fixtures: examples/scope-input.cdxml and examples/scope-recipe.json. Native SVG exports: assets/scope-before.svg and assets/scope-after.svg. Editable CDXML and transparent native-derived PNG are in the local review bundle.
- grid_positions adapted from the pinned Michael Leitch MIT source; upstream-sources.json and THIRD_PARTY_NOTICES.md updated, full notice retained in the built wheel.
- Version 0.4.0 wheel and source distribution built successfully. Package includes scope.py, native.applescript and the upstream licence notice. Usage, compatibility and contribution instructions updated.

Visual review remains required: native bounds and graph preservation do not establish all intramolecular glyph collisions, source chemical correctness, experimental yields or printed-page clipping. No external naming provider, publication, remote or original-code licence grant was added.

## 2026-09-15: explicit analogue editor

User approved the next bounded milestone and requested additional subagent research. The terminal `edit` command and MCP `chemdraw_edit_document` now create an edited native working copy from one molecular fragment with explicitly selected atoms/bonds. Original files and pre-existing documents remain untouched.

- Neutral main-group element/H changes and ordinary nonaromatic bond-order changes. No atom insertion/deletion, new stereochemistry or charged/isotopic target edits.
- `analyze` provides atom/bond IDs plus an export-content token; live edits reject stale snapshots.
- Every page caption needs an explicit replace, retain or remove decision. Changed atom labels are regenerated instead of carrying stale text.
- Chemical diff includes requested changes and observed implicit-H changes. Native roundtrip checks mapped chemistry/stereo, individual atom coordinates and saved label text, rather than only formula or unordered geometry.
- CLI file input validates before native import and remaps atom/bond/caption IDs. The final edited native document remains open; temporary source copies are closed with backups.
- Independent reviewer supplied failing tests for creation/removal of unspecified tetrahedral centres and formula-label corruption. All were fixed under the TDD workflow.
- Final portable suite: 75 passed, 7 opt-in native tests skipped. Six native integration tests passed together in 39.98 s, including four analogue operations and a chiral remote-halogen swap. The seventh native SVG regression then passed in 7.35 s after the fixture correction documented in docs/KNOWN_ISSUES.md.
- Corrected CLI demo: local-validation/bromo-analogue-v2/review.html, visually inspected. The halogen substitution retained all ten atom coordinates with maximum displacement 0.0 pt after native saving. Reproducible inputs are examples/chlorobenzoic-acid.cdxml and examples/bromo-analogue-recipe.json; native SVGs copied to assets/analogue-before.svg and assets/analogue-after.svg.
- New research: docs/NAME_CONVERSION_RESEARCH.md and docs/LAYOUT_WORKFLOW_RESEARCH.md. Strong follow-ons are scope grids, batch export, offline identifiers and strict name resolution. They remain research, not implemented tools or installed providers.

Version increment: 0.3.0, local only. Still no public release, remote or original-code licence grant.

## 2026-09-15: first native figure-polishing increment

The existing native bridge now has a terminal interface and a bounded figure-polishing workflow. Code is in a local Git repository on main; no remote, commit or publication has been created.

### Implemented and exercised

- CLI diagnostics, document listing, semantic analysis and polish commands.
- MCP diagnostics, analysis and polish tools using the same implementation.
- Source CDXML preflight for CLI imports; required optional RDKit validator for polish.
- Actual per-molecule median bond-length normalization, common fonts and strokes.
- Existing orientation retained, including wedges, explicit H and supported isotope/charge attributes.
- Explicit single-row caption and condition ownership, measured native bounds, equal component gaps, shared caption baseline and centred conditions.
- New native working copy, before/after PNG and SVG, editable CDXML, recipe, audit and HTML review.
- Final native graph comparison, molecule-scale measurement, inter-object box overlap checks and source metadata/file/unsaved-content comparison.
- Delayed native open reconciliation through read-only listing, without repeating the write.

### Evidence

- Portable suite: 48 passed, 2 opt-in native tests skipped.
- Native suite: both MCP stdio integration tests passed in 15.31 s with ChemDraw 23.0.1.11 on this Mac. Pre-existing document metadata remained unchanged.
- Native reaction demonstration: local-validation/oxidation-v3/review.html. Before/after SVGs also copied into assets/ for the project documentation. The white-background PNG was visually inspected.
- Demo chemistry: CCO and CC=O retained. Final median bond lengths 18.0013 and 17.9970 pt; caption baselines both 66.74 pt; requested component gap 24 pt. The [O] annotation is schematic, not a specified experimental reagent.
- Additional local normalization checks on the earlier LSD, betaine and HorGH1 CDXML outputs retained the decoded supported molecular identities. These checks are not a claim that arbitrary complex documents are supported.
- Independent review supplied regression cases for unsupported atom/bond queries, polymers, per-fragment identity mapping, explicit H and unsaved source-content changes. They now pass.

### Research and provenance

Eleven upstream repositories are pinned in upstream-sources.json. Box/find_overlaps are adapted from Michael Leitch's MIT-licensed live-chemdraw-mcp, with full notice. No other upstream source is vendored. RDKit is an optional installed dependency. See docs/UPSTREAM_RESEARCH.md for decisions and docs/ROADMAP.md for later work.

### Remaining release gates

- Independent-machine installation and additional ChemDraw versions are not tested.
- Nested groups, multipage layouts, polymer/query features, arbitrary page graphics, automatic scaffold edits and name resolution are not implemented in polish.
- No general charge-collision solver or mechanism-arrow editor in the new server.
- No new GUI, unattended installer or cross-process editing lock.
- Machine checks do not replace visual and chemical review. The server leaves visual_review as required.
- The older local house-style skill remains a draft and is not the release interface.
- Public licence, remote repository and publication require Glenn's approval.
