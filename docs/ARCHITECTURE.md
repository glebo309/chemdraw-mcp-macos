# MCP, the drawing harness, and ChemDraw

Your assistant interprets the request. MCP carries typed calls to this local
server. The drawing harness validates and carries out complete drawing jobs.
ChemDraw produces the editable document and native vector rendering. There is
no language model inside this package.

```text
Your natural-language request
           |
AI client: interprets intent, resolves ambiguity, selects tools
           |
MCP: discovers tools and carries structured calls/results
           |
           +--> Core operations -----------------------+
           |    import, create, inspect, clean, export |
           |                                          v
           +--> Drawing harness ----------------> Native bridge
                graphs, style, layout, validation      |
                |                                      v
Terminal CLI ---+                                    ChemDraw
                                             editable native output
```

This follows MCP's [client/server architecture](https://modelcontextprotocol.io/docs/learn/architecture).
MCP is the interface, not the reasoning engine. The client can call core tools
directly, use a complete workflow, or combine several tools. The CLI calls the
same implementation without requiring an AI client or MCP session.

## Choose the tool surface

`--profile drawing` offers the focused drawing, diagnostics and
physical-export surface. `full` includes the broader workflows and native
operations. `core` is useful for direct native operations without the optional
chemistry dependency. All three are views of one server.

From an installed checkout:

```sh
# Direct native tools only; optional RDKit is not required.
uv sync --locked
.venv/bin/chemdraw-mcp-macos --profile core
```

For the complete drawing toolset:

```sh
uv sync --locked --extra chemistry
.venv/bin/chemdraw-mcp-macos --profile full
```

These start stdio servers, which wait for an MCP client rather than an interactive
chat prompt. Configure the client to launch the executable with arguments
`["--profile", "core"]` or `["--profile", "full"]`.
`chemdraw-mac serve --profile core` is an equivalent entry point.
No flag retains the existing full profile for backward compatibility.

Profiles select the tools exposed to a client. They are not separate packages,
security sandboxes, or independent permission systems. Full includes every core
tool with the same argument schema and implementation. It also exposes workflows
that require the optional chemistry dependency; installing that dependency and
choosing a profile are separate actions.

## What core provides

| Tools | Responsibility |
| --- | --- |
| `chemdraw_list_documents`, `chemdraw_inspect_document` | Discover document IDs and inspect native molecule indices, bounds and settings |
| `chemdraw_import_file` | Open a private copy of supplied CDXML, CDX, MOL or SDF |
| `chemdraw_create_document` | Open a new editable drawing from supplied CDXML |
| `chemdraw_clean` | Run ChemDraw's own cleanup after a recovery export |
| `chemdraw_native_action` | Direct native structure/reaction cleanup, six alignments, two distributions and label expansion/contraction on an owned working document |
| `chemdraw_draw_name` | Native Name to Structure with explicit network consent; no RDKit seed or renderer |
| `chemdraw_apply_style`, `chemdraw_list_styles` | List numerical presets or apply one to a copied document |
| `chemdraw_export` | Export CDXML, CDX, SVG, PDF or PNG derived from native SVG |
| `chemdraw_close_working_document` | Back up and close only a document owned by this server session |
| `chemdraw_doctor` | Diagnose the installation and connection |

For example, a client can import a supplied MOL, inspect the returned document ID,
request cleanup, and export SVG. It does not need the scope builder, molecule
catalogue, reaction composer, a skill pack or RDKit to do that.

Core is a bounded native automation bridge, not every command in ChemDraw's GUI.
Toolbar drawing modes are not arbitrary atom-level setters. Native Name to
Structure is available, but requires network consent because ChemDraw may use
ChemACX and does not expose which lookup source it used. Creating CDXML checks
the accepted document format, not chemical truth.
Core export does not run the workflow layer's mapped stereochemistry or layout
checks. Cleanup can change orientation. Unsupported native operations and
uncertain writes must not be silently retried.

Untitled drawings are read through the desktop API without assigning a filename.
Use `chemdraw_export_figure` for checked physical-scale output: CDXML from the
live snapshot, SVG from native ChemDraw rendering, and DPI-tagged PNG pages from
that SVG. Optional PDF is exported from an owned hidden copy so the original
keeps its file binding. Legacy save-based exports can still refuse an untitled
document; these two export routes have different contracts.

## What the harness enforces

`chemdraw_draw` is the front door for new molecule batches and explicit reaction
requests. `harness.py` validates the request and routes supported work; it does
not translate free text or predict chemistry. For shared molecule tables:

1. Validate explicit identities and supported graph features. Resolve names only
   with network consent and retained provenance.
2. Read the active document, including unsaved edits. Identify verified shared
   scaffold geometry and retain existing content.
3. Plan a complete table at fixed bond scale. Measure visible molecule/caption
   bounds in one hidden native copy and center them in common cells.
4. Add the batch once to the same document. If necessary, add identical physical
   pages rather than shrinking molecules or splitting into unrelated documents.
5. Read the result and check graph/stereo, old content, geometry, style, page
   placement, centres and caption baselines. Retain an audit and editable output.

A snapshot token guards against stale source data. An uncertain native write is
not retried automatically. These checks cannot prove that a supplied structure
matches a paper, that a name was chemically intended, or that a reaction works.

The CLI `produce` command calls this same harness. Direct native tools remain
available for explicit lower-level work, and do not automatically acquire every
harness validation gate.

## Native connection and rendering

The MCP client launches a local **stdio** server. Separately, a private authenticated
loopback connection links that server to the installed ChemDraw JavaScript add-in.
That localhost channel is not a remotely accessible MCP endpoint. Bounded
AppleEvents handle other native commands and exports. The small modeless native
add-in panel must remain available while its server is connected.

RDKit validates supported graphs and supplies editable coordinates/CDXML seeds.
ChemDraw renders native SVG/PDF; resvg turns the native SVG into PNG. No RDKit
image is passed off as a ChemDraw export. Each route's native checks are scoped
to its supported object types.

Multiple assistants may be configured, but this version has one native endpoint
owner at a time. The cooperative lock and stale-snapshot checks prevent some
conflicting operations; they are not simultaneous multi-user collaboration.

## Customization boundaries

Assistant/project instructions express workflow preferences. Versioned lab-style
JSON supplies supported numerical drawing settings. MCP profiles choose which
tools are exposed. These are separate controls: none bypasses chemistry checks,
grants network consent, or enables unsupported ChemDraw objects. See
[examples and customization](GETTING_STARTED.md) and [lab styles](LAB_STYLE.md).

## What the workflow layer adds

Workflow functions consume explicit structured data: graphs, document IDs, object
ownership, style settings and requested layout. They compose multiple native
operations and check the saved result. Examples include drawing a set of supplied
structures at one bond scale, arranging reaction participants, aligning a supplied
common scaffold, and attaching electron-flow curves to explicit sources.

Optional RDKit handles graph validation, identifier conversion and MOL coordinate
seeds in the workflows that need it. ChemDraw still imports, cleans and renders
the new structures. Neither a successful parse nor a successful export establishes
that an AI-transcribed name, image, stereocentre or mechanism was correct.

The AI client remains responsible for turning "draw these compounds in my lab's
style" into the appropriate explicit calls, requesting missing chemical intent,
and inspecting the resulting artifacts. The server does not understand free-form
requests by itself, contain a hidden LLM, or learn from examples during use.

## Broad by design

Development should improve reusable operations, not add a function for every named
molecule or sentence:

- A molecule is input data. Example molecules are regression fixtures, not a whitelist.
- Style, molecular identity, layout and rendering remain separate concerns.
- Shared rules cover atom/bond scale, charge placement, label ownership and geometry.
- A high-level workflow should reduce repetitive tool calls without removing core access.
- New capabilities need reachable CLI/MCP controls, defined limits and tests of native output.
- Preserve supplied stereo and spatial geometry; report ambiguity instead of inventing it.
- Experimental coordination and multicentre support have separate acceptance evidence.
  They do not gate the already usable core or ordinary molecule workflows.

"Smart" here means choosing sensible documented defaults, composing operations,
measuring layout and validating results. It does not mean pretending that unsupported
chemistry is supported or using one successful example as proof of generality.

## Code map and acceptance

`server.py` exposes typed MCP functions and selects the profile. `cli.py` dispatches
terminal commands. `harness.py` routes complete jobs; `api_drawing.py` plans and
verifies shared tables. `addin.py`, `addin_client.js` and `shared.py` implement
the private API transport and append contract. `core.py` and
`native.applescript` provide the other native operations.
`physical_export.py` retains physical scale; `terminal_setup.py` and the SwiftUI
app share `desktop_setup.py` for guided connection setup.
Modules such as `draw.py`, `workflow.py`, `reaction.py` and `symbols.py` implement
reusable operations above that bridge. The workflow modules remain in the same
package; this is a tool-surface separation, not a new microservice architecture.

`tests/test_mcp_profiles.py` checks actual stdio discovery and calls, matching core
schemas, rejection of non-core calls in core mode, unchanged full discovery, CLI
forwarding and import without optional RDKit. Native scratch tests in
`tests/test_live.py` exercise both profiles against the installed ChemDraw. See
[compatibility](COMPATIBILITY.md) for platform limits and
[project progress](../PROJECT_PROGRESS.md) for run evidence.
