# Naming and identifier conversion opportunities

Reviewed 2026-09-15. This is research and a proposed implementation order, not a delivered capability. No provider was installed, no chemical query was submitted, and no native ChemDraw command was executed for this review. Public documentation and the installed scripting dictionary were read.

## Recommendation

Keep name resolution separate from drawing production. A resolver should return a candidate molecular graph with provenance and unresolved questions; ChemDraw should still render the accepted graph. Existing figure editing must never re-resolve its caption and silently replace the drawing.

| Rank | Useful request | Proposed capability | Boundary |
|---|---|---|---|
| 1 | “Give me the isomeric SMILES and InChI for this exact molecule” | Offline identifier export and round-trip audit | Not a naming engine; use supported chemistry only |
| 2 | “Draw (2R)-2-hydroxypropanoic acid without sending it online” | Optional offline OPSIN resolver | Systematic name parsing, not arbitrary synonym lookup |
| 3 | “Find caffeine by name or CAS, then draw the selected record” | Explicit opt-in PubChem resolution | Database lookup can be ambiguous and exposes the query |
| 4 | “Use ChemDraw's own Name-to-Structure” | Bounded native command investigation | Plausible automation surface, not yet working evidence |
| 5 | “Call this compound 7a everywhere, but retain its chemical identity” | Local alias/compound-label registry | Display names must not masquerade as IUPAC or CAS assignments |

The ranks reflect effort, utility and fit with the existing safety contracts. They are project recommendations, not results of a user survey.

## 1. Offline identifier export

Use the already optional RDKit dependency for `Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)`, `Chem.MolToCXSmiles(mol)` where its features are supported, and `rdkit.Chem.inchi.MolToInchi(mol)` / `MolToInchiKey(mol)`. Parse imported SMILES with explicit error handling. RDKit documents failures returning `None`; InChI exposes warning/error handling. This is graph conversion, not final rendering or systematic-name generation. [RDKit input/output guide](https://www.rdkit.org/docs/GettingStartedInPython.html), [SMILES API](https://www.rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html), [InChI API](https://www.rdkit.org/docs/source/rdkit.Chem.inchi.html).

**Proposed acceptance:** selected fragment IDs only; preserve isotope, charge, explicit hydrogen and supported stereo; record toolkit versions and export options. Compare supported graphs on round-trip, not strings alone. A lossy target must return warnings or refuse, never silently remove unsupported information. Canonical SMILES is not a universal numbering convention. InChIKey is a hash, not a reversible structure payload.

**Provenance/privacy:** RDKit's BSD-3-Clause license is already recorded in the upstream research. No query leaves the machine. An eventual distributable must retain applicable dependency notices. [License](https://github.com/rdkit/rdkit/blob/master/license.txt).

**Example test:** export both enantiomers of a supported chiral alcohol and assert that the stereo-inclusive outputs differ; an export explicitly requested without stereo must be marked lossy. This test is proposed, not executed here.

## 2. Optional OPSIN adapter

The official README currently documents OPSIN 2.9.0 with Java 8 or later. Exact Java API: `NameToStructure.getInstance().parseChemicalName(name, config)` returns an `OpsinResult`; inspect `getStatus()`, `getSmiles()` and warnings, including `nameAppearsToBeAmbiguous()`. Keep `allowUninterpretableStereo` disabled. Command-line batch entry point: `java -jar opsin-cli-2.9.0-jar-with-dependencies.jar -osmi input.txt output.txt`. Prefer a tiny structured library adapter over assuming a nonempty CLI SMILES means unqualified success. OPSIN parses names into structures; it does not generate systematic names from arbitrary structures. [Official README and API examples](https://github.com/dan2097/opsin/blob/master/README.md).

**Proposed acceptance:** a version-pinned optional installation, with an explicit resolver selector such as `opsin-local`. Retain the exact original name, flags, parser version, warnings and output graph. A warning requires review before drawing; unsuccessful parsing does not trigger a hidden online fallback. Test carbohydrate, isotope, charge, R/S and E/Z examples separately before advertising their support in our adapter.

**Provenance/privacy:** MIT, Copyright 2017 Daniel Lowe; retain the full license if distributing OPSIN, and separately review bundled dependencies. Offline after installation. The hosted EBI service is a different, networked provider; it offers JSON status/message/warnings but must not be mislabeled offline. [OPSIN license](https://github.com/dan2097/opsin/blob/master/LICENSE.txt), [EBI service](https://www.ebi.ac.uk/opsin).

## 3. Opt-in PubChem resolver and known-record naming

Documented PUG-REST requests, with `NAME` URL-encoded and `CID` an explicitly selected identifier:

```text
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/NAME/cids/JSON?name_type=complete
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/CID/property/Title,IUPACName,SMILES,InChI,InChIKey/JSON
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/CID/record/SDF?record_type=2d
```

Current documented property `SMILES` includes stereo and isotopes; `ConnectivitySMILES` does not. Fetch candidates before choosing one. Rate-limit below the documented five requests per second and handle throttling/server errors without changing provider silently. [Official PUG-REST specification](https://pubchem.ncbi.nlm.nih.gov/pcfe/docs/markdown/pug-rest.md).

A name can identify multiple related structures. The official IUPAC cookbook demonstrates this issue. [Name lookup examples](https://iupac.github.io/WFChemCookbook/datasources/pubchem_pugrest2.html).

**Proposed acceptance:** provider/network permission explicit; cache locally with retrieval timestamp, selected CID and complete response provenance. Distinguish “PubChem's IUPACName for this matched record” from “we generated an IUPAC name”. Compare selected record chemistry to any existing input graph before attaching its name. Do not standardize the user's drawing to force a match. “D-glucose” alone must not be treated as a user decision about cyclic form or anomer; present the candidate's actual specification.

**CAS boundary:** PubChem supports CAS-like strings through name lookup, but expressly does not manually curate or verify third-party CAS numbers. Treat a returned number as a sourced identifier claim, not a CAS REGISTRY certification. [PubChem's CAS explanation](https://pubchem.ncbi.nlm.nih.gov/docs/about/).

**Provenance/privacy:** queries leave the computer. Public access is not blanket permission to redistribute every contributed annotation; preserve source and license metadata. [PubChem data-source guidance](https://pubchem.ncbi.nlm.nih.gov/docs/data-sources), [NCBI policies](https://www.ncbi.nlm.nih.gov/home/about/policies/).

**CAS Common Chemistry decision:** evaluate only as a separately configured provider if authoritative CAS-linked lookup is requested. CAS directs API users to an access request and publishes noncommercial content terms plus separate commercial licensing. Do not build against an undocumented anonymous endpoint or bundle its data into a generally permissive package by default. [Official API access](https://www.cas.org/services/commonchemistry-api), [Common Chemistry](https://commonchemistry.cas.org/home/), [commercial terms](https://web.cas.org/marketing/pdf/common-chemistry-commercial-license.pdf).

## 4. Native ChemDraw naming: bounded investigation

The vendor advertises Name-to-Structure and Structure-to-Name in its product offerings, but a desktop feature listing is not proof of a callable Mac API. [Current feature comparison](https://revvitysignals.com/products/research/chemdraw).

Read-only inspection of `/Applications/ChemDraw 23.0.1.app/Contents/Resources/ChemDraw.sdef` found:

- Line 215: read-only `SMILES` property on `selection-object`, AppleEvent property code `Smls`.
- Lines 277 onward: `do`, event code `miscmenu`, acting on a specifier.
- Menu-item and command objects with names and enabled state.
- No dedicated Name-to-Structure, Structure-to-Name or InChI command declaration.

**Inference, not a tested capability:** a typed, tightly allowlisted native command wrapper might reach the existing conversion command. A future spike must first inspect available command identities without mutation, then test only owned scratch documents. It must establish how text input/selection and output are controlled, whether dialogs or network services are involved, and whether document targeting survives focus changes. Do not expose generic `do`, arbitrary menu text, clipboard writes or keystrokes as a shortcut. Failure of that spike would not justify claiming native conversion through OPSIN instead.

Revvity's description also acknowledges ambiguous names; successful native conversion still needs provenance and chemical review. [Name-to-Structure capabilities](https://support.revvitysignals.com/hc/en-us/articles/4408233124756-ChemDraw-What-are-the-general-capabilities-of-Name-to-Structure).

## 5. Local compound names and display conventions

This is our proposed feature, not an external naming algorithm: a local registry keyed to supported chemical identity, with `display_label`, `submitted_name`, `name_source`, `compound_number`, and optional provider identifiers as distinct fields. The current explicit caption ownership model supplies the drawing link.

Useful requests include “number the selected compounds 1 through 8”, “use short names on the slide and systematic names in the exported table”, and “retain 7a when moving this structure”. An analogue gets a new registry entry; it must not inherit the parent compound's IUPACName or CAS claim. No external dependency or network is required. Version the registry and store aliases outside the molecular graph.

## Shared implementation contract

These are proposed API fields, not tools already available:

```json
{
  "input_kind": "name",
  "original_input": "(2R)-2-hydroxypropanoic acid",
  "provider": "opsin-local",
  "network_used": false,
  "provider_version": "record actual installed version",
  "status": "resolved | ambiguous | unsupported | failed",
  "candidates": [],
  "warnings": [],
  "accepted_candidate": null
}
```

Resolve first, let the caller accept a specific candidate, then import a new native document and audit the saved chemistry. Molecular resolution, naming, coordinate generation, native rendering and human approval are separate checks. Never manufacture a structure from a name with unverified model-generated stereochemistry, never call a synonym search an IUPAC naming engine, and never substitute a caption lookup for the existing drawing's chemical identity.

No code was borrowed in this document. Any implementation that adopts dependencies or source must update the provenance manifest and third-party notices at that time.
