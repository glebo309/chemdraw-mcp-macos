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
from .styles import inspect_style_file
from .resolver import resolve_identifier
from .reaction import build_reaction
from .symbols import symbols_document,inspect_symbols_document
from .scope_decoration import decorate_scope_document
from .scope_job import plan_scope_job,build_scope_job
from .reaction_series import build_reaction_series
from .ownership import build_ownership,move_document
from .lab_style import make_package,save_package,load_package,run_styled_job

mcp=FastMCP('ChemDraw macOS',instructions='Controls actual ChemDraw through AppleScript. Use explicit current document IDs. Imports and styling create working copies. Review native cleanup before publication. No RDKit renderer is used.')
_bridge=None
def bridge():
    global _bridge
    if _bridge is None:_bridge=Bridge()
    return _bridge

READ=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
WRITE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)
EDIT=ToolAnnotations(readOnlyHint=False,destructiveHint=True,openWorldHint=False)

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
def chemdraw_draw_structures(structures:list[dict],output_dir:str,preset:Literal['house','acs-1996']|dict='house',columns:int|None=None,pixels:int=3200,scaffold_smiles:str|None=None,layout:dict|None=None,charge_style:Literal['plain','circled']='plain')->dict:
    """Create a native ChemDraw figure from 1..24 explicit {compound_id,label,smiles} records. Labels are caller supplied, not verified names. Connected supported nonradical structures only. RDKit supplies MOL coordinate seeds; actual ChemDraw imports, runs native Clean Up Structure and renders. Optional scaffold_smiles explicitly selects a common core, rigidly aligned to the first native structure without reflection; poor fits fail, no inferred core. Checks identity after import/cleanup and measured grid after native save. New absolute output directory, editable/vector/PNG preview and audit. Final document stays open, originals untouched. No name lookup or yields. Review stereo and intramolecular collisions visually. Native uncertainty stops without retry/close."""
    return draw_structures(bridge(),structures,output_dir,preset,columns,pixels,scaffold_smiles,layout,charge_style)

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
    """Check the Mac installation, live connection and optional chemistry validator without editing documents."""
    return doctor()

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

def main():mcp.run(transport='stdio')
if __name__=='__main__':main()
