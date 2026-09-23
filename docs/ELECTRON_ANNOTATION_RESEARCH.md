# Electron and mechanism annotation: working reference

Historical design notes, reviewed 2026-09-15. The current README and usage guide define the implemented annotation, symbol and routing tools. Native manual-drag attachment remains unverified.

## Start from the working drawing

The [SN2 input](../examples/sn2-annotation-input.cdxml) and [annotation recipe](../examples/sn2-annotation-recipe.json) provide a reproducible two-arrow example. Curves are native CDXML objects rendered by ChemDraw, not mouse-drawn overlays.

The saved curves have `CurveType="8"`, `ArrowheadHead="Full"`, `LineWidth="0.90"` and six coordinate pairs in `CurvePoints`: start, start, first control point, second control point, end, end. The nucleophile-to-carbon and bond-to-iodine curves are already working visual examples. Their source and target are described in the recipe, but the curves do not encode atom/bond ownership. Existing audit checks identity and curve count, not endpoint clearance, saved arrowhead geometry or attachment behavior.

Export by explicit document ID through the owned working-copy bridge, not by whichever document happens to be frontmost.

## Native object support

The archived manufacturer's [symbol specification](https://chemapps.stolaf.edu/iupac/cdx/sdk/properties/Symbol_Type.htm) enumerates `LonePair`, `Electron`, radical-ion symbols and circled charges. The [curve specification](https://chemapps.stolaf.edu/iupac/cdx/sdk/properties/Curve_Type.htm) defines full arrows at either end and half-arrows at either end. The full end arrow has flag 8; the half end arrow has flag 32. These are native editable objects, not typed punctuation or raster overlays.

Read-only inspection of installed ChemDraw examples also found LonePair/Electron symbols and ArrowSource/ArrowTarget references. This is file-format evidence, not a demonstrated modern attachment API. The older [RepresentsProperty documentation](https://chemapps.stolaf.edu/iupac/cdx/sdk/properties/RepresentsProperty.htm) explicitly cautions about read behavior; test saving and moving owned symbols rather than assuming a represent element guarantees attachment.

## Proposed bounded next feature

1. Turn the existing SN2 curve planning into a regression fixture using the current bridge. Preserve the original style and chemistry.
2. Expose explicit source and target IDs in an annotation recipe: atom, bond, or supported electron symbol. Full head means an electron pair; half head means one electron. Do not infer a complete mechanism from layout alone.
3. Add lone-pair and single-dot fixtures. Distinguish visual annotation from an actual radical-state graph change; never silently change chemical state to make a symbol render.
4. Verify curve points, head type/direction, symbol identity and dimensions after native saving. Measure endpoint clearance from label/bond ink and report unresolved collisions.
5. Ship CLI and MCP together, with editable native output, before/after preview, preservation audit and required visual review.

Current polish/grid/batch validators are not the annotation tool: curves and molecular symbol graphics remain outside their supported subset. The low-level native bridge can import/export such CDXML, but that does not establish safe automatic editing. Fishhook rendering and moving attachment still need project-specific native tests.

No proprietary installed templates or artwork were copied into the repository. No mechanism implementation or third-party source was incorporated by this research.
