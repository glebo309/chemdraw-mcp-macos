# Explicit-site aromatic scope proposals

`propose_custom_scope(parent_smiles, site_atom_maps, substituents, include_parent=True)`
extends offline candidate design to pre-substituted aromatic rings and simple
heteroaromatics. The existing `propose_scope` standard profile retains its original
monosubstituted benzene restriction and fourteen-candidate output.

The caller supplies each attachment site as an atom map on an H-bearing aromatic
carbon in the actual parent. Map numbers identify supplied atoms, not systematic
ring positions. No reaction handle, reactive site or substituent position is inferred.

## Examples

```python
from chemdraw_macos.scope_design import propose_custom_scope

# Pyridine: the explicitly mapped carbon sites receive Me or Cl separately.
pyridine = propose_custom_scope(
    'n1[cH:2]c[cH:4]cc1', [2, 4], ['Me', 'Cl'])

# A parent with existing methyl and chlorine groups: both groups stay present.
presubstituted = propose_custom_scope(
    'Cc1[cH:2]cc(Cl)[cH:5]c1', [2, 5], ['OMe', 'CF3'])
```

Each example returns five graphs: unchanged parent plus four single substitutions.
These are software examples of candidate proposals, not tested substrates or yields.
`include_parent=False` omits the reference. Each site is paired with each selected
group, one substitution per candidate. Multiple additions to the same candidate are
outside this interface.

## Inputs and limits

| Input | Contract |
|---|---|
| `parent_smiles` | Strict explicit SMILES, connected, at most 200 atoms and 10,000 characters; no trailing name or CX annotations |
| `site_atom_maps` | Nonempty list of unique positive integers that each exist in the parent |
| Selected site | Neutral, non-isotopic H-bearing aromatic carbon with two heavy-atom neighbours |
| Selected ring | Isolated simple five- or six-membered aromatic C/N/O/S ring; every ring atom is neutral, non-isotopic and belongs to exactly one ring |
| Existing substituents | Retained; selected rings can have multiple existing substituents and selections can span independently isolated rings in a connected parent |
| `substituents` | Nonempty list of unique case-sensitive names from the fixed vocabulary below |
| `include_parent` | Boolean, default `True` |
| Size | At most 100 requested site/group combinations including the optional parent, counted before symmetry deduplication |

Vocabulary: `Me`, `OMe`, `CF3`, `CN`, `NO2`, `F`, `Cl`, `Br`, `iPr`, `tBu`.
Custom here means selecting a list from this vocabulary; arbitrary SMILES fragments
are not accepted. Existing aromatic N, O and S atoms are retained, never selected for
attachment. Fused rings and charged or isotope-labelled selected rings are rejected.

The existing parent chemistry boundary applies: supported elements are C/N/O/F/P/S/Cl/Br/I;
explicit hydrogen atoms, radicals, queries, exotic bonds and disconnected components
are unsupported. Bracket hydrogen counts such as `[cH:2]` or `[nH]` are supported and
preserved except for the one H replaced at the chosen carbon. Remote supported
isotopes and formal charges remain intact. Existing fully assigned tetrahedral
stereochemistry is retained; unassigned or non-tetrahedral/directional stereo and
substitutions that create, remove or alter potential supported stereo fail closed.

Every candidate passes the shared parent atom/bond/hydrogen/stereo preservation
validator and canonical mapped-SMILES roundtrip check. A failure rejects the proposal;
it does not silently remove a failed candidate from the requested scan.

## Output semantics

The result has `schema_version: 1`, `status: "proposal"` and `profile: "custom"`.
It records the parent, site maps and atom indices, selected vocabulary, reference
choice, requested candidate count and deduplicated candidate count.

Candidates contain mapped/unmapped canonical isomeric SMILES, graph-derived
`candidate_id`, `display_label`, `substitutions`, `requested_variants`, rationale,
compatibility questions and preservation checks. All `yield_percent` fields are null.
Labels read, for example, `Me at parent atom map 2`; they are not chemical names.
Parent atom indices are zero-based RDKit indices for the supplied SMILES, not
ChemDraw document atom IDs.

Deduplication ignores atom maps and retains first-request order. `substitutions`
describes the representative mapped graph with `site_atom_map`, `parent_atom_index`
and `substituent`. `requested_variants` retains every requested site/group route that
produced that same unmapped graph. For example, methylating either of two mapped
benzene H sites yields one graph with two requested variants. Its representative
label/map refers to the first variant. The parent has empty substitution/variant lists.
IDs are derived from canonical graph serialization, not registry identifiers.

The proposer has no native rendering or external lookup side effects. Review the
chemistry and select explicit records before drawing. Use `canonical_smiles` for
the strict `draw` interface; `mapped_smiles` retains proposal map metadata and is not
a drawing input. Proposal limits do not override the drawing workflow's separate
structure-count, atom-count or page-fit constraints.

## Verification

`tests/test_scope_expanded.py` covers explicit pyridine positions, pre-substituted
benzene, five/six-membered heteroaromatics, all ten curated groups, symmetry route
retention, graph-derived IDs, remote stereo/isotope/charge preservation, strict
argument validation, unsupported chemistry rejection and the 100-request boundary.
`tests/test_scope_design.py` continues to exercise the unchanged standard profile.
These are offline graph checks. Native drawing and visual review are separate work.
