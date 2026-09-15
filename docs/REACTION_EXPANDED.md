# Explicit expanded reaction schemes

The reaction-specific builder accepts water, selected isolated ions, disconnected ionic salts, coefficients and one through three explicitly supplied steps. It produces one editable ChemDraw document with one stacked row per step. Native import, cleanup, saved chemistry and measured layout checks remain mandatory. The general molecule drawing subset is unchanged.

## Python API

```python
from chemdraw_macos.reaction_series import build_reaction_series

result = build_reaction_series(
    bridge, steps, "/absolute/new/output-directory",
    preset="house", pixels=3200,
    layout={"gap": 16, "label_gap": 10, "condition_gap": 10,
            "row_gap": 120, "margin": 36},
)
```

See [the example input](../examples/reaction-expanded.json). Each step has an explicit `step_id`, `reactants`, `products`, and optional `conditions_above` and `conditions_below`. Each side contains one through three participants. A participant requires `compound_id`, `label`, `smiles` and optionally `coefficient`. Products, conditions, labels and coefficients are supplied by the caller, never inferred.

`build_reaction` also accepts these expanded participants and the optional `layout` argument. Ordinary connected inputs without coefficients or custom spacing retain the original one-step route. Explicit scaffold alignment remains supported on that original route, but is rejected on the expanded route. This limitation is not silently ignored.

## Supported chemistry and ownership

- Ordinary connected molecules retain the existing draw validator's supported atom, bond and stereochemistry restrictions.
- Isolated participants are water (`O`), hydroxide (`[OH-]`), halide anions (`[F-]`, `[Cl-]`, `[Br-]`, `[I-]`) and alkali ions (`[Na+]`, `[K+]`). Other isolated atoms, radicals, metals and unspecified alternatives are rejected.
- A disconnected salt contains two through four supported components. Every component must have nonzero formal charge, and their summed formal charge must be zero. Neutral mixtures, hydrates and incomplete counterion sets are rejected.
- Salt components are separately seeded and checked, then kept under one participant record, one caption and one coefficient. They are not rendered as separate reaction participants joined by a plus sign. The native reaction role references every constituent fragment; the saved recipe retains their participant ownership.
- IDs are unique across both sides within a step. An ID reused between steps must retain exactly the same canonical graph and label. Repeated component graphs reuse the same cleaned native coordinates before translation, preserving their orientation. No atom mapping or automatic intermediate connection is claimed.

Each component has a checked RDKit MOL seed. Ordinary components are imported from that seed and cleaned by ChemDraw. Na+/K+ instead use a bounded explicit CDXML ion seed based on the project's native-tested isolated sodium fixture: the native MOL import was observed to add `AbnormalValence`, which the strict chemistry checker rejects. This is not a general permission to strip or ignore chemical properties. The explicit CDXML seed is checked before native creation and again after native cleanup; its corresponding MOL remains in the provenance directory. Native validation of the expanded production workflow is tracked separately from portable tests.

## Coefficients and layout

Coefficients are finite positive JSON numbers up to 999 with at most three decimal places. Booleans, strings, zero, negative and nonfinite values are rejected. The default is 1 and is not printed. Printed coefficients use the atom-label font size and sit 6 pt left of the participant's measured molecular bounds, vertically centered on the reaction row.

All configurable distances are in points:

| Field | Default | Accepted range | Meaning |
| --- | ---: | ---: | --- |
| `gap` | 16 | 4–60 | Equal gaps between occupied participant, plus and arrow layout units |
| `label_gap` | 10 | 4–60 | Clearance below row content before the shared caption line |
| `condition_gap` | 10 | 4–60 | Clearance from arrow bounds to above/below conditions |
| `row_gap` | 120 | 12–120 | Gap between the previous row's bottom and next row's top |
| `margin` | 36 | 0–100 | Inset from the native single-page bounds |

Salt components have a fixed internal 12 pt gap. Labels are centered below molecular bounds, not below the coefficient. Labels share a baseline within each row. Conditions are centered on their own arrow. Long labels participate in spacing calculations. Overwide or overtall schemes fail with a page-fit error; the builder does not shrink molecules or silently create additional pages. Initial text placement uses conservative bounds before the combined native export measures glyphs, so some long-text inputs can be rejected even when their final native text would be narrower. Use explicit shorter labels or a smaller supported gap/margin; this version does not automatically abbreviate names. The compact example uses an 8 pt gap and 18 pt margin on the observed 523 pt native page.

The 120 pt default row gap is intentional. A native two-row probe at 30 pt reassigned the previous row's product caption as an additional condition above the next arrow. The final semantic check rejected that output. The same measured plan passed native role and geometry checks at 120 pt. Smaller explicit gaps remain available, but may fail if ChemDraw reinterprets nearby captions; visual non-overlap alone does not establish correct reaction ownership. The verifier is not weakened to accept these changes.

## What the checks establish

The native output is checked for mapped component chemistry and existing stereochemistry, reaction roles, source-coordinate preservation after planned transforms, salt component ownership, coefficient values and placement, caption/condition alignment, page fit, coarse interobject bounds collisions and bond scale where bonds exist. Single-atom participants have no bond-length statistic. Original open documents are checked for unchanged inventory and content.

The workflow writes `figure.cdxml`, `figure.svg`, `figure.png`, `review.html`, seeds, plan and audit. An uncertain native operation stops without retry or automatic close. Determinate failures only close working copies owned by that job.

The audit deliberately reports `chemical_balance_certified: false`. Supplied coefficients are not proof of atom or charge balance, reaction feasibility, experimental conditions or mechanism. Ordered rows are explicit coordinated steps, not an inferred synthesis network. Bounding-box checks are not complete native glyph, bond-ink or stereochemical visual approval. Inspect the generated review before publication.
