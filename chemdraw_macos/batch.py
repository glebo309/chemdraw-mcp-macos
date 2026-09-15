"""Sequential native exports of explicit, supported CDXML files. No styling."""
from contextlib import nullcontext
import copy
import hashlib
import html
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .polish import supported_root, chemical_signature
from .core import validate_cdxml
from .editing import verify_native_edit
from .workflow import remap_ids, content_fingerprint, _write_json


class NativeUncertain(RuntimeError):
    pass


def _native(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except Exception as exc:
        raise NativeUncertain(str(exc)) from exc


def _has_annotations(root):
    return bool(root.findall('page/curve') or root.findall('page/fragment/graphic'))


def _supported(text):
    root=supported_root(text);page=root.find('page')
    if _has_annotations(root):
        # Local imports avoid the intentional annotations -> batch core verifier
        # dependency. The stripped core has no dispatching objects, so recursion
        # terminates in the original plain batch validation below.
        from .annotations import _root as annotation_root, _core
        validated=annotation_root(text)
        _supported(_core(text))
        return validated
    if any(e.tag not in ('fragment','t','arrow','graphic','scheme') for e in page):
        raise ValueError('Unsupported batch page object')
    for f in page.findall('fragment'):
        if any(e.tag not in ('n','b') for e in f):raise ValueError('Unsupported batch molecular annotation')
        if any(any(c.tag!='t' for c in n) for n in f.findall('n')):
            raise ValueError('Unsupported batch atom annotation')
    chemical_signature(text)
    return root


def _verify(before,after):
    old_root=_supported(before);new_root=_supported(after)
    if _has_annotations(old_root) or _has_annotations(new_root):
        from .annotations import verify_annotations
        # Reuses both annotation checks and the ordinary batch graph, position,
        # caption, reaction-arrow and explicit-scheme checks on its stripped core.
        return verify_annotations(before,after)
    old=old_root.find('page');new=new_root.find('page')
    mapping=remap_ids(before,after)
    objects=lambda page:[e for e in page if e.tag in ('fragment','t','arrow')]
    if len(objects(old))!=len(objects(new)) or set(mapping.values())!={e.get('id') for e in objects(new)}:
        raise ValueError('Native object coverage changed')
    for f in old.findall('fragment'):
        pair=[]
        for doc,obj in ((old_root,f),(new_root,new.find(f'fragment[@id="{mapping[f.get("id")]}"]'))):
            r=copy.deepcopy(doc);page=r.find('page')
            for child in list(page):page.remove(child)
            page.append(copy.deepcopy(obj))
            pair.append(ET.tostring(r,encoding='unicode'))
        verify_native_edit(*pair)
    # Export does not reposition arrows; check shape/head attributes as well as endpoints.
    for a in old.findall('arrow'):
        n=new.find(f'arrow[@id="{mapping[a.get("id")]}"]')
        # ChemDraw omits a local width equal to its document default on save.
        # Compare effective widths in both directions, including inherited input.
        width=a.get('LineWidth',old_root.get('LineWidth'))
        observed=n.get('LineWidth',new_root.get('LineWidth'))
        if width is not None:
            try:equal=math.isfinite(float(observed)) and abs(float(width)-float(observed))<.03
            except (TypeError,ValueError):equal=False
            if not equal:raise ValueError('Native arrow property changed: LineWidth')
        for key,value in a.attrib.items():
            if key in ('id','BoundingBox','Z','LineWidth'):continue
            actual=n.get(key)
            if actual==value:continue
            try:
                values=list(map(float,value.split()));observed=list(map(float,actual.split()))
                equal=len(values)==len(observed) and all(math.isfinite(v) and abs(v-w)<.03 for v,w in zip(values,observed))
            except (ValueError,AttributeError):equal=False
            if not equal:raise ValueError(f'Native arrow property changed: {key}')
    # Scheme object IDs may change; role/reference IDs must still address the same objects.
    for page in (old,new):
        for g in page.findall('graphic'):
            if g.get('SupersededBy'):
                if page is old:mapping[g.get('id')]=mapping[g.get('SupersededBy')]
    def schemes(page,remap):
        aliases={g.get('id'):g.get('SupersededBy') for g in page.findall('graphic')}
        def record(e):
            attrs=[]
            for key,value in e.attrib.items():
                if key in ('id','Z'):continue
                if key.startswith('ReactionStep'):
                    value=' '.join(remap.get(aliases.get(v,v),aliases.get(v,v)) for v in value.split())
                attrs.append((key,value))
            return (e.tag,tuple(sorted(attrs)),tuple(record(c) for c in e))
        return tuple(record(e) for e in page.findall('scheme'))
    # ChemDraw can generate inferred scheme metadata when none was supplied.
    # Explicit source roles must survive; generated roles are not chemically certified.
    if old.findall('scheme') and schemes(old,mapping)!=schemes(new,{}):raise ValueError('Native reaction scheme changed')


def _hash(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _document_content(bridge,document_id):
    path=bridge._new_path('.cdxml','backups')
    _native(bridge.export,document_id,str(path),'cdxml')
    root=validate_cdxml(path.read_text())
    for key in ('Name','CreationProgram','WindowPosition','WindowSize'):root.attrib.pop(key,None)
    def record(e):
        return (e.tag,tuple(sorted(e.attrib.items())),e.text if e.tag=='s' else (e.text or '').strip(),tuple(record(c) for c in e))
    return record(root)


def _report(out,report):
    _write_json(out/'audit.json',report)
    cards=[]
    for row in report['items']:
        key=row['key'];escaped=html.escape(key)
        links=' '.join(f'<a href="{key}/{key}.{fmt}">{fmt.upper()}</a>' for fmt in row.get('exports',[]))
        preview=f'<img src="{key}/{key}.png" alt="{escaped}">' if 'png' in row.get('exports',[]) else ''
        cards.append(f'<article><h2>{escaped}</h2><p>{row["status"]}</p>{preview}<p>{links}</p><p>{html.escape(row.get("error",""))}</p></article>')
    (out/'review.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ChemDraw batch export</title>
<style>body{font:16px system-ui;margin:32px;background:#f2f4f5;color:#182326}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;border:1px solid #ccd3d5;padding:20px;border-radius:12px}img{width:100%;height:280px;object-fit:contain}a{color:#17617c}</style>
<h1>ChemDraw batch export</h1><p>Visual review required. Diagnostic or uncertain outputs are not approved figures. No styling or layout changes requested.</p>
<p><a href="audit.json">Batch audit</a> · <a href="manifest.json">Manifest</a></p><main>'''+''.join(cards)+'</main></html>')


def batch_export(bridge,items,output_dir,pixels=3200):
    """Export explicit files into new keyed folders, stopping on uncertain native results."""
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output directory already exists')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be an integer from 256 to 8192')
    if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('Supply 1 through 100 manifest items')
    keys=set();normalized=[]
    for item in items:
        if not isinstance(item,dict) or set(item)-{'key','source','formats'}:raise ValueError('Unknown batch item fields')
        key=item.get('key')
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',key):raise ValueError('Invalid figure key')
        if key.casefold() in keys:raise ValueError('Duplicate case-insensitive figure key')
        keys.add(key.casefold())
        source=item.get('source')
        if not isinstance(source,str) or not Path(source).expanduser().is_absolute():raise ValueError('Source must be an absolute file path')
        formats=item.get('formats',[])
        if not isinstance(formats,list) or any(not isinstance(v,str) or v not in ('cdxml','svg','png','pdf','cdx') for v in formats):
            raise ValueError('Unsupported export formats')
        normalized.append({'key':key,'source':str(Path(source).expanduser()),'formats':list(dict.fromkeys(['cdxml','svg','png']+formats))})
    # All input validation precedes native calls. Freeze source text before import.
    prepared={};rows=[]
    for item in normalized:
        row={**item,'status':'pending','exports':[],'checks':{},'visual_review':'required'};rows.append(row)
        try:
            path=Path(item['source']).resolve(strict=True)
            if path.suffix.lower()!='.cdxml' or not path.is_file():raise ValueError('Batch input currently requires CDXML files')
            if path.stat().st_size>10_000_000:raise ValueError('Source exceeds 10 MB limit')
            data=path.read_bytes();text=data.decode('utf-8');_supported(text)
            row['source']=str(path);row['source_sha256']=hashlib.sha256(data).hexdigest()
            prepared[item['key']]=text
        except Exception as exc:row.update(status='rejected',error=str(exc))
    out.mkdir()
    _write_json(out/'manifest.json',{'schema_version':1,'items':normalized,'pixels':pixels})
    report={'status':'in_progress','items':rows,'checks':{'preexisting_documents_unchanged':None},
            'visual_review':'required','renderer':'native ChemDraw; PNG rasterized from native SVG',
            'limitations':'Supported CDXML preservation only. No styling, collision repair, source correctness or glyph certification.'}
    def save():
        for row in rows:
            folder=out/row['key']
            if folder.is_dir():_write_json(folder/'audit.json',row)
        _report(out,report)
    save()
    baseline=None;baseline_content={};interrupted=False
    with getattr(bridge,'lock',nullcontext()):
        for row in rows:
            if row['status']!='pending':continue
            if interrupted:row['status']='not_run';continue
            folder=out/row['key'];folder.mkdir();did=None;uncertain=False
            source=prepared[row['key']]
            snapshots=folder/'snapshots';snapshots.mkdir()
            (snapshots/'source.cdxml').write_text(source)
            try:
                if _hash(Path(row['source']))!=row['source_sha256']:raise ValueError('Source file changed after preflight')
                if baseline is None:
                    baseline=_native(bridge.documents)
                    baseline_content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline['documents']}
                row['status']='in_progress';save()
                result=_native(bridge.create,source);did=result['document']['document_id']
                row['working_document_id']=did
                row['working_copy']=result.get('working_copy')
                save()
                target=folder/(row['key']+'.cdxml')
                _native(bridge.export,did,str(target),'cdxml',pixels)
                row['exports'].append('cdxml');native=target.read_text();verification=_verify(source,native)
                row['checks'].update(mapped_chemistry_preserved=True,atom_coordinates_preserved=True,
                                     captions_and_arrow_endpoints_preserved=True)
                if verification is not None:
                    row['annotation_verification']=verification
                    row['checks'].update(verification['checks'])
                for fmt in row['formats'][1:]:
                    _native(bridge.export,did,str(folder/(row['key']+'.'+fmt)),fmt,pixels)
                    row['exports'].append(fmt);save()
                final=snapshots/'post-export.cdxml';_native(bridge.export,did,str(final),'cdxml',pixels)
                if content_fingerprint(native)!=content_fingerprint(final.read_text()):raise ValueError('Working document changed during exports')
                if _hash(Path(row['source']))!=row['source_sha256']:raise ValueError('Source file changed during export')
                row['checks'].update(source_file_unchanged=True,working_content_unchanged=True)
                row['status']='exported'
            except NativeUncertain as exc:
                uncertain=True;interrupted=True
                row.update(status='uncertain',error=str(exc),recovery='Native operation not retried. Inspect ChemDraw and retained artifacts before any new run.')
            except Exception as exc:row.update(status='failed',error=str(exc))
            finally:
                if did is not None and not uncertain:
                    try:
                        closed=_native(bridge.close,did);row['closed_working_document']=True
                        row['recovery_backup']=closed.get('backup') if isinstance(closed,dict) else None
                    except NativeUncertain as exc:
                        interrupted=True;row.update(status='uncertain',error=str(exc),recovery='Working-copy close was uncertain and was not retried.')
                save()
        if baseline is not None and not interrupted:
            try:
                final=_native(bridge.documents)
                byid={d['document_id']:d for d in final['documents']}
                preserved=set(byid)=={d['document_id'] for d in baseline['documents']} and all(byid.get(d['document_id'])==d for d in baseline['documents'])
                if preserved:
                    preserved=all(_document_content(bridge,did)==value for did,value in baseline_content.items())
                report['checks']['preexisting_documents_unchanged']=preserved
                if not preserved:report['error']='Open document inventory, metadata or pre-existing content changed; inspect before using outputs'
            except Exception as exc:interrupted=True;report['error']=str(exc)
    report['status']='interrupted' if interrupted else 'completed' if all(r['status']=='exported' for r in rows) and report['checks']['preexisting_documents_unchanged'] else 'partial_failure'
    report['review']=str(out/'review.html');report['output_dir']=str(out)
    save();return report
