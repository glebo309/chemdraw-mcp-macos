"""Native-measured scope grids with explicit compound/caption ownership."""
from __future__ import annotations

from contextlib import nullcontext
import copy
import html
import json
import math
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET

from .core import PRESETS
from .editing import source_token, verify_native_edit
from .geometry import Box, grid_positions, find_overlaps
from .polish import (supported_root, chemical_signature, normalize_cdxml, numbers,
                     bounds, transform, bond_lengths)
from .workflow import remap_ids, _file_hash, _write_json
from .batch import _native, NativeUncertain


def _root(text):
    root=supported_root(text);page=root.find('page')
    if any(e.tag not in ('fragment','t') for e in page):
        raise ValueError('Scope grids support molecules and owned captions, not reactions or page graphics')
    if page.get('HeightPages','1')!='1' or page.get('WidthPages','1')!='1':
        raise ValueError('Scope grid requires a single physical page')
    for f in page.findall('fragment'):
        if any(e.tag not in ('n','b') for e in f):
            raise ValueError('Unsupported molecular graphic in scope grid')
        if any(any(c.tag!='t' for c in n) for n in f.findall('n')):
            raise ValueError('Unsupported atom annotation in scope grid')
    return root


def validate_cells(text,cells,prepared=False):
    root=_root(text);page=root.find('page')
    if not isinstance(cells,list) or not 1<=len(cells)<=100:
        raise ValueError('Supply 1 to 100 explicit compound cells')
    fragments=[];captions=[];compound_ids=[]
    for cell in cells:
        allowed={'compound_id','fragment_ids','caption_id','yield_percent'}|({'metadata_id'} if prepared else set())
        if not isinstance(cell,dict) or set(cell)-allowed:raise ValueError('Unknown cell fields')
        cid=cell.get('compound_id')
        if not isinstance(cid,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,31}',cid):
            raise ValueError('Invalid compound_id; use a short explicit identifier')
        compound_ids.append(cid)
        fids=cell.get('fragment_ids')
        if not isinstance(fids,list) or not fids or not all(isinstance(v,str) for v in fids):
            raise ValueError('Each compound needs explicit fragment_ids')
        fragments.extend(fids)
        tid=cell.get('caption_id')
        if tid is not None:
            if not isinstance(tid,str):raise ValueError('Invalid caption_id')
            captions.append(tid)
        if prepared:captions.append(cell.get('metadata_id'))
        value=cell.get('yield_percent')
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100):
            raise ValueError('Yield must be a finite percentage 0 to 100, or null when missing')
    if len(set(compound_ids))!=len(compound_ids):raise ValueError('Duplicate compound_id')
    if len(set(fragments))!=len(fragments) or set(fragments)!={f.get('id') for f in page.findall('fragment')}:
        raise ValueError('Every fragment must belong to exactly one compound')
    if len(set(captions))!=len(captions) or set(captions)!={t.get('id') for t in page.findall('t')}:
        raise ValueError('Every caption must have exactly one explicit owner')
    return root


def _metadata(cell):
    value=cell.get('yield_percent')
    return cell['compound_id']+(f' · {value:g}%' if value is not None else '')


def prepare_scope(text,cells,preset='house'):
    validate_cells(text,cells)
    normalized,normalization=normalize_cdxml(text,preset)
    root=_root(normalized);page=root.find('page')
    ids=[int(e.get('id')) for e in root.iter() if e.get('id')]
    next_id=max(ids+[0])+1;prepared=copy.deepcopy(cells)
    for cell in prepared:
        cell['metadata_id']=str(next_id);next_id+=1
        f=page.find(f'fragment[@id="{cell["fragment_ids"][0]}"]')
        x,y=bounds(f).center
        t=ET.SubElement(page,'t',{'id':cell['metadata_id'],'p':f'{x} {y+60}',
                                'Justification':'Center','CaptionJustification':'Center'})
        face=root.get('CaptionFace','0') if isinstance(preset,dict) else '1'
        ET.SubElement(t,'s',{'font':root.get('CaptionFont'),'size':root.get('CaptionSize'),'face':face}).text=_metadata(cell)
    return ET.tostring(root,encoding='unicode'),{'cells':prepared,'normalization':normalization}


def _ink(element):
    if not element.get('BoundingBox'):raise ValueError('Native measured bounds required for every grid object')
    box=bounds(element)
    if box.width<=0 or box.height<=0:raise ValueError('Invalid or empty native ink bounds')
    return box


def _union(boxes):
    return Box(min(b.left for b in boxes),min(b.top for b in boxes),
               max(b.right for b in boxes),max(b.bottom for b in boxes))


def _numeric(value,name,minimum):
    if type(value) not in (int,float) or not math.isfinite(value) or value<minimum:
        raise ValueError(f'{name} must be finite and at least {minimum}')


def _place_measured_caption(text,ink_center_x,baseline):
    # A native text anchor is not necessarily its visible ink centre. Retain
    # that measured bearing and justification while translating both together.
    # Resetting p.x to ink_center_x would discard the correction on native save.
    anchor=numbers(text.get('p'),2)
    transform(text,dx=ink_center_x-_ink(text).center[0],dy=baseline-anchor[1])
    return numbers(text.get('p'),2)[0]


def arrange_scope(text,cells,columns=None,width=None,height=None,margin=36.,h_gap=18.,v_gap=24.,label_gap=10.):
    root=validate_cells(text,cells,prepared=True);page=root.find('page')
    for key,val,minimum in [('margin',margin,0),('h_gap',h_gap,4),('v_gap',v_gap,4),('label_gap',label_gap,4)]:
        _numeric(val,key,minimum)
    if columns is not None and (type(columns) is not int or not 1<=columns<=len(cells)):
        raise ValueError('Columns must be an integer from 1 through the compound count')
    px,py,pr,pb=numbers(page.get('BoundingBox'),4)
    if pr<=px or pb<=py:raise ValueError('Invalid saved page bounds')
    available_w=pr-px-2*margin;available_h=pb-py-2*margin
    for name,value,available in [('width',width,available_w),('height',height,available_h)]:
        if value is not None:
            _numeric(value,name,1)
            if value>available+.03:raise ValueError(f'Requested {name} does not fit the saved page and margins')
    width=available_w if width is None else width;height=available_h if height is None else height
    objects={e.get('id'):e for e in page}
    structures=[_union([_ink(objects[fid]) for fid in c['fragment_ids']]) for c in cells]
    name_texts=[objects[c['caption_id']] for c in cells if c.get('caption_id')]
    metadata=[objects[c['metadata_id']] for c in cells]
    name_boxes=[_ink(t) for t in name_texts];meta_boxes=[_ink(t) for t in metadata]
    def ascent(t):return numbers(t.get('p'),2)[1]-_ink(t).top
    def descent(t):return _ink(t).bottom-numbers(t.get('p'),2)[1]
    struct_h=max(b.height for b in structures)
    name_a=max([ascent(t) for t in name_texts]+[0]);name_d=max([descent(t) for t in name_texts]+[0])
    meta_a=max(ascent(t) for t in metadata);meta_d=max(descent(t) for t in metadata)
    name_base=struct_h+label_gap+name_a if name_texts else None
    meta_base=(name_base+name_d+4+meta_a) if name_texts else (struct_h+label_gap+meta_a)
    cell_w=max(b.width for b in structures+name_boxes+meta_boxes)
    cell_h=meta_base+meta_d
    if columns is None:columns=max(1,min(len(cells),int((width+h_gap)//(cell_w+h_gap))))
    rows=math.ceil(len(cells)/columns)
    total_w=columns*cell_w+(columns-1)*h_gap;total_h=rows*cell_h+(rows-1)*v_gap
    if total_w>width+.03 or total_h>height+.03:
        raise ValueError(f'Grid overflow: needs {total_w:.2f} × {total_h:.2f} pt, available {width:.2f} × {height:.2f}; choose fewer columns, a wider page or shorter captions. Molecules were not shrunk.')
    positions=grid_positions([Box(0,0,cell_w,cell_h)]*len(cells),columns,px+margin,py+margin,h_gap,v_gap)
    plan={'columns':columns,'rows':rows,'cell_width':cell_w,'cell_height':cell_h,
          'h_gap':h_gap,'v_gap':v_gap,'margin':margin,
          'region':[px+margin,py+margin,px+margin+width,py+margin+height],
          'cells':[]}
    for i,(cell,struct,(left,top)) in enumerate(zip(cells,structures,positions)):
        cx=left+cell_w/2;cy=top+struct_h/2;dx=cx-struct.center[0];dy=cy-struct.center[1]
        for fid in cell['fragment_ids']:transform(objects[fid],dx=dx,dy=dy)
        name_anchor=None
        if cell.get('caption_id'):
            name_anchor=_place_measured_caption(objects[cell['caption_id']],cx,top+name_base)
        metadata_anchor=_place_measured_caption(objects[cell['metadata_id']],cx,top+meta_base)
        plan['cells'].append({**cell,'row':i//columns,'column':i%columns,'center_x':cx,
                              'structure_center_y':cy,'name_baseline':top+name_base if name_base is not None else None,
                              'metadata_baseline':top+meta_base,'name_anchor_x':name_anchor,
                              'metadata_anchor_x':metadata_anchor,'translation_pt':[dx,dy]})
    return ET.tostring(root,encoding='unicode'),plan


def _single(root,fid):
    isolated=copy.deepcopy(root);page=isolated.find('page')
    for e in list(page):
        if e.tag!='fragment' or e.get('id')!=fid:page.remove(e)
    return ET.tostring(isolated,encoding='unicode')


def verify_molecules(expected,native):
    mapping=remap_ids(expected,native)
    old=_root(expected);new=_root(native)
    if (len(old.find('page'))!=len(new.find('page'))
            or set(mapping.values())!={e.get('id') for e in new.find('page')}):
        raise ValueError('Native output contains missing or unowned objects')
    reports={}
    for f in old.find('page').findall('fragment'):
        fid=f.get('id')
        reports[fid]=verify_native_edit(_single(old,fid),_single(new,mapping[fid]))
    return mapping,reports


def remap_cells(cells,mapping):
    return [{**c,'fragment_ids':[mapping[fid] for fid in c['fragment_ids']],
             'caption_id':mapping[c['caption_id']] if c.get('caption_id') else None,
             **({'metadata_id':mapping[c['metadata_id']]} if c.get('metadata_id') else {})} for c in cells]


def verify_scope(expected,native,plan):
    mapping,molecules=verify_molecules(expected,native)
    root=_root(native);page=root.find('page');objects={e.get('id'):e for e in page}
    mapped=remap_cells(plan['cells'],mapping)
    boxes=[_ink(e) for e in page];ids=[e.get('id') for e in page]
    x1,y1,x2,y2=plan['region'];page_box=numbers(page.get('BoundingBox'),4)
    if x1<page_box[0] or y1<page_box[1] or x2>page_box[2]+.03 or y2>page_box[3]+.03:
        raise ValueError('Native saved page differs from requested grid region')
    if any(b.left<x1-.05 or b.right>x2+.05 or b.top<y1-.05 or b.bottom>y2+.05 for b in boxes):
        raise ValueError('Native grid ink overflow; preview crop does not establish page fit')
    overlaps=find_overlaps(boxes,ids,tolerance=.05)
    if overlaps:raise ValueError(f'Native grid objects overlap: {overlaps}')
    for c in mapped:
        structure=_union([_ink(objects[f]) for f in c['fragment_ids']])
        if math.dist(structure.center,(c['center_x'],c['structure_center_y']))>.05:
            raise ValueError('Native compound alignment changed')
        meta=objects[c['metadata_id']]
        if ''.join(meta.itertext()).strip()!=_metadata(c):raise ValueError('Native compound/yield binding changed')
        for tid,baseline,anchor_x in [(c.get('caption_id'),c['name_baseline'],c.get('name_anchor_x',c['center_x'])),
                                      (c['metadata_id'],c['metadata_baseline'],c.get('metadata_anchor_x',c['center_x']))]:
            if tid and math.dist(numbers(objects[tid].get('p'),2),(anchor_x,baseline))>.05:
                raise ValueError('Native caption baseline or centering changed')
            if tid and abs(_ink(objects[tid]).center[0]-c['center_x'])>.75:
                raise ValueError('Native visible caption ink is not centred within 0.75 pt')
    medians=[statistics.median(bond_lengths(f)) for f in page.findall('fragment') if f.findall('b')]
    return {'checks':{'page_fit':True,'compound_bindings_preserved':True,'no_interobject_overlaps':True,
                      'mapped_chemistry_preserved':True,'orientation_preserved':True,'caption_alignment':True},
            'median_bond_lengths_pt':medians,'cells':mapped,'molecule_checks':molecules}


def grid_document(bridge,document_id,output_dir,cells,expected_source_token,preset='house',
                  columns=None,width=None,height=None,margin=36.,h_gap=18.,v_gap=24.,label_gap=10.,pixels=3200):
    from .styles import require_style_fonts
    require_style_fonts(preset)
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 to 8192')
    created=[];audit={'status':'in_progress','visual_review':'required','checks':{}}
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.inspect,document_id)['document'];source_hash=_file_hash(baseline)
        snapshot=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(snapshot),'cdxml')
        source=snapshot.read_text()
        if source_token(source)!=expected_source_token:raise ValueError('Source is stale; analyze again')
        prepared,state=prepare_scope(source,cells,preset)
        out.mkdir()
        try:
            (out/'before.cdxml').write_text(source)
            recipe={'schema_version':1,'cells':cells,'expected_source_token':expected_source_token,'preset':preset,
                    'columns':columns,'width':width,'height':height,'margin':margin,'h_gap':h_gap,
                    'v_gap':v_gap,'label_gap':label_gap,'pixels':pixels}
            _write_json(out/'recipe.json',recipe)
            for fmt in ('svg','png'):_native(bridge.export,document_id,str(out/f'before.{fmt}'),fmt,pixels)
            result=_native(bridge.create,prepared);did=result['document']['document_id'];created.append(did)
            snap=bridge._new_path('.cdxml');_native(bridge.export,did,str(snap),'cdxml');native=snap.read_text()
            mapping,_=verify_molecules(prepared,native)
            from .styles import verify_custom_style
            verify_custom_style(prepared,native,preset)
            measured_cells=remap_cells(state['cells'],mapping)
            arranged,plan=arrange_scope(native,measured_cells,columns,width,height,margin,h_gap,v_gap,label_gap)
            check=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(check),'cdxml')
            if source_token(check.read_text())!=expected_source_token:raise ValueError('Source became stale before final creation')
            result=_native(bridge.create,arranged);did=result['document']['document_id'];created.append(did)
            for fmt in ('cdxml','svg','png'):_native(bridge.export,did,str(out/f'figure.{fmt}'),fmt,pixels)
            verification=verify_scope(arranged,(out/'figure.cdxml').read_text(),plan)
            style_check=verify_custom_style(arranged,(out/'figure.cdxml').read_text(),preset)
            if style_check is not None:audit['custom_style_verification']=style_check
            from .core import preset_settings
            if not all(abs(v-float(preset_settings(preset)['BondLength']))<.03 for v in verification['median_bond_lengths_pt']):
                raise ValueError('Native molecular scale differs from preset')
            check=bridge._new_path('.cdxml','backups');_native(bridge.export,document_id,str(check),'cdxml')
            if (_native(bridge.inspect,document_id)['document']!=baseline or _file_hash(baseline)!=source_hash
                    or source_token(check.read_text())!=expected_source_token):raise RuntimeError('Source changed during grid production')
            audit.update(status='checks_passed',source_document=baseline,normalization=state['normalization'],
                         layout=plan,verification=verification,renderer='native ChemDraw',
                         yield_provenance='Caller supplied. Not experimental validation.',
                         limitation='Native ink boxes and saved chemistry checked, not all intra-molecular glyph collisions or printed output.')
            audit['checks'].update(verification['checks'],source_document_unchanged=True,normalized_bond_scale=True)
            _write_json(out/'audit.json',audit)
            rows=''.join(f'<tr><td>{html.escape(c["compound_id"])}</td><td>{html.escape(_metadata(c))}</td></tr>' for c in cells)
            (out/'review.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ChemDraw scope grid</title>
<style>body{{font:16px system-ui;margin:32px;background:#f2f4f5;color:#182326}}main{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}figure{{background:white;padding:24px;margin:0}}img{{width:100%;height:480px;object-fit:contain}}td{{padding:6px 20px}}@media(max-width:800px){{main{{grid-template-columns:1fr}}}}</style>
<h1>ChemDraw scope grid</h1><p>Explicit compound order and caller-supplied yields. Molecular scale, orientation and native page fit checked. Visual review required.</p>
<main><figure><figcaption>Before</figcaption><img src="before.png" alt="Original drawing"></figure><figure><figcaption>Scope grid</figcaption><img src="figure.png" alt="Native scope grid"></figure></main>
<p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="figure.svg">SVG</a> · <a href="figure.png">PNG</a> · <a href="recipe.json">Recipe</a> · <a href="audit.json">Audit</a></p><table><tr><th>Compound</th><th>Displayed metadata</th></tr>{rows}</table></html>''')
            for old in created[:-1]:
                _native(bridge.close,old)
            created=created[-1:]
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),recovery='No retry or automatic close; inspect owned copies and backups')
            _write_json(out/'audit.json',audit)
            raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc));_write_json(out/'audit.json',audit)
            for did in reversed(created):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit)
                    raise
            raise


def grid_file(bridge,path,output_dir,cells,expected_source_token=None,**options):
    import hashlib
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    allowed={'preset','columns','width','height','margin','h_gap','v_gap','label_gap','pixels'}
    if set(options)-allowed:raise ValueError('Unsupported grid options')
    pixels=options.get('pixels',3200)
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 to 8192')
    source_path=Path(path).expanduser().resolve(strict=True)
    if source_path.suffix.lower()!='.cdxml':raise ValueError('Grid file input requires CDXML')
    data=source_path.read_bytes();file_hash=hashlib.sha256(data).hexdigest()
    source=data.decode('utf-8');prepare_scope(source,cells,options.get('preset','house'))
    if expected_source_token is not None and source_token(source)!=expected_source_token:raise ValueError('File snapshot is stale')
    did=None;completed=None;uncertain=False

    def source_unchanged():
        try:return hashlib.sha256(source_path.read_bytes()).hexdigest()==file_hash
        except OSError:return False

    def record(status,**details):
        # grid_document owns normal output creation. Failures before that
        # point still need a diagnostic audit and the exact frozen source.
        if completed is not None:audit=completed['audit']
        elif (out/'audit.json').is_file():audit=json.loads((out/'audit.json').read_text())
        else:audit={'checks':{},'visual_review':'required'}
        out.mkdir(exist_ok=True)
        frozen=out/'source-input.cdxml';frozen.write_bytes(data)
        audit.update(status=status,source_file=str(source_path),source_file_sha256=file_hash,
                     source_snapshot=str(frozen),**details)
        audit.setdefault('checks',{})['source_file_unchanged']=source_unchanged()
        _write_json(out/'audit.json',audit)
        return audit

    with getattr(bridge,'lock',nullcontext()):
        try:
            # Create from frozen text, never ask ChemDraw to reopen a mutable
            # input pathname after it has been validated.
            imported=_native(bridge.create,source);did=imported['document']['document_id']
            snap=bridge._new_path('.cdxml','backups');_native(bridge.export,did,str(snap),'cdxml');native=snap.read_text()
            mapping,_=verify_molecules(source,native)
            if not source_unchanged():raise ValueError('Source file changed during import')
            completed=grid_document(bridge,did,output_dir,remap_cells(cells,mapping),source_token(native),**options)
            if not source_unchanged():raise ValueError('Source file changed during grid production')
            record('checks_passed')
            return completed
        except NativeUncertain as exc:
            uncertain=True
            record('uncertain',error=str(exc),recovery='No retry or automatic close; inspect owned copies and backups')
            raise
        except Exception as exc:
            record('failed',error=str(exc))
            if completed is not None:
                try:_native(bridge.close,completed['document']['document_id'])
                except NativeUncertain as closing:
                    uncertain=True;record('uncertain',close_error=str(closing));raise
            raise
        finally:
            if did is not None and not uncertain:
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    record('uncertain',close_error=str(closing));raise
