# Layout and everyday workflow research

Reviewed 2026-09-15. This is source inspection and product prioritization, not a benchmark or a claim that the proposed features already work on macOS. No upstream program was installed or executed, no source was copied, and no ChemDraw document was touched for this review. Name and identifier resolution are covered separately.

## Recommendation

Finish the approved explicit copy-and-modify editor first. Then build a **scope-grid workflow with stable compound IDs**, followed by **batch native export**. These extend the existing supported-object and native-rendering infrastructure. Common-scaffold alignment is valuable but needs a stricter atom-correspondence contract than several upstream implementations provide. General charge repair should start as a diagnostic, not a promise of automatic perfection.

The following ranking is engineering judgment about this project's fit, not measured market demand. Requests are illustrative, not quotations.

| Rank | Request a chemist could make | Useful first implementation | Effort / reusable foundation |
|---|---|---|---|
| 1 | Put these products into a four-column substrate scope, numbered 3a onward, with the supplied yields underneath | Explicit ordered fragment list, captions, one bond scale, fixed page width, measured overflow | Moderate; portable grid math exists |
| 2 | Export all these approved schemes for my thesis, with matching editable files and consistent filenames | Explicit file manifest, sequential native exports, per-file audit, HTML contact sheet | Low to moderate; reuse this project's export and working-copy layer |
| 3 | Keep the same scaffold pointing the same way in every analogue | Explicit reference atom mapping and rotation/translation only; report residual mismatch | Moderate to high; matching and constrained depiction libraries exist, but safe CDXML mapping is additional work |
| 4 | Tidy this reaction while keeping the sodium salt together and the conditions centred | Logical components, owned conditions, arrow span sized to text, bounded row placement | Moderate; portable planning code exists, document semantics need extension |
| 5 | Find and fix charges or labels that collide with bonds | Native-render preflight and explicit atom-owned charge placement for a bounded symbol subset | High for repair; no inspected source is a ready-made native ChemDraw charge solver |

## 1. Scope grids, numbering and caption ownership

Michael Leitch's `layout_math.py` already implements `choose_columns`, `grid_positions`, `caption_anchor`, `shelf_pack` and `page_overflow`. It uses point coordinates and separates calculation from Windows automation. That makes its pure geometry a direct candidate for the Mac planning layer; its COM calls are not. The existing project has already adapted only `Box` and `find_overlaps`. [Pinned implementation](https://github.com/MALeitch/live-chemdraw-mcp/blob/a9cebc6cf61e4d9b019463019626684fdf30beb6/chemdraw_connector/domain/layout_math.py), [MIT, copyright Michael Leitch 2026](https://github.com/MALeitch/live-chemdraw-mcp/blob/a9cebc6cf61e4d9b019463019626684fdf30beb6/LICENSE).

Proposed contract: captions belong to explicit logical compound IDs; numbering changes display text, not chemical identity or arbitrary document ID attributes. A supplied yield of zero must remain visible; absent yield is different from zero. Salt fragments occupy one cell. Reordering cells must not change assigned compound identities unless renumbering is explicitly requested. Reject page overflow rather than shrink individual structures.

PyCDXML provides another implemented precedent: a CDXML slide generator with structures, properties and annotations, plus style transfer. Its README distinguishes displayed text from chemical annotations and warns that style changes can misplace other objects. It is GPL-3.0, not a drop-in MIT donor. Use as a behavior reference unless a separate licensing decision is made. [Project and examples](https://github.com/kienerj/pycdxml), [license](https://github.com/kienerj/pycdxml/blob/master/LICENSE.txt).

Acceptance fixture: mixed-size molecules, one two-fragment salt, long names, missing and zero yields, and a deliberately overflowing last row. Native bounds must include captions rather than only atom coordinates.

## 2. Batch native exports and manuscript handoff

The most feasible implementation is local orchestration around our existing native exporter, not a new file converter. Input should be an explicit manifest of source path, stable figure key and requested formats. Each source produces its own new output directory and audit. An interrupted job reports completed and uncertain items separately; it must never repeat an uncertain AppleEvent write automatically.

Useful later precedent: keyClip addresses editable ChemDraw content in Keynote on macOS, but its documented clipboard and keystroke workflow is a separate adapter, not the current native-safe core. Do not promise editable Office objects merely because a slide contains an SVG. [Pinned keyClip documentation](https://github.com/mmaskeri/keyClip/blob/e6782a07a52ab600d643dd8d6060991627a52b21/README.md), [MIT license](https://github.com/mmaskeri/keyClip/blob/e6782a07a52ab600d643dd8d6060991627a52b21/LICENSE.txt).

Acceptance fixture: two valid inputs, one unsupported input, duplicate requested filenames and an existing destination. The report must show exact results without overwriting anything or hiding partial failure. Sequential native access is required until cross-process coordination exists.

## 3. Common-scaffold orientation

RDKit implements reference-constrained two-dimensional coordinates through `GenerateDepictionMatching2DStructure`, including explicit atom-map overloads and hard/soft constraint options. It can calculate coordinates without being the final renderer. Native ChemDraw would still render the resulting CDXML. [Official API](https://www.rdkit.org/docs/source/rdkit.Chem.rdDepictor.html), [BSD-3-Clause license](https://github.com/rdkit/rdkit/blob/23378a7f2f82ae6c867201db8c56ab4cc4a4e671/license.txt).

The community toolkit's `alignment.py` implements rigid rotation and an RDKit-based alignment route. However, inspected routines also use greedy nearest-coordinate matching between MOL and CDXML atoms, and first returned substructure/MCS matches. These are not sufficient guarantees of unique chemical correspondence. Some paths depend on ChemScript; those are not established Mac APIs. [Pinned implementation](https://github.com/ZiChenWang114514/cdxml-toolkit-community/blob/03c4d94dabf20d23b3118a5b2d9afd9d9c90f7d4/cdxml_toolkit/layout/alignment.py), [MIT, original copyright Hiu Fung Kevin Lee 2026](https://github.com/ZiChenWang114514/cdxml-toolkit-community/blob/03c4d94dabf20d23b3118a5b2d9afd9d9c90f7d4/LICENSE).

Proposed first version: the caller identifies corresponding atoms. Permit only a proper two-dimensional rotation and translation, no reflection and no silent re-depiction. Reject ambiguous correspondence or excessive residual mismatch. Symmetric rings, chiral centres, E/Z bonds and explicit H need fixtures. A later opt-in re-depiction mode must be labelled separately because it moves more than the unchanged scaffold.

## 4. Reaction layout with logical components

Leitch's same pure geometry module includes `plan_reaction_layout` with separate intra-group and inter-group spacing, plus `arrow_length_for_reagents`. This is a concrete implementation of keeping disconnected salt ions together and reserving enough arrow span for conditions. Its widths must come from measured native objects, not invented text widths. [Implementation](https://github.com/MALeitch/live-chemdraw-mcp/blob/a9cebc6cf61e4d9b019463019626684fdf30beb6/chemdraw_connector/domain/layout_math.py).

The toolkit's `label_anchors.py` is a useful warning: it restores captions by proximity to fragment bounds, excludes reaction-condition IDs, and updates positions. Our project should keep explicit ownership rather than inherit that heuristic as certainty. [Pinned source](https://github.com/ZiChenWang114514/cdxml-toolkit-community/blob/03c4d94dabf20d23b3118a5b2d9afd9d9c90f7d4/cdxml_toolkit/layout/label_anchors.py).

A real Indigo report concerns unwanted rearrangement on CDXML import. This is evidence for a preservation test, not evidence that all present Indigo imports fail. [Issue 2810](https://github.com/epam/Indigo/issues/2810).

Acceptance fixture: a salt, a catalyst above the arrow, multiline conditions below, product captions and a width limit. No accidental plus sign inside one compound; no chemical role inferred solely from where a component happened to be drawn.

## 5. Charge and label collision preflight

Ketcher records real descriptor/bond overlap defects, including after structure movement. These support testing annotations after transformations, not only checking molecular graphs. [Descriptor overlap issue](https://github.com/epam/ketcher/issues/219), [CIP-label overlap issue](https://github.com/epam/ketcher/issues/7318).

The linked fix changes CIP rendering and removes an opaque rectangle's fill/stroke. It is not a general charge-position optimizer and cannot simply be transplanted into ChemDraw. [Actual change](https://github.com/epam/ketcher/pull/7332/files), [Ketcher Apache-2.0 license](https://github.com/epam/ketcher/blob/df40dd518ab6122bb768c93fe27e697f9c4cd994/LICENSE).

Proposed diagnostic: inventory the formal charge, attached native symbol, measured symbol dimensions, and nearby bond/text extents. Proposed bounded repair: test candidate locations around the owning atom, prefer free angular sectors, enforce fixed native symbol dimensions and minimum visible clearance, then re-export. This candidate search is our design proposal, not an upstream implementation claim. Preserve chemistry separately from symbol appearance and leave unresolved cases for review.

Acceptance fixture: nitro groups in several orientations, crowded quaternary ammonium, zwitterions, isolated ions and a case with no valid placement. Correct rejection is preferable to inventing a visually detached charge.

## Reuse boundary and next deliverables

Only small pure geometry functions are immediate code-reuse candidates. New adaptations require immutable provenance entries and retained license notices before distribution. No code was added by this research, so the existing copied-code notice inventory is unchanged. Proprietary ChemDraw templates and sample artwork are not relicensed by an open-source wrapper.

After the approved analogue editor, propose one user-visible increment at a time: scope-grid recipe and native demo; batch export manifest and contact sheet; explicit scaffold alignment; reaction-component ownership; charge preflight followed by bounded repair. Each needs CLI and MCP access, native output, failing-first regressions and a documented unsupported boundary.
