"""Checked append into one existing native document using native CDX only."""
import copy
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .core import validate_cdxml
from .geometry import Box
from .polish import bounds, numbers, transform
from .native_lock import native_transaction


def fingerprint(text):
    root=validate_cdxml(text)
    for key in ('Name','CreationProgram','WindowPosition','WindowSize','BoundingBox','MacPrintInfo'):
        root.attrib.pop(key,None)
    # Copy As allocates a fresh page handle and normalizes the opaque printer
    # record. Keep actual page dimensions, drawing properties and object IDs.
    for page in root.findall('page'):page.attrib.pop('id',None)
    def record(e):
        return (e.tag,sorted(e.attrib.items()),e.text if e.tag=='s' else '',[record(c) for c in e])
    return record(root)


def _page(text, *, vertical_pages=False):
    root=validate_cdxml(text)
    pages=root.findall('page')
    if len(pages)!=1:raise ValueError('Shared append requires one page')
    page=pages[0]
    if page.get('WidthPages','1')!='1' or (not vertical_pages and page.get('HeightPages','1')!='1'):
        raise ValueError('Shared append requires one physical page')
    if vertical_pages and (not page.get('HeightPages','1').isdigit() or not 1<=int(page.get('HeightPages','1'))<=20):
        raise ValueError('Expected 1 through 20 vertical physical pages')
    for e in page:
        if e.tag == 'chemicalproperty':
            # ChemDraw's linked name caption is metadata, not another molecule
            # or an obstacle. Retain it unchanged; never resolve chemistry from it.
            ids={o.get('id') for f in page.findall('fragment') for o in f.iter() if o.get('id')}
            if (list(e) or set(e.attrib)-{'id','ChemicalPropertyDisplayID','ChemicalPropertyType','BasisObjects'}
                    or e.get('ChemicalPropertyType')!='1'
                    or page.find(f't[@id="{e.get("ChemicalPropertyDisplayID")}"]') is None
                    or not e.get('BasisObjects') or not set(e.get('BasisObjects').split())<=ids):
                raise ValueError('Unsupported linked caption chemical property')
            continue
        if e.tag not in ('fragment','t'):
            raise ValueError('Shared append currently supports molecules and captions only')
        if not e.get('BoundingBox'):raise ValueError('Shared append requires native measured object bounds')
    return root,page


def _union(boxes):
    return Box(min(b.left for b in boxes),min(b.top for b in boxes),
               max(b.right for b in boxes),max(b.bottom for b in boxes))


def plan_append(before,addition):
    _,page=_page(before);_,incoming=_page(addition)
    if not len(incoming):raise ValueError('Nothing to append')
    extent=bounds(page);ink=_union([bounds(e) for e in incoming])
    obstacles=[bounds(e) for e in page if e.tag!='chemicalproperty'];margin=24.;gap=24.
    xs=sorted({extent.left+margin,*[b.right+gap for b in obstacles]})
    ys=sorted({extent.top+margin,*[b.bottom+gap for b in obstacles]})
    for y in ys:
        for x in xs:
            candidate=Box(x,y,x+ink.width,y+ink.height)
            if candidate.right>extent.right-margin or candidate.bottom>extent.bottom-margin:continue
            if any(not(candidate.right+gap<=b.left or b.right+gap<=candidate.left or
                       candidate.bottom+gap<=b.top or b.bottom+gap<=candidate.top) for b in obstacles):continue
            return {'left':x,'top':y,'width':ink.width,'height':ink.height}
    raise ValueError('No free space on this page; no paste or page expansion was requested')


def verify_append(before,after,addition,placement=None,*,exact_coordinates=False,allow_page_expansion=False):
    from .workflow import remap_ids
    from .batch import _verify
    from .polish import chemical_signature
    old,op=_page(before,vertical_pages=allow_page_expansion);new,np=_page(after,vertical_pages=allow_page_expansion);supplied,sp=_page(addition,vertical_pages=allow_page_expansion)
    # addCDXML retains existing IDs. Linked caption metadata is immutable and
    # independently checked before the chemistry/geometry verifier sees a view.
    properties=lambda p:{e.get('id'):dict(e.attrib) for e in p.findall('chemicalproperty')}
    if properties(op)!=properties(np) or properties(sp):
        raise ValueError('Existing linked caption metadata changed during append')
    for p in (op,np):
        for e in list(p.findall('chemicalproperty')):p.remove(e)
    before=ET.tostring(old,encoding='unicode');after=ET.tostring(new,encoding='unicode')
    if allow_page_expansion:validate_page_expansion(op,sp)
    for key in ('BoundingBox','WidthPages','HeightPages'):
        expected=sp if allow_page_expansion else op
        if expected.get(key,'1' if key!='BoundingBox' else '')!=np.get(key,'1' if key!='BoundingBox' else ''):raise ValueError('Page dimensions changed during append')
    try:mapping=remap_ids(before,after) if len(op) else {}
    except ValueError as exc:raise ValueError('Existing content changed during append: '+str(exc)) from exc
    old_ids=set(mapping.values())
    existing=copy.deepcopy(new);ep=existing.find('page')
    for e in list(ep):
        if e.get('id') not in old_ids:ep.remove(e)
    try:
        if len(op):_verify(before,ET.tostring(existing,encoding='unicode'))
    except ValueError as exc:raise ValueError('Existing content changed during append: '+str(exc)) from exc
    added=copy.deepcopy(new);ap=added.find('page')
    for e in list(ap):
        if e.get('id') in old_ids:ap.remove(e)
    if len(ap)!=len(sp):raise ValueError('Unexpected appended object count')
    if chemical_signature(ET.tostring(added,encoding='unicode'))!=chemical_signature(addition):
        raise ValueError('Appended chemical identity differs from native output')
    actual=_union([bounds(e) for e in ap]);expected=_union([bounds(e) for e in sp])
    if placement is not None and (abs(actual.left-placement['left'])>1 or abs(actual.top-placement['top'])>1):
        raise ValueError('Native position differs from planned placement')
    if not exact_coordinates:
        for e in sp:transform(e,dx=actual.left-expected.left,dy=actual.top-expected.top)
    _verify(ET.tostring(supplied,encoding='unicode'),ET.tostring(added,encoding='unicode'))
    if exact_coordinates:
        measured=[bounds(e) for e in ap]
        for i,a in enumerate(measured):
            if any(not(a.right+2<=b.left or b.right+2<=a.left or a.bottom+2<=b.top or b.bottom+2<=a.top) for b in measured[:i]):
                raise ValueError('Native measured appended objects overlap')
    if any(not(actual.right+2<=bounds(e).left or bounds(e).right+2<=actual.left or
               actual.bottom+2<=bounds(e).top or bounds(e).bottom+2<=actual.top) for e in ep):
        raise ValueError('New drawing overlaps existing content')
    extent=bounds(np)
    if actual.left<extent.left or actual.top<extent.top or actual.right>extent.right or actual.bottom>extent.bottom:
        raise ValueError('Appended drawing exceeds page')
    result={'existing_content_preserved':True,'added_chemistry_and_geometry_verified':True,
            'page_unchanged':bounds(op)==bounds(np),'nonoverlapping_placement':True}
    if allow_page_expansion:result['page_expansion_verified']=True
    return result


def validate_page_expansion(old,new):
    """Only append whole sheets vertically; retain paper size and origin."""
    a,b=bounds(old),bounds(new)
    old_n=int(old.get('HeightPages','1'));new_n=int(new.get('HeightPages','1'))
    if (new.get('WidthPages','1')!='1' or not old_n<=new_n<=20
            or abs(a.left-b.left)>.01 or abs(a.top-b.top)>.01 or abs(a.width-b.width)>.01
            or abs(a.height/old_n-b.height/new_n)>.01):
        raise ValueError('Expansion must append identical physical pages vertically')


@native_transaction
def clipboard(bridge,document_id,cdx=None,placement=None,expected=None,undo_steps=0):
    """Internal bounded operation, not a raw scripting endpoint. Restores clipboard."""
    did=bridge._id(document_id)
    if cdx is not None:
        path=Path(cdx).resolve(strict=True)
        if path.suffix.lower()!='.cdx' or not path.read_bytes().startswith(b'VjCD0100'):
            raise ValueError('Only native ChemDraw CDX is accepted for shared insertion')
        if path.stat().st_size>10_000_000:raise ValueError('CDX exceeds limit')
        if not isinstance(placement,dict) or set(placement)!={'left','top','width','height'} or any(
            type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>2000 for v in placement.values()):
            raise ValueError('Invalid checked placement')
        if not expected:raise ValueError('An expected snapshot is required')
        cdx=str(path)
    if type(undo_steps) is not int or not 0<=undo_steps<=500:raise ValueError('Invalid undo count')
    options={'app':str(bridge.app),'document_id':did,'cdx':cdx,'placement':placement,
             'expected':expected,'undo_steps':undo_steps}
    script=Path(__file__).with_name('shared.js')
    # Pass snapshots through stdin, not process arguments. The child owns the
    # clipboard transaction until finally has run, including native errors.
    try:
        run=subprocess.run(['/usr/bin/osascript','-l','JavaScript',str(script)],
            input=json.dumps(options),capture_output=True,text=True,timeout=max(45,bridge.timeout))
    except subprocess.TimeoutExpired as exc:
        from .batch import NativeUncertain
        raise NativeUncertain('Shared operation timed out; do not retry. Clipboard/document may need inspection.') from exc
    if run.returncode:
        from .batch import NativeUncertain
        raise NativeUncertain('Shared operation failed; no retry: '+run.stderr.strip())
    result=json.loads(run.stdout)
    if result.get('error'):
        from .batch import NativeUncertain
        raise NativeUncertain(result['error']+'; clipboard restored: '+str(result.get('clipboard_restored')))
    return result


@native_transaction
def run_shared(bridge,plan,out,document_id=None):
    from .api_drawing import run_api_drawing
    return run_api_drawing(bridge,plan,out,document_id)


@native_transaction
def run_shared_legacy(bridge,plan,out,document_id=None):
    from .harness import _execute,NeedsInput
    from .workflow import _write_json
    from .batch import NativeUncertain
    if plan.get('workflow','molecules')!='molecules' or plan.get('groups') is not None:
        raise NeedsInput('unsupported_shared_objects',
            'Shared insertion supports plain molecules and captions only. Request a separate '
            'interactive/background document for reactions or decorated groups; no native generation was started.')
    docs=bridge.documents()['documents']
    if document_id is None:
        visible=set(bridge._run('visible_documents'))
        candidates=[d for d in docs if d['document_id'] in visible]
        if len(candidates)!=1:
            raise NeedsInput('choose_shared_document','Choose one open working document.',documents=candidates)
        document_id=candidates[0]['document_id']
    did=bridge._id(document_id)
    original=next((d for d in docs if d['document_id']==did),None)
    if original is None:raise ValueError('Shared document is absent; refresh document IDs')
    if any(not d['file'] for d in docs if d['document_id']!=did):
        raise NeedsInput('other_untitled_document','Another untitled document cannot yet be preservation-read in this job.',documents=docs)
    before=clipboard(bridge,did)['cdxml'];_page(before)
    depth=getattr(bridge,'_production_depth',0)
    old_shared=getattr(bridge,'_shared_document_id',None)
    bridge._production_depth=depth+1;bridge._shared_document_id=did
    try:
        result=_execute(bridge,plan,out)
        generated=result['document']['document_id']
        addition=Path(result['artifacts']['cdxml']).read_text()
        placement=plan_append(before,addition)
        fresh=clipboard(bridge,did)['cdxml']
        if fingerprint(fresh)!=fingerprint(before):
            raise ValueError('Working document changed during generation; no insertion was sent')
        (out/'shared-before.cdxml').write_text(fresh)
        cdx=out/'shared-payload.cdx';bridge.export(generated,str(cdx),'cdx')
        bridge.close(generated)
        inserted=clipboard(bridge,did,cdx=str(cdx),placement=placement,expected=fresh)
        (out/'shared-after.cdxml').write_text(inserted['cdxml'])
        try:checks=verify_append(fresh,inserted['cdxml'],addition,placement)
        except ValueError as exc:
            raise NativeUncertain('Shared paste occurred but verification failed; inspect before Undo or retry: '+str(exc)) from exc
        current=next(d for d in bridge.documents()['documents'] if d['document_id']==did)
        if current['file']!=original['file']:
            raise NativeUncertain('Shared document file binding changed; inspect native state')
        clipboard(bridge,did)  # Restore the shared window as the active document.
        result.update(document=current,presentation={'mode':'shared','intermediates':'hidden'},
            shared={'checks':checks,'snapshot':str(out/'shared-after.cdxml'),
                    'undo_steps':inserted['undo_steps'],'clipboard_restored':inserted['clipboard_restored'],
                    'selection':'all objects selected by verification',
                    'note':'Existing document retained, not saved or closed. Exports contain the new drawing only.'})
        _write_json(out/'result.json',result)
        return result
    finally:
        bridge._production_depth=depth;bridge._shared_document_id=old_shared
