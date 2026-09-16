# Test candidate 0.10.0rc3

Prepared 2026-09-16 for another-Mac and cross-client testing. Not published to a
package index and not certified on an independent Mac.

## Changes

- First-run no longer requires or returns HTML and never opens a browser. It
  delivers the same-canvas native drawing plus CDXML, SVG, PNG and JSON checks.
- Doctor verifies an actual RDKit CDXML writer roundtrip and a live desktop API
  read. Offline readiness, absent setup, absent document, busy endpoint and live
  readiness are distinct. MCP diagnostics reuses its own existing connection.
- Shared panels retain a verified supplied core when a parent's substituent is
  replaced. Automatic shared panels select a plain grid without an initial
  decoration rejection. Explicit unsupported decorations are not discarded.
- Captions remain non-chemical text; unlabelled graph inputs receive numbers.
  Conservative structure envelopes share row/column centres and equal pitch.

## Environment and evidence

Development platform: macOS 15.6, arm64, ChemDraw 23.0.1.11 / desktop API 1.6,
Python 3.13.2, RDKit 2026.03.6, resvg-py 0.5.0. The uv lock records the complete
dependency set. No result here establishes another build's compatibility.

Portable suite: **1043 passed, 79 skipped**, 13.63 seconds. Fresh source-archive
installation in a separate virtual environment: **1043 passed, 79 skipped**,
15.13 seconds. Installed wheel imported from site-packages, reported 0.10.0rc3
and passed the offline CDXML writer diagnostic.

Native shared API plus first-run suite: **6 passed**, 38.37 seconds. Covered:

- Untitled read, five-object append, stale-token refusal and a sixth-object append.
- Ordinary parent plus eight analogues with intermediate imports forbidden.
- Captions remain text rather than extra chemical fragments; default numbers.
- Parent plus ten substituent-replacement analogues through panel=auto, one
  untitled document, native core coordinates within 0.03 pt without fitting away
  rotations, label count and house typography/scale.
- Mixed isotope, charge, explicit-H and stereo inputs.
- Diagnostic API read followed by HTML-free native first-run.

Finder foreground assertions passed in this suite; earlier development runs were
inconsistent and are retained in project history. The latest scope, caption and
first-run native-derived PNGs were inspected on white. Visual review is separate
from graph/coordinate/style gates and is not universal collision certification.
Tests closed only successful test-owned documents. No user process was terminated.

A portable run overlapping native tests encountered two expected cooperative-lock
refusals. The clean serial portable rerun above passed. Run native editing clients
and acceptance suites serially.

## Package checks and remaining gates

Wheel and source distribution retain application code, JavaScript/native scripts,
locked source dependencies, tests, examples and licence/provenance notices as
appropriate. Archive inspection excludes virtual environments, caches, generated
private add-ins, connection credentials and local validation bundles. Use the
SHA256SUMS file accompanying the final handoff artifacts for identity.

Native test output remains local; this document contains no machine credential.
The add-in must be generated freshly on the receiving Mac. Another-Mac installation,
the receiving user's ChemDraw build and individual model/client combinations are
the next acceptance gates. The full older native feature suite was not rerun for
this shared-document candidate.
