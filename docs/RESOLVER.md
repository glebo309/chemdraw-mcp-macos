# Explicit name and CAS resolution

`resolve_identifier(query, input_kind='name', allow_network=False, provider='pubchem', use_cache=False)`
returns candidate records from PubChem. The network request requires literal
`allow_network=True` for every call. It sends the supplied query to PubChem over
HTTPS. It does not read documents, draw structures or contact ChemDraw.

The drawing harness opts into a bounded five-minute, 128-entry in-memory cache.
Only nonempty results whose returned candidates all pass local validation are
cached. Ambiguity, truncation, query kind and exact query text are retained;
no candidate is silently chosen by the cache. Hits report age and keep the
original retrieval timestamp. Returned dictionaries are independent copies.
Errors, rejected chemistry and not-found responses are not cached. Permission
and input validation run before cache access. `use_cache=False` performs a fresh
lookup and discards an older entry for that query; the standalone CLI/MCP resolver
keeps this fresh-lookup default. No cache files are written.

```python
from chemdraw_macos.resolver import resolve_identifier

names = resolve_identifier('caffeine', allow_network=True)
registry = resolve_identifier('58-08-2', input_kind='cas', allow_network=True)
```

The optional chemistry extra is required and checked before disclosure. No new
dependency, account, API key or provider installation is needed. `pubchem` is the
only accepted provider. There is no provider fallback, retry, background request,
automatic polling, authentication, environment proxy or redirect following.

## Input and matching

Queries contain 1 through 200 printable characters, without surrounding
whitespace. The caller chooses `name` or `cas`; input kinds are not guessed.
CAS input requires the usual 2 through 7 digit first group, two-digit middle
group and checksum digit, with ASCII hyphens, no leading zero and a valid
weighted checksum. This validates syntax, not ownership of a CAS registration.

The [PubChem PUG REST specification](https://pubchem.ncbi.nlm.nih.gov/pcfe/docs/markdown/pug-rest.md)
documents the request forms used here:

- Names use `compound/name/{query}/cids/JSON?name_type=complete`.
- CAS uses `compound/identifier/{query}/cids/JSON?identifier_type=CAS`.
- Matched CIDs are retrieved with a property table containing `SMILES`, `InChI`,
  `InChIKey`, `IUPACName` and `Title`. `SMILES` retains stereo and isotopes;
  `ConnectivitySMILES` omits them and is deliberately not used.

These are PubChem associations, not an authoritative CAS Registry lookup or
proof that a chemical name means the structure intended by the caller.

## Candidates and selection

The result reports `status` (`candidates` or `not_found`), `total_candidates`,
`ambiguous`, `truncated`, `omitted_candidates` and a list of candidate records.
Every matched record in the bounded result is retained, including candidates
whose chemistry validation fails. Returned order follows the provider CID list;
it is not a confidence ranking.

`selected_candidate` is always null and `selection_required` is always true,
including when the provider returns a single candidate. Review the proposed
identity, choose a record and explicitly supply its graph to a separate drawing
request. A rejected record must not be used as validated input.

Each record contains the CID, provider record/property URLs, unmodified provider
SMILES/InChI/InChIKey/name fields and strict offline `identifiers` output. The
validation status refers to supported chemistry parsing and consistency only.
It does not validate the name-to-structure association or certify draw support.

Provider SMILES pass through the same strict parser as offline `identify`.
Unsupported syntax is retained as a rejected candidate, with its reason and no
identifier summary. No salt stripping, neutralization, stereo guessing or
SMILES fallback runs. If available, locally generated Standard InChI and key
are compared to the provider fields; a mismatch rejects the candidate.

The separate `inchi_graph_roundtrip_equivalent` field comes from the offline
identifier check. Equal Standard InChI strings do not establish that the exact
SMILES graph survives normalization. Missing provider InChI/key leaves the
respective comparison null. An unavailable local InChI backend leaves both
comparisons null and reports the limitation while retaining valid strict SMILES.

## Bounds, errors and provenance

At most 20 candidate property records are fetched, in one request following the
CID lookup. If the CID list contains more, the full match count and number
omitted are returned, `truncated` is true and a warning asks for a narrower query.
Omitted candidates are neither fetched nor validated. A CID response exceeding
the byte bound fails explicitly, so no false total or completeness claim is made.

Each response is limited to 1,000,000 bytes. Malformed JSON, unexpected schemas,
missing/duplicate/unrequested property rows, unsupported asynchronous results,
timeouts and provider failures raise explicit errors. A lookup HTTP 404 returns
`not_found`; a 404 while fetching properties for known matches raises an error.
No failure is converted into a successful empty candidate list.

The network socket timeout is 10 seconds. A 15-second elapsed response budget
is checked between reads. A blocking socket read can run up to its socket
timeout, and operating-system DNS resolution is outside that socket timeout;
these settings are not a guaranteed wall-clock deadline. There are at most two
requests per call and no retry. Request starts are spaced by at least 0.25 seconds
within the process. This is below PubChem's documented limit of five requests
per second; separate processes and other applications are not coordinated.

`provenance` records the exact query, input kind, provider, request URLs and UTC
retrieval timestamp. `limits` reports the implemented bounds. Names and IDs are
provider data; strict canonical SMILES and summaries identify the local RDKit
engine/version separately. The result is returned as JSON data without writing
files or changing an existing drawing.

## Verification evidence

On 2026-09-15, both public examples above were exercised through the actual
implementation. Each returned CID 2519, formula C8H10N4O2, canonical SMILES
`Cn1c(=O)c2c(ncn2C)n(C)c1=O` and InChIKey
`RYYVLZVUVIJVGH-UHFFFAOYSA-N`. Both provider InChI checks matched and the separate
graph roundtrip check passed. Retrieval completed at
2026-09-15T07:19:49.422108+00:00 and 2026-09-15T07:19:50.212631+00:00.
These examples establish two live requests, not universal provider correctness.

The portable resolver tests mock provider responses and include opt-in denial,
CAS syntax/checksum, URL escaping, ambiguity, visible truncation, malformed
responses, strict chemistry rejection, InChI disagreement and normalization,
unavailable local chemistry, request size, timeout/error handling, redirect
denial, no retries and request spacing. They perform no network or native calls.
