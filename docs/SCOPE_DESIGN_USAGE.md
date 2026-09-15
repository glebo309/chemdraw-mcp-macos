# Offline standard aromatic scope proposals

`chemdraw_macos.scope_design.propose_scope` builds a small, deduplicated list of candidate molecular graphs from an explicitly supplied parent. It makes no network or ChemDraw calls and writes no files. RDKit is the optional graph construction and validation dependency, not a renderer. The public CLI and MCP integration uses this same function; consult the main usage reference for those entry points.

```python
from chemdraw_macos.scope_design import propose_scope

# Acetophenone is an illustrative software example, not a proposed experiment.
proposal = propose_scope('CC(=O)[c:1]1ccccc1', handle_atom_map=1)
```

The mapped atom is the aromatic carbon attached to the existing reaction handle, not an inferred reacting atom. The entire existing handle is retained. `profile` currently accepts only `standard`. A client must obtain the actual parent and identify the intended ring attachment explicitly rather than choosing a reaction from context.

## CLI and MCP entry points

```sh
uv run --extra chemistry chemdraw-mac propose-scope \
  --parent 'CC(=O)[c:1]1ccccc1' \
  --handle-map 1
```

The CLI prints proposal JSON. It does not draw, save a proposal file or contact ChemDraw. The equivalent MCP call is `chemdraw_propose_scope(parent_smiles="CC(=O)[c:1]1ccccc1", handle_atom_map=1, profile="standard")`.

`examples/standard-scope-parent.json` records these example arguments. It is a data fixture, not a CLI manifest input: the current command accepts `--parent` and `--handle-map`, not an input-file flag.

## Candidate coverage

The standard profile returns 14 unique graphs for a supported parent:

- Original parent reference.
- 2-, 3- and 4-Me positional series, relative to the handle.
- 4-OMe, 4-CF3, 4-CN and 4-NO2 electronic comparisons.
- 4-F, 4-Cl and 4-Br halogen series.
- 2-iPr, 2-tBu and 2,6-Me2 steric comparisons.

The 4-Me candidate belongs to both positional and electron-donating categories. The 2-Me candidate belongs to both positional and steric categories. Duplicate chemical identities merge their categories and rationales rather than producing repeated compounds. Electronic and steric effects are not asserted to be perfectly separable.

## Output contract

The JSON-compatible result has `schema_version: 1`, `status: "proposal"`, `profile`, `parent`, `candidates` and `limitations`.

Each candidate contains:

| Field | Meaning |
|---|---|
| `candidate_id` | `scope-` plus the first 16 hexadecimal characters of the SHA-256 of its map-free canonical isomeric SMILES |
| `canonical_smiles` | Sanitized molecular graph without atom-map tags |
| `mapped_smiles` | Molecular graph retaining the caller's original parent atom-map tags |
| `display_label` | Relative description such as `2-Me relative to parent`, not a generated systematic name |
| `substitutions` | Added substituent, ring position and zero-based atom index in the parsed parent |
| `categories`, `rationale` | Coverage reasons, with duplicates merged |
| `compatibility_questions` | Review prompts, not claimed compatibility or synthetic accessibility |
| `yield_percent` | Always `null`; no results are generated |
| `checks` | Computed parent graph, supported stereo and SMILES roundtrip checks |

Parent atom indices address this specific parsed input, not a later ChemDraw document. Ring positions begin at the handle carbon as position 1. The two directions are equivalent for the supported monosubstituted benzene graph. These are relative scope positions, not guaranteed whole-molecule IUPAC locants. Changing the input atom-map numbers does not change graph-identity candidate IDs. ID stability follows the canonicalization provided by the locked RDKit environment; it is not guaranteed across arbitrary future canonicalization versions.

## Validation and exclusions

The selected ring must be a single isolated, neutral, non-isotopic, six-carbon aromatic ring. Its anchor must have exactly one existing bond to an outside atom. All five other ring carbons must have one hydrogen and no outside substituent. The graph must be connected, with at most 200 atoms and unique supplied atom maps.

Assigned tetrahedral stereochemistry outside the selected ring is retained and checked. Substitution that creates, removes or changes the supported stereo inventory fails. Unspecified potential stereocentres, alkene stereo, enhanced stereo, ring isotopes, fused or heteroaromatic selected rings, pre-substituted selected rings, disconnected salts, dummy/query/radical atoms and unsupported bonds are rejected. Explicit hydrogen atom nodes are rejected instead of silently removed; attached H counts on supported atoms are handled explicitly. Ordinary charges and isotope labels in the retained outside handle are preserved.

For every candidate the implementation checks original atom element, isotope, charge, map, aromaticity, radical count and chiral tag; original bonds and their supported stereo; hydrogen counts with exactly one H removed at each new attachment site; the supported stereochemical inventory; and canonical isomeric SMILES roundtrip. These checks establish the stated graph transformation, not suitability for any chemistry.

## Review boundary

This is candidate design, not reaction prediction, yield prediction, literature coverage, availability lookup, systematic naming or an experimental recommendation. Review the parent and proposed candidate list before selecting structures for a native drawing. Rendering and figure layout belong to the separate native ChemDraw production workflow. A graph passing these checks is not a publication-ready drawing or a chemically approved experiment.

## Draw explicitly selected candidates

After review, create a drawing manifest with a `structures` list. For each selected candidate, supply a short, unique `compound_id`, an explicit `label` and its map-free `canonical_smiles` as `smiles`. Do not pass `mapped_smiles`, the whole candidate object, proposed yields or the proposal JSON directly to `draw`. No built-in parser selects candidates or turns a proposal file into a drawing manifest.

Choose readable drawing IDs such as `a`, `b` and `c`; graph-derived proposal IDs are useful for provenance but can make long captions. Labels are caller supplied and are not verified as chemical names. A manifest also accepts `schema_version: 1`, `preset`, `columns`, `pixels` and optional `scaffold_smiles`.

The independent three-structure drawing fixture exercises ethanol, a chiral isotope-labelled graph and nitrobenzene, not an acetophenone scope:

```sh
uv run --extra chemistry chemdraw-mac draw \
  --manifest examples/draw-structures.json \
  --output /absolute/existing/parent/native-structures-review
```

Choose a new absolute output directory whose parent exists. The fixture requests three columns. The equivalent MCP tool is `chemdraw_draw_structures(structures=[...], output_dir="...", columns=3)`; pass only the structure records as `structures`, not the entire manifest.

RDKit supplies a MOL graph/coordinate seed. Actual desktop ChemDraw imports it, runs native Clean Up Structure, saves and renders it, followed by the native-measured grid workflow. Existing originals are not the cleanup targets. Graph identity is checked after native import and cleanup, and the final grid carries its own audit. The final native document remains open and the output includes an HTML preview plus editable CDXML, SVG and PNG. Successful checks still require visual review.

Candidates are cleaned separately. To retain a common depiction, provide an explicit `scaffold_smiles`, as in `examples/acetophenone-scope-draw.json`. Each normalized native candidate is aligned to the first structure by proper rotation and translation only, with no reflection or scaling. Fits above 0.25 pt RMSD fail; the native application then remeasures the drawing before final grid layout. The explicit scaffold must match every input. No scaffold is guessed automatically, and symmetric matches do not establish correspondence outside that scaffold. Drawing support is a separate bounded subset, so a valid proposal graph is not an unconditional guarantee of successful native rendering.
