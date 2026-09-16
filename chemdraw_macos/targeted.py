"""Explicit snapshot selections and copied-CDXML edits, rendered by ChemDraw.

Selections are logical target records, NOT native UI highlights. The tested Mac
AppleEvent selection setter rejects individual atom/bond references.
"""
from contextlib import nullcontext
import copy
import html
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from .editing import (source_token, inspect_editable, _decoded, _label, _tetra,
                      _potential_tetra, _stereo_bonds, verify_native_edit)
from .polish import supported_root, chemical_signature, numbers, transform, bond_lengths
from .workflow import _write_json, remap_ids
from .native_actions import ACTIONS

ALIGN_ACTIONS = {k for k in ACTIONS if k.startswith(('align_', 'distribute_'))}


def _root(text):
    root=supported_root(text)
    if any(e.tag not in ('fragment','t') for e in root.find('page')):
        raise ValueError('Target editing currently requires a molecular sheet and captions, without reactions or graphics')
    return root


def _isolated(root, fid):
    result=copy.deepcopy(root);page=result.find('page')
    for e in list(page):
        if e.tag!='fragment' or e.get('id')!=fid:page.remove(e)
    return ET.tostring(result,encoding='unicode')


def inspect_targets(text):
    root=_root(text);atoms=[];bonds=[];molecules=[]
    for f in root.find('page').findall('fragment'):
        info=inspect_editable(_isolated(root,f.get('id')))
        atoms.extend({**a,'molecule_id':f.get('id')} for a in info['atoms'])
        bonds.extend({**b,'molecule_id':f.get('id')} for b in info['bonds'])
        molecules.append({'id':f.get('id'),'atom_ids':[a['id'] for a in info['atoms']],
                          'bond_ids':[b['id'] for b in info['bonds']],'smiles':info['smiles']})
    return {'source_token':source_token(text),'atoms':atoms,'bonds':bonds,'molecules':molecules,
            'warnings':[{'kind':e.tag,'id':e.get('id'),'message':e.get('Warning')} for e in root.iter() if e.get('Warning')],
            'native_ui_selection':False,
            'note':'IDs address this snapshot, not native AppleScript indices. Refresh after edits.'}


def prepare_selection(text,kind,ids,expected_source_token):
    if source_token(text)!=expected_source_token:raise ValueError('Source selection is stale; inspect again')
    if kind not in ('atom','bond','molecule'):raise ValueError('Select atom, bond or molecule targets')
    if (not isinstance(ids,list) or not 1<=len(ids)<=100 or
            any(not isinstance(i,str) for i in ids) or len(ids)!=len(set(ids))):
        raise ValueError('Supply 1 to 100 unique string target IDs')
    inventory=inspect_targets(text);by_id={e['id']:e for e in inventory[kind+'s']}
    if not set(ids)<=set(by_id):raise ValueError('Target ID absent or wrong object kind')
    return {'kind':kind,'ids':ids,'source_token':inventory['source_token'],
            'objects':[by_id[i] for i in ids],'native_ui_selection':False}


def _selection(text,selection):
    if not isinstance(selection,dict) or set(selection)-{'kind','ids','source_token','objects','native_ui_selection'}:
        raise ValueError('Invalid selection record')
    return prepare_selection(text,selection.get('kind'),selection.get('ids'),selection.get('source_token'))


def _fresh_ids(root,count):
    used={e.get('id') for e in root.iter() if e.get('id')}
    value=max([int(i) for i in used if i.isdigit()]+[0])+1
    return [str(value+i) for i in range(count)]


def plan_target_edit(text,selection,operation):
    selected=_selection(text,selection);root=_root(text)
    if not isinstance(operation,dict):raise ValueError('Operation must be an object')
    if operation.get('kind') in ('attach_ring','attach_fragment') and operation.get('angle_degrees')=='auto':
        errors=[]
        for index,angle in enumerate(range(0,360,30),1):
            try:planned,report=plan_target_edit(text,selection,{**operation,'angle_degrees':angle})
            except ValueError as exc:
                if 'overlap' not in str(exc).lower() and 'collision' not in str(exc).lower():raise
                errors.append(str(exc));continue
            report['operation']=operation
            report['placement'].update(angle_degrees=angle,checked_candidates=index)
            return planned,report
        raise ValueError('No collision-free placement in the 12-angle search; no structure was moved')
    if len(selected['ids'])!=1:raise ValueError('Chemical edits require exactly one selected atom or bond')
    obj=selected['objects'][0];fid=obj['molecule_id'];f=root.find(f"page/fragment[@id='{fid}']")
    before,mapping=_decoded(_isolated(root,fid))
    old_points={n.get('id'):n.get('p') for n in root.findall('.//n')}
    report={'operation':operation,'selected_ids':selected['ids'],'added_atoms':0,'added_bonds':0}
    kind=operation.get('kind')
    if kind=='bond_display':
        if set(operation)!={'kind','display','from_atom_id','allow_stereo_change'}:
            raise ValueError('Bond display requires explicit direction and allow_stereo_change=true')
        if operation['allow_stereo_change'] is not True:raise ValueError('Explicit stereo change authorization required')
        if selected['kind']!='bond' or obj['order']!='1':raise ValueError('Select one single bond')
        displays={'hashed_wedge':'WedgedHash','solid_wedge':'Wedge'}
        if operation['display'] not in displays:raise ValueError('Supported display: hashed_wedge or solid_wedge')
        origin=operation['from_atom_id']
        if origin not in (obj['begin'],obj['end']):raise ValueError('Wedge origin must be a selected bond endpoint')
        b=f.find(f"b[@id='{obj['id']}']")
        b.set('Display',displays[operation['display']]+('Begin' if origin==obj['begin'] else 'End'))
        b.attrib.pop('BS',None)
        report.update(stereo_change_authorized=True,from_atom_id=origin,display=b.get('Display'))
    elif kind=='attach_ring':
        if set(operation)!={'kind','size','angle_degrees'}:raise ValueError('Ring needs size and explicit angle_degrees; no inferred attachment mode')
        size=operation['size'];angle=operation['angle_degrees']
        if type(size) is not int or not 3<=size<=8:raise ValueError('Ring size must be an integer from 3 to 8')
        if type(angle) not in (int,float) or not math.isfinite(angle) or not -360<=angle<=360:
            raise ValueError('Ring angle must be finite and within -360 to 360 degrees')
        if selected['kind']!='atom' or obj['element'] not in ('C','N','O') or obj['charge'] or obj['isotope'] or obj['hydrogens']<1:
            raise ValueError('Ring attachment requires a neutral, nonisotopic H-bearing C/N/O atom')
        if obj['stereo']!='CHI_UNSPECIFIED':raise ValueError('Ring attachment at a stereocentre is unsupported')
        atom=before.GetAtomWithIdx(mapping[obj['id']])
        if any(n.GetAtomicNum()==1 for n in atom.GetNeighbors()):raise ValueError('Explicit H-atom replacement requires a separate edit')
        length=statistics.median(bond_lengths(f));r=length/(2*math.sin(math.pi/size))
        theta=math.radians(angle);x,y=obj['position_pt'];cx=x+(length+r)*math.cos(theta);cy=y+(length+r)*math.sin(theta)
        points=[(cx+r*math.cos(theta+math.pi+2*math.pi*i/size),cy+r*math.sin(theta+math.pi+2*math.pi*i/size)) for i in range(size)]
        existing=[numbers(n.get('p'),2) for n in root.findall('.//n')]
        if any(math.dist(p,q)<.6*length for p in points for q in existing):
            raise ValueError('Requested ring placement overlaps existing atoms; choose another explicit angle')
        ids=_fresh_ids(root,2*size+1);nodeids=ids[:size];bondids=ids[size:]
        n=f.find(f"n[@id='{obj['id']}']");n.set('NumHydrogens',str(obj['hydrogens']-1));_label(root,n)
        for nid,(px,py) in zip(nodeids,points):ET.SubElement(f,'n',{'id':nid,'p':f'{px:.6f} {py:.6f}'})
        pairs=[(obj['id'],nodeids[0])]+[(nodeids[i],nodeids[(i+1)%size]) for i in range(size)]
        for bid,(a,b) in zip(bondids,pairs):
            ET.SubElement(f,'b',{'id':bid,'B':a,'E':b,'Order':'1','Display':'Solid',
                'LineWidth':root.get('LineWidth','1.58'),'BoldWidth':root.get('BoldWidth','2')})
        report.update(added_atoms=size,added_bonds=size+1,attachment_mode='single_bond_substituent',
                      hydrogen_change={'atom_id':obj['id'],'before':obj['hydrogens'],'after':obj['hydrogens']-1})
    elif kind in ('set_atom','set_bond_order','attach_fragment','remove_substituent'):
        from .targeted_changes import apply_change
        apply_change(root,f,obj,selected,operation,before,mapping,report)
    else:raise ValueError('Unknown targeted chemical edit')
    for n in f.findall('n'):n.attrib.pop('AS',None)
    planned=ET.tostring(root,encoding='unicode');after,after_map=_decoded(_isolated(root,fid))
    old_stereo=_tetra(before,mapping);new_stereo=_tetra(after,after_map)
    for aid in report.get('removed_atom_ids',[]):old_stereo.pop(aid,None)
    expected_fragment=report.pop('fragment_stereo',{})
    old_stereo.update(expected_fragment)
    if kind=='bond_display':
        origin=operation['from_atom_id'];old_stereo.pop(origin,None);new_stereo.pop(origin,None)
    if old_stereo!=new_stereo:raise ValueError('Edit changes stereo outside the explicitly targeted centre')
    if kind!='bond_display':
        retained=set(mapping)&set(after_map)
        if _potential_tetra(before,mapping)&retained != _potential_tetra(after,after_map)&retained:
            raise ValueError('Edit creates or removes potential stereochemistry on retained atoms; unsupported')
        if _stereo_bonds(before,mapping)!=_stereo_bonds(after,after_map):
            raise ValueError('Edit changes potential alkene stereochemistry; unsupported')
    for aid,requested in report.get('requested_atoms',{}).items():
        atom=after.GetAtomWithIdx(after_map[aid])
        if (atom.GetSymbol(),atom.GetTotalNumHs(),atom.GetFormalCharge())!=(requested['element'],requested['hydrogens'],requested['charge']):raise ValueError('Decoded atom does not match explicit request')
    for aid,h in report.get('requested_hydrogens',{}).items():
        if after.GetAtomWithIdx(after_map[aid]).GetTotalNumHs()!=h:raise ValueError('Decoded hydrogen count differs from request')
    if any(root.find(f".//n[@id='{i}']").get('p')!=p for i,p in old_points.items() if i not in report.get('removed_atom_ids',[])):
        raise ValueError('Existing atom coordinates changed')
    from .placement import check_edit_placement
    report['placement']=check_edit_placement(text,planned)
    if kind in ('attach_ring','attach_fragment'):report['placement'].update(angle_degrees=operation['angle_degrees'],checked_candidates=1)
    report.update(before_smiles=chemical_signature(text),after_smiles=chemical_signature(planned),
                  original_atom_coordinates_preserved=True)
    return planned,report


def verify_targeted(planned,native):
    p=_root(planned);n=_root(native);mapping=remap_ids(planned,native)
    if len(p.find('page'))!=len(n.find('page')):raise ValueError('Native page object count changed')
    checks=[]
    for f in p.find('page').findall('fragment'):
        old=_isolated(p,f.get('id'));new=_isolated(n,mapping[f.get('id')])
        checked=verify_native_edit(old,new);atommap=checked['atom_id_map']
        nf=n.find(f"page/fragment[@id='{mapping[f.get('id')]}']")
        # Explicit wedge direction must survive native saving as well as stereo.
        for b in f.findall('b'):
            hits=[v for v in nf.findall('b') if {v.get('B'),v.get('E')}=={atommap[b.get('B')],atommap[b.get('E')]}]
            if len(hits)!=1:raise ValueError('Native bond matching is ambiguous')
            v=hits[0]
            def display(bond,ids):
                d=bond.get('Display','Solid')
                for suffix,key in (('Begin','B'),('End','E')):
                    if d.endswith(suffix):return (d[:-len(suffix)],ids[bond.get(key)])
                return (d,None)
            if display(b,atommap)!=display(v,{a:a for a in atommap.values()}):
                raise ValueError('Native bond display or wedge direction changed')
        checks.append(checked)
    for t in p.find('page').findall('t'):
        u=n.find(f"page/t[@id='{mapping[t.get('id')]}']")
        if ''.join(t.itertext()).strip()!=''.join(u.itertext()).strip():raise ValueError('Native caption text changed')
    return {'mapped_chemistry_verified':True,'coordinates_verified':True,'bond_displays_verified':True,
            'page_object_id_map':mapping,'molecules':checks}


def _snapshot(bridge,did):
    path=bridge._new_path('.cdxml','backups');bridge.export(did,str(path),'cdxml')
    return path.read_text()


def validate_alignment(text,selection,operation):
    selected=_selection(text,selection)
    if (not isinstance(operation,dict) or set(operation)!={'kind','action'} or
            operation['kind']!='native_align' or operation['action'] not in ALIGN_ACTIONS):
        raise ValueError('Choose an allowlisted native alignment or distribution action')
    minimum=3 if operation['action'].startswith('distribute_') else 2
    if selected['kind']!='molecule' or len(selected['ids'])<minimum:
        raise ValueError(f'Native action requires at least {minimum} selected molecules')
    return selected


def _align_selected(bridge,text,selection,operation,audit):
    selected=validate_alignment(text,selection,operation);root=_root(text)
    isolated=copy.deepcopy(root);page=isolated.find('page')
    for e in list(page):
        if e.tag!='fragment' or e.get('id') not in selected['ids']:page.remove(e)
    seed=ET.tostring(isolated,encoding='unicode')
    created=bridge.create(seed);did=created['document']['document_id'];audit['owned_document_ids'].append(did)
    before=_snapshot(bridge,did);mapping=remap_ids(seed,before)
    result=bridge.native_action(did,operation['action'],selection='all')
    if result['status']!='native_action_applied_review_required':
        raise ValueError('Native alignment unavailable for the selected molecules')
    after=_snapshot(bridge,did);a=_root(before);b=_root(after);moves=[]
    if chemical_signature(before)!=chemical_signature(after):raise ValueError('Native alignment changed chemistry')
    for fid in selected['ids']:
        old=a.find(f"page/fragment[@id='{mapping[fid]}']");new=b.find(f"page/fragment[@id='{mapping[fid]}']")
        if new is None:raise ValueError('Native alignment renumbered a molecule; cannot safely match its move')
        oldnodes={n.get('id'):n for n in old.findall('n')};newnodes={n.get('id'):n for n in new.findall('n')}
        if oldnodes.keys()!=newnodes.keys():raise ValueError('Native alignment changed atom IDs')
        deltas=[tuple(v-u for u,v in zip(numbers(oldnodes[i].get('p'),2),numbers(newnodes[i].get('p'),2))) for i in oldnodes]
        dx,dy=deltas[0]
        if any(math.dist(d,(dx,dy))>.03 for d in deltas):raise ValueError('Native alignment was not a rigid translation')
        # Verify each moved native molecule against that exact translation.
        moved=copy.deepcopy(a);moved.find('page').clear();mf=copy.deepcopy(old);transform(mf,dx=dx,dy=dy);moved.find('page').append(mf)
        verify_native_edit(ET.tostring(moved,encoding='unicode'),_isolated(b,new.get('id')))
        transform(root.find(f"page/fragment[@id='{fid}']"),dx=dx,dy=dy)
        moves.append({'molecule_id':fid,'dx':dx,'dy':dy})
    # Only translate the original selected fragments. Captions and unselected
    # objects are never replaced with native subset-export content.
    bridge.close(did)
    return ET.tostring(root,encoding='unicode'),{'operation':operation,'native_command':ACTIONS[operation['action']],
        'moves':moves,'caption_policy':'unchanged','unselected_objects':'unchanged',
        'before_smiles':chemical_signature(text),'after_smiles':chemical_signature(text)}


def inspect_targets_document(bridge,document_id):
    with getattr(bridge,'lock',nullcontext()):return inspect_targets(_snapshot(bridge,document_id))


def prepare_selection_document(bridge,document_id,kind,ids,expected_source_token):
    with getattr(bridge,'lock',nullcontext()):
        return prepare_selection(_snapshot(bridge,document_id),kind,ids,expected_source_token)


def edit_targets_document(bridge,document_id,output_dir,selection,operation,pixels=2400):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('New absolute output directory with existing parent required')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be 256 to 8192')
    with getattr(bridge,'lock',nullcontext()):
        source=_snapshot(bridge,document_id);selected=_selection(source,selection)
        alignment=isinstance(operation,dict) and operation.get('kind')=='native_align'
        if alignment:validate_alignment(source,selected,operation)
        else:planned,diff=plan_target_edit(source,selected,operation)
        baseline=bridge.documents();out.mkdir()
        audit={'status':'in_progress','visual_review':'required','native_ui_selection':False,
               'editing_backend':'copied CDXML','renderer':'native ChemDraw','owned_document_ids':[]}
        try:
            (out/'before.cdxml').write_text(source)
            if alignment:
                planned,diff=_align_selected(bridge,source,selected,operation,audit)
                audit['editing_backend']='native subset alignment; copy only verified translations'
            (out/'planned.cdxml').write_text(planned)
            _write_json(out/'recipe.json',{'selection':selected,'operation':operation,'pixels':pixels})
            for fmt in ('svg','png'):bridge.export(document_id,str(out/f'before.{fmt}'),fmt,pixels)
            if source_token(_snapshot(bridge,document_id))!=selected['source_token']:raise ValueError('Source became stale')
            result=bridge.create(planned);did=result['document']['document_id'];audit['owned_document_ids'].append(did)
            for fmt in ('svg','png','cdxml'):bridge.export(did,str(out/f'figure.{fmt}'),fmt,pixels)
            verified=verify_targeted(planned,(out/'figure.cdxml').read_text())
            if not alignment:
                # Restore planned IDs solely for comparing source/new obstacle pairs.
                native_root=ET.fromstring((out/'figure.cdxml').read_text())
                ids={v:k for k,v in verified['page_object_id_map'].items()}
                for check in verified['molecules']:ids.update({v:k for k,v in check['atom_id_map'].items()})
                for e in native_root.iter():
                    for key in ('id','B','E'):
                        if e.get(key) in ids:e.set(key,ids[e.get(key)])
                # Bond IDs are not returned by the page mapper; match endpoints.
                expected_root=ET.fromstring(planned)
                bondids={frozenset((b.get('B'),b.get('E'))):b.get('id') for b in expected_root.findall('.//b')}
                for b in native_root.findall('.//b'):b.set('id',bondids[frozenset((b.get('B'),b.get('E')))])
                from .placement import check_edit_placement
                verified['placement']=check_edit_placement(source,ET.tostring(native_root,encoding='unicode'),measured=True)
            if source_token(_snapshot(bridge,document_id))!=selected['source_token']:raise ValueError('Source changed during editing')
            if [d for d in bridge.documents()['documents'] if d['document_id']!=did]!=baseline['documents']:
                raise ValueError('Pre-existing document metadata changed')
            audit.update(status='checks_passed',changes=diff,verification=verified,source_unchanged=True)
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Targeted ChemDraw edit</title>'
                '<style>body{font:16px system-ui;background:#eee;margin:24px}main{display:flex;gap:20px}figure{margin:0;background:white;padding:16px;width:46%}img{width:100%;height:400px;object-fit:contain}pre{white-space:pre-wrap}</style>'
                '<h1>Targeted edit</h1><p>Explicit copied-CDXML edit, rendered by ChemDraw. Visual and chemical review required.</p>'
                '<main><figure>Before<img src="before.png"></figure><figure>After<img src="figure.png"></figure></main>'
                '<p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="audit.json">Audit</a></p><pre>'+html.escape(str(diff))+'</pre>')
            return {'document':result['document'],'review':str(out/'review.html'),'audit':audit,
                    'artifacts':{fmt:str(out/f'figure.{fmt}') for fmt in ('cdxml','svg','png')}}
        except BaseException as exc:
            audit.update(status='failed_or_uncertain',error=str(exc));_write_json(out/'audit.json',audit)
            # Keep diagnostic copies; never close or retry an uncertain write.
            raise
