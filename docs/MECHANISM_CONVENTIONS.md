# Electron-flow drawing conventions

Reference: Jonathan Clayden, Nick Greeves and Stuart Warren, *Organic Chemistry*, second edition, chapter 5, printed pages 113, 117 and 120. Those pages were inspected in the owner's local PDF, including the diagrams. The book and its artwork are not distributed with this project. These are independently worded implementation requirements, not copied textbook content.

## The tail names an electron source

A two-electron arrow starts at the depicted donor electron pair: a lone-pair symbol, an appropriate negative-charge symbol, or the bond supplying the pair. It must not float near an atom without communicating its source.

The negative-charge convention is conditional, not universal. For a halide nucleophile the charge can stand for a donating lone pair. For borohydride the donor is a B-H bond: its overall negative charge is not the arrow source. The caller must specify the source; charge detection alone cannot choose a mechanism.

For a displayed lone pair, start at that pair. For a one-electron arrow, a single-electron symbol uses a fishhook head, not a full two-electron head. A bond-breaking arrow starts at the affected bond and points toward the atom receiving the electrons. A bond-forming arrow ends on the prospective bond direction, close to the electrophile, without covering its label.

## Geometry and ownership

- Record the actual source object ID, not only a guessed coordinate near an atom.
- A symbol-anchored tail meets the visible symbol edge along its departure direction. Do not run the curve through the charge sign or lone-pair dots.
- Keep full heads and fishhooks distinct. A positive-charge symbol is not a donating electron-pair source.
- Require a displayed donor symbol or donor bond for new arrow sources. Bare atom sources are rejected; explicit atom/bond targets remain supported.
- Determine chemical intent separately from curve routing. Clear glyphs and a successful native save do not establish mechanistic correctness.
- Review the complete path, head clearance, source contact and resulting charge balance. Endpoint checks alone do not establish whole-path collision avoidance or reaction validity.

Native symbol and curve properties must survive ChemDraw saving and export. Recipe ownership does not imply that ChemDraw will keep an arrow attached when a person subsequently moves its molecule.

## Acceptance examples

1. Halide substitution: full arrow from the explicit negative-charge symbol to the electrophilic carbon; separate full arrow from the carbon-leaving-group bond to the leaving atom.
2. Neutral donor: full arrow from the displayed lone pair, not a nonexistent negative charge.
3. Radical annotation: fishhook from the explicitly displayed electron dot. Drawing a dot does not by itself update the underlying radical state.
4. Hydride donor: full arrow from the specified donor bond. Do not infer its origin from the nearest negative charge.

These examples are conventions and test targets. Consult the current symbol and annotation API documentation for the implemented subset and native validation status.

Fishhook rendering regressions may use explicit bond sources to exercise native half-head geometry without asserting a complete radical mechanism. They must not turn a negative-charge or lone-pair source into a one-electron donor merely by changing the requested head.
