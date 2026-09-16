# Explicit coordination drawings

## Spatial chelates (development checkout)

The newer schema 2 can draw the spatial ruthenium chelate example with plain axial bonds, solid front wedges and hashed back wedges. Atom labels are **black by default**. The optional per-atom `color: "#RRGGBB"` is only for deliberately requested highlighting; blue nitrogen is not a house-style default.

```sh
uv run --locked --extra chemistry chemdraw-mac complex-draw --recipe examples/coordination-ruthenium-chelate.json --output /absolute/new/ruthenium
```

This uses the same MCP endpoint below. Schema 2 retains the atom fields and adds required top-level `attachments` (normally `[]`) and `overall_charge` (`null` or a nonzero integer from -8 to 8). Each bond additionally requires `display`. Explicit `order: "coordination"` is drawn as native order 1 with `Solid`, `WedgeEnd` or `WedgedHashEnd`; begin is the donor and end is the metal, so the wedge narrows at the metal. This is a conventional perspective depiction, not a dative-arrow bond. `dative` remains a separate, directed native bond type.

Overall charge is an editable **top-right corner annotation**, using two native lines and the charge text. It is checked separately from atomic formal charges, and is not a claim that a downstream structure parser will calculate that net charge. It is not an oxidation-state assignment. ChemDraw supersedes line graphics with arrow objects without arrowheads; the validator checks both the relationship and endpoints. This avoids the slanted, full-height unmatched bracket from the initial prototype.

The ruthenium fixture is an original procedural projection of three 2,2'-bipyridine ligands. The ligand connectivity matches the [PubChem description](https://pubchem.ncbi.nlm.nih.gov/compound/1474). It is not a resolved crystal structure and no Delta/Lambda assignment is certified. XYZ are drawing coordinates, not physical measurements. Native ChemDraw reports valence warnings on the conventionally bonded donor nitrogens. Those warnings remain visible in ChemDraw and are retained in `audit.json`, not suppressed or presented as chemical validation.

## Multicentre work: experimental, ferrocene blocked

Schema 2 can express `attachments: [{id, position: [x,y,z], atoms: [atom_ids]}]`. These become actual native `MultiAttachment` nodes with `Attachments`, not dummy carbon atoms. An optional `ellipse: [width,height]` creates a separate native ring outline. `order: "haptic"`, `display: "Solid"` connects a multicentre begin to a metal end using a normal native bond. Bond list order defines drawing depth; native crossing foreground order is checked. Optional perspective displays on aromatic attachment-ring bonds are `Solid`, `WedgeBegin`, `WedgeEnd` and `Bold`.

**Do not advertise the ferrocene recipe as working.** `examples/coordination-ferrocene.json` is a regression fixture for a refused drawing: on the tested native CDXML path, requested aromatic order `1.5` saves as ordinary single bonds. Native multicentre membership survives, but chemistry does not. The workflow detects the changed order/effective hydrogen count, fails, and closes only its own determinate failed copy. It does not return a successful PNG/review. The installed native binary template preserves aromatic order, so this is not a claim that ChemDraw itself cannot draw ferrocene.

Distributed charge on a multicentre node was also discarded in a separate native probe. It is therefore not accepted by this recipe schema. No silent loss, arbitrary charge reassignment, substituted renderer or hidden warning suppression is used to force success. The private installed-template inspection supplied only a format pattern; none of its artwork or coordinates is included here.

These changes are development-checkout work. The existing 0.10.0rc2 test archive was not rebuilt or replaced.

## Original schema 1

Experimental first slice, tested with ChemDraw 23.0.1.11 on the development Mac. This is a native editable drawing workflow, not a 3D modeller, structure resolver or chemical plausibility validator.

```sh
uv run --locked --extra chemistry chemdraw-mac complex-draw --recipe examples/coordination-explicit.json --output /absolute/new/complex-output
```

The matching MCP tool is `chemdraw_draw_complex(recipe, output_dir, preset="house", pixels=2400)`. Both interfaces call the same implementation. Outputs are native CDXML/SVG, PNG rasterized from native SVG, an HTML review, the supplied request and a preservation audit. The final private working copy stays open; pre-existing documents are checked for changes. Native uncertainty stops without retries or automatic closure.

## Input contract

The recipe has exactly `schema_version: 1`, `label`, `atoms` and `bonds`. Every atom supplies a unique `id`, `element`, integer formal `charge`, explicit `hydrogens`, and `position: [x, y, z]`. Every bond supplies `begin`, `end` and string `order`: `1`, `2`, `3` or `dative`. Dative bonds start at the donor and end at the metal. Formal charge is not an inferred oxidation state.

Coordinates are **CDXML points**, not angstroms. X/Y define the drawing projection and must fall within 40..540 and 40..650 pt respectively. Z is retained as supplied metadata; nonzero Z does not automatically produce a wedge, perspective or shaded model. No cleanup, scale normalization, geometry optimization or inferred stereochemistry runs. The example deliberately contains nonzero Z values to test preservation, not to assert a preferred real-world copper geometry.

The bounded subset allows one connected complex, 2..80 atoms, 1..120 bonds and at least one dative bond. Donors are N/O/P/S/F/Cl/Br/I. Metal endpoints are Mg/Al/Ca/Cr/Mn/Fe/Co/Ni/Cu/Zn/Ru/Rh/Pd/Ag/Ir/Pt/Au. Other ordinary atoms are H/B/C/N/O/F/Si/P/S/Cl/Br/I. All metal bonds must be dative in this first slice. This element list is a parser boundary, not a native chemistry certification matrix.

## Preservation and limits

Native saved records must retain atom elements, formal charges, hydrogen counts, labels, projected coordinates, effective XYZ, bond direction/order/display and caption. ChemDraw omits XYZ when Z is zero; this is compared as the equivalent X/Y/0 tuple. Missing nonzero Z fails. Multi-charge labels use an explicit superscript run: writing `Cu2+` as one chemically interpreted plain run was experimentally found to create a nested two-copper fragment and is not used.

The actual direct workflow and fresh stdio MCP round trip both passed with the five-atom copper/ammine fixture. The exported image was inspected on white. This does not establish arbitrary complexes, hapticity, metal-metal bonds, multicentre bonding, ligand-field geometry, fac/mer or cis/trans assignments, stereochemical descriptors, radicals, isotopes, disconnected counterions, circled multicharges or automatic collision-free layout. Ordinary organic grid/polish/edit validators do not gain metal support from this separate entry point. Human chemistry and visual review remain required.

Format references: [native bond order](https://iupac.github.io/IUPAC-FAIRSpec/cdx_sdk/properties/Bond_Order.htm), [XYZ position](https://chemapps.stolaf.edu/iupac/cdx/sdk/properties/3DPosition.htm). Only format semantics informed the original implementation; no vendor artwork or source was copied.
