"""Explicit coordination drawings, without inferred chemistry or geometry.

This is deliberately separate from the organic SMILES/RDKit validator. The
contract is preservation of supplied records, not chemical plausibility.
"""
from contextlib import nullcontext
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .core import validate_cdxml, style_cdxml, preset_settings
from .batch import _native, _document_content, NativeUncertain
from .workflow import _write_json

METALS = {'Mg':12, 'Al':13, 'Ca':20, 'Cr':24, 'Mn':25, 'Fe':26,
          'Co':27, 'Ni':28, 'Cu':29, 'Zn':30, 'Ru':44, 'Rh':45,
          'Pd':46, 'Ag':47, 'Ir':77, 'Pt':78, 'Au':79}
ELEMENTS = {'H':1, 'B':5, 'C':6, 'N':7, 'O':8, 'F':9, 'Si':14,
            'P':15, 'S':16, 'Cl':17, 'Br':35, 'I':53, **METALS}


def _position(value, count=3):
    if isinstance(value, str):
        try: value = [float(v) for v in value.split()]
        except ValueError: raise ValueError('Invalid coordinates') from None
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError('Supply three explicit point coordinates per atom')
    if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v)>10000 for v in value):
        raise ValueError('Coordinates must be finite bounded numbers')
    return tuple(value)


def plan_complex(recipe, preset='house'):
    preset_settings(preset)
    spatial = isinstance(recipe,dict) and type(recipe.get('schema_version')) is int and recipe['schema_version']==2
    fields = {'schema_version','label','atoms','bonds'} | ({'attachments','overall_charge'} if spatial else set())
    if not isinstance(recipe, dict) or set(recipe) != fields:
        raise ValueError('Complex recipe requires schema_version, label, atoms and bonds only')
    if type(recipe['schema_version']) is not int or recipe['schema_version'] not in (1,2):
        raise ValueError('Unsupported complex schema')
    label = recipe['label']
    if not isinstance(label, str) or not label.strip() or len(label)>100 or any(ord(c)<32 for c in label):
        raise ValueError('Supply a single-line caption up to 100 characters')
    atoms, bonds = recipe['atoms'], recipe['bonds']
    if not isinstance(atoms, list) or not 2<=len(atoms)<=80 or not isinstance(bonds, list) or not 1<=len(bonds)<=120:
        raise ValueError('Supply 2..80 atoms and 1..120 bonds')
    lookup = {}; positions = []
    for atom in atoms:
        required = {'id','element','charge','hydrogens','position'}
        if not isinstance(atom, dict) or not required<=set(atom) or set(atom)-required-({'color'} if spatial else set()):
            raise ValueError('Each atom needs id, element, charge, hydrogens and position')
        if 'color' in atom and (not isinstance(atom['color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',atom['color'])):
            raise ValueError('Atom color must be an explicit #RRGGBB value')
        key = atom['id']
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', key) or key in lookup:
            raise ValueError('Atom IDs must be unique safe identifiers')
        if not isinstance(atom['element'], str) or atom['element'] not in ELEMENTS:
            raise ValueError('Unsupported explicit element')
        if type(atom['charge']) is not int or not -4<=atom['charge']<=4 or type(atom['hydrogens']) is not int or not 0<=atom['hydrogens']<=4:
            raise ValueError('Supply bounded integer formal charges and hydrogen counts')
        position = _position(atom['position'])
        if not 40<=position[0]<=540 or not 40<=position[1]<=650:
            raise ValueError('Supplied projection must fit inside the page margins')
        if any(math.dist(position[:2], p[:2])<12 for p in positions):
            raise ValueError('Projected atom positions overlap or are too close')
        lookup[key] = atom; positions.append(position)
    attachments = recipe['attachments'] if spatial else []
    charge = recipe['overall_charge'] if spatial else None
    if charge is not None and (type(charge) is not int or not 1<=abs(charge)<=8):
        raise ValueError('Overall charge is null or a nonzero integer from -8 to 8')
    if not isinstance(attachments,list) or len(attachments)>8:
        raise ValueError('Supply at most eight multicentre attachments')
    atom_ids=set(lookup)
    for attachment in attachments:
        if not isinstance(attachment,dict) or not {'id','position','atoms'}<=set(attachment) or set(attachment)-{'id','position','atoms','ellipse'}:
            raise ValueError('Attachments require id, position and atoms only; distributed charges are unsupported')
        key=attachment['id']; members=attachment['atoms']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}',key) or key in lookup:
            raise ValueError('Attachment IDs must be unique safe identifiers')
        if not isinstance(members,list) or not 2<=len(members)<=12 or any(not isinstance(m,str) or m not in atom_ids for m in members) or len(set(members))!=len(members):
            raise ValueError('Attachment members must identify distinct supplied atoms')
        p=_position(attachment['position'])
        if 'ellipse' in attachment:
            size=_position(attachment['ellipse'],2)
            if any(not 2<=v<=80 for v in size): raise ValueError('Ring ellipse dimensions must be 2..80 points')
        if not 40<=p[0]<=540 or not 40<=p[1]<=650 or any(math.dist(p[:2],q[:2])<2 for q in positions):
            raise ValueError('Attachment projection is outside the page or coincides with a node')
        lookup[key]=attachment; positions.append(p)
    adjacency = {key:set() for key in lookup}; pairs=set(); dative=0
    for attachment in attachments:
        for member in attachment['atoms']:
            adjacency[attachment['id']].add(member); adjacency[member].add(attachment['id'])
    for bond in bonds:
        if not isinstance(bond, dict) or set(bond) != {'begin','end','order'}|({'display'} if spatial else set()):
            raise ValueError('Bonds require begin, end and order only')
        b,e,order = bond['begin'],bond['end'],bond['order']
        if not isinstance(b,str) or not isinstance(e,str) or b not in lookup or e not in lookup or b==e:
            raise ValueError('Bond endpoints must identify two supplied atoms')
        if not isinstance(order,str) or order not in (('1','1.5','2','3','dative','coordination','haptic') if spatial else ('1','2','3','dative')):
            raise ValueError('Supported orders: 1, 2, 3, dative')
        display=bond.get('display','Solid')
        aromatic_perspective=order=='1.5' and any(b in a['atoms'] and e in a['atoms'] for a in attachments)
        allowed_displays=('Solid','WedgeBegin','WedgeEnd','Bold') if aromatic_perspective else ('Solid','WedgeEnd','WedgedHashEnd') if order=='coordination' else ('Solid',)
        if display not in allowed_displays:
            raise ValueError('Front/back displays are supported only on explicit coordination bonds')
        if frozenset((b,e)) in pairs: raise ValueError('Duplicate bond')
        pairs.add(frozenset((b,e))); adjacency[b].add(e); adjacency[e].add(b)
        if order in ('dative','coordination'):
            if lookup[b].get('element') not in ('N','O','P','S','F','Cl','Br','I') or lookup[e].get('element') not in METALS:
                raise ValueError('Dative bonds require an explicit donor begin and metal end')
            dative += 1
        elif order=='haptic':
            if b in atom_ids or lookup[e].get('element') not in METALS or display!='Solid':
                raise ValueError('Haptic bonds require a multicentre begin and metal end, displayed Solid')
            dative += 1
        elif b not in atom_ids or e not in atom_ids or lookup[b]['element'] in METALS or lookup[e]['element'] in METALS:
            raise ValueError('Metal bonds must be explicitly dative in this first slice')
    reached=set(); pending=[next(iter(lookup))]
    while pending:
        key=pending.pop()
        if key not in reached: reached.add(key); pending.extend(adjacency[key]-reached)
    if reached!=set(lookup) or not dative:
        raise ValueError('Supply one connected complex with at least one dative bond')
    root=ET.Element('CDXML'); page=ET.SubElement(root,'page',{'id':'1','BoundingBox':'0 0 600 750'})
    fragment=ET.SubElement(page,'fragment',{'id':'2'}); mapping={}
    for index,atom in enumerate(atoms,3):
        mapping[atom['id']]=str(index)
        p=atom['position']; element=atom['element']; h=atom['hydrogens']; charge=atom['charge']
        node=ET.SubElement(fragment,'n',{'id':str(index),'p':f'{p[0]} {p[1]}',
            'xyz':' '.join(map(str,p)), 'Element':str(ELEMENTS[element]),
            'Charge':str(charge),'NumHydrogens':str(h)})
        if spatial and element=='C' and charge==0:
            orders=[bond['order'] for bond in bonds if atom['id'] in (bond['begin'],bond['end'])]
            if all(o in ('1','1.5','2','3') for o in orders) and 4-sum(map(float,orders))==h:
                node.attrib.pop('NumHydrogens')
            continue
        t=ET.SubElement(node,'t',{'p':f'{p[0]} {p[1]}','LabelJustification':'Auto','LabelAlignment':'Auto'})
        labeltext=element+('H'+(str(h) if h>1 else '') if h else '')
        ET.SubElement(t,'s',{'face':'96'}).text=labeltext
        if charge:
            ET.SubElement(t,'s',{'face':'64'}).text=(str(abs(charge)) if abs(charge)>1 else '')+('+' if charge>0 else '-')
    next_id=3+len(atoms)
    for attachment in attachments:
        p=attachment['position']; mapping[attachment['id']]=str(next_id)
        ET.SubElement(fragment,'n',{'id':str(next_id),'NodeType':'MultiAttachment',
            'p':f'{p[0]} {p[1]}','xyz':' '.join(map(str,p)),
            'Attachments':' '.join(mapping[m] for m in attachment['atoms'])})
        next_id+=1
    for index,bond in enumerate(bonds,next_id):
        ET.SubElement(fragment,'b',{'id':str(index),'Z':str(index),'B':mapping[bond['begin']],
            'E':mapping[bond['end']],'Order':'1' if bond['order'] in ('coordination','haptic') else bond['order'],
            'Display':bond.get('display','Solid')})
    t=ET.SubElement(page,'t',{'id':str(next_id+len(bonds)),
        'p':f'{sum(p[0] for p in positions)/len(positions)} {max(p[1] for p in positions)+35}',
        'Justification':'Center'})
    ET.SubElement(t,'s').text=label
    gid=next_id+len(bonds)+1
    for attachment in attachments:
        if 'ellipse' not in attachment: continue
        x,y,_=attachment['position']; w,h=attachment['ellipse']
        ET.SubElement(page,'graphic',{'id':str(gid),'GraphicType':'Oval','OvalType':'Circle',
            'BoundingBox':f'{x-w/2} {y-h/2} {x+w/2} {y+h/2}'})
        gid+=1
    charge=recipe['overall_charge'] if spatial else None
    if charge is not None:
        x=max(p[0] for p in positions)+24; y=min(p[1] for p in positions)-24
        # Two native lines form the conventional top-right charge corner.
        # It is an annotation, not an unmatched polymer bracket.
        ET.SubElement(page,'graphic',{'id':str(gid),'GraphicType':'Line',
            'BoundingBox':f'{x-16} {y} {x} {y}'})
        ET.SubElement(page,'graphic',{'id':str(gid+1),'GraphicType':'Line',
            'BoundingBox':f'{x} {y} {x} {y+16}'})
        t=ET.SubElement(page,'t',{'id':str(gid+2),'p':f'{x+5} {y+4}'})
        ET.SubElement(t,'s').text=(str(abs(charge)) if abs(charge)>1 else '')+('+' if charge>0 else '-')
    text=style_cdxml(ET.tostring(root,encoding='unicode'),preset)
    styled=ET.fromstring(text)
    palette=ET.SubElement(styled,'colortable') if any('color' in a for a in atoms) else None
    colours={}
    for atom in atoms:
        if 'color' not in atom: continue
        value=atom['color'].upper()
        if value not in colours:
            colours[value]=str(2+len(colours))
            ET.SubElement(palette,'color',{k:str(int(value[i:i+2],16)/255) for k,i in (('r',1),('g',3),('b',5))})
        node=styled.find(f".//n[@id='{mapping[atom['id']]}']")
        node.set('color',colours[value])
        for run in node.findall('t/s'): run.set('color',colours[value])
    return ET.tostring(styled,encoding='unicode'), {'geometry':'caller-supplied, not optimized or inferred', 'units':'CDXML points',
        'dative_direction':'begin donor to end metal', 'atom_ids':mapping,
        'chemical_plausibility':'not validated', 'spatial_rendering':'2D projection; xyz preservation checked',
        'overall_charge':charge,'charge_semantics':'Whole-complex charge is an explicit bracket annotation; it is not assigned to individual atoms or certified by a structure parser.'}


def _records(text, spatial=False):
    root=validate_cdxml(text)
    if len(root.findall('page'))!=1: raise ValueError('One page required')
    page=root.find('page'); fragments=page.findall('fragment')
    if len(fragments)!=1 or len(page.findall('t')) not in ((1,2) if spatial else (1,)) or any(e.tag not in (('fragment','t','graphic','arrow') if spatial else ('fragment','t')) for e in page):
        raise ValueError('Unexpected complex page objects')
    _validate_corner_lines(page)
    for g in page.findall('graphic'):
        allowed={'id','Z','BoundingBox','GraphicType','OvalType','BracketType','SupersededBy','LineWidth','color','bgcolor','Warning','LipSize','Center3D','MajorAxisEnd3D','MinorAxisEnd3D'}
        if set(g.attrib)-allowed or list(g): raise ValueError('Unsupported complex graphic metadata')
    fragment=fragments[0]
    if any(e.tag not in ('n','b') for e in fragment): raise ValueError('Unsupported complex annotation')
    nodes=fragment.findall('n'); bonds=fragment.findall('b')
    # Font IDs have their own namespace.
    ids=[e.get('id') for e in page.iter() if e.get('id')]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate native object IDs')
    allowed={'id','p','xyz','Z','Element','Charge','NumHydrogens','color','AS','Geometry',
             'BoundingBox','NodeType','AtomNumber','ShowAtomNumber','BondOrdering','NeedsClean','AtomID'}
    if spatial: allowed.update(('Attachments','Warning'))
    for node in nodes:
        if set(node.attrib)-allowed or any(e.tag!='t' for e in node):
            raise ValueError('Unsupported native atom metadata')
        if node.get('NodeType','Element') not in (('Element','MultiAttachment') if spatial else ('Element',)): raise ValueError('Unsupported native node type')
        _position(node.get('p'),2)
        if node.get('xyz') is not None: _position(node.get('xyz'))
    for bond in bonds:
        allowed_bond={'id','B','E','Order','Display','Z','color','LineWidth','BoldWidth','BS'}|({'BondCircularOrdering','CrossingBonds','Warning'} if spatial else set())
        if set(bond.attrib)-allowed_bond or list(bond):
            raise ValueError('Unsupported native coordination bond metadata')
        if 'BondCircularOrdering' in bond.attrib:
            order=bond.get('BondCircularOrdering').split()
            if len(order)!=4 or any(v!='0' and v not in {b.get('id') for b in bonds} for v in order):
                raise ValueError('Invalid native bond circular ordering')
    return root,nodes,bonds


def verify_complex(expected, native):
    expected_root=validate_cdxml(expected)
    spatial=bool(expected_root.findall('page/graphic') or expected_root.findall('.//n[@NodeType="MultiAttachment"]') or expected_root.find('colortable') is not None or any(b.get('Display','Solid')!='Solid' for b in expected_root.findall('.//b')))
    old,atoms,bonds=_records(expected,spatial); new,observed,newbonds=_records(native,spatial)
    if len(atoms)!=len(observed) or len(bonds)!=len(newbonds): raise ValueError('Native atom/bond count changed')
    mapping={}; used=set()
    for atom in atoms:
        p=_position(atom.get('p'),2)
        candidates=[n for n in observed if math.dist(p,_position(n.get('p'),2))<.03]
        if len(candidates)!=1 or candidates[0].get('id') in used: raise ValueError('Native projection changed or atom mapping ambiguous')
        n=candidates[0]; mapping[atom.get('id')]=n.get('id'); used.add(n.get('id'))
        if atom.get('NodeType','Element')!=n.get('NodeType','Element'): raise ValueError('Native node type changed')
        for key,default in (('Element','6'),('Charge','0')):
            if atom.get(key,default)!=n.get(key,default): raise ValueError('Native atom record changed: '+key)
        if _hydrogens(atom,bonds)!=_hydrogens(n,newbonds): raise ValueError('Native atom record changed: NumHydrogens')
        xyz=lambda a: _position(a.get('xyz')) if a.get('xyz') is not None else (*_position(a.get('p'),2),0)
        if math.dist(xyz(atom),xyz(n))>=.03:
            raise ValueError('Native supplied spatial coordinates changed')
        # Native text may reorder hydrogen and element runs, but not lose either.
        tokens=lambda a: sorted(re.findall(r'[A-Z][a-z]?|\d+|[+−-]', ''.join(a.itertext())))
        if tokens(atom)!=tokens(n): raise ValueError('Native atom label changed')
        if _node_colours(old,atom)!=_node_colours(new,n): raise ValueError('Native donor colour changed')
    for atom in atoms:
        observed_node=next(n for n in observed if n.get('id')==mapping[atom.get('id')])
        try: members=sorted(mapping[m] for m in atom.get('Attachments','').split())
        except KeyError: raise ValueError('Invalid attachment target') from None
        if members!=sorted(observed_node.get('Attachments','').split()): raise ValueError('Native multicentre attachments changed')
    before=sorted((mapping[b.get('B')],mapping[b.get('E')],b.get('Order','1'),b.get('Display','Solid')) for b in bonds)
    after=sorted((b.get('B'),b.get('E'),b.get('Order','1'),b.get('Display','Solid')) for b in newbonds)
    if before!=after: raise ValueError('Native bond direction/order/display changed')
    for bond in bonds:
        match=next(b for b in newbonds if b.get('B')==mapping[bond.get('B')] and b.get('E')==mapping[bond.get('E')])
        for key in ('LineWidth','BoldWidth'):
            if abs(float(bond.get(key,old.get(key)))-float(match.get(key,new.get(key))))>.011:
                raise ValueError('Native bond stroke changed')
    if spatial:
        from .crossings import verify_crossings
        verify_crossings(old.find('page/fragment'),new.find('page/fragment'),mapping)
    for tag in ('t','graphic'):
        before=old.findall('page/'+tag); after=new.findall('page/'+tag)
        if len(before)!=len(after): raise ValueError('Native complex annotation count changed')
        for a,b in zip(before,after):
            if tag=='t':
                if ''.join(a.itertext()).strip()!=''.join(b.itertext()).strip() or math.dist(_position(a.get('p'),2),_position(b.get('p'),2))>=.03:
                    raise ValueError('Native caption or charge annotation changed')
            else:
                if a.get('GraphicType')!=b.get('GraphicType') or a.get('BracketType')!=b.get('BracketType') or a.get('OvalType','')!=b.get('OvalType','') or math.dist(_position(a.get('BoundingBox'),4),_position(b.get('BoundingBox'),4))>=.03 or list(b):
                    raise ValueError('Native complex bracket changed')
                if _node_colours(old,a)!=_node_colours(new,b) or abs(float(a.get('LineWidth',old.get('LineWidth')))-float(b.get('LineWidth',new.get('LineWidth'))))>.011:
                    raise ValueError('Native complex annotation ink changed')
    return {'checks':{'explicit_atom_bond_records_preserved':True,'supplied_xyz_preserved':True,
                      'projected_positions_preserved':True,'dative_direction_preserved':True,
                      'donor_colours_preserved':True,'multicentre_attachments_preserved':True,
                      'whole_complex_charge_annotation_preserved':True},'atom_id_map':mapping,
            'chemical_plausibility':'not validated',
            'native_warnings':[{'id':e.get('id'),'message':e.get('Warning')} for e in new.iter() if e.get('Warning')]}


def _hydrogens(node,bonds):
    if node.get('NumHydrogens') is not None: return int(node.get('NumHydrogens'))
    if node.get('NodeType','Element')=='Element' and node.get('Element','6')=='6' and node.get('Charge','0')=='0' and node.find('t') is None:
        # ChemDraw omits the redundant explicit H count for skeletal carbon.
        orders=[b.get('Order','1') for b in bonds if node.get('id') in (b.get('B'),b.get('E'))]
        if all(o in ('1','1.5','2','3') for o in orders): return max(0,4-sum(map(float,orders)))
        raise ValueError('Cannot establish implicit hydrogen count for this native carbon')
    return 0


def _validate_corner_lines(page):
    """ChemDraw writes a legacy graphic plus a superseding arrow for each line."""
    arrows={a.get('id'):a for a in page.findall('arrow')}; seen=set()
    for g in page.findall('graphic'):
        target=g.get('SupersededBy')
        if not target: continue
        if g.get('GraphicType')!='Line' or target not in arrows or target in seen:
            raise ValueError('Unsupported superseding complex annotation')
        a=arrows[target]; seen.add(target)
        allowed={'id','BoundingBox','Z','FillType','ArrowheadType','Head3D','Tail3D','Center3D','MajorAxisEnd3D','MinorAxisEnd3D','LineWidth','color','ArrowheadHead','ArrowheadTail'}
        if set(a.attrib)-allowed or list(a) or a.get('ArrowheadHead','None')!='None' or a.get('ArrowheadTail','None')!='None' or a.get('FillType','None')!='None':
            raise ValueError('Charge corner changed into an arrow or filled object')
        x,y,u,v=_position(g.get('BoundingBox'),4)
        if math.dist(_position(a.get('Head3D')),(x,y,0))>=.03 or math.dist(_position(a.get('Tail3D')),(u,v,0))>=.03:
            raise ValueError('Native charge corner endpoints changed')
    if seen!=set(arrows): raise ValueError('Unexpected native arrow')


def _node_colours(root,node):
    palette=[(0.,0.,0.),(1.,1.,1.)]+[tuple(float(c.get(k,'0')) for k in ('r','g','b')) for c in root.findall('colortable/color')]
    def rgb(e):
        try: return tuple(round(c,3) for c in palette[int(e.get('color',node.get('color',root.get('color','0'))))])
        except (IndexError,ValueError): raise ValueError('Invalid native colour index') from None
    return rgb(node),sorted(set(rgb(s) for s in node.findall('t/s')))


def draw_complex(bridge, recipe, output_dir, preset='house', pixels=2400):
    text,plan=plan_complex(recipe,preset)
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir(): raise ValueError('Use a new absolute output directory')
    if out.exists() or out.is_symlink(): raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192: raise ValueError('Pixels must be 256..8192')
    from .styles import require_style_fonts, verify_custom_style
    require_style_fonts(preset)
    audit={'status':'in_progress','plan':plan,'visual_review':'required','renderer':'native ChemDraw'}
    owned=[]
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents)
        content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline['documents']}
        out.mkdir(); (out/'requested.cdxml').write_text(text)
        _write_json(out/'request.json',recipe); _write_json(out/'audit.json',audit)
        try:
            result=_native(bridge.create,text); did=result['document']['document_id']; owned.append(did)
            path=out/'figure.cdxml'; _native(bridge.export,did,str(path),'cdxml')
            audit.update(verify_complex(text,path.read_text()))
            verify_custom_style(text,path.read_text(),preset)
            for fmt in ('svg','png'): _native(bridge.export,did,str(out/f'figure.{fmt}'),fmt,pixels=pixels)
            if [d for d in _native(bridge.documents)['documents'] if d['document_id']!=did]!=baseline['documents']:
                raise ValueError('Pre-existing document inventory changed')
            if any(_document_content(bridge,oid)!=original for oid,original in content.items()):
                raise ValueError('Pre-existing document content changed')
            audit['checks']['preexisting_documents_unchanged']=True; audit['status']='checks_passed'
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Explicit coordination drawing</title><style>body{font:16px system-ui;background:#eee;margin:32px}img{background:white;max-width:100%;max-height:80vh}</style><h1>Explicit coordination drawing</h1><p>Caller-supplied geometry. Preservation checks are not chemical plausibility validation. Review required.</p><img src="figure.png" alt="Native coordination drawing"><p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="audit.json">Audit</a></p>')
            return {'document':result['document'],'audit':audit,'review':str(out/'review.html'),
                    'artifacts':{fmt:str(out/f'figure.{fmt}') for fmt in ('cdxml','svg','png')}}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned)
            _write_json(out/'audit.json',audit); raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc)); _write_json(out/'audit.json',audit)
            for did in reversed(owned):
                try: _native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing)); _write_json(out/'audit.json',audit); raise
            raise
