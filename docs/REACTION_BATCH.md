# Complete reaction batching

Use `chemdraw_draw` or CLI `produce` for an explicit single-step reaction.
Supply every reactant and product in the request. Products, balance, mechanism
and experimental outcomes are not inferred.

The workflow retains water and other supported small species as participants.
It does not shorten supplied labels or conditions to make a row fit.

## Paper and exports

`reaction_paper` accepts `auto` (default), `A4 portrait`, `A4 landscape` or
`A3 landscape`. Local staging uses estimated text widths; after one complete
native measurement, `auto` selects the smallest supported sheet that fits actual
ink. A fixed paper choice must pass both staging and native measured checks.
Oversized requests fail with a layout explanation, not a smaller molecule scale.
No endless canvas or cross-page reaction splitting is introduced.

Full delivery contains:

- Editable CDXML with a native-verified physical paper record.
- Cropped SVG with point-sized dimensions and unchanged native artwork.
- Transparent PNG at 600 DPI, with physical-resolution metadata.
- White 1200-pixel review preview, recipe, input provenance and audit.

House bond length remains 18 points. Equal physical scale does not mean equal
image dimensions. Insert the SVG or DPI-aware PNG at its physical size; fitting
every image to an identical width would change the apparent molecular scale.

## Native operations

The complete explicit graph batch is assembled locally. ChemDraw opens one
hidden measuring document, then one hidden final document. Reactions with unit
formal charges add one whole-document measurement for the circled-charge ink.
There are no separate
native imports or cleanup calls for each participant. `background` and `auto`
close the owned documents after verification. `interactive` additionally opens
a verified presentation copy. Existing documents are not edited or closed.

An active untitled original is read through the installed add-in, without binding
it to a filename. This needs the add-in connection. Do not use mouse actions,
save an original, or close user documents to bypass a failed preservation check.
Explicit `shared` reaction requests remain unsupported rather than silently
redirecting to another document.

ChemDraw is still a licensed desktop application. Native opening can briefly
flash a window; this is not a display-free renderer. A native operation with an
unknown outcome stops without retry or automatic closure.

## Validation and limits

Portable regressions cover complete glycoside input, water retention, label and
condition preservation, early overflow, uncertain-write behavior, native style,
physical-paper checks, collision rejection, export scale and input provenance.
Native acceptance checks the complete glycoside reaction and all three paper
formats on ChemDraw 23.0.1.11. See [release validation](../PROJECT_PROGRESS.md).

The print record is calibrated against native blank-document exports. The
[archived CDX SDK description](https://iupac.github.io/IUPAC-FAIRSpec/cdx_sdk/properties/MacPrintInfo.htm)
alone was insufficient: a minimal record fell back to portrait pages. A2 also
normalized to another paper on the tested Mac and is deliberately unavailable.
Other printer configurations and ChemDraw builds need separate acceptance.

Fresh seeds with exactly one explicit carbon-bound nitro group receive a rigid
orientation that leaves space for the nitrogen charge. Atom distances, graph,
stereo and scale are preserved and checked after native import. This is not
general charge-placement repair or a change to existing user drawings.

From rc18, ordinary batched reactions display existing +1/-1 atom charges as
native editable circled symbols. Placement uses measured labels, conservative
bond envelopes and atom ownership. The saved native result must preserve every
charge association and at least 2 pt clearance from bonds, labels and other
symbols. Native circled-symbol bounds are measured before final row layout, so
caption centring and paper fit include the circles. No safe placement is a
failure, not permission to overlap a bond or silently remove the circles.
Other charge magnitudes retain their native labels. Existing user documents and
the older explicit `reaction`/`reaction-series` workflows are not restyled.

The advanced `reaction` and `reaction-series` tools retain their older supported
subsets and page behavior. Electron-flow annotations remain separate operations.
Measured screening is not a universal collision-free certificate; inspect the
native preview before using the figure.
