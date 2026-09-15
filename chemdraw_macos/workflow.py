"""Transactional figure production using the bounded native bridge."""
from __future__ import annotations

from contextlib import nullcontext
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .core import PRESETS, preset_settings
from .geometry import find_overlaps
from .native_lock import native_transaction
from .polish import (analyze_cdxml, chemical_signature, supported_root,
                     normalize_cdxml, layout_row, bounds, numbers)


def remap_ids(before, after):
    """Find objects after ChemDraw renumbers them; never assume IDs survive open."""
    old = supported_root(before).find('page')
    new = supported_root(after).find('page')
    def key(e):
        if e.tag=='fragment':
            isolated=ET.Element('CDXML');ET.SubElement(isolated,'page').append(copy.deepcopy(e))
            identity=tuple(chemical_signature(ET.tostring(isolated,encoding='unicode')))
            return (('fragment', identity), tuple(numbers(n.get('p'),2) for n in e.findall('n')))
        if e.tag=='t':
            return (('t', ''.join(e.itertext()).strip()), (numbers(e.get('p'),2),))
        if e.tag=='arrow':
            return (('arrow',), (numbers(e.get('Head3D'),3), numbers(e.get('Tail3D'),3)))
        return None
    def same_positions(left,right,unordered):
        if len(left)!=len(right):return False
        if not unordered:
            return all(math.dist(a,b)<.03 for a,b in zip(left,right))
        # Near-equal x values can swap lexicographic order when native saving
        # rounds coordinates. Require a unique point bijection instead, without
        # changing tolerance or treating arrow head/tail positions as unordered.
        used=set()
        for point in left:
            hits=[i for i,other in enumerate(right) if math.dist(point,other)<.03]
            if len(hits)!=1 or hits[0] in used:return False
            used.add(hits[0])
        return len(used)==len(right)
    candidates=[]
    for e in new:
        k=key(e)
        if k is not None:candidates.append((k,e.get('id')))
    result={}
    for e in old:
        k=key(e)
        if k is None:continue
        hits=[eid for candidate,eid in candidates if candidate[0]==k[0]
              and same_positions(candidate[1],k[1],e.tag=='fragment')]
        if len(hits)!=1:
            raise ValueError(f'Cannot uniquely match native object {e.get("id")}; inspect the working copy')
        result[e.get('id')]=hits[0]
    return result


@native_transaction
def analyze_document(bridge, document_id):
    snapshot=bridge._new_path('.cdxml','backups')
    bridge.export(document_id,str(snapshot),'cdxml')
    from .editing import inspect_editable,source_token
    try:editing=inspect_editable(snapshot.read_text())
    except (ValueError,RuntimeError,ImportError) as exc:editing={'unsupported':str(exc)}
    return {**analyze_cdxml(snapshot.read_text()), 'snapshot':str(snapshot),
            'source_token':source_token(snapshot.read_text()),
            'editing':editing,
            'document':bridge.inspect(document_id)['document'],
            'note':'IDs belong to this snapshot. Pass these IDs in polish caption/condition maps.'}


def _file_hash(document):
    file=document.get('file')
    if file and Path(file).is_file():return hashlib.sha256(Path(file).read_bytes()).hexdigest()
    return None


def _write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def content_fingerprint(text):
    """Compare document content, excluding export name and window-only metadata."""
    root=supported_root(text)
    for key in ('Name','CreationProgram','WindowPosition','WindowSize'):
        root.attrib.pop(key,None)
    def record(e):
        value=e.text if e.tag=='s' else (e.text or '').strip()
        return (e.tag,tuple(sorted(e.attrib.items())),value,tuple(record(c) for c in e))
    return record(root)


def polish_document(bridge, document_id, output_dir, preset='house', layout='preserve',
                    caption_map=None, condition_map=None, gap=24., label_gap=14.,
                    width=None, pixels=3200):
    """Produce a new native document plus before/after review, never edit source.

    Row layout requires explicit label ownership. Structural cleanup is not
    automatically run: it could change a user's carefully chosen orientation.
    """
    out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():
        raise ValueError('Output directory must be absolute with an existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output directory already exists; choose a new one')
    preset_settings(preset)
    from .styles import require_style_fonts
    require_style_fonts(preset)
    if layout not in ('preserve','row'):raise ValueError('Choose preserve or row layout')
    if not 256<=pixels<=8192:raise ValueError('PNG size must be 256 to 8192')
    caption_map=caption_map or {};condition_map=condition_map or {}
    if layout=='preserve' and (caption_map or condition_map):
        raise ValueError('Ownership maps require row layout')
    created=[];audit={'status':'in_progress','visual_review':'required','checks':{}}
    recipe={'schema_version':1,'preset':preset,'layout':layout,'caption_map':caption_map,
            'condition_map':condition_map,'gap':gap,'label_gap':label_gap,'width':width,'pixels':pixels}
    with getattr(bridge,'lock',nullcontext()):
        baseline=bridge.inspect(document_id)['document'];source_hash=_file_hash(baseline)
        out.mkdir()
        try:
            bridge.export(document_id,str(out/'before.cdxml'),'cdxml')
            source=(out/'before.cdxml').read_text()
            signature=chemical_signature(source)
            normalized,normalization=normalize_cdxml(source,preset)
            audit['normalization']=normalization
            _write_json(out/'recipe.json',recipe)
            for fmt in ('svg','png'):
                bridge.export(document_id,str(out/f'before.{fmt}'),fmt,pixels)
            result=bridge.create(normalized);nid=result['document']['document_id'];created.append(nid)
            measured=bridge._new_path('.cdxml')
            bridge.export(nid,str(measured),'cdxml');native=measured.read_text()
            if chemical_signature(native)!=signature:
                raise ValueError('Native normalization changed chemistry; output rejected')
            from .styles import verify_custom_style
            verify_custom_style(normalized,native,preset)
            planned=native
            if layout=='row':
                mapping=remap_ids(normalized,native)
                mapped_captions={mapping[f]:mapping[t] for f,t in caption_map.items()}
                mapped_conditions={mapping[a]:[mapping[t] for t in ts] for a,ts in condition_map.items()}
                arranged,layout_audit=layout_row(native,mapped_captions,mapped_conditions,gap,label_gap,width)
                audit['layout']=layout_audit
                planned=arranged
                result=bridge.create(arranged);nid=result['document']['document_id'];created.append(nid)
            for fmt in ('cdxml','svg','png'):
                bridge.export(nid,str(out/f'figure.{fmt}'),fmt,pixels)
            final_text=(out/'figure.cdxml').read_text()
            style_check=verify_custom_style(planned,final_text,preset)
            if style_check is not None:audit['custom_style_verification']=style_check
            if chemical_signature(final_text)!=signature:
                raise ValueError('Final native export changed chemistry; output rejected')
            report=analyze_cdxml(final_text)
            target=float(preset_settings(preset)['BondLength'])
            medians=[m['median_bond_pt'] for m in report['molecules'] if m['median_bond_pt'] is not None]
            if not all(abs(v-target)<.03 for v in medians):
                raise ValueError('Native export failed bond-scale normalization')
            after=bridge.inspect(document_id)['document']
            source_check=bridge._new_path('.cdxml','backups')
            bridge.export(document_id,str(source_check),'cdxml')
            if (after!=baseline or _file_hash(after)!=source_hash
                    or content_fingerprint(source_check.read_text())!=content_fingerprint(source)):
                raise RuntimeError('Source document state changed during processing; inspect source and backups')
            root=supported_root(final_text)
            visible=[e for e in root.find('page') if e.tag in ('fragment','t','arrow')]
            overlaps=find_overlaps([bounds(e) for e in visible],[e.get('id') for e in visible])
            audit.update(status='checks_passed' if not overlaps else 'needs_review',
                         source_document=baseline,source_file_sha256=source_hash,
                         source_cdxml_sha256=hashlib.sha256(source.encode()).hexdigest(),
                         final_chemical_signature=signature,final_measurements=report,
                         overlaps=overlaps,renderer='native ChemDraw',
                         limitation='Graph preservation and inter-object boxes checked; human review of glyphs, charges and chemistry is still required.')
            audit['checks'].update(source_document_unchanged=True,native_roundtrip_chemistry_preserved=True,
                                   normalized_bond_scale=True,no_interobject_overlaps=not overlaps)
            _write_json(out/'audit.json',audit)
            title=html.escape('ChemDraw figure review')
            (out/'review.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font:16px system-ui;margin:32px;color:#182326;background:#f2f4f5}}main{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}figure{{margin:0;padding:24px;background:white;border:1px solid #ccd3d5;border-radius:12px}}img{{width:100%;height:380px;object-fit:contain}}a{{color:#17617c}}@media(max-width:800px){{main{{grid-template-columns:1fr}}}}</style>
<h1>{title}</h1><p>Source preserved. Chemical graph checked after native export. Visual review remains required.</p>
<main><figure><figcaption>Before</figcaption><img src="before.png" alt="Original figure"></figure><figure><figcaption>After</figcaption><img src="figure.png" alt="Polished figure"></figure></main>
<p><a href="figure.cdxml">Editable ChemDraw</a> · <a href="figure.svg">Vector SVG</a> · <a href="figure.png">Transparent PNG</a> · <a href="audit.json">Audit</a> · <a href="recipe.json">Recipe</a></p></html>''')
            for did in created[:-1]:bridge.close(did)
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except Exception as exc:
            audit.update(status='failed',error=str(exc))
            _write_json(out/'audit.json',audit)
            # Recovery copies are retained by close. Never close a pre-existing document.
            for did in reversed(created):
                try:bridge.close(did)
                except Exception:pass
            raise
