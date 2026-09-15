"""One explicit approved scope job through native grouped figures."""
from contextlib import nullcontext
import copy
import html
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .scope_design import propose_scope
from .draw import draw_structures
from .scope import arrange_scope, verify_scope, _root
from .scope_decoration import decorate_scope_document, plan_scope_decoration
from .core import preset_settings
from .polish import transform, chemical_signature
from .editing import source_token
from .batch import _native, NativeUncertain, _document_content
from .workflow import _write_json


def _spacing(value):
    defaults={'h_gap':18.,'v_gap':24.,'label_gap':10.,'margin':48.}
    if not isinstance(value,dict) or set(value)-set(defaults):raise ValueError('Unknown job layout fields.')
    for key,number in value.items():
        if type(number) not in (int,float) or not math.isfinite(number) or not (24 if key=='margin' else 4)<=number<=144:
            raise ValueError('Invalid job layout spacing.')
    return {**defaults,**value}


def plan_scope_job(job):
    """Offline proposal/explicit selection/grouping; never accepts a proposal implicitly."""
    allowed = {'schema_version','parent_smiles','handle_atom_map','groups','accept_all',
               'selected_candidate_ids','columns','preset','frame','separators','pixels','layout'}
    if not isinstance(job,dict) or set(job)-allowed:
        raise ValueError('Unsupported scope job fields.')
    if type(job.get('schema_version',1)) is not int or job.get('schema_version',1)!=1:
        raise ValueError('Unsupported scope job schema.')
    if 'parent_smiles' not in job or 'handle_atom_map' not in job:
        raise ValueError('Scope job requires explicit parent_smiles and handle_atom_map.')
    if 'accept_all' in job and type(job['accept_all']) is not bool:
        raise ValueError('accept_all must be a boolean.')
    if 'accept_all' in job and 'selected_candidate_ids' in job:
        raise ValueError('Choose accept_all or selected_candidate_ids, never both.')
    for key in ('frame','separators'):
        if type(job.get(key,True)) is not bool:raise ValueError(f'{key} must be a boolean.')
    columns = job.get('columns',4);pixels = job.get('pixels',3200)
    if type(columns) is not int or not 1<=columns<=24:raise ValueError('Columns must be 1 through 24.')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be 256 through 8192.')
    preset = copy.deepcopy(job.get('preset','house'));preset_settings(preset)
    layout = _spacing(job.get('layout',{}))
    proposal = propose_scope(job['parent_smiles'],job['handle_atom_map'])
    by_id = {c['candidate_id']:c for c in proposal['candidates']}
    vocabulary = {category for c in by_id.values() for category in c['categories']}
    definitions = job.get('groups');labels = set()
    if not isinstance(definitions,list) or not 1<=len(definitions)<=14:
        raise ValueError('Supply an explicit ordered list of groups.')
    for group in definitions:
        if not isinstance(group,dict) or set(group)!={'label','categories'}:
            raise ValueError('Groups require label and categories.')
        label = group['label'];categories = group['categories']
        if (not isinstance(label,str) or not label.strip() or len(label)>80 or label in labels or
                any(ord(c)<32 or ord(c)==127 for c in label)):
            raise ValueError('Group labels must be unique nonblank single-line text of at most 80 characters.')
        labels.add(label)
        if (not isinstance(categories,list) or not categories or
                any(not isinstance(c,str) or c not in vocabulary for c in categories) or
                len(categories)!=len(set(categories))):
            raise ValueError('Group categories must be a unique list of explicit proposal categories.')
    accepted = job.get('accept_all',False) or 'selected_candidate_ids' in job
    selected_ids = list(by_id) if job.get('accept_all') else job.get('selected_candidate_ids',[])
    if accepted and (not isinstance(selected_ids,list) or not selected_ids or
            any(not isinstance(cid,str) or cid not in by_id for cid in selected_ids) or
            len(selected_ids)!=len(set(selected_ids))):
        raise ValueError('Explicit selection must contain unique known candidate IDs.')
    selected = [];groups = [];structures = [];assigned = set()
    for definition in definitions:
        records = []
        for candidate in proposal['candidates']:
            cid = candidate['candidate_id']
            if cid not in selected_ids or cid in assigned:continue
            primary = next((c for c in definition['categories'] if c in candidate['categories']),None)
            if primary is None:continue
            assigned.add(cid);compound_id = str(len(selected)+1)
            selected.append({**copy.deepcopy(candidate),'compound_id':compound_id,
                'assigned_group':definition['label'],'primary_category':primary,
                'secondary_categories':[c for c in candidate['categories'] if c!=primary]})
            label = candidate['display_label'].removesuffix(' relative to parent')
            if label=='Parent reference':label='Parent'
            structures.append({'compound_id':compound_id,'label':label,'smiles':candidate['canonical_smiles']})
            records.append(compound_id)
        if records:groups.append({**copy.deepcopy(definition),'compound_ids':records})
    if accepted and assigned!=set(selected_ids):
        raise ValueError('Every selected candidate must match an explicit ordered group category.')
    return {'schema_version':1,'status':'planned','selection_required':not accepted,
        'selection':{'mode':'accept_all' if job.get('accept_all') else 'selected_ids' if accepted else 'unapproved',
                     'candidate_ids':list(selected_ids)},'proposal':proposal,
        'selected_count':len(selected),'selected_candidates':selected,'structures':structures,'groups':groups,
        'group_definitions':copy.deepcopy(definitions),'scaffold_smiles':proposal['parent']['canonical_smiles'],
        'columns':columns,'preset':preset,'layout':layout,'frame':job.get('frame',True),
        'separators':job.get('separators',True),'pixels':pixels,
        'limitations':['One candidate is assigned to its first matching explicit group; all memberships are retained.',
                       'Proposals and group names are not chemical compatibility or experimental yield predictions.',
                       'Native layout uses group-specific rows; page overflow fails instead of shrinking.']}


def arrange_scope_groups(text,cells,groups,columns=4,layout=None,frame=True,separators=True):
    """Translate measured, aligned compounds into true group bands using shared cell geometry."""
    if not isinstance(groups,list) or not groups:raise ValueError('No selected groups to arrange.')
    by_id = {c['compound_id']:c for c in cells}
    ordered_ids = [cid for g in groups for cid in g['compound_ids']]
    if len(ordered_ids)!=len(set(ordered_ids)) or set(ordered_ids)!=set(by_id):
        raise ValueError('Groups must own every selected compound exactly once.')
    ordered = [{k:v for k,v in by_id[cid].items() if k in
                {'compound_id','fragment_ids','caption_id','metadata_id','yield_percent'}} for cid in ordered_ids]
    columns = min(columns,len(ordered))
    uniform,layout = arrange_scope(text,ordered,columns=columns,**_spacing(layout or {}))
    root = _root(uniform);page = root.find('page');objects = {e.get('id'):e for e in page}
    heading_size = float(root.get('CaptionSize',root.get('LabelSize','10')))
    gap = max(heading_size+28,layout['v_gap']);cursor = layout['region'][1]+heading_size+10
    by_id = {c['compound_id']:c for c in layout['cells']};decoration_groups = [];group_layout = [];total_rows = 0
    for group in groups:
        local = [];top = cursor
        for index,cid in enumerate(group['compound_ids']):
            cell = by_id[cid];row,column = divmod(index,columns)
            dx = (column-cell['column'])*(layout['cell_width']+layout['h_gap'])
            old_top = layout['region'][1]+cell['row']*(layout['cell_height']+layout['v_gap'])
            new_top = cursor+row*(layout['cell_height']+layout['v_gap']);dy = new_top-old_top
            owned = cell['fragment_ids']+[c for c in (cell.get('caption_id'),cell.get('metadata_id')) if c]
            for oid in owned:transform(objects[oid],dx=dx,dy=dy)
            cell.update(column=column,row=total_rows+row,center_x=cell['center_x']+dx,
                structure_center_y=cell['structure_center_y']+dy,
                name_baseline=cell['name_baseline']+dy if cell['name_baseline'] is not None else None,
                metadata_baseline=cell['metadata_baseline']+dy,
                name_anchor_x=cell['name_anchor_x']+dx if cell['name_anchor_x'] is not None else None,
                metadata_anchor_x=cell['metadata_anchor_x']+dx)
            local.append(cell)
        rows = math.ceil(len(local)/columns)
        total_rows += rows
        bottom = top+rows*layout['cell_height']+(rows-1)*layout['v_gap']
        group_layout.append({'label':group['label'],'top':top,'bottom':bottom,'rows':rows})
        decoration_groups.append({'label':group['label'],
            'fragment_ids':[fid for c in local for fid in c['fragment_ids']],
            'caption_ids':[tid for c in local for tid in (c.get('caption_id'),c.get('metadata_id')) if tid]})
        cursor = bottom+gap
    layout['rows'] = total_rows
    arranged = ET.tostring(root,encoding='unicode')
    if chemical_signature(arranged)!=chemical_signature(text):raise ValueError('Grouped layout changed chemical identity.')
    verify_scope(arranged,arranged,layout)
    # Preflight decoration space using the measured translations, before another native write.
    plan_scope_decoration(arranged,decoration_groups,frame,separators)
    return arranged,{'layout':layout,'decoration_groups':decoration_groups,'group_bands':group_layout}


def build_scope_job(bridge,job,output_dir):
    plan = plan_scope_job(job)
    if plan['selection_required']:raise ValueError('Explicit selection or accept_all=true is required before native creation.')
    out = Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires an absolute path and existing parent.')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists.')
    from .styles import require_style_fonts
    require_style_fonts(plan['preset'])
    owned = [];audit = {'status':'in_progress','checks':{},'visual_review':'required','selection':plan['selection']}
    with getattr(bridge,'lock',nullcontext()):
        baseline = _native(bridge.documents)['documents']
        content = {d['document_id']:_document_content(bridge,d['document_id']) for d in baseline}
        out.mkdir();_write_json(out/'job.json',job);_write_json(out/'plan.json',plan)
        _write_json(out/'proposal.json',plan['proposal']);_write_json(out/'audit.json',audit)
        try:
            drawn = draw_structures(bridge,plan['structures'],str(out/'drawing'),preset=plan['preset'],
                columns=min(plan['columns'],len(plan['structures'])),pixels=plan['pixels'],
                scaffold_smiles=plan['scaffold_smiles'],layout=plan['layout'])
            did = drawn['document']['document_id'];owned.append(did);audit['drawing_audit'] = drawn['audit']
            snapshot = out/'drawn-native.cdxml';_native(bridge.export,did,str(snapshot),'cdxml')
            cells = drawn['audit']['grid_audit']['verification']['cells']
            arranged,group_plan = arrange_scope_groups(snapshot.read_text(),cells,plan['groups'],plan['columns'],
                plan['layout'],plan['frame'],plan['separators'])
            (out/'grouped-planned.cdxml').write_text(arranged);_write_json(out/'group-layout.json',group_plan)
            grouped = _native(bridge.create,arranged);gid = grouped['document']['document_id'];owned.append(gid)
            grouped_path = out/'grouped-native.cdxml';_native(bridge.export,gid,str(grouped_path),'cdxml');native = grouped_path.read_text()
            verification = verify_scope(arranged,native,group_plan['layout']);audit['grouped_verification'] = verification
            from .styles import verify_custom_style
            audit['custom_style_verification'] = verify_custom_style(arranged,native,plan['preset'])
            native_cells = {c['compound_id']:c for c in verification['cells']}
            groups = [{'label':g['label'],
                'fragment_ids':[fid for cid in g['compound_ids'] for fid in native_cells[cid]['fragment_ids']],
                'caption_ids':[tid for cid in g['compound_ids'] for tid in
                               (native_cells[cid].get('caption_id'),native_cells[cid].get('metadata_id')) if tid]}
                      for g in plan['groups']]
            final = decorate_scope_document(bridge,gid,str(out/'figure'),groups,source_token(native),
                frame=plan['frame'],separators=plan['separators'],pixels=plan['pixels'])
            fid = final['document']['document_id'];owned.append(fid);audit['decoration_audit'] = final['audit']
            # The child verifies its source and rendering; close intermediates only after that success.
            for old in owned[:-1]:_native(bridge.close,old)
            owned = [fid]
            if [d for d in _native(bridge.documents)['documents'] if d['document_id']!=fid]!=baseline:
                raise ValueError('Pre-existing document inventory changed.')
            if any(_document_content(bridge,did)!=source for did,source in content.items()):
                raise ValueError('Pre-existing document content changed.')
            audit.update(status='checks_passed',selected_count=plan['selected_count'],groups=plan['groups'])
            audit['checks'].update(explicit_selection=True,group_bands_verified=True,
                                   final_native_decoration_verified=True,preexisting_documents_unchanged=True)
            _write_json(out/'audit.json',audit)
            summary=''.join(f'<li>{html.escape(g["label"])}: {len(g["compound_ids"])}</li>' for g in plan['groups'])
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Scope job</title><h1>Grouped scope</h1>'
                '<p>Explicit approved candidates. No experimental yields. Visual review required.</p><ul>'+summary+'</ul>'
                '<img style="max-width:100%" src="figure/figure.png"><p><a href="figure/figure.cdxml">Editable ChemDraw</a> '
                '<a href="figure/figure.svg">SVG</a> <a href="figure/figure.png">PNG</a> <a href="plan.json">Selection and groups</a> '
                '<a href="audit.json">Audit</a></p>')
            return {'document':final['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit,'plan':plan}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned,
                         recovery='No retries or automatic closes after native uncertainty.')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc));_write_json(out/'audit.json',audit)
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit);raise
            raise
