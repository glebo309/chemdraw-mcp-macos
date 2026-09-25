"""Explicit SMILES to native ChemDraw drawings with a measured grid handoff.

RDKit supplies a validated MOL coordinate seed, never the exported renderer.
Desktop ChemDraw imports, cleans, measures and renders the actual structures.
"""
from contextlib import nullcontext
import copy
import html
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .batch import _native, NativeUncertain, _document_content
from .core import PRESETS, style_cdxml, preset_settings
from .editing import source_token, _decoded
from .polish import chemical_signature, bounds, transform, numbers, normalize_cdxml
from .scope import _root, grid_document, remap_cells, verify_molecules
from .workflow import _write_json


def prepare_structures(structures,unit_charges=False):
    from rdkit import Chem
    from .identifiers import inspect_identifier
    if not isinstance(structures,list) or not 1<=len(structures)<=24:
        raise ValueError('Supply 1 through 24 explicit structures')
    result=[];keys=set()
    for item in structures:
        if not isinstance(item,dict) or set(item)!={'compound_id','label','smiles'}:
            raise ValueError('Each structure requires exactly compound_id, label and smiles; no invented yields')
        key=item['compound_id'];label=item['label']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,31}',key) or key.lower() in keys:
            raise ValueError('Compound IDs must be unique safe identifiers')
        keys.add(key.lower())
        if not isinstance(label,str) or not label.strip() or len(label)>120 or any(ord(c)<32 or ord(c)==127 for c in label):
            raise ValueError('Supply a single-line label of 1 through 120 characters')
        info=inspect_identifier(item['smiles'],'smiles')
        params=Chem.SmilesParserParams();params.removeHs=False
        mol=Chem.MolFromSmiles(info['canonical_smiles'],params)
        if mol is None or len(Chem.GetMolFrags(mol))!=1 or not 2<=mol.GetNumAtoms()<=150:
            raise ValueError('Native creation supports connected structures of 2 through 150 atoms')
        if unit_charges and any(a.GetFormalCharge() not in (-1,0,1) for a in mol.GetAtoms()):
            raise ValueError('Circled drawing supports only formal unit charges (+1/-1)')
        if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
            raise ValueError('Radical creation is not supported')
        if any(a.GetAtomicNum() not in (1,5,6,7,8,9,14,15,16,17,35,53) for a in mol.GetAtoms()):
            raise ValueError('Unsupported native creation element')
        if any(a.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED for a in mol.GetAtoms()):
            # Plain isomeric SMILES specifies absolute centres, not an AND
            # mixture. ChemDraw interprets a zero MOL chiral flag as relative.
            mol.SetIntProp('_MolFileChiralFlag',1)
        block=Chem.MolToMolBlock(mol)
        check=Chem.MolFromMolBlock(block,removeHs=False)
        if check is None or Chem.MolToSmiles(check,isomericSmiles=True)!=info['canonical_smiles']:
            raise ValueError('MOL seed did not preserve the explicit molecular identity')
        result.append({**item,'canonical_smiles':info['canonical_smiles'],'molblock':block})
    return result


def combine_native_structures(native_texts,items,preset='house'):
    if len(native_texts)!=len(items) or not items:raise ValueError('Native structure count mismatch')
    spec=preset_settings(preset)
    native_texts=[normalize_cdxml(text,preset)[0] for text in native_texts]
    root=copy.deepcopy(_root(native_texts[0]));page=root.find('page')
    for child in list(page):page.remove(child)
    for attr in ('Name','WindowPosition','WindowSize'):root.attrib.pop(attr,None)
    x1,y1,x2,y2=numbers(page.get('BoundingBox'),4)
    page.set('id','1')
    native_boxes=[bounds(_root(text).find('page/fragment')) for text in native_texts]
    seed_width=max(max(b.width for b in native_boxes),max(len(i['label'])*float(spec['CaptionSize']) for i in items))+24
    seed_height=max(b.height for b in native_boxes)+55
    seed_columns=min(len(items),max(1,int((x2-x1-72)//seed_width)))
    seed_rows=math.ceil(len(items)/seed_columns)
    if seed_width>x2-x1-72 or seed_rows*seed_height>y2-y1-72:
        raise ValueError('Initial native assembly does not fit one physical page; use fewer structures or shorter labels')
    cells=[];next_id=2
    for index,(text,item) in enumerate(zip(native_texts,items)):
        native=_root(text)
        if chemical_signature(text)!=[item['canonical_smiles']]:raise ValueError('Native molecular identity differs from requested SMILES')
        _validate_native_labels(text)
        fragments=native.findall('page/fragment')
        if len(fragments)!=1 or native.findall('page/t'):raise ValueError('Expected one native molecule without inferred page captions')
        f=copy.deepcopy(fragments[0]);mapping={}
        for e in f.iter():
            if e.get('id'):
                mapping[e.get('id')]=str(next_id);next_id+=1
        for e in f.iter():
            from .crossings import remap_crossings
            remap_crossings(e, mapping)
            for attr in ('id','B','E'):
                if e.get(attr):e.set(attr,mapping[e.get(attr)])
            # These are cached/ID-valued properties, not the depicted wedges.
            e.attrib.pop('AS',None);e.attrib.pop('BondOrdering',None);e.attrib.pop('BondCircularOrdering',None)
        box=bounds(f)
        cx=x1+36+seed_width*(index%seed_columns+.5)
        cy=y1+36+seed_height*(index//seed_columns)+max(b.height for b in native_boxes)/2+4
        if box.width>x2-x1-96 or box.height>y2-y1-160:
            raise ValueError('Native molecule is too large for initial single-page assembly')
        if len(item['label'])*float(spec['CaptionSize'])>x2-x1-96:
            raise ValueError('Label is too long for conservative initial page-fit preflight')
        transform(f,dx=cx-box.center[0],dy=cy-box.center[1]);page.append(f)
        tid=str(next_id);next_id+=1
        t=ET.SubElement(page,'t',{'id':tid,'p':f'{cx} {cy+max(b.height for b in native_boxes)/2+18}','Justification':'Center'})
        ET.SubElement(t,'s',{'size':'10'}).text=item['label']
        cells.append({'compound_id':item['compound_id'],'fragment_ids':[f.get('id')],
                      'caption_id':tid,'yield_percent':None})
    text=style_cdxml(ET.tostring(root,encoding='unicode'),preset)
    if chemical_signature(text)!=sorted(item['canonical_smiles'] for item in items):
        raise ValueError('Combined native structure identity changed')
    return text,cells


def _validate_native_labels(text):
    """Check native elemental/H text against decoded atoms, not arbitrary names."""
    root=_root(text);mol,mapping=_decoded(text)
    for node in root.findall('page/fragment/n'):
        atom=mol.GetAtomWithIdx(mapping[node.get('id')])
        label=''.join(s.text or '' for s in node.findall('t/s'))
        if not label and atom.GetAtomicNum()==6:continue
        symbols=re.findall(r'([A-Z][a-z]?)(\d*)',label)
        if atom.GetAtomicNum()==1 and atom.GetIsotope() in (2,3) and label in ('D','T'):continue
        heavy=[s for s,n in symbols if s!='H']
        expected_heavy=[] if atom.GetAtomicNum()==1 else [atom.GetSymbol()]
        hydrogens=sum(int(n or '1') for s,n in symbols if s=='H')
        expected_h=1 if atom.GetAtomicNum()==1 else atom.GetTotalNumHs()
        if heavy!=expected_heavy or hydrogens!=expected_h:
            raise ValueError('Native atom label differs from its elemental/hydrogen graph')


def charge_requests(text):
    from .core import validate_cdxml
    root=validate_cdxml(text);requests=[]
    for fragment in root.findall('page/fragment'):
        for atom in fragment.findall('n'):
            charge=int(atom.get('Charge','0'))
            if not charge:continue
            if charge not in (-1,1):raise ValueError('Circled drawing supports only formal unit charges (+1/-1)')
            aid=atom.get('id')
            if any(g.find(f'represent[@attribute="Charge"][@object="{aid}"]') is not None for g in fragment.findall('graphic')):continue
            requests.append({'key':'charge-'+aid,'kind':'charge','atom_id':aid})
    if len(requests)>50:raise ValueError('At most 50 circled charges per drawing')
    return requests


from .presentation import production_job


@production_job(shared_molecules=True)
def draw_structures(bridge,structures,output_dir,preset='house',columns=None,pixels=3200,scaffold_smiles=None,layout=None,charge_style='plain',groups=None,frame=True,separators=True,scaffold_layout='rigid'):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if charge_style not in ('plain','circled'):raise ValueError('charge_style must be plain or circled')
    layout={} if layout is None else dict(layout)
    if set(layout)-{'margin','h_gap','v_gap','label_gap'} or any(type(v) not in (int,float) or not math.isfinite(v) or not 2<=v<=144 for v in layout.values()):
        raise ValueError('Invalid draw layout settings')
    preset_settings(preset)
    from .styles import require_style_fonts
    require_style_fonts(preset)
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be 256 through 8192')
    records=prepare_structures(structures,unit_charges=charge_style=='circled')
    if scaffold_layout not in ('rigid','reference'):raise ValueError('scaffold_layout must be rigid or reference')
    if scaffold_layout=='reference' and scaffold_smiles is None:raise ValueError('Reference layout requires scaffold_smiles')
    if type(frame) is not bool or type(separators) is not bool:raise ValueError('frame and separators must be booleans')
    if groups is not None:
        from .grouped_draw import validate_draw_groups
        validate_draw_groups(groups,[r['compound_id'] for r in records])
    if charge_style=='circled':
        from rdkit import Chem
        charges=[a.GetFormalCharge() for item in records for a in Chem.MolFromMolBlock(item['molblock'],removeHs=False).GetAtoms() if a.GetFormalCharge()]
        if any(c not in (-1,1) for c in charges):raise ValueError('Circled drawing supports only formal unit charges (+1/-1)')
        if len(charges)>50:raise ValueError('At most 50 circled charges per drawing')
    if scaffold_smiles is not None:
        from .alignment import validate_scaffold_inputs
        validate_scaffold_inputs([r['canonical_smiles'] for r in records],scaffold_smiles)
    if columns is not None and (type(columns) is not int or not 1<=columns<=len(records)):
        raise ValueError('Columns must be an integer from 1 through structure count')
    if groups is not None and charge_style=='plain':
        from .scope_table import draw_scope_table
        return draw_scope_table(bridge,structures,output_dir,groups=groups,preset=preset,
            columns=columns,pixels=pixels,scaffold_smiles=scaffold_smiles,layout=layout,
            frame=frame,separators=separators)
    audit={'status':'in_progress','checks':{},'visual_review':'required','renderer':'native ChemDraw',
           'coordinate_seed':'RDKit MOL writer; native Clean Up Structure runs on each new private import',
           'limitations':'Labels are caller supplied, not name-verified. No common-scaffold alignment, experimental yields or comprehensive intramolecular collision checks.'}
    owned=[];texts=[]
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents)
        content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline['documents']}
        out.mkdir();seeds=out/'seeds';seeds.mkdir()
        _write_json(out/'request.json',{'schema_version':1,'structures':structures,'preset':preset,'columns':columns,'pixels':pixels,'scaffold_smiles':scaffold_smiles,'layout':layout,'charge_style':charge_style,'groups':groups,'frame':frame,'separators':separators,'scaffold_layout':scaffold_layout})
        _write_json(out/'audit.json',audit)
        try:
            for i,item in enumerate(records):
                molblock=item['molblock']
                constrained=scaffold_layout=='reference' and i>0
                if constrained:
                    from .scaffold_seed import seed_from_native_scaffold
                    molblock,seed_audit=seed_from_native_scaffold(item['canonical_smiles'],texts[0],scaffold_smiles)
                    audit.setdefault('reference_seeds',[]).append({'compound_id':item['compound_id'],**seed_audit})
                seed=seeds/f'{item["compound_id"]}.mol';seed.write_text(molblock)
                imported=_native(bridge.import_file,str(seed));did=imported['document']['document_id'];owned.append(did)
                initial=seeds/f'{item["compound_id"]}-imported.cdxml'
                _native(bridge.export,did,str(initial),'cdxml')
                if chemical_signature(initial.read_text())!=[item['canonical_smiles']]:raise ValueError('Native MOL import changed requested identity')
                if not constrained:_native(bridge.clean,did)
                native=seeds/f'{item["compound_id"]}-clean.cdxml';_native(bridge.export,did,str(native),'cdxml')
                if chemical_signature(native.read_text())!=[item['canonical_smiles']]:raise ValueError('Native cleanup changed requested identity')
                texts.append(native.read_text())
                _native(bridge.close,did);owned.remove(did)
            if scaffold_smiles is not None:
                from .alignment import align_native_structures
                normalized=[normalize_cdxml(text,preset)[0] for text in texts]
                texts,alignment=align_native_structures(normalized,scaffold_smiles)
                audit['alignment']=alignment
                audit['limitations']='Explicit scaffold rigid alignment, not inferred correspondence outside that scaffold. Caller-supplied labels, no experimental yields or comprehensive intramolecular collision certification.'
            combined,cells=combine_native_structures(texts,records,preset)
            (out/'combined.cdxml').write_text(combined)
            created=_native(bridge.create,combined);did=created['document']['document_id'];owned.append(did)
            snap=out/'combined-native.cdxml';_native(bridge.export,did,str(snap),'cdxml')
            mapping,_=verify_molecules(combined,snap.read_text())
            from .styles import verify_custom_style
            verify_custom_style(combined,snap.read_text(),preset)
            result=grid_document(bridge,did,str(out/'figure'),remap_cells(cells,mapping),source_token(snap.read_text()),
                                 preset=preset,columns=columns,pixels=pixels,**layout)
            final_id=result['document']['document_id'];owned.append(final_id)
            final_folder='figure';grid_audit=result['audit']
            if charge_style=='circled':
                from .symbols import symbols_document
                from .ownership import _page_fit
                from .annotations import _root as annotation_root
                native=(out/'figure/figure.cdxml').read_text()
                requests=charge_requests(native)
                audit['charge_style']={'mode':'circled','requested_count':len(requests)}
                if requests:
                    charged=symbols_document(bridge,final_id,str(out/'charged'),requests,source_token(native),pixels=pixels)
                    charged_id=charged['document']['document_id'];owned.append(charged_id)
                    _page_fit(annotation_root((out/'charged/figure.cdxml').read_text()))
                    audit['charge_style']['audit']=charged['audit']
                    _native(bridge.close,final_id);owned.remove(final_id)
                    result=charged;final_id=charged_id;final_folder='charged'
                audit['checks']['final_charge_style_and_page_fit']=True
            _native(bridge.close,did);owned.remove(did)
            if groups is not None:
                from .grouped_draw import group_drawn_structures
                native=(out/final_folder/'figure.cdxml').read_text()
                grouped=group_drawn_structures(bridge,final_id,native,grid_audit['verification']['cells'],groups,
                    str(out/'grouped'),grid_audit['layout']['columns'],
                    {'margin':grid_audit['layout']['margin'],**layout},frame,separators,pixels)
                grouped_id=grouped['document']['document_id'];owned.append(grouped_id)
                _native(bridge.close,final_id);owned.remove(final_id)
                result=grouped;final_id=grouped_id;final_folder='grouped/figure'
                audit['grouping']={'groups':groups,'plan':grouped['group_plan'],
                    'verification':grouped['group_verification'],'decoration_audit':grouped['audit']}
                audit['checks']['grouped_bands_and_native_decoration']=True
            observed=_native(bridge.documents)['documents']
            if [d for d in observed if d['document_id']!=final_id]!=baseline['documents']:
                raise ValueError('Pre-existing document inventory changed')
            for oid,original in content.items():
                if _document_content(bridge,oid)!=original:raise ValueError('Pre-existing document content changed')
            audit.update(status='checks_passed',structures=[{k:v for k,v in item.items() if k!='molblock'} for item in records],
                         grid_audit=grid_audit,final_artifacts={fmt:str(out/final_folder/f'figure.{fmt}') for fmt in ('cdxml','svg','png')})
            audit['checks'].update(native_import_identity=True,native_cleanup_identity=True,
                                   final_grid_checks=True,preexisting_documents_unchanged=True)
            if scaffold_layout=='reference':
                audit['coordinate_seed']='First structure: native cleanup. Remaining structures: MOL seeds constrained to that native core, without subsequent cleanup.'
                audit['native_cleanup_count']=1
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Native structures</title><style>body{font:16px system-ui;margin:32px;background:#f2f4f5}figure{background:white;padding:24px}img{max-width:100%;max-height:85vh}a{color:#17617c}</style><h1>Native ChemDraw structures</h1><p>Explicit input graphs, native import and cleanup, measured grid. Names are caller-supplied. Visual review required.</p><figure><img src="figure/figure.png" alt="Native chemical structures"></figure><p><a href="figure/figure.cdxml">Editable ChemDraw</a> · <a href="figure/figure.svg">SVG</a> · <a href="figure/figure.png">PNG</a> · <a href="audit.json">Audit</a> · <a href="request.json">Request</a></p></html>''')
            if final_folder!='figure':
                review=out/'review.html';review.write_text(review.read_text().replace('figure/figure.',final_folder+'/figure.'))
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit,'artifacts':audit['final_artifacts']}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned,
                         recovery='No retries or automatic closes after native uncertainty. Inspect retained copies and backups.')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit);raise
            _write_json(out/'audit.json',audit);raise
