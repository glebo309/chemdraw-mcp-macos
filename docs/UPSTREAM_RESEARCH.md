# Upstream research and reuse decisions

Reviewed 2026-09-14. This is an implementation research record, not a claim that every upstream feature has been executed on a Mac. Repository heads and license files were fetched from GitHub; immutable revisions are recorded in [upstream-sources.json](../upstream-sources.json). Runtime dependencies should be selected from tested releases, not automatically from those research heads.

## Decision in one sentence

Build a native macOS adapter around a conservative CDXML transformation layer; reuse small, testable platform-independent components, keep chemical interpretation optional and explicit, and let desktop ChemDraw produce the final render.

Windows COM integration is not a Mac backend. Portable CDXML editing is not native rendering. An image preview is not proof of preserved chemistry. These distinctions must remain visible in tool results and documentation.

## Most useful sources

### Michael Leitch: live-chemdraw-mcp

[Project](https://github.com/MALeitch/live-chemdraw-mcp) · [pinned layout implementation](https://github.com/MALeitch/live-chemdraw-mcp/blob/a9cebc6cf61e4d9b019463019626684fdf30beb6/chemdraw_connector/domain/layout_math.py) · [MIT license](https://github.com/MALeitch/live-chemdraw-mcp/blob/a9cebc6cf61e4d9b019463019626684fdf30beb6/LICENSE)

The strongest direct donor: native Windows automation with a separate pure-geometry layer. Its README also records operational limits rather than presenting COM declarations as working capabilities. Layout code includes bounding boxes, overlap detection, packing, caption anchors, reaction spacing and page overflow checks.

**Selected reuse:** adapt `Box` and `find_overlaps` into `chemdraw_macos/geometry.py`, with the full upstream MIT notice retained. Everything else in this review is evaluated or an architectural idea unless explicitly added to the provenance manifest.

**Transfer next:** owned captions that travel with structures; explicit overflow reporting; distinguish logical components from disconnected molecular fragments. Atomically planning movement is preferable to successive untracked moves.

**Do not transplant:** COM bridge calls, Windows registration, assumed native coordinate/property behavior, or the entire tool catalogue. Upstream itself warns that several symbols and annotations do not follow structures automatically. Our Mac implementation must test those relationships rather than inherit claims.

### ChemDraw Skill and the CDXML Toolkit family

[ChemDraw Skill](https://github.com/ZiChenWang114514/chemdraw-skill) · [community toolkit](https://github.com/ZiChenWang114514/cdxml-toolkit-community) · [original toolkit](https://github.com/leehiufung911/cdxml-toolkit)

These projects explicitly separate portable CDXML/RDKit work from licensed Windows ChemDraw rendering. The skill's useful contribution is workflow discipline: provenance, editable artifacts, native save-cycle checks, and openly unresolved stereo in difficult reconstruction examples. A large exported symbol inventory does not mean every SDK member succeeds.

**Transfer:** treat document objects, reaction roles, captions and conditions as structured data; produce a reviewable change report and native preview; preserve unresolved chemistry rather than silently filling it in. Consult toolkit layout and label-anchor modules for future implementations. No source copied from this family in the current increment.

**Rejected as a drop-in:** [`coord_normalizer.py`](https://github.com/ZiChenWang114514/cdxml-toolkit-community/blob/03c4d94dabf20d23b3118a5b2d9afd9d9c90f7d4/cdxml_toolkit/coord_normalizer.py) defaults to flipping the y axis and removing explicit hydrogen atoms. That is a coordinate-import utility, not a safe transformation of an existing ChemDraw document. Applying it unchanged to already-y-down coordinates or stereochemically significant explicit H would violate our preservation contract. Use positive uniform scaling and translation on supported existing objects; handle imports separately.

The original toolkit and community fork retain `Copyright (c) 2026 Hiu Fung Kevin Lee`; crediting only the fork maintainer would miss that provenance. The skill has its own contributor copyright. Paper artwork and installed ChemDraw templates are not automatically relicensed with repository code.

### jurimaxam-dotcom: chemdraw-mcp

[Project and architecture](https://github.com/jurimaxam-dotcom/chemdraw-mcp/tree/9f19767c0c48289ab62b5743602f1a3aff05b375) · [Apache-2.0 license](https://github.com/jurimaxam-dotcom/chemdraw-mcp/blob/9f19767c0c48289ab62b5743602f1a3aff05b375/LICENSE)

The existing generator is complementary, not something to dismiss. Its documented primary output is local RDKit PNG/SVG; CDXML is optional, with separate name resolution and validation. The README explicitly acknowledges this boundary. It has useful user-facing patterns: a diagnostic command, absolute launcher paths, reusable style names, shared molecular scale and clearly reported limitations.

**Transfer:** deterministic tool contracts, input-resolution provenance, offline explicit-structure paths, and a diagnostic command that distinguishes missing optional capability from a broken server. Existing external output can be imported without copying its generator code into this project.

**Not selected:** taking on its unrelated calculations, spectra, flashcards or 3D tools. Those broaden the product without solving native figure editing. No source from this repository is vendored in the current increment. If later adapted, preserve Apache license/notice requirements and mark modified files; a README credit alone is not the full provenance record.

### RDKit

[Project](https://github.com/rdkit/rdkit) · [CDXML parser source](https://github.com/rdkit/rdkit/blob/23378a7f2f82ae6c867201db8c56ab4cc4a4e671/Code/GraphMol/FileParsers/CDXMLParser.cpp) · [BSD-3-Clause license](https://github.com/rdkit/rdkit/blob/23378a7f2f82ae6c867201db8c56ab4cc4a4e671/license.txt)

**Selected role:** optional independent molecular-graph validation and, later, substructure matching. It must not become an implicit replacement renderer for a tool promising a native ChemDraw result. Preserve the installed validator version in verification output.

A molecular parser is not a lossless document parser: captions, graphical symbols and page composition need their own checks. Ordinary canonical identity comparison alone does not prove preservation of every query feature, enhanced stereo group, atom map or depiction convention. Unsupported parsing must yield an explicit unverified result, never a green check. There is no need to vendor RDKit C++ code.

### EPAM Indigo and Ketcher

[Indigo](https://github.com/epam/Indigo/tree/8642d73cca2b827a5351d8a8eb21816492381497) · [Ketcher](https://github.com/epam/ketcher/tree/df40dd518ab6122bb768c93fe27e697f9c4cd994)

Indigo is an Apache-2.0 chemistry toolkit with multiple language interfaces and a renderer. Ketcher's documented editor API exposes CDXML/CDX export, structure cleanup and layout through Indigo, with service and WebAssembly options. These are credible cross-platform alternatives, not native ChemDraw control.

**Transfer:** explicit selection/edit operations and typed molecular interchange. A browser review/editor could eventually complement the Mac application, but that is a separate interface and packaging project. Evaluate difficult structure handling against the same fixture suite before choosing any additional chemistry backend.

**Not selected now:** replacing ChemDraw with a web editor or bundling a second native-rendering stack. No source copied. Preserve their individual Apache license and NOTICE files if code is adopted later; bundled third-party components require their own review.

### Open Babel

[Project](https://github.com/openbabel/openbabel) · [CDXML implementation](https://github.com/openbabel/openbabel/blob/9be528bcdb31a219637ae3d1699170a8aaa5be6d/src/formats/xml/cdxmlformat.cpp) · [GPL v2 license](https://github.com/openbabel/openbabel/blob/9be528bcdb31a219637ae3d1699170a8aaa5be6d/COPYING)

Useful for broad chemical file conversion, but the inspected CDXML format implementation explicitly describes minimal chemical-structure support. That is not sufficient for preserving an editable publication figure with native annotations.

**Decision:** no code copied, no dependency selected, and no conversion roundtrip through Open Babel in the preservation path. Its GPL-2.0 source also requires a separate licensing decision before incorporation. An independently installed optional converter could be assessed later, without assuming that a process boundary resolves all distribution questions.

### OPSIN

[Project and interface](https://github.com/dan2097/opsin/tree/996a580588c8fd8c6dd07529d63449fa72e66f2f) · [MIT license](https://github.com/dan2097/opsin/blob/996a580588c8fd8c6dd07529d63449fa72e66f2f/LICENSE.txt)

A strong future offline systematic-name resolver. It exposes warning states for ambiguity or ignored stereochemistry and can output SMILES/CML/InChI. Preserve those warnings and the submitted name in provenance. Do not enable permissive stereo-ignore settings to make a request appear successful.

**Decision:** evaluate a version-pinned optional adapter rather than implement nomenclature parsing ourselves. Not installed, copied or exposed by this increment. It is not ChemDraw's native Name-to-Structure command.

### Mark A. Maskeri: keyClip

[Project](https://github.com/mmaskeri/keyClip/tree/e6782a07a52ab600d643dd8d6060991627a52b21) · [MIT license](https://github.com/mmaskeri/keyClip/blob/e6782a07a52ab600d643dd8d6060991627a52b21/LICENSE.txt)

A relevant Mac precedent for keeping ChemDraw content editable across Keynote handoffs. Its documented workflow uses clipboard data, Automator/keystrokes and version-specific behavior, with placement caveats.

**Transfer later:** pair figure presentation with an editable chemical source and explicit receiving-document workflow. Do not copy global clipboard or keystroke operations into the current safe core. No code copied; this is a future adapter idea, not delivered Keynote integration.

## What the research changes in the design

1. Separate pure planning, native application operations and chemistry checks. Both CLI and MCP should call the same implementation.
2. For existing figures, preserve first. Reject unknown complex objects before changing them. Arbitrary nested groups, multistep arrows and decorative graphics need explicit support, not guesses.
3. Ownership is data. Callers must identify which captions and conditions move with which molecule or arrow when that cannot be inferred safely.
4. Verify the native saved artifact, not only a pre-import CDXML string. Inspect both chemistry and visible layout.
5. Report equal bond scale separately from equal overall molecular dimensions. Never shrink one molecule alone just to fit a layout slot.
6. A portable fixture suite is the most valuable collaboration surface with Windows projects. Native backends can differ while testing the same contracts.

## Verification boundary

The source review establishes available implementations and their documented claims, not reproduced performance. No Windows host, Linux editor or upstream graphical demo was executed during this review. Current native Mac support must be stated from this project's own live tests. See [ROADMAP.md](ROADMAP.md) for acceptance gates and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for actual copied-code attribution.
