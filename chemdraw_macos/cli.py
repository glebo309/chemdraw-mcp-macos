"""Terminal interface to the same workflows exposed through MCP."""
import argparse
import json
from pathlib import Path
import sys

from .core import Bridge,PRESETS
from .diagnostics import doctor
from .polish import chemical_signature
from .workflow import analyze_document,polish_document,remap_ids
from .editing import edit_document,edit_file
from .scope import grid_document,grid_file
from .batch import batch_export
from .annotations import annotate_file,annotate_document,inspect_annotations_document
from .identifiers import inspect_identifier
from .scope_design import propose_scope,propose_custom_scope
from .draw import draw_structures
from .styles import inspect_style_file
from .resolver import resolve_identifier
from .reaction import build_reaction
from .symbols import symbols_file,symbols_document,inspect_symbols_document
from .scope_decoration import decorate_scope_file,decorate_scope_document
from .scope_job import plan_scope_job,build_scope_job
from .reaction_series import build_reaction_series
from .ownership import build_ownership,move_file,move_document
from .lab_style import make_package,save_package,load_package,run_styled_job


def main(argv=None):
    parser=argparse.ArgumentParser(prog='chemdraw-mac',description='Native ChemDraw automation for macOS')
    commands=parser.add_subparsers(dest='command',required=True)
    d=commands.add_parser('doctor',help='Check installation, native connection and validation support')
    d.add_argument('--no-connect',action='store_true')
    commands.add_parser('documents',help='List live document IDs')
    a=commands.add_parser('analyze',help='Inspect exported native object IDs, geometry and labels')
    a.add_argument('document_id',type=int)
    p=commands.add_parser('polish',help='Create a normalized working copy and before/after review')
    src=p.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int)
    src.add_argument('--input',type=Path)
    p.add_argument('--output',required=True,help='New absolute output directory')
    p.add_argument('--preset',choices=PRESETS,default='house')
    p.add_argument('--layout',choices=('preserve','row'),default='preserve')
    p.add_argument('--recipe',type=Path,help='JSON with explicit caption_map/condition_map and spacing')
    e=commands.add_parser('edit',help='Make an analogue copy with explicit atom/bond edits and native review')
    src=e.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int)
    src.add_argument('--input',type=Path)
    e.add_argument('--recipe',type=Path,required=True,help='JSON operations, captions and source token for live documents')
    e.add_argument('--output',required=True,help='New absolute output directory')
    g=commands.add_parser('grid',help='Create a native scope grid with explicit compound IDs and yields')
    src=g.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int)
    src.add_argument('--input',type=Path)
    g.add_argument('--recipe',type=Path,required=True,help='JSON cells, columns, spacing and live source token')
    g.add_argument('--output',required=True,help='New absolute output directory')
    b=commands.add_parser('batch',help='Export explicit CDXML files with native previews and a contact sheet')
    b.add_argument('--manifest',type=Path,required=True)
    b.add_argument('--output',required=True,help='New absolute output directory')
    an=commands.add_parser('annotate',help='Add explicit native electron-flow curves to a working copy')
    src=an.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int);src.add_argument('--input',type=Path)
    an.add_argument('--recipe',type=Path,required=True);an.add_argument('--output',required=True)
    ai=commands.add_parser('inspect-annotations',help='Inspect atom/bond IDs, curve geometry and source token')
    ai.add_argument('document_id',type=int)
    ident=commands.add_parser('identify',help='Inspect SMILES or canonical Standard InChI offline; no name guessing')
    ident.add_argument('--value',required=True)
    ident.add_argument('--format',choices=('smiles','inchi'),default='smiles')
    proposal=commands.add_parser('propose-scope',help='Propose electronic, positional and steric aromatic candidates, without yields')
    proposal.add_argument('--parent',required=True,help='SMILES with an explicit atom map on the benzene handle anchor')
    proposal.add_argument('--handle-map',type=int,required=True)
    drawing=commands.add_parser('draw',help='Create native ChemDraw structures from an explicit SMILES manifest')
    drawing.add_argument('--manifest',type=Path,required=True)
    drawing.add_argument('--output',required=True,help='New absolute output directory')
    drawing.add_argument('--style',type=Path,help='Explicit .cds/.cdx/.cdxml template overrides manifest preset')
    sty=commands.add_parser('import-style',help='Extract supported document style values without opening ChemDraw')
    sty.add_argument('--input',required=True,type=Path)
    sty.add_argument('--output',type=Path,help='Optional new absolute JSON report file')
    resolve=commands.add_parser('resolve',help='Return PubChem name/CAS candidates; explicit network opt-in required')
    resolve.add_argument('--query',required=True)
    resolve.add_argument('--kind',choices=('name','cas'),default='name')
    resolve.add_argument('--allow-network',action='store_true')
    scan=commands.add_parser('scan-scope',help='Propose curated substitutions at explicitly mapped aromatic sites offline')
    scan.add_argument('--manifest',type=Path,required=True)
    reaction=commands.add_parser('reaction',help='Build a native reaction from explicit reactants, products and conditions')
    reaction.add_argument('--manifest',type=Path,required=True)
    reaction.add_argument('--output',required=True,help='New absolute output directory')
    reaction.add_argument('--style',type=Path,help='Explicit template overrides manifest preset')
    sym=commands.add_parser('symbols',help='Add native charge/electron symbols in a new working copy')
    src=sym.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int);src.add_argument('--input',type=Path)
    sym.add_argument('--recipe',type=Path,required=True);sym.add_argument('--output',required=True)
    si=commands.add_parser('inspect-symbols',help='Inspect native symbol/atom IDs and current source token')
    si.add_argument('document_id',type=int)
    decor=commands.add_parser('decorate-scope',help='Add an editable rounded shadow frame and dotted group dividers')
    src=decor.add_mutually_exclusive_group(required=True)
    src.add_argument('--document',type=int);src.add_argument('--input',type=Path)
    decor.add_argument('--recipe',type=Path,required=True);decor.add_argument('--output',required=True)
    sj=commands.add_parser('scope-job',help='Plan or build an explicitly accepted, categorized substrate scope')
    sj.add_argument('--manifest',type=Path,required=True);sj.add_argument('--output')
    sj.add_argument('--plan-only',action='store_true')
    rs=commands.add_parser('reaction-series',help='Build explicit reaction steps on one editable native page')
    rs.add_argument('--manifest',type=Path,required=True);rs.add_argument('--output',required=True)
    rs.add_argument('--style',type=Path)
    ls=commands.add_parser('make-lab-style',help='Create a portable, versioned numerical style JSON')
    ls.add_argument('--name',required=True);ls.add_argument('--version',required=True)
    ls.add_argument('--style',type=Path,required=True);ls.add_argument('--settings',type=Path)
    ls.add_argument('--output',type=Path,required=True)
    li=commands.add_parser('inspect-lab-style',help='Verify a portable style package and its content hash')
    li.add_argument('--input',type=Path,required=True)
    sjob=commands.add_parser('styled-job',help='Run a native workflow with locked lab style settings')
    sjob.add_argument('--lab-style',type=Path,required=True)
    sjob.add_argument('--workflow',choices=('draw','reaction','reaction-series','scope-job','grid','symbols'),required=True)
    sjob.add_argument('--recipe',type=Path,required=True);sjob.add_argument('--output',required=True)
    own=commands.add_parser('build-ownership',help='Create an explicit snapshot-bound ownership sidecar offline')
    own.add_argument('--input',type=Path,required=True);own.add_argument('--recipe',type=Path,required=True)
    own.add_argument('--output',type=Path,required=True)
    move=commands.add_parser('move-owned',help='Translate explicit molecules with their owned annotations in a native copy')
    src=move.add_mutually_exclusive_group(required=True)
    src.add_argument('--input',type=Path);src.add_argument('--document',type=int)
    move.add_argument('--recipe',type=Path,required=True);move.add_argument('--output',required=True)
    routes=commands.add_parser('suggest-routes',help='Suggest bounded curves between explicit chemical anchors offline')
    routes.add_argument('--input',type=Path,required=True);routes.add_argument('--recipe',type=Path,required=True)
    routes.add_argument('--output',type=Path,required=True)
    route=commands.add_parser('apply-route',help='Render an explicitly selected, snapshot-bound route in a native copy')
    route.add_argument('--input',type=Path,required=True);route.add_argument('--report',type=Path,required=True)
    route.add_argument('--candidate',required=True);route.add_argument('--output',required=True)
    commands.add_parser('serve',help='Run the MCP stdio server')
    args=parser.parse_args(argv)
    try:
        if args.command=='make-lab-style':
            sections=json.loads(args.settings.read_text()) if args.settings else {}
            result=save_package(make_package(args.name,args.version,inspect_style_file(args.style)['preset'],**sections),args.output)
            print(json.dumps(result,indent=2));return 0
        if args.command=='inspect-lab-style':
            print(json.dumps(load_package(args.input),indent=2));return 0
        if args.command in ('build-ownership','suggest-routes'):
            recipe=json.loads(args.recipe.read_text());text=args.input.read_text()
            if not isinstance(recipe,dict):raise ValueError('Recipe must be a JSON object')
            if type(recipe.get('schema_version',1)) is not int or recipe.pop('schema_version',1)!=1:raise ValueError('Unsupported recipe schema')
            if args.command=='build-ownership':result=build_ownership(text,**recipe)
            else:
                from .route_suggestions import suggest_routes
                result=suggest_routes(text,**recipe)
            if not args.output.is_absolute() or not args.output.parent.is_dir():raise ValueError('Use a new absolute output file')
            with args.output.open('x') as handle:json.dump(result,handle,indent=2)
            print(json.dumps(result,indent=2));return 0
        if args.command=='scope-job' and args.plan_only:
            print(json.dumps(plan_scope_job(json.loads(args.manifest.read_text())),indent=2));return 0
        if args.command=='scope-job' and not args.output:raise ValueError('Scope build requires --output; use --plan-only for offline planning')
        if args.command=='resolve':
            result=resolve_identifier(args.query,args.kind,args.allow_network)
            print(json.dumps(result,indent=2,ensure_ascii=False));return 0
        if args.command=='scan-scope':
            options=json.loads(args.manifest.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','parent_smiles','site_atom_maps','substituents','include_parent'}:raise ValueError('Invalid custom scope manifest fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported scope manifest schema')
            result=propose_custom_scope(**options)
            print(json.dumps(result,indent=2,ensure_ascii=False));return 0
        if args.command=='import-style':
            if args.output and (not args.output.is_absolute() or not args.output.parent.is_dir()):raise ValueError('Style output requires absolute new file and existing parent')
            result=inspect_style_file(args.input)
            if args.output:
                with args.output.open('x') as f:json.dump(result,f,indent=2)
            print(json.dumps(result,indent=2));return 0
        if args.command in ('identify','propose-scope'):
            result=inspect_identifier(args.value,args.format) if args.command=='identify' else propose_scope(args.parent,args.handle_map)
            print(json.dumps(result,indent=2,ensure_ascii=False));return 0
        if args.command=='doctor':
            result=doctor(connect=not args.no_connect)
            print(json.dumps(result,indent=2));return 0 if result['status'] in ('ready','basic_only') else 1
        if args.command=='serve':
            from .server import main as serve
            serve();return 0
        bridge=Bridge()
        if args.command=='scope-job':result=build_scope_job(bridge,json.loads(args.manifest.read_text()),args.output)
        elif args.command=='reaction-series':
            options=json.loads(args.manifest.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','steps','preset','pixels','layout'}:raise ValueError('Invalid reaction series fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported reaction series schema')
            if args.style:options['preset']=inspect_style_file(args.style)['preset']
            result=build_reaction_series(bridge,output_dir=args.output,**options)
        elif args.command=='styled-job':result=run_styled_job(bridge,args.lab_style,args.workflow,json.loads(args.recipe.read_text()),args.output)
        elif args.command=='move-owned':
            options=json.loads(args.recipe.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','ownership','moves','expected_source_token','pixels'}:raise ValueError('Invalid owned move fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported owned move schema')
            if args.input:result=move_file(bridge,args.input,args.output,**options)
            else:result=move_document(bridge,args.document,args.output,**options)
        elif args.command=='apply-route':
            from .route_suggestions import annotate_selected_route_file
            report=json.loads(args.report.read_text())
            result=annotate_selected_route_file(bridge,args.input,args.output,report,args.candidate)
        elif args.command=='decorate-scope':
            options=json.loads(args.recipe.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','groups','expected_source_token','frame','separators','pixels'}:raise ValueError('Invalid scope decoration recipe fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported scope decoration recipe schema')
            if args.input:result=decorate_scope_file(bridge,args.input,args.output,**options)
            else:result=decorate_scope_document(bridge,args.document,args.output,**options)
        elif args.command=='inspect-symbols':result=inspect_symbols_document(bridge,args.document_id)
        elif args.command=='symbols':
            options=json.loads(args.recipe.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','symbols','expected_source_token','span','line_width','clearance','pixels'}:raise ValueError('Invalid symbol recipe fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported symbol recipe schema')
            if args.input:result=symbols_file(bridge,args.input,args.output,**options)
            else:result=symbols_document(bridge,args.document,args.output,**options)
        elif args.command=='reaction':
            options=json.loads(args.manifest.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','reactants','products','conditions_above','conditions_below','preset','pixels','scaffold_smiles','layout'}:raise ValueError('Invalid reaction manifest fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported reaction manifest schema')
            if args.style:options['preset']=inspect_style_file(args.style)['preset']
            result=build_reaction(bridge,output_dir=args.output,**options)
        elif args.command=='draw':
            options=json.loads(args.manifest.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','structures','preset','columns','pixels','scaffold_smiles','layout','charge_style'}:raise ValueError('Invalid draw manifest fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported draw manifest schema')
            if args.style:options['preset']=inspect_style_file(args.style)['preset']
            result=draw_structures(bridge,output_dir=args.output,**options)
        elif args.command=='documents':result=bridge.documents()
        elif args.command=='analyze':result=analyze_document(bridge,args.document_id)
        elif args.command=='inspect-annotations':result=inspect_annotations_document(bridge,args.document_id)
        elif args.command=='annotate':
            options=json.loads(args.recipe.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','arrows','expected_source_token','line_width','pixels'}:raise ValueError('Invalid annotation recipe fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported annotation recipe schema')
            if args.input:result=annotate_file(bridge,args.input,args.output,**options)
            else:result=annotate_document(bridge,args.document,args.output,**options)
        elif args.command=='batch':
            options=json.loads(args.manifest.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','items','pixels'}:raise ValueError('Invalid batch manifest fields')
            if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:raise ValueError('Unsupported batch manifest schema')
            result=batch_export(bridge,output_dir=args.output,**options)
            print(json.dumps(result,indent=2,ensure_ascii=False));return 0 if result['status']=='completed' else 1
        elif args.command=='grid':
            options=json.loads(args.recipe.read_text())
            allowed={'schema_version','cells','expected_source_token','preset','columns','width','height','margin','h_gap','v_gap','label_gap','pixels'}
            if not isinstance(options,dict) or set(options)-allowed:raise ValueError('Invalid grid recipe fields')
            if options.pop('schema_version',1)!=1:raise ValueError('Unsupported grid recipe schema')
            if args.input:result=grid_file(bridge,args.input,args.output,**options)
            else:result=grid_document(bridge,args.document,args.output,**options)
        elif args.command=='edit':
            options=json.loads(args.recipe.read_text())
            if not isinstance(options,dict) or set(options)-{'schema_version','operations','captions','expected_source_token','pixels'}:
                raise ValueError('Invalid edit recipe fields')
            if options.pop('schema_version',1)!=1:raise ValueError('Unsupported edit recipe schema')
            if args.input:result=edit_file(bridge,args.input,args.output,**options)
            else:result=edit_document(bridge,args.document,args.output,**options)
        else:
            options={}
            if args.recipe:
                options=json.loads(args.recipe.read_text())
                allowed={'schema_version','preset','layout','caption_map','condition_map','gap','label_gap','width','pixels'}
                if set(options)-allowed:raise ValueError('Unknown recipe fields: '+str(set(options)-allowed))
                if options.pop('schema_version',1)!=1:raise ValueError('Unsupported recipe schema version')
            options.setdefault('preset',args.preset);options.setdefault('layout',args.layout)
            imported=None
            if args.input:
                if args.input.suffix.lower()!='.cdxml':
                    raise ValueError('Polish file input currently requires CDXML for pre-import validation; other formats can be imported and inspected with native tools')
                source_signature=chemical_signature(args.input.read_text())
                imported=bridge.import_file(str(args.input));did=imported['document']['document_id']
            else:did=args.document
            try:
                if args.input:
                    native=analyze_document(bridge,did)
                    if chemical_signature(Path(native['snapshot']).read_text())!=source_signature:
                        raise ValueError('Native file import changed source chemistry')
                if args.input and (options.get('caption_map') or options.get('condition_map')):
                    mapping=remap_ids(args.input.read_text(),Path(native['snapshot']).read_text())
                    options['caption_map']={mapping[f]:mapping[t] for f,t in options.get('caption_map',{}).items()}
                    options['condition_map']={mapping[a]:[mapping[t] for t in ts] for a,ts in options.get('condition_map',{}).items()}
                result=polish_document(bridge,did,args.output,**options)
            finally:
                if imported:bridge.close(did)
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except Exception as exc:
        print(json.dumps({'status':'error','error':str(exc)}),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
