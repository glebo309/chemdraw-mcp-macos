# Reproducible software fixtures

These drawings and recipes are software demonstrations, not research results or experimental protocols.

- `ions-circled.json`: glycine zwitterion and benzoate with opt-in native circled charges. Uses the ordinary `draw` command and returns final artifact paths.
- `molecules-circled.json`: crowded four-molecule stress case. At the supplied house style it is expected to reject unsafe circled-charge placement; it is not a successful demonstration. Its same four graphs are covered by native plain-charge drawing tests.

- `messy-oxidation.cdxml` + `oxidation-recipe.json`: normalize an illustrative ethanol/ethanal scheme.
- `chlorobenzoic-acid.cdxml` + `bromo-analogue-recipe.json`: change one explicit halogen atom in a native copy.
- `scope-input.cdxml` + `scope-recipe.json`: eight labelled structures into four columns. Every percentage in this recipe is invented test data. The zero and missing values deliberately test different display behavior. Do not cite these values as experimental yields.
- `batch-manifest.json`: replace its absolute placeholder paths with supported approved CDXML files, then use the batch command. It exports without styling or rearranging the figures.
- `sn2-annotation-input.cdxml` + `sn2-annotation-recipe.json`: add the two native electron-pair curves from the earlier user-approved SN2 drawing. The source retains existing charge symbols and style. Atom/bond references and cubic controls are explicit; no reaction mechanism is inferred. Fishhook test variants are rendering regressions, not alternative SN2 mechanisms.
- `standard-scope-parent.json`: explicitly mapped acetophenone argument fixture for offline standard scope proposals. This is an illustrative software parent, not Glenn's experimental substrate. The CLI accepts these values through `--parent` and `--handle-map`, not by reading this file. Proposals contain no experimental results or yields.
- `draw-structures.json`: three explicit SMILES records for ethanol, a stereo/isotope test and nitrobenzene. The native `draw` command imports private MOL seeds, runs native cleanup, checks graphs and makes a three-column figure. This independent test panel is not the acetophenone proposal scope.
- `acetophenone-scope-draw.json`: fourteen explicit candidate records with short relative labels, three columns and an explicit acetophenone `scaffold_smiles`. Covers parent, electronic/halogen variants, 2/3/4-Me and steric variants. No yields are supplied. This is a software demonstration, not experimental scope data. The alignment-enabled native output was verified and visually inspected in local-validation/standard-scope-v3; a native SVG is retained in assets/standard-scope.svg.

Run examples from the project root with the CLI documented in README.md. Native workflows require a new absolute output directory and provide review and editable artifacts; the offline proposal prints JSON only. Review/select proposal candidates explicitly before creating a separate drawing manifest with `compound_id`, `label` and map-free `smiles`. No direct proposal-file parser or automatic candidate acceptance is implemented. Optional `scaffold_smiles` aligns an explicitly supplied common core to the first structure by rigid rotation/translation only; automatic core inference remains unsupported. See the usage guide for fit, symmetry and native-verification limits.
