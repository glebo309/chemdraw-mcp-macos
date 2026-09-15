"""Explicit scope bands, native rounded shadow frames and real dotted separators."""
from contextlib import nullcontext
import copy
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .core import validate_cdxml
from .polish import supported_root, bounds, numbers, encode
from .geometry import Box, find_overlaps
from .editing import source_token
from .batch import _native, NativeUncertain, _verify, _document_content
from .workflow import remap_ids, _write_json, _file_hash
from .native_lock import native_transaction


def _xml(root):
    return ET.tostring(root, encoding='unicode')


def _union(boxes):
    return Box(min(b.left for b in boxes), min(b.top for b in boxes),
               max(b.right for b in boxes), max(b.bottom for b in boxes))


def _box(element):
    if not element.get('BoundingBox'):
        raise ValueError('Native measured bounds required for every scope object.')
    b = bounds(element)
    if b.width <= 0 or b.height <= 0:
        raise ValueError('Invalid measured scope bounds.')
    return b


def _source(text):
    root = supported_root(text);page = root.find('page')
    if any(e.tag not in ('fragment', 't') for e in page):
        raise ValueError('Scope decoration requires only plain fragments and owned page text.')
    if page.get('WidthPages', '1') != '1' or page.get('HeightPages', '1') != '1':
        raise ValueError('Scope decoration requires one physical page.')
    _verify(text, text)
    return root, page


def _groups(page, groups):
    if not isinstance(groups, list) or not 1 <= len(groups) <= 20:
        raise ValueError('Supply 1 through 20 explicitly owned groups.')
    objects = {e.get('id'): e for e in page};owned = [];bands = []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {'label', 'fragment_ids', 'caption_ids'}:
            raise ValueError('Groups require label, fragment_ids and caption_ids.')
        label = group['label']
        if (not isinstance(label, str) or len(label) > 80 or
                any(ord(c) < 32 or ord(c) == 127 for c in label) or
                (label and not label.strip())):
            raise ValueError('Group labels must be empty or nonblank single-line text of at most 80 characters.')
        ids = []
        for key, tag in (('fragment_ids', 'fragment'), ('caption_ids', 't')):
            values = group[key]
            if not isinstance(values, list) or (key == 'fragment_ids' and not values):
                raise ValueError('Each group needs fragments and an explicit caption list.')
            for oid in values:
                if not isinstance(oid, str) or oid not in objects or objects[oid].tag != tag:
                    raise ValueError('Unknown group object or wrong object kind.')
            ids.extend(values)
        owned.extend(ids);bands.append(_union([_box(objects[oid]) for oid in ids]))
    if len(owned) != len(set(owned)) or set(owned) != set(objects):
        raise ValueError('Every fragment and page caption must have exactly one group owner.')
    if any(a.bottom >= b.top for a, b in zip(bands, bands[1:])):
        raise ValueError('Groups must occupy disjoint top-to-bottom bands in supplied order.')
    if find_overlaps([_box(e) for e in page], [e.get('id') for e in page], tolerance=.05):
        raise ValueError('Existing scope objects overlap.')
    return bands


def plan_scope_decoration(text, groups, frame=True, separators=True):
    if type(frame) is not bool or type(separators) is not bool:
        raise ValueError('Frame and separators must be booleans.')
    root, page = _source(text);bands = _groups(page, groups)
    region = Box(*numbers(page.get('BoundingBox'), 4));union = _union(bands)
    width = float(root.get('LineWidth', '.6'));size = float(root.get('CaptionSize', root.get('LabelSize', '10')))
    if not math.isfinite(width) or not .2 <= width <= 3 or not math.isfinite(size) or not 4 <= size <= 72:
        raise ValueError('Unsupported scope line width or group-label size.')
    next_id = max(int(e.get('id')) for e in root.iter() if e.get('id')) + 1
    def fresh():
        nonlocal next_id
        value = str(next_id);next_id += 1;return value
    label_ids = [];label_records = [];display_bands = []
    for group, band in zip(groups, bands):
        if group['label']:
            baseline = band.top - 6
            # Estimates reserve space only; the saved native box is checked separately.
            box = Box(union.left, baseline-size, union.left+len(group['label'])*size, baseline+size*.25)
            if box.bottom >= band.top:
                raise ValueError('Group label cannot fit above its existing band.')
            tid = fresh();font = root.get('CaptionFont', root.get('LabelFont'))
            if font is None or root.find(f'fonttable/font[@id="{font}"]') is None:
                raise ValueError('Group labels require an explicit resolved caption font.')
            t = ET.SubElement(page, 't', {'id': tid, 'p': encode((union.left, baseline)),
                'BoundingBox': encode((box.left,box.top,box.right,box.bottom)), 'Justification': 'Left'})
            ET.SubElement(t, 's', {'font': font, 'size': str(size), 'face': '1', 'color': '0'}).text = group['label']
            label_ids.append(tid);label_records.append(copy.deepcopy(t));display_bands.append(_union([band, box]))
        else:display_bands.append(band)
    if any(b.top-a.bottom < 8 for a,b in zip(display_bands, display_bands[1:])):
        raise ValueError('Group labels or separators do not fit the existing inter-group gap.')
    union = _union(display_bands);graphics = []
    def graphic(attrs):
        g = ET.SubElement(page, 'graphic', {'id': fresh(), 'color': '0', **attrs})
        graphics.append(copy.deepcopy(g))
    if frame:
        # Native factory Human Insulin.cdxml rectangle 6853 uses these flags/axes.
        left,top,right,bottom = union.left-12,union.top-12,union.right+12,union.bottom+12
        cx,cy = (left+right)/2,(top+bottom)/2
        graphic({'GraphicType': 'Rectangle', 'RectangleType': 'RoundEdge Shadow',
            'CornerRadius': '600', 'ShadowSize': '400', 'LineWidth': str(width),
            'BoundingBox': encode((right,bottom,left,top)), 'Center3D': encode((cx,cy,0)),
            'MajorAxisEnd3D': encode((right,cy,0)), 'MinorAxisEnd3D': encode((cx,bottom,0))})
        outer = Box(left-width/2,top-width/2,right+8,bottom+8)
    else:outer = union
    separator_rows = []
    if separators:
        for first,second in zip(display_bands,display_bands[1:]):
            y = (first.bottom+second.top)/2;separator_rows.append(y)
            count = max(2, math.ceil(union.width/5)+1)
            if len(graphics)+count > 1500:
                raise ValueError('Scope decoration exceeds the 1500-graphic bound.')
            for i in range(count):
                x = union.left+i*union.width/(count-1);radius = .55
                graphic({'GraphicType': 'Oval', 'OvalType': 'Circle Filled', 'LineWidth': '.2',
                    'BoundingBox': encode((x+radius,y,x,y)), 'Center3D': encode((x,y,0)),
                    'MajorAxisEnd3D': encode((x+radius,y,0)), 'MinorAxisEnd3D': encode((x,y+radius,0))})
        if separator_rows and not frame:
            outer = Box(union.left-.7,union.top,union.right+.7,union.bottom)
    if outer.left < region.left or outer.top < region.top or outer.right > region.right or outer.bottom > region.bottom:
        raise ValueError('Scope frame, shadow or labels do not fit the native page.')
    return _xml(root), {'groups': copy.deepcopy(groups), 'frame': frame, 'separators': separators,
        'label_ids': label_ids, 'labels': [_xml(t) for t in label_records],
        'graphics': [_xml(g) for g in graphics], 'separator_y_pt': separator_rows,
        'display_bands': [[b.left,b.top,b.right,b.bottom] for b in display_bands],
        'page_region': [region.left,region.top,region.right,region.bottom],
        'outer_bounds': [outer.left,outer.top,outer.right,outer.bottom],
        'padding_pt': 12, 'shadow_reserved_pt': 8}


def _equal(a,b):
    if a == b:return True
    try:
        aa,bb = list(map(float,a.split())),list(map(float,b.split()))
        return len(aa)==len(bb) and all(math.isfinite(y) and abs(x-y)<=.03 for x,y in zip(aa,bb))
    except (TypeError,AttributeError,ValueError):return False


def _graphic_match(expected, actual, root):
    if list(actual) or actual.tag != 'graphic':return False
    if set(actual.attrib)-set(expected.attrib)-{'Z'}:return False
    for key,value in expected.attrib.items():
        if key == 'id':continue
        inherited = root.get('color','0') if key == 'color' else root.get(key) if key == 'LineWidth' else None
        observed = actual.get(key,inherited)
        if key in ('RectangleType','OvalType'):
            if set(value.split()) != set((observed or '').split()):return False
        elif not _equal(value,observed):return False
    return True


def _text_content(t,root):
    fonts = {f.get('id'): f.get('name') for f in root.findall('fonttable/font')}
    result = []
    for s in t.iter('s'):
        family = fonts.get(s.get('font'));face = s.get('face','0');size = s.get('size')
        # Observed native 23.0.1 heading serialization: Helvetica + face=1
        # saves as Helvetica Bold + face=1. Keep all other family/face changes strict.
        if family == 'Helvetica Bold' and face == '1':family = 'Helvetica'
        try:
            numeric = float(size)
            if not math.isfinite(numeric):raise ValueError('Nonfinite native font size.')
            size = format(numeric,'.10g')
        except (TypeError,ValueError):raise ValueError('Invalid native font size.')
        result.append((s.text or '',family,size,face,s.get('color','0')))
    return result


def verify_scope_decoration(source, native, plan):
    original, _ = _source(source);root = validate_cdxml(native);page = root.find('page')
    if page is None:raise ValueError('Native scope page missing.')
    if not _equal(page.get('BoundingBox'), encode(plan['page_region'])):
        raise ValueError('Native page geometry changed.')
    graphics = list(page.findall('graphic'));mapping = {};label_boxes = []
    if len(graphics) != len(plan['graphics']):raise ValueError('Native decoration graphic count changed.')
    for text in plan['graphics']:
        expected = ET.fromstring(text);hits = [g for g in graphics if _graphic_match(expected,g,root)]
        if len(hits) != 1:raise ValueError('Native decoration geometry or styling changed.')
        found = hits[0];mapping[expected.get('id')] = found.get('id');graphics.remove(found);page.remove(found)
    for text in plan['labels']:
        expected = ET.fromstring(text)
        hits = [t for t in page.findall('t') if _equal(t.get('p'),expected.get('p')) and
                _text_content(t,root) == _text_content(expected,original) and
                t.get('Justification','Left') == expected.get('Justification','Left')]
        if len(hits) != 1:raise ValueError('Native group label content, style or position changed.')
        found = hits[0];label_boxes.append(_box(found));mapping[expected.get('id')] = found.get('id');page.remove(found)
    stripped = _xml(root);_verify(source,stripped);source_map = remap_ids(source,stripped)
    # Existing page text is immutable, including its typography.
    for t in original.findall('page/t'):
        actual = page.find(f't[@id="{source_map[t.get("id")]}"]')
        if _text_content(t,original) != _text_content(actual,root):
            raise ValueError('Existing scope caption typography changed.')
    for fragment in original.findall('page/fragment'):
        actual_fragment = page.find(f'fragment[@id="{source_map[fragment.get("id")]}"]')
        for atom in fragment.findall('n'):
            hits = [n for n in actual_fragment.findall('n') if _equal(n.get('p'),atom.get('p'))]
            if len(hits)!=1 or _text_content(atom,original)!=_text_content(hits[0],root):
                raise ValueError('Existing atom label typography or position changed.')
    content_boxes = [_box(e) for e in page]+label_boxes
    if find_overlaps(content_boxes, tolerance=.05):raise ValueError('Native group label overlaps source objects.')
    region = Box(*plan['page_region']);outer = Box(*plan['outer_bounds'])
    for box in label_boxes:
        if box.left<region.left or box.top<region.top or box.right>region.right or box.bottom>region.bottom:
            raise ValueError('Native label exceeds page fit.')
        if plan['frame'] and (box.left<outer.left+10 or box.right>outer.right-18 or box.top<outer.top+10 or box.bottom>outer.bottom-18):
            raise ValueError('Native label exceeds frame content region.')
        if any(box.top-.7 <= y <= box.bottom+.7 for y in plan['separator_y_pt']):
            raise ValueError('Native group label overlaps dotted separator.')
    return {'checks': {'source_objects_preserved': True, 'decoration_geometry_preserved': True,
                       'labels_and_page_fit': True}, 'id_map': {**source_map,**mapping}}


def _destination(output_dir,pixels):
    out = Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent.')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists.')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('PNG pixels must be 256 through 8192.')
    return out


def _run(bridge,did,out,groups,token,frame,separators,pixels,reserved=False):
    created = None;audit = {'status':'in_progress','checks':{},'visual_review':'required'}
    with getattr(bridge,'lock',nullcontext()):
        inventory = _native(bridge.documents)['documents']
        contents = {d['document_id']:_document_content(bridge,d['document_id']) for d in inventory}
        baseline = _native(bridge.inspect,did)['document'];disk_hash = _file_hash(baseline)
        snapshot = bridge._new_path('.cdxml','backups');_native(bridge.export,did,str(snapshot),'cdxml');source = snapshot.read_text()
        if source_token(source) != token:raise ValueError('Source snapshot is stale; analyze again.')
        planned,plan = plan_scope_decoration(source,groups,frame,separators)
        if not reserved:out.mkdir()
        (out/'before.cdxml').write_text(source);(out/'planned.cdxml').write_text(planned)
        _write_json(out/'recipe.json',{'schema_version':1,'groups':groups,'frame':frame,'separators':separators,'expected_source_token':token,'pixels':pixels})
        audit['plan'] = plan;_write_json(out/'audit.json',audit)
        try:
            for fmt in ('svg','png'):_native(bridge.export,did,str(out/f'before.{fmt}'),fmt,pixels)
            result = _native(bridge.create,planned);created = result['document']['document_id']
            audit['working_document_id'] = created;_write_json(out/'audit.json',audit)
            for fmt in ('svg','png','cdxml'):_native(bridge.export,created,str(out/f'figure.{fmt}'),fmt,pixels)
            audit['native_verification'] = verify_scope_decoration(source,(out/'figure.cdxml').read_text(),plan)
            audit['checks'].update(audit['native_verification']['checks'])
            if [d for d in _native(bridge.documents)['documents'] if d['document_id']!=created] != inventory:
                raise ValueError('Pre-existing document inventory changed.')
            if any(_document_content(bridge,oid)!=content for oid,content in contents.items()) or _file_hash(baseline)!=disk_hash:
                raise ValueError('Source or pre-existing document content changed.')
            audit['checks']['source_document_unchanged'] = True;audit['status'] = 'checks_passed'
            _write_json(out/'audit.json',audit)
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Scope decoration</title><h1>Scope decoration</h1><p>Visual review required. Groups are caller supplied.</p><img width="48%" src="before.png"><img width="48%" src="figure.png"><p><a href="figure.cdxml">Editable ChemDraw</a> <a href="figure.svg">SVG</a> <a href="audit.json">Audit</a></p>')
            return {'document':result['document'],'output_dir':str(out),'review':str(out/'review.html'),'audit':audit}
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),recovery='No retry or automatic close; inspect retained documents.')
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc));_write_json(out/'audit.json',audit)
            if created is not None:
                try:_native(bridge.close,created)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',close_error=str(closing));_write_json(out/'audit.json',audit);raise
            raise


def decorate_scope_document(bridge,document_id,output_dir,groups,expected_source_token,frame=True,separators=True,pixels=3200):
    return _run(bridge,document_id,_destination(output_dir,pixels),groups,expected_source_token,frame,separators,pixels)


@native_transaction
def decorate_scope_file(bridge,path,output_dir,groups,expected_source_token=None,frame=True,separators=True,pixels=3200):
    out = _destination(output_dir,pixels);path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower()!='.cdxml' or not path.is_file() or path.stat().st_size>10_000_000:
        raise ValueError('Scope decoration input requires CDXML of at most 10 MB.')
    data = path.read_bytes();source = data.decode('utf-8');plan_scope_decoration(source,groups,frame,separators)
    if expected_source_token is not None and source_token(source)!=expected_source_token:raise ValueError('Source file snapshot is stale.')
    out.mkdir();(out/'source-input.cdxml').write_bytes(data)
    evidence = {'source_file':str(path),'source_file_sha256':hashlib.sha256(data).hexdigest()}
    _write_json(out/'audit.json',{'status':'in_progress',**evidence})
    did = None;completed = None;uncertain = False
    try:
        result = _native(bridge.create,source);did = result['document']['document_id']
        snap = bridge._new_path('.cdxml','backups');_native(bridge.export,did,str(snap),'cdxml');native = snap.read_text()
        _verify(source,native);mapping = remap_ids(source,native)
        if path.read_bytes()!=data:raise ValueError('Source file changed during import.')
        mapped = [{**g,'fragment_ids':[mapping[i] for i in g['fragment_ids']],
                   'caption_ids':[mapping[i] for i in g['caption_ids']]} for g in groups]
        completed = _run(bridge,did,out,mapped,source_token(native),frame,separators,pixels,True)
        try:preserved = path.read_bytes()==data
        except OSError:preserved = False
        completed['audit'].update(evidence);completed['audit']['checks']['source_file_unchanged'] = preserved
        _write_json(out/'audit.json',completed['audit'])
        if not preserved:raise ValueError('Source file changed during decoration.')
        return completed
    except Exception as exc:
        uncertain = isinstance(exc,NativeUncertain)
        import json
        audit = json.loads((out/'audit.json').read_text());audit.update(evidence,status='uncertain' if uncertain else 'failed',error=str(exc))
        _write_json(out/'audit.json',audit)
        if completed and not uncertain:
            try:_native(bridge.close,completed['document']['document_id'])
            except NativeUncertain as closing:
                uncertain = True;audit.update(status='uncertain',close_error=str(closing))
                _write_json(out/'audit.json',audit);raise
        raise
    finally:
        if did is not None and not uncertain:
            try:_native(bridge.close,did)
            except NativeUncertain as exc:
                import json
                audit = json.loads((out/'audit.json').read_text());audit.update(status='uncertain',close_error=str(exc));_write_json(out/'audit.json',audit)
                raise
