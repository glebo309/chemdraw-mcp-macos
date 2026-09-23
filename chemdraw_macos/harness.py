"""One typed entry point with non-skippable native drawing gates."""
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET
from pydantic import BaseModel, ConfigDict, Field

from .draw import draw_structures, prepare_structures
from .reaction import build_reaction
from .identifiers import inspect_identifier
from .resolver import resolve_identifier
from .drawing_defaults import plan_drawing_defaults
from .batch import NativeUncertain
from .presentation import production_job
from .workflow import _write_json
from .timing import StageTimer


class CompoundInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    value: str = Field(min_length=1,max_length=10000,description='Chemical name, CAS, SMILES or Standard InChI, exactly as supplied.')
    format: Literal['name','cas','smiles','inchi']
    label: str | None = Field(default=None,min_length=1,max_length=120)
    selected_cid: int | None = Field(default=None,gt=0,description='Explicit selection from a previous ambiguous PubChem result.')


class DrawingRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    molecules: list[CompoundInput] = Field(min_length=1,max_length=24,description='Molecules to draw, or reactants when products are supplied.')
    products: list[CompoundInput] | None = Field(default=None,min_length=1,max_length=24,description='Explicit products only. Omit for molecule drawings; no reaction prediction.')
    conditions_above: str = Field(default='',max_length=120)
    conditions_below: str = Field(default='',max_length=120)
    panel: Literal['auto','plain'] = Field(default='auto',description='Auto may group supported related panels; plain omits category grouping. Shared tables retain verified common-ring orientation in either mode.')
    page_policy: Literal['add_pages','keep'] = Field(default='add_pages',description='For shared molecule tables, append identical physical pages inside the same document when needed; keep refuses overflow. Never shrink molecules.')
    exports: Literal['auto','preview','full','canvas'] = Field(default='auto',description='Auto: shared molecules get native SVG plus a white 1200-pixel review preview; reactions get physical-scale SVG, 600-DPI transparent PNG and preview. Full: transparent 3200-pixel PNG for molecules, 600-DPI PNG for reactions. Canvas: shared molecules only, editable CDXML and native checks without image export; review in ChemDraw. Use export_figure later for molecule publication files.')
    refresh_identifiers: bool = Field(default=False,description='Bypass the five-minute in-memory validated name/CAS cache. Network permission is still required on every name/CAS request.')
    reaction_paper: Literal['auto','A4 portrait','A4 landscape','A3 landscape'] = Field(default='auto',description='Separate reaction output only: bounded staging preflight followed by the smallest paper fitting native measurements, at unchanged bond scale. Explicit paper refuses estimated overflow before native production and rechecks actual ink.')


class NeedsInput(ValueError):
    def __init__(self,code,message,**detail):
        super().__init__(message); self.code=code; self.detail=detail


def _resolve(items,allow_network,start=1,*,refresh_identifiers=False):
    records=[]; provenance=[]
    for number,item in enumerate(items,start):
        if item.format in ('smiles','inchi'):
            if item.selected_cid is not None:raise ValueError('selected_cid applies only to names or CAS')
            identity=inspect_identifier(item.value,item.format)
            source={'kind':item.format,'value':item.value,'identity':identity}
        else:
            if not allow_network:
                raise NeedsInput('network_permission_required',
                    'Name/CAS lookup requires allow_network=true, or supply an explicit SMILES/InChI. Do not guess a replacement graph.')
            resolution=resolve_identifier(item.value,item.format,allow_network=True,use_cache=not refresh_identifiers)
            candidates=resolution['candidates']
            if item.selected_cid is None:
                if resolution.get('ambiguous') or resolution.get('truncated') or len(candidates)!=1:
                    raise NeedsInput('ambiguous_identifier','Select a candidate CID or provide a more specific identifier.',candidates=candidates)
                chosen=candidates[0]
            else:
                choices=[c for c in candidates if c['cid']==item.selected_cid]
                if len(choices)!=1:raise NeedsInput('unknown_candidate','Selected CID is not in the resolved candidates.',candidates=candidates)
                chosen=choices[0]
            if chosen.get('validation',{}).get('status')!='valid':
                raise NeedsInput('unvalidated_identifier','Provider structure failed local identity validation.',candidates=candidates)
            identity=chosen['identifiers']; source={'kind':item.format,'value':item.value,'resolution':resolution,'selected_cid':chosen['cid']}
        label=item.label or (item.value if item.format in ('name','cas') else str(number))
        records.append({'compound_id':str(number),'label':label,'smiles':identity['canonical_smiles']})
        provenance.append(source)
    return records,provenance


def plan_request(request,allow_network=False,*,shared=False):
    if type(allow_network) is not bool:raise ValueError('allow_network must be a boolean')
    model=DrawingRequest.model_validate(request)
    if model.products is None and model.reaction_paper!='auto':
        raise ValueError('reaction_paper requires products')
    if model.exports in ('preview','canvas') and (not shared or model.products is not None):
        raise ValueError('preview/canvas exports require the shared molecule workflow')
    structures,provenance=_resolve(model.molecules,allow_network,refresh_identifiers=model.refresh_identifiers)
    if model.products is not None:
        products,product_provenance=_resolve(model.products,allow_network,len(structures)+1,refresh_identifiers=model.refresh_identifiers)
        from .reaction_series import prepare_steps
        from rdkit import Chem
        prepare_steps([{'step_id':'reaction','reactants':structures,'products':products,
                       'conditions_above':model.conditions_above,'conditions_below':model.conditions_below}])
        expanded=any('.' in r['smiles'] or Chem.MolFromSmiles(r['smiles']).GetNumAtoms()==1 for r in structures+products)
        return {'workflow':'reaction','reactants':structures,'products':products,'preset':'house',
                'expanded_reaction':expanded,
                'reaction_paper':model.reaction_paper,
                'conditions_above':model.conditions_above,'conditions_below':model.conditions_below,
                'provenance':provenance+product_provenance}
    if model.conditions_above or model.conditions_below:
        raise ValueError('Reaction conditions require explicit products')
    prepared=prepare_structures(structures)
    defaults=plan_drawing_defaults(prepared) if model.panel=='auto' else {'scaffold_smiles':None,'groups':None}
    if shared:
        # Auto is a policy choice, not an explicit request for decorations.
        # Keep its verified scaffold but select a layout supported by this path.
        defaults={**defaults,'groups':None,'panel_layout':'shared_plain_grid'}
    return {'workflow':'molecules','structures':structures,'preset':'house','columns':None,
            **({'page_policy':model.page_policy,'exports':'preview' if model.exports=='auto' else model.exports} if shared else {}),
            'scaffold_smiles':defaults['scaffold_smiles'],
            'scaffold_layout':'reference' if defaults['scaffold_smiles'] else 'rigid',
            'groups':defaults['groups'],'frame':True,'separators':True,
            'provenance':provenance,'decisions':defaults}


def _verify_delivery(result,plan,out):
    audit=result.get('audit',{}); checks=audit.get('checks',{})
    if plan.get('expanded_reaction'):
        required={'native_component_import_identity','native_component_cleanup_identity','preexisting_documents_unchanged'}
    else:
        required={'native_import_identity','native_cleanup_identity','preexisting_documents_unchanged'}
        required.add('final_grid_checks' if plan['workflow']=='molecules' else 'working_content_unchanged')
    if plan.get('groups'):required.add('grouped_bands_and_native_decoration')
    if audit.get('status')!='checks_passed' or any(checks.get(k) is not True for k in required):
        raise ValueError('Required native verification gates are missing or failed')
    if any(v is not True for v in checks.values()):raise ValueError('A native check did not pass')
    artifacts=result.get('artifacts') or {fmt:str(out/f'figure.{fmt}') for fmt in ('cdxml','svg','png')}
    for fmt in ('cdxml','svg','png'):
        path=Path(artifacts.get(fmt,''))
        if not path.is_file() or path.stat().st_size==0 or not path.resolve().is_relative_to(out.resolve()):
            raise ValueError('Missing, empty or out-of-job '+fmt+' artifact')
    from .core import validate_cdxml
    from .polish import chemical_signature
    root=validate_cdxml(Path(artifacts['cdxml']).read_text())
    # The underlying workflow verifies decoration separately. This gate compares
    # molecule graphs again, independent of captions, frame and dividers.
    for page in root.findall('page'):
        for obj in list(page):
            if obj.tag!='fragment':page.remove(obj)
    expected=plan.get('structures') or plan['reactants']+plan['products']
    canonical=sorted(part for r in expected for part in inspect_identifier(r['smiles'])['canonical_smiles'].split('.'))
    if chemical_signature(ET.tostring(root,encoding='unicode'))!=canonical:
        raise ValueError('Delivered native document does not match requested molecular graphs')
    from .placement import collision_pairs
    collisions=collision_pairs(Path(artifacts['cdxml']).read_text(),measured=True)
    if collisions:
        raise ValueError('Delivered placement collision candidates: '+repr(sorted(collisions)[:8]))
    return artifacts


@production_job
def _execute(bridge,plan,out):
    options={k:v for k,v in plan.items() if k not in ('workflow','provenance','decisions','expanded_reaction')}
    if plan['workflow']=='molecules':result=draw_structures(bridge,output_dir=str(out),**options)
    else:result=build_reaction(bridge,output_dir=str(out),**options)
    artifacts=_verify_delivery(result,plan,out)
    return {'status':'completed','stage':'delivery','policy_version':1,'artifacts':artifacts,
            'document':result['document'],'audit':str(out/'audit.json'),
            'visual_review':'required','plan':plan,
            'gates':['input_validated','native_identity_checked','layout_checked','delivered_graphs_checked','artifacts_checked'],
            'placement_check':'Native measured label boxes and conservative atom/bond envelopes; no collision candidates. Not a pixel-perfect visual certificate.'}


def run_drawing(bridge,request,output_dir,allow_network=False,presentation='auto',document_id=None):
    timer=StageTimer()
    result=_run_drawing(bridge,request,output_dir,allow_network,presentation,document_id,timer)
    # Native stages are non-overlapping with input planning. Keep the overall
    # clock separate so lock waits and response preparation remain visible.
    report=timer.report()
    report['stages_seconds'].update(result.get('timings',{}).get('stages_seconds',{}))
    result['timings']=report
    out=Path(output_dir).expanduser()
    if result.get('status')=='completed' and (out/'result.json').is_file():
        _write_json(out/'result.json',result)
    return result


def _run_drawing(bridge,request,output_dir,allow_network,presentation,document_id,timer):
    stage='input';out=Path(output_dir).expanduser()
    try:
        if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output needs an absolute new folder and existing parent')
        if out.exists() or out.is_symlink():raise FileExistsError('Output already exists; no overwrite performed')
        if presentation not in ('auto','background','interactive','shared'):raise ValueError('Invalid presentation mode')
        if document_id is not None and presentation not in ('auto','shared'):
            raise ValueError('An existing document requires shared presentation')
        from .core import Bridge
        shared_molecules=(presentation=='shared' or document_id is not None or
                          isinstance(bridge,Bridge) and presentation in ('auto','interactive'))
        plan=plan_request(request,allow_network,shared=shared_molecules)
        timer.mark('input_resolution_and_planning')
        if plan['workflow']=='reaction' and presentation!='shared' and document_id is None:
            from .reaction_batch import run_reaction_batch
            stage='reaction_batch'
            result=run_reaction_batch(bridge,[{'step_id':'reaction','reactants':plan['reactants'],
                'products':plan['products'],'conditions_above':plan['conditions_above'],
                'conditions_below':plan['conditions_below']}],out,preset=plan['preset'],
                paper=plan['reaction_paper'],presentation=presentation)
            result['plan']=plan
            return result
        if presentation=='shared' or document_id is not None:
            from .shared import run_shared
            stage='shared_execution'
            return run_shared(bridge,plan,out,document_id)
        from .core import Bridge
        if isinstance(bridge,Bridge):
            stage='native_preflight'
            if plan['workflow']=='molecules' and presentation in ('auto','interactive'):
                from .shared import run_shared
                stage='shared_execution'
                return run_shared(bridge,plan,out,document_id)
            if presentation=='auto':
                presentation=bridge.automatic_presentation()
                if presentation=='interactive':
                    from .shared import run_shared
                    stage='shared_execution'
                    return run_shared(bridge,plan,out)
            unsaved=[d for d in bridge.documents()['documents'] if not d.get('file')]
            if unsaved:
                raise NeedsInput('unsaved_user_document',
                    'For supported molecule additions, use presentation=shared with the working document_id; '
                    'that path supports untitled drawings without saving. Separate/background jobs still require '
                    'named pre-existing documents for their preservation checks. '
                    'No production write was sent and no document was modified.',documents=unsaved)
        stage='native_execution'
        try:
            result=_execute(bridge,plan,out,presentation=presentation)
        except ValueError as exc:
            if str(exc).startswith(('Required native verification','A native check','Missing, empty','Delivered native')):
                stage='verification'
            raise
        _write_json(out/'result.json',result)
        return result
    except NeedsInput as exc:
        return {'status':'needs_input','stage':stage,'code':exc.code,'message':str(exc),**exc.detail}
    except NativeUncertain as exc:
        return {'status':'uncertain','stage':stage,'code':'native_state_uncertain','message':str(exc),
                'retry_safe':False,'next_action':'Inspect current native documents and retained audit before any further write.','output_dir':str(out)}
    except (ValueError,FileExistsError,RuntimeError,OSError) as exc:
        return {'status':'rejected','stage':stage,'code':'drawing_gate_failed','message':str(exc),
                'retry_safe':False,'next_action':'Correct the reported input or inspect the retained job. No automatic retry or renderer fallback was attempted.','output_dir':str(out)}
