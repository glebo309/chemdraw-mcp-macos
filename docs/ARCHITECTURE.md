# Core MCP and drawing workflows

The native MCP server already exists and is independently usable. The additional
development is a reusable drawing workflow layer, not a prerequisite for connecting
an AI client to ChemDraw, and not a second language model.

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
           +--> Optional drawing workflows ------> Native bridge
                explicit graphs, style, layout,       |
                preservation checks                    v
                                                  ChemDraw
                                             editable native output
```

This follows MCP's [client/server architecture](https://modelcontextprotocol.io/docs/learn/architecture).
MCP is the interface, not the reasoning engine. The client can call core tools
directly, use a complete workflow, or combine several tools. The CLI calls the
same implementation without requiring an AI client or MCP session.

## Choose the tool surface

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
| `chemdraw_apply_style`, `chemdraw_list_styles` | List numerical presets or apply one to a copied document |
| `chemdraw_export` | Export CDXML, CDX, SVG, PDF or PNG derived from native SVG |
| `chemdraw_close_working_document` | Back up and close only a document owned by this server session |
| `chemdraw_doctor` | Diagnose the installation and connection |

For example, a client can import a supplied MOL, inspect the returned document ID,
request cleanup, and export SVG. It does not need the scope builder, molecule
catalogue, reaction composer, a skill pack or RDKit to do that.

Core is a bounded native automation bridge, not every command in ChemDraw's GUI.
It does not currently expose native Name to Structure or arbitrary atom-level
setters. Creating CDXML checks the accepted document format, not chemical truth.
Core export does not run the workflow layer's mapped stereochemistry or layout
checks. Cleanup can change orientation. Unsupported native operations and
uncertain writes must not be silently retried.

An untitled drawing currently cannot be exported safely: the native save command
would assign it a filename. The bridge refuses that export before saving. This
also blocks workflows that need a preservation snapshot of an open untitled
drawing. It is a known limitation, not a claim that all unsaved-document scenarios
are supported.

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
terminal commands. `core.py` and `native.applescript` provide the native bridge.
Modules such as `draw.py`, `workflow.py`, `reaction.py` and `symbols.py` implement
reusable operations above that bridge. The workflow modules remain in the same
package; this is a tool-surface separation, not a new microservice architecture.

`tests/test_mcp_profiles.py` checks actual stdio discovery and calls, matching core
schemas, rejection of non-core calls in core mode, unchanged full discovery, CLI
forwarding and import without optional RDKit. Native scratch tests in
`tests/test_live.py` exercise both profiles against the installed ChemDraw. See
[compatibility](COMPATIBILITY.md) for platform limits and
[project progress](../PROJECT_PROGRESS.md) for run evidence.
