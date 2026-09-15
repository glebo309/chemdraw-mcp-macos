"""Explicit, bounded analogue edits on a copied native molecular drawing.

No coordinate generator, name resolver, implicit caption ownership or new stereo.
"""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import html
import json
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from .polish import supported_root, chemical_signature, numbers
from .workflow import content_fingerprint, _file_hash, _write_json
from .native_lock import native_transaction

ELEMENTS = {'C':6, 'N':7, 'O':8, 'F':9, 'P':15, 'S':16, 'Cl':17, 'Br':35, 'I':53}


def _root(text):
    root = supported_root(text)
    page = root.find('page')
    if len(page.findall('fragment')) != 1 or any(e.tag not in ('fragment','t') for e in page):
        raise ValueError('Editing requires one molecule and optional captions, not a reaction or multiple fragments')
    fragment = page.find('fragment')
    if any(e.tag not in ('n','b') for e in fragment):
        raise ValueError('Unsupported molecular annotation in editor')
    for n in fragment.findall('n'):
        if any(e.tag != 't' for e in n) or len(n.findall('t')) > 1:
            raise ValueError('Unsupported atom annotation in editor')
    if any(not b.get('id') for b in fragment.findall('b')):
        raise ValueError('Editing requires explicit bond IDs')
    points = [numbers(n.get('p'),2) for n in fragment.findall('n')]
    if any(math.dist(a,b)<.1 for i,a in enumerate(points) for b in points[i+1:]):
        raise ValueError('Ambiguous coincident atom coordinates')
    if any(not t.get('id') for t in page.findall('t')):
        raise ValueError('Each caption requires an ID')
    return root


def source_token(text):
    return hashlib.sha256(repr(content_fingerprint(text)).encode()).hexdigest()


def _decoded(text):
    """Associate decoded atoms by unique geometry, not parser iteration order."""
    from rdkit import Chem
    chemical_signature(text)
    root = _root(text)
    for e in root.iter():
        e.attrib.pop('AS',None)
        e.attrib.pop('BondOrdering',None)
    mols = Chem.MolsFromCDXML(ET.tostring(root,encoding='unicode'),removeHs=False)
    mol = mols[0]
    if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
        raise ValueError('Unsupported radical or incomplete valence')
    nodes = root.find('page/fragment').findall('n')
    positions = [(float(p.x),float(p.y)) for p in
                 [mol.GetConformer().GetAtomPosition(i) for i in range(mol.GetNumAtoms())]]
    original = [numbers(n.get('p'),2) for n in nodes]
    # RDKit scales and flips the CDXML y axis. Infer scale/offset instead of
    # depending on a specific parser's unit factor or XML atom ordering.
    span = max(max(p[k] for p in original)-min(p[k] for p in original) for k in (0,1))
    native_span = max(max(p[k] for p in positions)-min(p[k] for p in positions) for k in (0,1))
    scale = native_span/span if span else 1.
    mean = tuple(sum(p[k] for p in original)/len(original) for k in (0,1))
    centre = tuple(sum(p[k] for p in positions)/len(positions) for k in (0,1))
    mapped = {}
    for n,(x,y) in zip(nodes,original):
        expected = (centre[0]+(x-mean[0])*scale,centre[1]-(y-mean[1])*scale)
        hits = [i for i,p in enumerate(positions) if math.dist(p,expected)<1e-4]
        if len(hits)!=1 or hits[0] in mapped.values():
            raise ValueError('Cannot uniquely associate decoded atoms with CDXML coordinates')
        atom=mol.GetAtomWithIdx(hits[0])
        if atom.GetAtomicNum()!=int(n.get('Element','6')):
            raise ValueError('Decoded atom identity differs from CDXML')
        mapped[n.get('id')]=hits[0]
    return mol,mapped


def inspect_editable(text):
    from rdkit import Chem
    root = _root(text)
    mol,mapping = _decoded(text)
    fragment = root.find('page/fragment')
    atoms=[]
    for n in fragment.findall('n'):
        a=mol.GetAtomWithIdx(mapping[n.get('id')])
        atoms.append({'id':n.get('id'),'element':a.GetSymbol(),
                      'position_pt':list(numbers(n.get('p'),2)),
                      'charge':a.GetFormalCharge(),'isotope':a.GetIsotope(),
                      'hydrogens':a.GetTotalNumHs(),
                      'stereo':str(a.GetChiralTag()),
                      'label':''.join(n.itertext()).strip()})
    return {'source_token':source_token(text),'fragment_id':fragment.get('id'),
            'atoms':atoms,'bonds':[{'id':b.get('id'),'begin':b.get('B'),'end':b.get('E'),
                                   'order':b.get('Order','1'),'display':b.get('Display','Solid')}
                                  for b in fragment.findall('b')],
            'captions':[{'id':t.get('id'),'text':''.join(t.itertext()).strip()}
                        for t in root.find('page').findall('t')],
            'smiles':chemical_signature(text)}


def _label(root, node):
    """Replace chemical text, retaining font settings; ChemDraw measures ink."""
    old=node.find('t');style={}
    if old is not None and old.find('s') is not None:style=dict(old.find('s').attrib)
    for t in node.findall('t'):node.remove(t)
    element=int(node.get('Element','6'))
    if element==6:return  # skeletal carbon; explicit H atoms remain separate
    symbol=next(k for k,v in ELEMENTS.items() if v==element)
    h=int(node.get('NumHydrogens','0'))
    label=symbol+('H' if h else '')+(str(h) if h>1 else '')
    t=ET.SubElement(node,'t',{'p':node.get('p')})
    style.setdefault('font',root.get('LabelFont','3'))
    style.setdefault('size',root.get('LabelSize','10'))
    style['face']='96'
    ET.SubElement(t,'s',style).text=label


def _tetra(mol,mapping):
    reverse={index:aid for aid,index in mapping.items()}
    result={}
    for a in mol.GetAtoms():
        tag=str(a.GetChiralTag())
        if tag=='CHI_UNSPECIFIED':continue
        if tag not in ('CHI_TETRAHEDRAL_CW','CHI_TETRAHEDRAL_CCW'):
            raise ValueError('Unsupported non-tetrahedral stereo')
        neighbours=[reverse[n.GetIdx()] for n in a.GetNeighbors()]
        parity=sum(x>y for i,x in enumerate(neighbours) for y in neighbours[i+1:])%2
        result[reverse[a.GetIdx()]]=(tag=='CHI_TETRAHEDRAL_CW') ^ bool(parity)
    return result


def _stereo_bonds(mol,mapping):
    from rdkit import Chem
    reverse={index:aid for aid,index in mapping.items()}
    result=set()
    for info in Chem.FindPotentialStereo(mol):
        if str(info.type)=='Bond_Double':
            bond=mol.GetBondWithIdx(info.centeredOn)
            result.add(frozenset((reverse[bond.GetBeginAtomIdx()],reverse[bond.GetEndAtomIdx()])))
    return result


def _potential_tetra(mol,mapping):
    from rdkit import Chem
    reverse={index:aid for aid,index in mapping.items()}
    return {reverse[info.centeredOn] for info in Chem.FindPotentialStereo(mol)
            if str(info.type)=='Atom_Tetrahedral'}


def plan_edit(text, operations, captions):
    root=_root(text);before,mapping=_decoded(text)
    if not isinstance(operations,list) or not 1<=len(operations)<=50:
        raise ValueError('Supply 1 to 50 explicit atom/bond operations')
    page=root.find('page');fragment=page.find('fragment')
    nodes={n.get('id'):n for n in fragment.findall('n')}
    bonds={b.get('id'):b for b in fragment.findall('b')}
    texts={t.get('id'):t for t in page.findall('t')}
    if not isinstance(captions,dict) or set(captions)!=set(texts):
        raise ValueError('Every caption requires explicit replacement, retention or removal')
    changed=set();atom_changes=[];bond_changes=[];h_decisions=set()
    for op in operations:
        if not isinstance(op,dict):raise ValueError('Each operation must be an object')
        kind=op.get('kind');oid=op.get('id')
        if not isinstance(oid,str) or oid in changed:raise ValueError('Duplicate or invalid edit ID')
        changed.add(oid)
        if kind=='atom':
            if set(op)-{'kind','id','element','hydrogens'} or oid not in nodes:
                raise ValueError('Unknown atom edit field or atom ID')
            n=nodes[oid];old_element=int(n.get('Element','6'))
            if n.get('Isotope') or int(n.get('Charge','0')) or old_element not in ELEMENTS.values():
                raise ValueError('Editing charged, isotopic or unsupported elements is not supported')
            if 'hydrogens' not in op or type(op['hydrogens']) is not int or not 0<=op['hydrogens']<=4:
                raise ValueError('Atom edits require explicit hydrogens (integer 0 to 4)')
            symbol=op.get('element',next(k for k,v in ELEMENTS.items() if v==old_element))
            if symbol not in ELEMENTS:raise ValueError('Unsupported target element')
            if str(before.GetAtomWithIdx(mapping[oid]).GetChiralTag())!='CHI_UNSPECIFIED':
                raise ValueError('Editing a stereocentre is not supported')
            old_h=before.GetAtomWithIdx(mapping[oid]).GetTotalNumHs()
            if ELEMENTS[symbol]==old_element and op['hydrogens']==old_h:
                raise ValueError('No-op atom edit')
            atom_changes.append({'id':oid,'before':{'element':old_element,'hydrogens':old_h},
                                 'after':{'element':ELEMENTS[symbol],'hydrogens':op['hydrogens']}})
            n.set('Element',str(ELEMENTS[symbol]));n.set('NumHydrogens',str(op['hydrogens']))
            h_decisions.add(oid);_label(root,n)
        elif kind=='bond':
            if set(op)!={'kind','id','order'} or oid not in bonds or type(op['order']) is not int or op['order'] not in (1,2,3):
                raise ValueError('Bond edit requires existing ID and integer order 1, 2 or 3')
            b=bonds[oid]
            if b.get('Display','Solid')!='Solid' or b.get('Display2','Solid')!='Solid':
                raise ValueError('Cannot change a stereo or special-display bond')
            parsed=before.GetBondBetweenAtoms(mapping[b.get('B')],mapping[b.get('E')])
            if parsed.GetIsAromatic() or str(parsed.GetStereo())!='STEREONONE':
                raise ValueError('Editing aromatic or stereo bonds is unsupported')
            if b.get('Order','1')==str(op['order']):raise ValueError('No-op bond edit')
            bond_changes.append({'id':oid,'begin':b.get('B'),'end':b.get('E'),
                                 'before':b.get('Order','1'),'after':str(op['order'])})
            b.set('Order',str(op['order']))
        else:raise ValueError('Unknown operation kind')
    old_nodes={n.get('id'):n for n in _root(text).findall('.//n')}
    for change in bond_changes:
        for aid in (change['begin'],change['end']):
            if old_nodes[aid].get('NumHydrogens') is not None and aid not in h_decisions:
                raise ValueError('Bond endpoints with explicit hydrogen counts require an atom hydrogen edit')
    for tid,value in captions.items():
        t=texts[tid]
        if value is None:page.remove(t);continue
        if not isinstance(value,str) or not value.strip() or len(value)>500 or any(ord(c)<32 for c in value):
            raise ValueError('Invalid caption text; use null to remove')
        runs=t.findall('s')
        if not runs:raise ValueError('Unsupported caption without text runs')
        style=dict(runs[0].attrib)
        for child in list(t):t.remove(child)
        ET.SubElement(t,'s',style).text=value
        t.attrib.pop('BoundingBox',None)
    # Cached labels must not override re-evaluation of the modified graph.
    for n in nodes.values():n.attrib.pop('AS',None)
    planned=ET.tostring(root,encoding='unicode')
    after,after_map=_decoded(planned)
    if _tetra(before,mapping)!=_tetra(after,after_map):
        raise ValueError('Edit changes or removes tetrahedral stereo; unsupported')
    if _potential_tetra(before,mapping)!=_potential_tetra(after,after_map):
        raise ValueError('Edit creates or removes potential tetrahedral stereo; unsupported')
    if _stereo_bonds(after,after_map)!=_stereo_bonds(before,mapping):
        raise ValueError('Edit creates or removes potential alkene stereo; explicit stereo editing is not supported')
    # Do not let inherited implicit-H counts mask unintended valence changes.
    for aid in h_decisions:
        a=after.GetAtomWithIdx(after_map[aid])
        if a.GetTotalNumHs()!=int(nodes[aid].get('NumHydrogens')):
            raise ValueError('Decoded hydrogen count differs from requested edit')
    hydrogen_changes=[]
    for aid in mapping:
        old_h=before.GetAtomWithIdx(mapping[aid]).GetTotalNumHs()
        new_h=after.GetAtomWithIdx(after_map[aid]).GetTotalNumHs()
        if old_h!=new_h:hydrogen_changes.append({'id':aid,'before':old_h,'after':new_h})
    return planned,{'before_smiles':chemical_signature(text),'after_smiles':chemical_signature(planned),
                    'atom_changes':atom_changes,'bond_changes':bond_changes,
                    'observed_hydrogen_changes':hydrogen_changes,
                    'caption_changes':captions,'coordinate_changes':0,
                    'stereo':'mapped tetrahedral configuration retained; no new alkene stereo'}


def atom_mapping(before,after):
    old=_root(before).find('page/fragment');new=_root(after).find('page/fragment')
    if len(old.findall('n'))!=len(new.findall('n')):raise ValueError('Native atom count changed')
    result={};distances=[]
    for n in old.findall('n'):
        hits=[m for m in new.findall('n') if math.dist(numbers(n.get('p'),2),numbers(m.get('p'),2))<.03]
        if len(hits)!=1 or hits[0].get('id') in result.values():
            raise ValueError('Native atom coordinates changed or mapping is ambiguous')
        m=hits[0];result[n.get('id')]=m.get('id')
        distances.append(math.dist(numbers(n.get('p'),2),numbers(m.get('p'),2)))
    return result,max(distances,default=0.)


def _mapped_smiles(text,ids):
    from rdkit import Chem
    mol,mapping=_decoded(text)
    for aid,index in mapping.items():mol.GetAtomWithIdx(index).SetAtomMapNum(ids[aid])
    return Chem.MolToSmiles(mol,isomericSmiles=True)


def verify_native_edit(planned,native):
    mapping,displacement=atom_mapping(planned,native)
    ids={aid:i+1 for i,aid in enumerate(sorted(mapping))}
    if _mapped_smiles(planned,ids)!=_mapped_smiles(native,{mapping[k]:v for k,v in ids.items()}):
        raise ValueError('Native mapped chemistry or stereo differs from requested edit')
    p=_root(planned);n=_root(native)
    # Rendered atom text is independent of Element in CDXML. Compare formula
    # tokens (NH2 and H2N agree, N2H does not), not just graph parsing.
    for old in p.findall('.//n'):
        new=n.find(f'.//n[@id="{mapping[old.get("id")]}\"]')
        def label(node):
            value=''.join(node.itertext()).replace(' ','').strip()
            tokens=re.findall(r'[A-Z][a-z]?\d*',value)
            return sorted(tokens) if ''.join(tokens)==value else value
        if label(old)!=label(new):raise ValueError('Native atom label differs from planned chemical label')
    if sorted(''.join(t.itertext()).strip() for t in p.find('page').findall('t')) != sorted(''.join(t.itertext()).strip() for t in n.find('page').findall('t')):
        raise ValueError('Native captions differ from requested text')
    return {'atom_id_map':mapping,'maximum_displacement_pt':displacement,
            'mapped_chemistry_verified':True,'native_labels_verified':True}


@native_transaction
def edit_file(bridge,path,output_dir,operations,captions,expected_source_token=None,pixels=2400):
    """Validate original CDXML before native import; remap explicit recipe IDs."""
    path=Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower()!='.cdxml':raise ValueError('Edit file input requires CDXML')
    source=path.read_text()
    if expected_source_token is not None and expected_source_token!=source_token(source):
        raise ValueError('File source snapshot is stale')
    plan_edit(source,operations,captions)
    imported=bridge.import_file(str(path));did=imported['document']['document_id']
    try:
        snap=bridge._new_path('.cdxml','backups');bridge.export(did,str(snap),'cdxml')
        native=snap.read_text();mapping=verify_native_edit(source,native)['atom_id_map']
        old=_root(source);new=_root(native)
        for b in old.findall('.//b'):
            hits=[c for c in new.findall('.//b') if {c.get('B'),c.get('E')}=={mapping[b.get('B')],mapping[b.get('E')]}]
            if len(hits)!=1:raise ValueError('Ambiguous native bond ID mapping')
            mapping[b.get('id')]=hits[0].get('id')
        for t in old.find('page').findall('t'):
            hits=[u for u in new.find('page').findall('t') if ''.join(u.itertext()).strip()==''.join(t.itertext()).strip()
                  and math.dist(numbers(u.get('p'),2),numbers(t.get('p'),2))<.03]
            if len(hits)!=1:raise ValueError('Ambiguous native caption ID mapping')
            mapping[t.get('id')]=hits[0].get('id')
        ops=[{**op,'id':mapping[op['id']]} for op in operations]
        renamed={mapping[tid]:value for tid,value in captions.items()}
        return edit_document(bridge,did,output_dir,ops,renamed,source_token(native),pixels)
    finally:bridge.close(did)


def edit_document(bridge,document_id,output_dir,operations,captions,expected_source_token,pixels=2400):
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output directory already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 to 8192')
    created=None;audit={'status':'in_progress','visual_review':'required','checks':{}}
    with getattr(bridge,'lock',nullcontext()):
        baseline=bridge.inspect(document_id)['document'];file_hash=_file_hash(baseline)
        snap=bridge._new_path('.cdxml','backups');bridge.export(document_id,str(snap),'cdxml')
        source=snap.read_text()
        if source_token(source)!=expected_source_token:raise ValueError('Source snapshot is stale; inspect again before editing')
        planned,diff=plan_edit(source,operations,captions)
        out.mkdir()
        try:
            (out/'before.cdxml').write_text(source)
            _write_json(out/'recipe.json',{'schema_version':1,'operations':operations,'captions':captions,
                                         'expected_source_token':expected_source_token,'pixels':pixels})
            for fmt in ('svg','png'):bridge.export(document_id,str(out/f'before.{fmt}'),fmt,pixels)
            # Recheck immediately before creating the native working copy.
            check=bridge._new_path('.cdxml','backups');bridge.export(document_id,str(check),'cdxml')
            if source_token(check.read_text())!=expected_source_token:raise ValueError('Source became stale before native creation')
            result=bridge.create(planned);created=result['document']['document_id']
            for fmt in ('cdxml','svg','png'):bridge.export(created,str(out/f'figure.{fmt}'),fmt,pixels)
            verified=verify_native_edit(planned,(out/'figure.cdxml').read_text())
            check=bridge._new_path('.cdxml','backups');bridge.export(document_id,str(check),'cdxml')
            if (bridge.inspect(document_id)['document']!=baseline or _file_hash(baseline)!=file_hash
                    or source_token(check.read_text())!=expected_source_token):
                raise RuntimeError('Source document changed during editing; inspect recovery snapshots')
            audit.update(status='checks_passed',chemical_diff=diff,native_verification=verified,
                         source_document=baseline,renderer='native ChemDraw',
                         limitation='One molecule; explicit neutral element/H and plain bond-order edits only. No new stereo, naming, collision repair or automatic cleanup.')
            audit['checks'].update(source_document_unchanged=True,mapped_product_chemistry_verified=True,
                                   scaffold_coordinates_preserved=True,native_labels_verified=True)
            _write_json(out/'audit.json',audit)
            changes=html.escape(json.dumps(diff,indent=2,ensure_ascii=False))
            (out/'review.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ChemDraw analogue review</title>
<style>body{{font:16px system-ui;margin:32px;background:#f2f4f5;color:#182326}}main{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}figure{{margin:0;padding:24px;background:white}}img{{width:100%;height:340px;object-fit:contain}}pre{{white-space:pre-wrap}}@media(max-width:700px){{main{{grid-template-columns:1fr}}}}</style>
<h1>ChemDraw analogue review</h1><p>Source retained. Requested chemical changes and native atom coordinates verified. Visual review required.</p>
<main><figure><figcaption>Original</figcaption><img src="before.png" alt="Original molecule"></figure><figure><figcaption>Edited copy</figcaption><img src="figure.png" alt="Edited molecule"></figure></main>
<p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="figure.svg">SVG</a> · <a href="figure.png">PNG</a> · <a href="recipe.json">Recipe</a> · <a href="audit.json">Audit</a></p><h2>Explicit chemical diff</h2><pre>{changes}</pre></html>''')
            return {'document':result['document'],'review':str(out/'review.html'),'output_dir':str(out),'audit':audit}
        except Exception as exc:
            audit.update(status='failed',error=str(exc));_write_json(out/'audit.json',audit)
            if created is not None:
                try:bridge.close(created)
                except Exception:pass
            raise
