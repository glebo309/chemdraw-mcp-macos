# Standard substrate scope: request and implemented boundary

Glenn's request, 2026-09-15: given a parent aromatic substrate, propose the familiar electronic, positional and steric variants expected in a substrate-scope study. A first bounded offline proposal is now callable through CLI and MCP, distinct from native drawing and scope-grid layout. No candidates are experimental results and no yields are invented. The broader request below remains the design direction; [proposal usage](SCOPE_DESIGN_USAGE.md) defines the implemented subset.

## The request it should answer

"Make a standard scope for this substrate: the usual electron-withdrawing and donating substituents, bulky cases, and methyl in ortho, meta and para positions."

The parent structure and reaction handle must be explicit. Keep the functional group being transformed and the conserved scaffold fixed. If the parent or transformation is unknown, ask for it rather than choosing a reaction.

## Coverage blocks

- Parent/unsubstituted reference.
- Electronic variation: representative Me/OMe donors and CF3/CN/NO2 withdrawing groups, at matched positions where feasible. These are candidate choices, not a universal compatibility list.
- Halogen series as its own group, rather than treating halogens as interchangeable with strongly withdrawing substituents.
- Positional variation: matched 2-, 3- and 4-methyl examples relative to the reaction handle. Extend to another matched substituent series only when useful.
- Steric variation near the reaction handle: ortho-Me, ortho-iPr, ortho-tBu and 2,6-dimethyl as illustrative candidates. Sterics and electronics are not perfectly separable controls.
- Optional broader scaffold set: heteroaromatics, fused aromatics or other motifs relevant to the specific transformation.

Deduplicate equivalent substitutions using the actual parent graph and its symmetry. Do not duplicate para-methyl if it already appears in both the electronic and positional blocks; tag one candidate with both reasons. A substituent's name is not enough to locate it safely on an already substituted ring.

## Proposal output

Each implemented candidate returns a checked molecular graph, graph-derived candidate ID, changed atom/site, relative display label, coverage categories and short rationale. Labels describe changes relative to the supplied parent, not inferred systematic names. Compatibility questions are separate from claims of likely reactivity. All proposed yields are blank. Review and select candidates before composing a native drawing.

The available flow is: explicit parent and handle anchor, candidate list with rationale, chemical/identity review and selection, explicit SMILES records for native structure creation, then measured scope-grid production. The drawing command receives `compound_id`, `label` and `smiles` records; it does not accept a proposal JSON file directly. A larger expanded proposal profile remains future work, and size should follow requested coverage rather than padding with arbitrary molecules.

## Current implementation boundary

The offline `standard` profile supports one explicitly mapped anchor on an isolated, neutral, non-isotopic, monosubstituted benzene ring. It retains the existing reaction handle and yields 14 unique candidate graphs covering the listed starter categories. Supported assigned tetrahedral stereo outside the ring is checked; ambiguous/unsupported stereo and substitutions that create new stereocentres fail closed. Pre-substituted, fused and heteroaromatic selected rings remain unsupported. See the usage reference for the full exclusions.

The native grid tool still arranges supplied structures rather than designing a scope. The existing analogue editor still changes explicit atoms/H or bond orders without inserting substituent fragments into a native drawing. The separate offline proposer constructs its own checked candidate graphs, and the explicit-SMILES drawing tool imports new private MOL seeds into ChemDraw, runs native cleanup and hands the native structures to grid layout. These are separate supported operations, not a general native substitution editor.

Preserving the parent graph alone does not preserve a common depiction across separately cleaned candidates. Drawing can now use an explicit `scaffold_smiles` to align each candidate to the first native structure using rotation and translation only. It rejects poor fits and never reflects or rescales a scaffold. Automatic scaffold inference remains future work. Native label remeasurement and visual inspection are required. No reaction prediction, yield prediction, external database lookup, universal literature-coverage claim or new standalone application is implied.
