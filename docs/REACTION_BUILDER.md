# Explicit native reaction builder

Implementation date: 2026-09-15. Portable tests cover composition and guarded workflow behavior. Native compatibility and visual approval must be recorded by the serial native test run before this feature is described as validated on an application version.

## Contract

Python workflow:

```python
build_reaction(
    bridge,
    reactants,
    products,
    output_dir,
    conditions_above='',
    conditions_below='',
    preset='house',
    pixels=3200,
    scaffold_smiles=None,
)
```

Supply one through three records on each side. Each record has exactly `compound_id`, `label` and `smiles`. IDs are case-insensitively unique across the whole request. Label and strict SMILES validation reuse the existing `draw` input path. Labels and conditions are caller-supplied, not generated chemical names or experimental claims.

```json
{
  "reactants": [{"compound_id": "r1", "label": "Ethanol", "smiles": "CCO"}],
  "products": [{"compound_id": "p1", "label": "Ethanal", "smiles": "CC=O"}],
  "conditions_above": "[O]",
  "conditions_below": "",
  "preset": "house",
  "pixels": 3200
}
```

This is an illustrative composition input, not a specified oxidation protocol. The workflow does not balance the reaction, predict products, infer reagents, assign stoichiometric coefficients, calculate yields or validate mechanism feasibility. The explicit side/order and graph of every record define what is drawn.

## Input boundaries

- The inherited native creation subset is one connected nonradical graph of 2 through 150 atoms per record, with H/B/C/N/O/F/Si/P/S/Cl/Br/I. This first version therefore does not draw a standalone one-atom water/halide record or disconnected salt as a molecular participant. It must not silently invent an alternative depiction.
- `compound_id` uses the draw workflow's safe 1 through 32-character identifier rule. Labels are nonblank, single line and at most 120 characters.
- Each conditions field is empty or nonblank single-line text of at most 120 characters, with no control characters. Multiline conditions and arbitrary annotations are not supported.
- Preset is `house`, `acs-1996`, or a validated numerical style dictionary from the style-import interface. Custom label/caption font families must be installed before native production; caption font and supported face are retained. Pixels is an integer from 256 through 8192.
- The output directory must be new, absolute, nonsymlink and have an existing parent.
- Optional `scaffold_smiles` must satisfy the existing explicit-core alignment validator and match every reactant and product. Alignment uses proper rotation and translation after preset normalization, not reflection or core inference. A different core for each side is not implemented.

Input and scaffold validation run before native calls. A conservative initial one-row fit can reject a large set even when its record count is valid. The workflow retains the first import's page settings; it does not resize the physical page or shrink individual molecules to force a fit.

## Production procedure

1. Prepare strict graph-checked MOL seeds with the existing draw helper. RDKit supplies the seed coordinates; it does not render the exported figure.
2. Import each seed as a private native document, verify identity, run native Clean Up Structure, then verify identity again. Close only the successful private seed document.
3. Optionally align the explicitly supplied core. Combine the cleaned native fragments with normalized scale and unique object IDs.
4. Add one native rightward reaction arrow, explicit plus signs, owned name captions and above/below conditions. The arrow attributes follow the already exercised oxidation fixture, not a new inferred format. Explicit CDXML scheme roles bind reactants, products, arrow and condition objects.
5. Import this composition and verify native object/role preservation. Native saved text bounds replace conservative staging estimates.
6. Reuse the measured row planner. All main-component gaps grow together if captions require more space. A row with overlap or native-page overflow is rejected; molecular scale is not reduced. Captions share a baseline and conditions are centred over/under the arrow.
7. Native-save and export the final drawing. Verify mapped chemistry, supported stereo and coordinates, explicit role/caption binding, arrow/condition placement, scale, spacing and measured page fit. Compare pre-existing documents and retained unsaved content before acceptance.

The final editable document remains open; intermediate private documents close with backups. Any native exception becomes `NativeUncertain`: no retry and no subsequent automatic close. Determinate local validation failures may close owned documents. Pre-existing user documents are never an editing target.

## Outputs and audit

The new directory contains `request.json`, `recipe.json`, `audit.json`, `review.html`, native `figure.cdxml`, `figure.svg`, `figure.png`, `combined.cdxml`, `combined-native.cdxml`, `planned.cdxml`, `post-export.cdxml`, and retained per-compound MOL/imported/cleaned snapshots in `seeds/`.

The saved recipe binds native composition IDs and records role order, caption ownership, condition sides, main-component gaps and saved-page region. The final audit maps those roles to actual native output IDs and reports measured bond lengths and gaps. It verifies the supplied product graphs rather than claiming the reaction preserves reactant identity.

`checks_passed` means implemented checks passed. `failed` and `uncertain` artifacts are diagnostic. `visual_review` remains `required`: chemical graphs and CDXML label content do not establish all glyph positions, subscript rendering, intramolecular collision clearance or correctness of the user's chemistry. No automatic mechanism curves or electron/charge symbols are added.

## Pure helpers and tests

- `compose_reaction(native_texts, reactants, products, ...)` returns composed CDXML and explicit ownership. Native snapshots must be ordered reactants first, then products.
- `arrange_reaction(native_text, recipe)` requires native-measured bounds and returns the planned row plus its audit geometry.
- `verify_reaction(planned, native, plan)` uses the existing mapped preservation verifier and adds reaction-specific role, label, spacing and page checks.

Portable tests cover role metadata, unique IDs, conditions, input rejection before native access, identity changes, page overflow, caption alignment, corrupted native roles/labels/positions, missing explicit cores, lifecycle preservation and no retries/closes following native uncertainty. Fake rendering in these tests is deliberately limited to bounds and cannot establish actual ChemDraw typography.
