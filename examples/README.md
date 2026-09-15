# Reproducible software fixtures

These drawings and recipes are software demonstrations, not research results or experimental protocols.

- `ions-circled.json`: glycine zwitterion and benzoate with opt-in native circled charges. Uses the ordinary `draw` command and returns final artifact paths.
- `molecules-circled.json`: crowded four-molecule stress case. At the supplied house style it is expected to reject unsafe circled-charge placement; it is not a successful demonstration. Its same four graphs are covered by native plain-charge drawing tests.

Run examples from the project root with the CLI documented in README.md. Native workflows require a new absolute output directory and provide review and editable artifacts; the offline proposal prints JSON only. Review/select proposal candidates explicitly before creating a separate drawing manifest with `compound_id`, `label` and map-free `smiles`. No direct proposal-file parser or automatic candidate acceptance is implemented. Optional `scaffold_smiles` aligns an explicitly supplied common core to the first structure by rigid rotation/translation only; automatic core inference remains unsupported. See the usage guide for fit, symmetry and native-verification limits.
