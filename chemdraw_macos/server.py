"""Typed stdio MCP tools for native ChemDraw on macOS."""
from typing import Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .core import Bridge,PRESETS
from .diagnostics import doctor
from .workflow import analyze_document,polish_document
from .editing import edit_document
from .scope import grid_document
from .batch import batch_export
from .annotations import annotate_document,inspect_annotations_document
from .identifiers import inspect_identifier
from .scope_design import propose_scope,propose_custom_scope
from .draw import draw_structures
from .complexes import draw_complex
from .styles import inspect_style_file
from .resolver import resolve_identifier
from .reaction import build_reaction
from .symbols import symbols_document,inspect_symbols_document
from .scope_decoration import decorate_scope_document
from .scope_job import plan_scope_job,build_scope_job
from .reaction_series import build_reaction_series
from .ownership import build_ownership,move_document
from .lab_style import make_package,save_package,load_package,run_styled_job
from .first_run import run_first_run
from .native_actions import NativeAction
from .harness import DrawingRequest, run_drawing

INSTRUCTIONS = (
    'Controls actual ChemDraw through its desktop API and bounded AppleScript commands. Natural-language interpretation and '
    'tool selection belong to the connected AI client; this server has no embedded LLM. '
    'Use explicit current document IDs. Imports and styling create working copies. '
    'For additions to a working document, pass its current document_id to chemdraw_draw '
    'or chemdraw_draw_structures with presentation=shared. Auto and interactive molecule '
    'drawing reuse the active ChemDraw canvas through one API insertion. No per-molecule windows. '
    'Do not repeat a whole drawing job merely to change labels or numbering. '
    'Do not use mouse or keyboard automation to bypass a rejected drawing, page-fit check or unsaved-document guard. '
    'Do not remove participants or change supplied labels/conditions to force a reaction to fit. '
    'Read molecular_graphs from read_live_document or analyze_document after human edits. '
    'Unsaved edits are included. Captions such as Caffeine may be stale and are NEVER molecular identities. '
    'Keep the house preset unless the user explicitly requests a different style. Do not use a guessed '
    'SMILES reconstructed from the picture. Never report an uncertain job as completed '
    'because export files exist. For same-document native commands, use read_live_document and live_action for '
    'supported native commands. Do not substitute a copy-based chemical edit without '
    'explaining that limitation. Refresh live state after manual changes; no continuous '
    'subscription is implemented. render_cdxml supports hidden-window native exports '
    'inside a logged-in desktop, not display-free operation. '
    'Native cleanup changes depiction; inspect its result. Core calls do not certify '
    'chemical identity or layout. No RDKit renderer is used. '
)
mcp=FastMCP('ChemDraw macOS',instructions=INSTRUCTIONS +
    'For NEW molecule drawings, panels and explicit reactions, start with chemdraw_draw. '
    'Its harness enforces validation, native rendering, layout and delivery checks. '
    'Do not manually assemble lower-level tools or silently drop a failed requirement. '
    'Names/CAS stay typed identifiers, not model-invented SMILES. Follow needs_input, '
    'rejected and uncertain states; only completed indicates passed mandatory gates. '
    'Full profile: direct native operations plus optional deterministic drawing, layout '
    'and validation workflows. Prefer an appropriate workflow when its documented '
    'input subset fits; otherwise use supported core operations with explicit inputs. '
    'Electron-pushing arrows ARE supported in this full profile, separately from reaction construction. '
    'For a mechanism, first establish explicit structures and chemical steps; do not substitute '
    'a reaction-series drawing for a complete electron-pushing mechanism. Use chemdraw_inspect_symbols '
    'and chemdraw_add_symbols for missing donor lone pairs, then refresh IDs/token with '
    'chemdraw_inspect_annotations and use chemdraw_annotate_document for native editable '
    'two-electron curves or one-electron fishhooks. chemdraw_suggest_routes and chemdraw_apply_route '
    'offer explicit, geometry-checked route candidates. These workflows create NEW COPIES, not '
    'in-place annotations. They do not infer or validate the chemical mechanism. Inspect the final '
    'native image for arrow placement and overlaps. If an operation is rejected, report that '
    'specific limitation rather than claiming that electron-pushing arrows cannot be drawn. '
    'Do not invent missing stereochemistry, products or experimental results. '
    'Experimental complex support is not a prerequisite for ordinary drawing.')
_bridge=None
def bridge():
    global _bridge
    if _bridge is None:_bridge=Bridge()
    return _bridge

READ=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
WRITE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)
NAME_WRITE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=True)

_addin=None
def addin_backend():
    from .addin import get_backend
    return get_backend(bridge())

@mcp.tool(annotations=WRITE)
def chemdraw_addin_connect()->dict:
    """Experimental desktop JavaScript API connection. Installs no external service.
    Starts an authenticated loopback listener and prepares a private local add-in
    package. First use may return needs_setup with one-time Add-in Manager steps.
    Opens one small modeless connection panel, not another drawing document.
    Keep this MCP process running. Do not share the generated session package.
    Ordinary molecule drawing and live reads now share this connection.
    """
    return addin_backend().connect()

@mcp.tool(annotations=READ)
def chemdraw_addin_read_document(document_id:int)->dict:
    """Experimental native getCDXML read of the active ChemDraw document.
    Returns editable CDXML, existing selection and a fresh source token without
    save/export, selecting all, clipboard or keyboard events. ChemDraw need not
    have OS focus; document_id must be its active drawing. Add-in setup required.
    Not continuous synchronization. App autosave remains under ChemDraw's control.
    """
    return addin_backend().read(document_id)

@mcp.tool(annotations=WRITE)
def chemdraw_addin_append_cdxml(document_id:int,cdxml:str,expected_source_token:str)->dict:
    """Experimental exact-coordinate append through native addCDXML in the SAME
    active document. Read with addin_read_document first. Supported flat molecules
    and captions require supplied bounds, target document settings/font tables,
    nonoverlap and page fit. Retains existing content, checks graph and positions
    after insertion. No intermediate documents, clipboard, key presses, save or
    fallback. ChemDraw may autosave named files. Timeout/verification failure is
    uncertain: never retry. Does not generate coordinates from names/SMILES or
    infer scaffold orientation. A small modeless add-in connection panel remains.
    """
    return addin_backend().append(document_id,cdxml,expected_source_token)

@mcp.tool(annotations=NAME_WRITE)
def chemdraw_draw(request:DrawingRequest,output_dir:str,allow_network:bool=False,presentation:Literal['auto','background','interactive','shared']='auto',document_id:int|None=None)->dict:
    """START HERE for new molecule drawings, panels and explicit reactions.
    Supply molecules [{value,format:name|cas|smiles|inchi,label?}]; products only
    for an explicit reaction. Names/CAS require network opt-in; ambiguous matches
    return needs_input. The enforced pipeline owns native rendering, house style,
    measured layout, graph checks and exports. No yield/product prediction.
    Auto and interactive reuse the active working document for supported flat
    molecules/captions, including untitled documents. Supply document_id to bind a
    specific active canvas. One final API insertion, no clipboard or keyboard movement.
    Tables use one hidden native measuring copy for exact visible-ink centering.
    OS foreground focus is not required after the connection is opened.
    page_policy=add_pages (default) adds identical physical sheets vertically inside
    the SAME document when needed, up to 20 pages; keep refuses overflow.
    No molecule shrinking or separate overflow document. New objects use house style;
    existing objects retain their style. A unique matching live parent supplies
    scaffold orientation automatically. A whole ring/linker scaffold extracted from
    a supplied input can anchor related structures when it matches every graph with chirality.
    panel=auto selects a plain aligned grid on the shared canvas, without a retry
    or inferred decorations. Missing labels on SMILES/InChI become numbers, not
    formulas. Exports contain the whole current canvas.
    Shared molecules default to exports=auto: editable CDXML, native SVG and a
    white 1200-pixel artifacts.preview PNG for direct visual review. Open that
    preview directly; no white-background conversion or separate export is needed.
    Use exports=full only when a transparent 3200-pixel PNG is requested, or
    exports=canvas when only the editable canvas is wanted (review in ChemDraw).
    Publication/DPI exports use chemdraw_export_figure afterwards, without redrawing.
    Validated name/CAS results are cached in this process for five minutes;
    refresh_identifiers=true forces a new lookup. Permission/ambiguity rules remain.
    timings measures server work, not model reasoning or client-side image review.
    Reactions in auto/background assemble the complete reaction locally, select
    reaction_paper=auto at unchanged scale, then use one whole-reaction measuring
    document and one final export document. Unit formal charges are circled by
    default, with one additional whole-document measurement for their ink. Saved
    charge ownership and bond/label clearance must pass; never omit failed circles.
    Editable CDXML, physical-scale SVG,
    600-DPI transparent PNG and a white preview are returned. Background documents
    are closed; interactive opens an additional verified presentation copy of the
    output. No per-participant native imports or cleanup. An active untitled original
    can be preserved through the add-in read; do not save or close it to bypass checks.
    Shared reactions and decorated panels are not supported; never silently redirect
    an explicit same-document request. This requires the licensed desktop, not a
    display-free renderer; native window opening can briefly flash. Output_dir must
    not already exist: the tool creates it. On rejection inspect the returned reason;
    do not retry with changed chemistry or UI control.
    Only completed means required gates passed; visual review remains required.
    Never retry uncertain writes or substitute another renderer.
    Submit a requested table as ONE complete batch, not independent rows.
    On table_needs_space stop: never retry smaller batches, drop requested entries,
    or create a second document to bypass a same-document request.
    """
    return run_drawing(bridge(),request.model_dump(),output_dir,allow_network,presentation,document_id=document_id)

@mcp.tool(annotations=NAME_WRITE)
def chemdraw_draw_name(name:str,output_dir:str,allow_network:bool=False,preset:Literal['house','acs-1996']='house',pixels:int=2400)->dict:
    """Draw ONE chemical name with actual desktop ChemDraw Name to Structure, with no RDKit depiction or graph prerequisite. Requires explicit allow_network=True: ChemDraw may send the name to ChemACX; provider use is not observable. Creates an owned caption-only copy, invokes the native command, returns editable CDXML/SVG/PNG, white-background HTML review and audit. Name interpretation and stereo are NOT independently certified. Native limitations include coordination complexes, polymers and some common names. Unsupported/ambiguous names may raise a native dialog: stop without retry/automatic close. New absolute output directory only. Review the generated structure before use. No clipboard or GUI automation."""
    from .native_names import draw_name
    return draw_name(bridge(),name=name,output_dir=output_dir,allow_network=allow_network,preset=preset,pixels=pixels)

@mcp.tool(annotations=WRITE)
def chemdraw_draw_complex(recipe:dict,output_dir:str,preset:Literal['house','acs-1996']='house',pixels:int=2400)->dict:
    """Experimental explicit coordination drawing in a NEW native copy. V1 recipe: schema_version=1, label, atoms [{id,element,charge,hydrogens,position:[x,y,z]}], bonds [{begin,end,order:'1'|'2'|'3'|'dative'}]. V2 adds attachments=[] and overall_charge=null|nonzero integer, requires each bond's display, permits order='coordination' with Solid/WedgeEnd/WedgedHashEnd, and optional atom color='#RRGGBB'. Default atoms are BLACK; colouring is opt-in. Whole-complex charge is a checked corner annotation, not an atom-charge assignment. V2 multicentre/haptic planning is experimental; the ferrocene fixture currently FAILS native aromatic-order preservation, so do not promise ferrocene output. Positions are CDXML points, not angstroms; x/y are supplied projection, z retained metadata. No cleanup, geometry/stereo/oxidation-state inference, chemical plausibility certification or 3D renderer. Native warnings are reported, not suppressed. New absolute output directory, native CDXML/SVG/PNG/audit/review; existing documents unchanged. Human chemical and visual review required. See docs/METAL_COMPLEXES.md and examples/coordination-ruthenium-chelate.json."""
    return draw_complex(bridge(),recipe,output_dir,preset,pixels)
EDIT=ToolAnnotations(readOnlyHint=False,destructiveHint=True,openWorldHint=False)

@mcp.tool(annotations=READ)
def chemdraw_read_live_document(document_id:int)->dict:
    """Read the current canvas through the desktop API, including unsaved edits and selection. No clipboard, saving, selecting all or duplicate window. molecular_graphs gives canonical SMILES and atom/bond records when chemistry support is installed; unresolved graphs are explicit. Captions are separate and may be stale: NEVER identify a molecule from its caption instead of this graph. Returns a fresh token for live_action; read again after human edits. Not an automatic subscription."""
    from .live import read_live_document
    return read_live_document(bridge(),document_id)

@mcp.tool(annotations=EDIT)
def chemdraw_live_action(document_id:int,action:NativeAction,expected_source_token:str,selection:Literal['current','all']='current')->dict:
    """Explicitly edit the SAME existing document with native cleanup/alignment/distribution/label commands, including user-opened documents. Read_live_document first. Refuses a changed content/selection token; saves a recovery snapshot before dispatch. Requires that document frontmost within ChemDraw. Does not import, close, duplicate or promote ownership. No arbitrary atom setter. Human edits during dispatch are not atomically locked. No automatic retry; refresh afterward."""
    from .live import live_action
    return live_action(bridge(),document_id,action,expected_source_token,selection)

@mcp.tool(annotations=WRITE)
def chemdraw_set_visibility(document_id:int,visible:bool)->dict:
    """Show or hide only this existing document's window. Does not close it or hide other documents. Hidden-window operation still needs licensed ChemDraw and a logged-in Mac desktop. No display-free server claim."""
    return bridge().set_visibility(document_id,visible)

@mcp.tool(annotations=WRITE)
def chemdraw_render_cdxml(cdxml:str,output_dir:str,background:bool=True)->dict:
    """Render supplied CDXML into editable CDXML, native SVG/PDF and PNG, with no preview page. New absolute output directory. Background hides the new document after opening and closes only that owned document after successful exports; an opening flash is possible. Needs a logged-in licensed desktop, not a display-free server. No chemistry/layout certificate. Failures retain the document, never retry or close an uncertain write. Other drawing workflows are unchanged."""
    from .live import render_cdxml
    return render_cdxml(bridge(),cdxml,output_dir,background)

@mcp.tool(annotations=READ)
def chemdraw_inspect_targets(document_id:int)->dict:
    """Inspect snapshot-bound atom, bond and molecule IDs across a supported flat molecular sheet, including elements, positions, endpoints and stereo. Requires chemistry extra. These are CDXML IDs, not native indices. No native UI highlighting."""
    from .targeted import inspect_targets_document
    return inspect_targets_document(bridge(),document_id)

@mcp.tool(annotations=READ)
def chemdraw_prepare_selection(document_id:int,kind:Literal['atom','bond','molecule'],ids:list[str],expected_source_token:str)->dict:
    """Resolve explicit IDs into a fresh snapshot-checked logical selection for edit_targets. Does NOT change ChemDraw's visible UI selection: the tested Mac setter does not support individual atom/bond references. No ambiguous element or position guessing."""
    from .targeted import prepare_selection_document
    return prepare_selection_document(bridge(),document_id,kind,ids,expected_source_token)

@mcp.tool(annotations=WRITE)
def chemdraw_edit_targets(document_id:int,output_dir:str,selection:dict,operation:dict,pixels:int=2400)->dict:
    """Edit explicit snapshot targets in a NEW native-rendered copy. selection comes from prepare_selection; operation has kind plus exact fields. set_atom: element, hydrogens (0..4), charge (-1,0,1). set_bond_order: order (1..3), hydrogens mapping BOTH endpoint IDs to counts. attach_fragment: fragment_cdxml (one supported supplied molecule, no captions), attachment_atom_id in it, angle_degrees. attach_ring: size (3..8), angle_degrees. Attachments replace implicit H with one connecting single bond, not fusion/spiro; angle_degrees is a number or 'auto' for bounded collision-checked candidates. remove_substituent: select its plain connecting bond, keep_atom_id, hydrogens on that kept endpoint; refuses ring cuts. bond_display: display=hashed_wedge|solid_wedge, from_atom_id (narrow end), allow_stereo_change=true. native_align: action from native alignment/distribution commands, select molecules; only verified translations are transferred. Existing retained atom positions and other molecules stay fixed. Captions retained verbatim, NOT chemically renamed. No UI highlighting or native atom setter. Native saved chemistry, coordinates, displays and measured placement checked; unsupported stereo/valence/collisions fail. Output directory must be new and absolute. Never retry uncertain writes."""
    from .targeted import edit_targets_document
    return edit_targets_document(bridge(),document_id,output_dir,selection,operation,pixels)

@mcp.tool(annotations=EDIT)
def chemdraw_native_action(document_id:int,action:NativeAction,selection:Literal['current','all']='current')->dict:
    """Call an EXISTING ChemDraw native command, not a custom layout implementation: structure/reaction cleanup, six alignments, horizontal/vertical distribution, expand/contract labels. Modifies only a session-owned working document; import a copy first. Document must be frontmost within ChemDraw. selection=current uses its existing selection; all explicitly selects all objects, including captions. Backup before action. Disabled commands return unavailable_for_selection, not success. align_horizontal_centers shares x centres; align_vertical_centers shares y centres. No automatic grouping/owned-caption behavior, chemical preservation certificate, retry or GUI clicks. Export/inspect afterward. Not every toolbar drawing mode is a parameterized command."""
    return bridge().native_action(document_id,action,selection=selection)

@mcp.tool(annotations=WRITE)
def chemdraw_first_run(output_dir:str|None=None)->dict:
    """Explicit setup smoke test: check dependencies, then append caffeine and aspirin once to the active ChemDraw canvas through the desktop API with house layout and validation. Open a blank document for an isolated test. Returns editable CDXML, SVG, PNG and JSON report, no HTML or browser. The canvas stays open; existing objects are preserved. Default output is a unique workspace folder; supplied path must be new and absolute. No permission or client configuration changes. No retry or extra close after uncertainty. Inspect the visible drawing; this is not full compatibility certification."""
    return run_first_run(output_dir,bridge_factory=bridge)

@mcp.tool(annotations=READ)
def chemdraw_plan_scope_job(job:dict)->dict:
    """Offline standard aromatic scope proposal, explicit candidate selection and category grouping plan. Job needs mapped parent_smiles, handle_atom_map and ordered groups {label,categories}. Building requires selected_candidate_ids or accept_all=true; planning never implicitly accepts. All yields null."""
    return plan_scope_job(job)

@mcp.tool(annotations=WRITE)
def chemdraw_build_scope_job(job:dict,output_dir:str)->dict:
    """Build an explicitly approved scope job in NEW native documents: selected candidates, conserved scaffold, true category rows, headings, optional frame/dividers, editable exports and audit. Single supported physical page; overflow fails without shrinking molecules. Source drawings unchanged; no inferred experimental outcomes."""
    return build_scope_job(bridge(),job,output_dir)

@mcp.tool(annotations=WRITE)
def chemdraw_build_reaction_series(steps:list[dict],output_dir:str,preset:Literal['house','acs-1996']|dict='house',pixels:int=3200,layout:dict|None=None)->dict:
    """Build 1 through 3 explicitly supplied reaction rows on ONE editable ChemDraw page. Steps contain step_id, reactants/products and optional above/below conditions; participants specify compound_id,label,smiles and optional positive coefficient. Supported water/halides and bounded salts. No product inference or balance certificate; native chemistry and measured layout verified separately."""
    return build_reaction_series(bridge(),steps,output_dir,preset,pixels,layout)

@mcp.tool(annotations=READ)
def chemdraw_build_ownership(document_id:int,owners:list[dict],curves:list[dict]|None=None)->dict:
    """Snapshot a native document and build explicit sidecar ownership. Each owner {key,fragment_ids,caption_ids}; every fragment exactly once. Existing curves require curve_id and explicit source/target {kind,id}. Returns source-token-bound ownership; does not change manual dragging behavior."""
    from pathlib import Path
    snapshot=inspect_annotations_document(bridge(),document_id)
    return build_ownership(Path(snapshot['snapshot']).read_text(),owners,curves)

@mcp.tool(annotations=WRITE)
def chemdraw_move_owned(document_id:int,output_dir:str,ownership:dict,moves:list[dict],expected_source_token:str,pixels:int=3200)->dict:
    """Move explicit owners {owner_key,delta:[dx,dy]} in a NEW native copy, carrying owned captions, symbols and internal curves. Cross-owner curves require equal translation of both owners. Returns remapped ownership sidecar. No automatic manual-drag attachment or collision-free layout claim."""
    return move_document(bridge(),document_id,output_dir,ownership,moves,expected_source_token,pixels)

@mcp.tool(annotations=READ)
def chemdraw_suggest_routes(document_id:int,source:dict,target:dict,electrons:int=2,fishhook_side:str|None=None,line_width:float=.9,clearance:float=2,max_candidates:int=5)->dict:
    """Suggest bounded cubic electron-flow paths using measured obstacles. Source must be an explicit displayed CircleMinus/LonePair for two electrons, Electron dot for one electron, or donating bond. Atom-label sources are rejected; add a symbol first if needed. Target is an explicit atom or bond ID. No chemistry inference or automatic route selection. Returns snapshot-bound candidate recipes and clearance audit; native arrowhead ink still needs visual review."""
    from pathlib import Path
    from .route_suggestions import suggest_routes
    snapshot=inspect_annotations_document(bridge(),document_id)
    return suggest_routes(Path(snapshot['snapshot']).read_text(),source,target,electrons,fishhook_side,line_width,clearance,max_candidates)

@mcp.tool(annotations=WRITE)
def chemdraw_apply_route(document_id:int,output_dir:str,report:dict,candidate_id:str,pixels:int=3200)->dict:
    """Validate and render one explicitly selected suggested route in a NEW native copy. Rejects stale snapshots or modified proposals; preserves source and saves selection audit. This selects a geometric path, not a chemical mechanism."""
    from .route_suggestions import annotate_selected_route_document
    return annotate_selected_route_document(bridge(),document_id,output_dir,report,candidate_id,pixels)

@mcp.tool(annotations=WRITE)
def chemdraw_create_lab_style(name:str,version:str,preset:dict,output_path:str,settings:dict|None=None,references:list[dict]|None=None)->dict:
    """Write a new portable versioned numerical style JSON with content hash. Settings sections grid/reaction/symbols; references are names/hashes/descriptions only. No fonts, proprietary artwork, code or local paths embedded. Does not publish or install anything."""
    return save_package(make_package(name,version,preset,references,**(settings or {})),output_path)

@mcp.tool(annotations=READ)
def chemdraw_inspect_lab_style(path:str)->dict:
    """Read and validate a portable style package, exact supported settings, version and content hash. No native application or network access."""
    return load_package(path)

@mcp.tool(annotations=WRITE)
def chemdraw_run_styled_job(package_path:str,workflow:Literal['draw','reaction','reaction-series','scope-job','grid','symbols'],recipe:dict,output_dir:str)->dict:
    """Run a native workflow with a locked portable lab style. Conflicting recipe settings rejected, actual package/hash retained beside output. Grid/symbols recipes require input CDXML path. Native exports use ChemDraw; numerical conventions do not replace explicit chemical review."""
    return run_styled_job(bridge(),package_path,workflow,recipe,output_dir)

@mcp.tool(annotations=WRITE)
def chemdraw_decorate_scope(document_id:int,output_dir:str,groups:list[dict],expected_source_token:str,frame:bool=True,separators:bool=True,pixels:int=3200)->dict:
    """Decorate an existing flat scope in a NEW copy with an optional native rounded shadow frame and dotted group dividers. Explicit groups {label,fragment_ids,caption_ids} must own every source fragment and caption once and form nonoverlapping top-to-bottom bands. Labels can be empty; nonempty labels need measured free space. No automatic chemical classification or molecule reordering. Inspect current IDs/source token first. Native editable CDXML/SVG/PNG with source preservation and layout audit; human visual review still required. New absolute output directory only; uncertain native writes stop without retry."""
    return decorate_scope_document(bridge(),document_id,output_dir,groups,expected_source_token,frame,separators,pixels)

@mcp.tool(annotations=READ)
def chemdraw_inspect_symbols(document_id:int)->dict:
    """Snapshot native atom/bond/symbol IDs and measured label bounds, returning a source_token. Supports existing associated circled charges and unassociated graphical electron/lone-pair symbols. A graphical electron dot is not a verified radical state."""
    return inspect_symbols_document(bridge(),document_id)

@mcp.tool(annotations=WRITE)
def chemdraw_add_symbols(document_id:int,output_dir:str,symbols:list[dict],expected_source_token:str,span:float|None=None,line_width:float|None=None,clearance:float=2,pixels:int=3200)->dict:
    """Add native symbols to a NEW copy from explicit {key,kind:charge|lone_pair|electron,atom_id} requests. Charge derives sign from existing +1/-1 formal charge, not a chemical edit. Lone-pair/electron dots are graphical annotations, not radical-state edits. Bounded outward placement checks geometry against labels/bonds/objects; unsupported or colliding placement fails. Inspect current IDs/token first. New absolute output directory, before/after native exports and audit, source unchanged. Visual and chemical review required; no moving attachment or complete mechanism validation promise."""
    return symbols_document(bridge(),document_id,output_dir,symbols,expected_source_token,span,line_width,clearance,pixels)

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=True))
def chemdraw_resolve(query:str,input_kind:Literal['name','cas']='name',allow_network:bool=False)->dict:
    """Resolve an explicit name or CAS query using PubChem ONLY with allow_network=True. Sends the query to PubChem and returns up to 20 candidates, provenance, ambiguity/truncation and graph-validation results. No silent candidate selection, native drawing, retries, provider fallback or CAS Registry certification. Review and select an explicit valid candidate SMILES before drawing. Network denied by default."""
    return resolve_identifier(query,input_kind,allow_network)

@mcp.tool(annotations=READ)
def chemdraw_scan_scope(parent_smiles:str,site_atom_maps:list[int],substituents:list[str],include_parent:bool=True)->dict:
    """Propose substitutions offline at explicit mapped H-bearing aromatic carbon sites. Supports isolated five/six-membered rings, including heteroaromatics and pre-substituted rings. Curated Me, OMe, CF3, CN, NO2, F, Cl, Br, iPr, tBu; one site at a time, capped at 100 requests before deduplication. Preserves supported parent graph/stereo, retains alternative provenance for duplicates, no invented yields or reaction prediction. Select explicit candidates and use draw_structures for native output."""
    return propose_custom_scope(parent_smiles,site_atom_maps,substituents,include_parent)

@mcp.tool(annotations=WRITE)
def chemdraw_build_reaction(reactants:list[dict],products:list[dict],output_dir:str,conditions_above:str='',conditions_below:str='',preset:Literal['house','acs-1996']|dict='house',pixels:int=3200,scaffold_smiles:str|None=None,layout:dict|None=None)->dict:
    """Create a native reaction with explicit 1..3 reactant and 1..3 product records {compound_id,label,smiles,coefficient?}, single-line above/below conditions and measured spacing. The expanded path supports water, hydroxide, halide/alkali ions, bounded charge-balanced salts and explicit positive coefficients. Connected-only input may use explicit shared-core alignment; expanded input with scaffold alignment is rejected. Actual ChemDraw cleanup and native identity/layout checks; no reaction prediction or balance certificate. New absolute output directory, editable CDXML/SVG/PNG and HTML review. Originals untouched, native uncertainty stops without retry/close."""
    return build_reaction(bridge(),reactants,products,output_dir,conditions_above,conditions_below,preset,pixels,scaffold_smiles,layout)

@mcp.tool(annotations=READ)
def chemdraw_import_style(path:str)->dict:
    """Read a local .cds/.cdx/.cdxml document style without opening ChemDraw or modifying the source. Returns validated preset settings, hash, defaults used and unapplied properties. Pass its preset object to draw/polish/grid/apply_style. Only supported typography and bond settings, not template artwork, page geometry or colour palette. Custom fonts are checked on the rendering Mac before use."""
    return inspect_style_file(path)

@mcp.tool(annotations=READ)
def chemdraw_identify(value:str,input_format:Literal['smiles','inchi']='smiles')->dict:
    """Inspect an explicit SMILES or canonical Standard InChI entirely offline with optional RDKit. Returns canonical isomeric SMILES, formula, charge, components, isotope/stereo summaries and InChI/Key when available. No ChemDraw call, names/CAS resolution, salt stripping or tautomer conversion. Standard InChI normalization and graph-roundtrip differences are explicit."""
    return inspect_identifier(value,input_format)

@mcp.tool(annotations=READ)
def chemdraw_propose_scope(parent_smiles:str,handle_atom_map:int,profile:Literal['standard']='standard')->dict:
    """Propose a standard aromatic substrate scope offline, not experimental results. Parent requires a uniquely atom-mapped benzene carbon attached to the existing reaction handle on an isolated monosubstituted ring. Produces deduplicated parent, electronic, halogen, 2/3/4-Me and steric variants with stable graph IDs, SMILES, relative labels, rationale and blank yields. Preserves supported parent graph/stereo. No native drawing or reaction prediction. Review/select candidates, then call draw_structures with explicit compound_id/label/smiles."""
    return propose_scope(parent_smiles,handle_atom_map,profile)

@mcp.tool(annotations=WRITE)
def chemdraw_draw_structures(structures:list[dict],output_dir:str,preset:Literal['house','acs-1996']|dict='house',columns:int|None=None,pixels:int=3200,scaffold_smiles:str|None=None,layout:dict|None=None,charge_style:Literal['plain','circled']='plain',groups:list[dict]|None=None,frame:bool=True,separators:bool=True,scaffold_layout:Literal['rigid','reference']='rigid',presentation:Literal['auto','background','interactive','shared']='auto',document_id:int|None=None)->dict:
    """Advanced explicit-input drawing; prefer chemdraw_draw for ordinary requests. Accept 1..24 {compound_id,label,smiles} records. Keep preset=house unless the USER requests another style. Shared/auto/interactive append one complete batch to the active canvas, including untitled documents. Tables use one hidden native measuring copy, closed before final insertion, with visible-ink center and caption-baseline checks. No clipboard or keyboard movement. Overflow appends identical vertical physical pages in the SAME document, without shrinking molecules or dropping entries. Supply document_id to bind the active canvas. A matching live parent or verified common ring framework supplies orientation; scaffold_smiles can specify a core. Omit columns for automatic fit. IDs are not duplicate captions. Shared batches support plain charges and flat molecules/captions only; custom layout/style, decorated groups and circled charges are rejected. Explicit background retains the separate legacy workflow. Use chemdraw_export_figure for physical-scale publication exports. Do not open extra final documents or retry uncertain writes. Review final appearance."""
    from .harness import NeedsInput
    try:
        return draw_structures(bridge(),structures,output_dir,preset,columns,pixels,scaffold_smiles,layout,charge_style,
                               groups=groups,frame=frame,separators=separators,scaffold_layout=scaffold_layout,presentation=presentation,document_id=document_id)
    except NeedsInput as exc:
        return {'status':'needs_input','code':exc.code,'message':str(exc),
                'document_id':document_id,**exc.detail}

@mcp.tool(annotations=READ)
def chemdraw_inspect_annotations(document_id:int)->dict:
    """Export a read-only snapshot and list atom/bond IDs, measured label boxes, supported native curves and source_token for electron-flow annotation. Supports existing circled charge graphics. Ownership in an annotation recipe is not a native moving attachment guarantee."""
    return inspect_annotations_document(bridge(),document_id)

@mcp.tool(annotations=WRITE)
def chemdraw_annotate_document(document_id:int,output_dir:str,arrows:list[dict],expected_source_token:str,line_width:float=.9,pixels:int=3200)->dict:
    """Add native full or fishhook electron-flow curves to a NEW copy. Inspect annotations first. Each arrow has unique key, electrons 2 or 1, source {kind:symbol,id} for a displayed CircleMinus/LonePair (2 electrons) or Electron dot (1 electron), OR source {kind:bond,id,offset:[dx,dy]} for a donating bond. Atom-label sources and positive-charge donors are rejected; add a symbol first if needed. Target {kind:atom|bond,id,offset:[dx,dy]}; controls:[[dx1,dy1],[dx2,dy2]] relative to start/end; optional fishhook_side left/right only for one electron. Symbol targets rejected. A negative charge may represent a donating lone pair, but this is caller-supplied chemical intent, not inferred for every anion. Existing molecules/symbols retained; no chemical/radical-state edits. New absolute output directory, native CDXML/SVG/PNG before/after, recipe and audit. Source untouched. Visual review required; no whole-path collision or native moving attachment promise. Native errors not retried."""
    return annotate_document(bridge(),document_id,output_dir,arrows,expected_source_token,line_width,pixels)

@mcp.tool(annotations=WRITE)
def chemdraw_batch_export(items:list[dict],output_dir:str,pixels:int=3200)->dict:
    """Sequential native batch export of explicit supported CDXML files. Each item: {key: safe-unique-figure-key, source: absolute-file-path, formats: [pdf,cdx]}. Always exports CDXML/SVG/PNG plus requested PDF/CDX, with per-item audit and HTML contact sheet. New absolute output directory only. No style/layout/chemistry edits. Creates private copies and closes only those copies. Input failures reported per item. Any native-operation error is conservatively uncertain: stop later items, do not retry or close the uncertain document. Requires chemistry extra; flat supported drawings plus the annotation verifier's existing circled-charge/full-or-half cubic-curve subset. Unknown annotations rejected. Review all outputs; source metadata and mapped chemistry checks do not certify source correctness or glyph appearance."""
    return batch_export(bridge(),items,output_dir,pixels)

@mcp.tool(annotations=READ)
def chemdraw_list_documents()->dict:
    """List running ChemDraw documents with unique IDs, names, paths and modified flags."""
    return bridge().documents()

@mcp.tool(annotations=READ)
def chemdraw_inspect_document(document_id:int)->dict:
    """Inspect 1-based molecule indices/bounds and document settings. Refresh indices after edits. Native molecule IDs are broken in ChemDraw 23. Does not return atom-level chemistry."""
    return bridge().inspect(document_id)

@mcp.tool(annotations=WRITE)
def chemdraw_import_file(path:str)->dict:
    """Open a private working copy of a local CDXML, CDX, MOL or SDF. Never opens the original for editing."""
    return bridge().import_file(path)

@mcp.tool(annotations=WRITE)
def chemdraw_create_document(cdxml:str)->dict:
    """Create an editable native document from CDXML. Caller supplies validated chemical structures; no name resolver or chemistry invention is performed."""
    return bridge().create(cdxml)

@mcp.tool(annotations=EDIT)
def chemdraw_clean(document_id:int,molecule_index:int|None=None)->dict:
    """Run native Clean Up Structure on the specified molecule or whole document, after a recovery export. This changes depiction and can alter orientation."""
    return bridge().clean(document_id,molecule_index)

@mcp.tool(annotations=WRITE)
def chemdraw_apply_style(document_id:int,preset:Literal['house','acs-1996']|dict='house')->dict:
    """Create a styled copy with consistent explicit fonts/strokes. Does not normalize existing coordinates or reposition charges. Cleanup is a separate explicit action."""
    return bridge().apply_style(document_id,preset)

@mcp.tool(annotations=WRITE)
def chemdraw_export_figure(document_id:int,output_dir:str,dpi:int=600,include_pdf:bool=False)->dict:
    """Preferred export for 'export this for my paper/slides' or 'keep benzene rings the same size'. Export the whole live drawing as editable CDXML, physically sized SVG and transparent PNG, cropped by ChemDraw, preserving original bond/font/stroke scale. Default 600 DPI for publication; choose 300 for slides. Different drawings intentionally have different pixel dimensions. Never fit separate molecules to equal image widths. Set include_pdf=True for a native PDF retaining physical paper pages, exported through one hidden private copy, not by saving the original. New absolute output directory only; source is read before/after and stays open, including untitled drawings. SVG is resolution independent. Insert at original size in Word/PowerPoint; resizing there changes chemical scale. This exports existing layout, not a layout repair or selected-molecule extraction. Paper size and chemical scale are unchanged."""
    from .physical_export import export_figure
    return export_figure(bridge(),document_id,output_dir,dpi,**({'include_pdf':True} if include_pdf else {}))

@mcp.tool(annotations=WRITE)
def chemdraw_export(document_id:int,path:str,format:Literal['svg','pdf','cdxml','cdx','png'],pixels:int=3200)->dict:
    """Export through actual ChemDraw, refusing overwrites. PNG rasterizes unchanged native SVG offline with resvg; pixels controls longest side. Output parent must exist. Unsupported SVG resources fail explicitly; no rasterizer fallback."""
    return bridge().export(document_id,path,format,pixels)

@mcp.tool(annotations=EDIT)
def chemdraw_close_working_document(document_id:int)->dict:
    """Back up and close a document opened by this server session. Refuses all other documents."""
    return bridge().close(document_id)

@mcp.tool(annotations=READ)
def chemdraw_list_styles()->dict:
    """List numeric style presets. These are defaults plus explicit text/bond overrides, not chemistry or automatic layout engines."""
    return {'presets':PRESETS}

@mcp.tool(annotations=READ)
def chemdraw_doctor()->dict:
    """Check environment versions, actual CDXML writer roundtrip and desktop API read readiness without changing drawing content. An installed connection panel may open. Reports missing setup, another client owning the endpoint, or no open document separately. ready verifies prerequisites and a read, not a successful drawing; first-run is the explicit write test."""
    return doctor(bridge=bridge())

@mcp.tool(annotations=WRITE)
def chemdraw_analyze_document(document_id:int)->dict:
    """Export a recovery snapshot and return molecule IDs, bounds, text, arrows and a top-level source_token for supported drawings. Use that token and explicit object IDs for scope grids. For supported single molecules, editing also includes atom/bond IDs and the same token for analogue edits. Source is not edited."""
    return analyze_document(bridge(),document_id)

@mcp.tool(annotations=WRITE)
def chemdraw_polish_document(document_id:int,output_dir:str,preset:Literal['house','acs-1996']|dict='house',
                            layout:Literal['preserve','row']='preserve',caption_map:dict[str,str]|None=None,
                            condition_map:dict[str,list[str]]|None=None,gap:float=24.,label_gap:float=14.,
                            width:float|None=None,pixels:int=3200)->dict:
    """Create a new normalized native drawing plus editable CDXML, SVG, PNG, before/after HTML, recipe and audit. Never edits the source. Requires chemistry extra. Flat one-page drawings only; queries/groups/abbreviations fail closed. Row layout requires explicit fragment-to-caption and arrow-to-condition ID maps from analyze; unassigned text is rejected. Preserves orientation, charges, isotopes and supported stereo. Does not run native cleanup automatically. Review previews before publication; checks establish preservation, not source correctness."""
    return polish_document(bridge(),document_id,output_dir,preset,layout,caption_map,condition_map,gap,label_gap,width,pixels)

@mcp.tool(annotations=WRITE)
def chemdraw_edit_document(document_id:int,output_dir:str,operations:list[dict],
                           captions:dict[str,str|None],expected_source_token:str,pixels:int=2400)->dict:
    """Make an edited COPY of one molecule with native before/after exports and chemical diff. Analyze first: use editing atom/bond IDs and source_token. Atom op: {kind:atom,id,element:S,hydrogens:1}; element optional, H count required. Bond op: {kind:bond,id,order:2}. Captions must explicitly replace, retain or null-remove every page text ID. Supports neutral main-group atom/H changes and plain nonaromatic bond orders; no insertions/deletions, charged/isotopic target edits, radicals, stereocentre edits or new alkene stereo. Coordinates preserved, no cleanup. Existing source untouched; final mapped chemistry, labels and coordinates verified after ChemDraw export. Visual review required."""
    return edit_document(bridge(),document_id,output_dir,operations,captions,expected_source_token,pixels)

@mcp.tool(annotations=WRITE)
def chemdraw_grid_document(document_id:int,output_dir:str,cells:list[dict],expected_source_token:str,
                           preset:Literal['house','acs-1996']|dict='house',columns:int|None=None,
                           width:float|None=None,height:float|None=None,margin:float=36.,
                           h_gap:float=18.,v_gap:float=24.,label_gap:float=10.,pixels:int=3200)->dict:
    """Create a native scope grid COPY. Analyze first for source_token and IDs. Cells in requested order: {compound_id:3a,fragment_ids:[ID],caption_id:ID|null,yield_percent:82|null}. Every fragment and existing page caption needs one owner. 0% remains visible; missing yield omitted. Multi-fragment compounds translate together after normalization. Native measured molecular+caption bounds determine uniform cells. Columns auto-fit if omitted; overflow fails, never shrinks individual molecules. Requires chemistry extra. No reactions/page graphics/nested groups/native symbol graphics. Preserves orientation and chemistry, adds caller-supplied compound IDs/yields, verifies native saved page fit and alignment. Yields are not experimentally validated. Visual review required."""
    return grid_document(bridge(),document_id,output_dir,cells,expected_source_token,preset,
                         columns,width,height,margin,h_gap,v_gap,label_gap,pixels)

def get_server(profile: str = 'full') -> FastMCP:
    """Select the exposed tool surface without changing the shared implementations."""
    if profile == 'full':
        return mcp
    if profile == 'drawing':
        drawing=FastMCP('ChemDraw drawing',instructions=
            'For every new molecule, panel or explicit reaction use chemdraw_draw. '
            'Send names/CAS as supplied rather than inventing SMILES. Ask for network opt-in when needed. '
            'The server owns styling, layout, validation and export. Follow needs_input or rejected results; '
            'never claim success without status completed. Do not retry uncertain native writes. '
            'Use chemdraw_doctor only for installation diagnostics.')
        drawing.add_tool(chemdraw_draw,annotations=NAME_WRITE)
        drawing.add_tool(chemdraw_doctor,annotations=READ)
        drawing.add_tool(chemdraw_export_figure,annotations=WRITE)
        return drawing
    if profile != 'core':
        raise ValueError(f'Unknown MCP profile: {profile}')
    core = FastMCP('ChemDraw macOS', instructions=INSTRUCTIONS +
        'Core profile: native document operations only. Accept local CDXML/CDX/MOL/SDF '
        'through import_file or explicit CDXML through create_document. draw_name uses '
        'native Name to Structure with explicit possible-network opt-in. No RDKit '
        'SMILES drawing workflow is exposed. RDKit is not required. Inspect exports '
        'visually and validate supplied chemistry separately. Export of an untitled '
        'document is refused because native save would assign it a filename.')
    for fn, annotations in (
        (chemdraw_list_documents, READ),
        (chemdraw_inspect_document, READ),
        (chemdraw_import_file, WRITE),
        (chemdraw_create_document, WRITE),
        (chemdraw_clean, EDIT),
        (chemdraw_apply_style, WRITE),
        (chemdraw_export, WRITE),
        (chemdraw_export_figure, WRITE),
        (chemdraw_close_working_document, EDIT),
        (chemdraw_list_styles, READ),
        (chemdraw_doctor, READ),
        (chemdraw_draw_name, NAME_WRITE),
        (chemdraw_native_action, EDIT),
        (chemdraw_read_live_document, READ),
        (chemdraw_live_action, EDIT),
        (chemdraw_set_visibility, WRITE),
        (chemdraw_render_cdxml, WRITE),
    ):
        core.add_tool(fn, annotations=annotations)
    return core


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Native ChemDraw MCP server over stdio')
    parser.add_argument('--profile', choices=('core', 'full', 'drawing'), default='full',
                        help='core: direct native tools; full: core plus drawing workflows (default)')
    args = parser.parse_args(argv)
    get_server(args.profile).run(transport='stdio')

if __name__=='__main__':main()
