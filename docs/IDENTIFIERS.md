# Offline molecular identifiers

`chemdraw_macos.identifiers.inspect_identifier(value, input_format='smiles')` inspects one explicit molecular identifier using the installed optional RDKit chemistry extra. It returns a JSON-serializable dictionary. It performs no network calls, naming-provider requests, native ChemDraw calls, drawing or file writes.

This is graph inspection and identifier conversion, not name or CAS resolution. Names and CAS numbers are not guessed. A caller must explicitly select `smiles` or `inchi`.

```python
from chemdraw_macos.identifiers import inspect_identifier

result = inspect_identifier('[13CH3][C@H](O)C(=O)[O-].[Na+]')
print(result['canonical_smiles'])
print(result['inchi']['status'])
```

## Input boundary

The input is a nonempty ASCII string of at most 10,000 characters. Whitespace is rejected everywhere, including leading/trailing whitespace, a trailing molecule name, and multiple lines. No permissive name parsing or CXSMILES annotation parsing runs.

SMILES parsing retains explicit hydrogen atoms and isotopes, accepts disconnected components, and sanitizes molecular valence. Supported bonds are ordinary single, double, triple and aromatic bonds. Atom stereochemistry is restricted to ordinary tetrahedral `@`/`@@`; specified alkene geometry uses the ordinary slash/backslash form. Queries, dummy atoms, atom-map annotations, coordinate/exotic bonds, enhanced stereo groups and extended `@TH`/`@AL`/`@SP`/`@TB`/`@OH` syntax are rejected. A tetrahedral marker discarded during sanitization, or a directional bond that does not contribute to retained specified alkene stereo, is an error rather than silently simplified input.

Only canonical Standard InChI (`InChI=1S/...`) is accepted for InChI input, including repeated-component layer notation such as `2*+1`. Parsing errors and warnings are rejected; re-encoding the parsed molecule must exactly reproduce the supplied Standard InChI. This rejects ignored, unsupported or redundant trailing layers rather than treating partial parsing as success. Nonstandard, fixed-H and reconnected InChI input are outside this first bounded interface. InChI already represents normalized identifier semantics, not an exact original drawing or its explicit-hydrogen depiction.

Invalid or unsupported input raises `ValueError`. Missing RDKit raises `RuntimeError`. Missing InChI support raises `RuntimeError` for InChI input, but does not prevent inspection of supported SMILES.

Radicals can be inspected when RDKit accepts the graph, and their total `radical_electrons` is reported. This is not a claim that the native drawing workflows support radical chemistry. Those workflows apply their own narrower graph restrictions.

## Result

| Field | Meaning |
|---|---|
| `input_format` | Explicit caller-selected parser |
| `canonical_smiles` | Canonical isomeric SMILES of the parsed graph, retaining explicit H, isotopes and supported specified stereochemistry |
| `formula` | Molecular formula across all components, with isotope distinctions retained |
| `formal_charge` | Sum of atom formal charges; opposite ion charges are not neutralized |
| `component_count`, `atom_count` | Parsed disconnected components and explicit graph atoms |
| `isotopes` | Isotope-bearing atoms, with zero-based input-graph index, element and mass number |
| `stereo.tetrahedral` | Specified tetrahedral atoms, their RDKit chiral tag and CIP label when available |
| `stereo.double_bonds` | Specified bond stereochemistry with input-graph atom/bond indices |
| `stereo.unspecified` | Potential but unspecified stereo detected by RDKit; no configuration is invented |
| `radical_electrons` | Sum of explicit graph radical-electron counts |
| `inchi` | Independently reported Standard InChI/InChIKey availability, messages and graph roundtrip comparison |
| `normalization` | Explicitly records no salt stripping, salt neutralization, tautomer canonicalization or explicit-H removal by this graph-inspection workflow |
| `engine` | RDKit version and offline execution flag |

Summary indices refer to the parsed input graph, not the canonical SMILES traversal and not ChemDraw document IDs. RDKit atom chiral tags are local traversal descriptors; use the reported CIP label when available rather than equating a tag directly with R/S. Canonical ordering and stereo detection are dependent on the recorded RDKit version.

## Standard InChI is a separate normalized identifier

Standard InChI generation has its own normalization rules. A valid InChI or matching InChIKey does not prove preservation of a particular tautomer, protonation depiction or drawn graph. The canonical SMILES remains the graph-level result; the module does not replace it with an InChI-decoded structure.

`inchi` has the following shape:

```json
{
  "status": "available",
  "value": "InChI=1S/...",
  "key": "...",
  "reason": null,
  "warnings": [],
  "graph_roundtrip_equivalent": true
}
```

The example values above are placeholders, not a compound identifier. `status` is `unavailable` with null `value`/`key` and an explanatory `reason` if the backend is missing or conversion fails. A generated warning is retained in `warnings`, rather than discarded. `graph_roundtrip_equivalent` is true or false only when the generated InChI can be decoded and compared; otherwise it is null. The comparison expands hydrogens on temporary copies on both sides, preserving isotopes, components, charges and supported stereo for comparison. It does not remove explicit hydrogen atoms from the returned canonical SMILES.

A false roundtrip result adds an explicit warning. For example, the tested lactam `O=C1CCCCN1` retains that canonical SMILES while its Standard InChI roundtrip reports a different graph. Isotopic sodium lactate retains both ionic components and the isotope/stereo in canonical SMILES while exposing the InChI proton-adjustment warning separately.

## Verification and provenance

Portable tests cover strict malformed/trailing input rejection, queries/dummy/map/exotic-stereo rejection, discarded stereo, stereoisomers, E/Z, unspecified centres, explicit ordinary/isotopic H, disconnected chiral isotopic salt, canonical Standard InChI, normalization reporting and missing/failed InChI support. They do not contact external services or a native app.

The module uses installed RDKit parsing, descriptor and InChI bindings. It does not vendor upstream code or add a new dependency. Implementation contracts were checked against the installed package's parser parameters, InChI binding docstrings and Python wrapper source. It is not an independent chemical name, registry identity or experimental-data verification service.
