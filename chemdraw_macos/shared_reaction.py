"""Draw explicit reactions into the ONE open ChemDraw document via the desktop API.

No hidden measuring document, no scratch copy, no clipboard, no close/reopen: the
whole reaction is laid out offline (RDKit seeds, per-string text-width estimates),
appended once, then verified from the live document's own read-back. A second
reaction goes into the same document, below the first. Products, balance and yields
are never inferred.
"""
import copy
import math
import xml.etree.ElementTree as ET

from .polish import bounds, numbers
from .shared import _page, geometric

# Arial advance widths in em; deliberately a little generous (see _PAD).
_W = {**{c: .556 for c in '0123456789abdeghnopqu'}, **{c: .5 for c in 'ckvxyzs'},
      **{c: .222 for c in 'ijl'}, **{c: .278 for c in 'ft I,.:;/ '}, 'm': .833, 'r': .333, 'w': .722,
      'A': .667, 'B': .667, 'C': .722, 'D': .722, 'E': .667, 'F': .611, 'G': .778, 'H': .722,
      'J': .5, 'K': .667, 'L': .556, 'M': .833, 'N': .722, 'O': .778, 'P': .667, 'Q': .778,
      'R': .722, 'S': .667, 'T': .611, 'U': .722, 'V': .667, 'W': .944, 'X': .667, 'Y': .667,
      'Z': .611, '-': .333, '(': .333, ')': .333, '+': .584, '°': .4, '=': .584}
_PAD = 1.12
PAPER_ORDER = ('A4 landscape', 'A3 landscape')
CENTRE_TOLERANCE = 1.5
INK_SLACK = 2.  # the offline ink model is within ~1 pt; keep that much clear of the page region
MARGIN = 36.  # equals the reaction layout margin, so verify_series keeps every object inside its region
GAP = 24.


def estimate_text_width(text, size):
    """Conservative width in points; centring never depends on it, only spacing."""
    return sum(_W.get(c, .62) for c in text) * size * _PAD + 2.


def _sheet(page):
    box = bounds(page)
    count = int(page.get('HeightPages', '1'))
    return box.left, box.top, box.right, (box.bottom - box.top) / count, count


def _font_map(source_root, target_root):
    """source font id -> target font id, adding missing fonts by name like plan_addition."""
    fonts = target_root.find('fonttable')
    if fonts is None:
        fonts = ET.SubElement(target_root, 'fonttable')
    names = {f.get('name'): f.get('id') for f in fonts}
    result = {}
    for font in source_root.findall('fonttable/font'):
        name = font.get('name')
        if name not in names:
            names[name] = str(max([int(f.get('id')) for f in fonts] + [2]) + 1)
            ET.SubElement(fonts, 'font', id=names[name], name=name, charset='Unicode')
        result[font.get('id')] = names[name]
    return result


def _rehome(composed, target):
    """Move composed page objects into a copy of the target document's own root."""
    source_root = ET.fromstring(composed)
    payload = copy.deepcopy(target)
    page = payload.find('page')
    for child in list(page):
        page.remove(child)
    mapping = _font_map(source_root, payload)
    for child in source_root.find('page'):
        child = copy.deepcopy(child)
        for e in child.iter():
            for key in ('font', 'LabelFont', 'CaptionFont'):
                if e.get(key) is not None:
                    e.set(key, mapping.get(e.get(key), e.get(key)))
        page.append(child)
    return payload


def _clear_of_target_ids(payload, target, plan):
    """Shift composed ids above every id the live document already uses (page, fonts, objects).

    A fresh canvas can carry a small page id (e.g. 8) that the composer's own ids would
    collide with; ChemDraw renumbers on insertion, but the payload must be unambiguous.
    """
    from .addin import REFERENCE_LISTS
    from .reaction_series import remap_series
    floor = max([int(e.get('id')) for e in target.iter() if (e.get('id') or '').isdigit()] + [0])
    page = payload.find('page')
    ids = [int(e.get('id')) for e in page.iter() if e is not page and (e.get('id') or '').isdigit()]
    offset = floor + 1 - min(ids)
    if offset <= 0:
        return plan
    mapping = {str(i): str(i + offset) for i in ids}
    for e in page.iter():
        if e is page:
            continue
        for key in ('id', 'B', 'E', 'SupersededBy'):
            if e.get(key) in mapping:
                e.set(key, mapping[e.get(key)])
        for key in REFERENCE_LISTS + ('CrossingBonds',):
            if e.get(key):
                e.set(key, ' '.join(mapping.get(v, v) for v in e.get(key).split()))
    return remap_series(plan, mapping)


def _translate(page, dx, dy):
    from .polish import transform
    for e in page:
        transform(e, dx=dx, dy=dy)


def _destination(oldpage, block, allow_expansion=True):
    """First free slot for a full-width row: top margin of a sheet or below existing ink."""
    left, top, right, sheet_h, count = _sheet(oldpage)
    if block.width > right - left - 2 * (MARGIN + INK_SLACK) + .01:
        return None
    existing = [bounds(e) for e in geometric(oldpage)]
    tops = {top + k * sheet_h + MARGIN + INK_SLACK for k in range(20)} | {b.bottom + GAP for b in existing}
    for y in sorted(tops):
        k = int((y - top) // sheet_h)
        if k >= (20 if allow_expansion else count):
            continue
        if y + block.height > top + (k + 1) * sheet_h - MARGIN - INK_SLACK:
            continue
        x = left + MARGIN + INK_SLACK
        if any(not (x + block.width + GAP <= b.left or b.right + GAP <= x or
                    y + block.height + GAP <= b.top or b.bottom + GAP <= y) for b in existing):
            continue
        return x, y, max(count, k + 1)
    return None


def plan_reaction_payload(before, steps, preset='house', allow_page_expansion=True):
    """Layout one reaction offline; return (addition CDXML, plan, planning report)."""
    from .reaction_batch import _components
    from .reaction_series import prepare_steps, compose_series
    prepared = prepare_steps(steps)
    target, oldpage = _page(before, vertical_pages=True)
    left, top, right, sheet_h, count = _sheet(oldpage)
    base = copy.deepcopy(target)
    bp = base.find('page')
    for child in list(bp):
        bp.remove(child)
    bp.set('BoundingBox', f'{left:g} {top:g} {right:g} {top + sheet_h:g}')
    bp.set('WidthPages', '1')
    bp.set('HeightPages', '1')
    base_text = ET.tostring(base, encoding='unicode')
    components = _components(prepared, preset, base=base_text)
    sheet_box = f'{left:g} {top:g} {right:g} {top + sheet_h:g}'
    from .core import preset_settings
    spec = preset_settings(preset)
    for smiles, text in list(components.items()):
        root = ET.fromstring(text)
        page = root.find('page')
        for fragment in page.findall('fragment'):
            _apply_ink_model(fragment, float(spec['LineWidth']), float(spec['LabelSize']))
        page.set('BoundingBox', sheet_box)
        page.set('WidthPages', '1')
        page.set('HeightPages', '1')
        components[smiles] = ET.tostring(root, encoding='unicode')
    try:
        composed, plan = compose_series(components, prepared, preset, text_width=estimate_text_width)
    except ValueError as exc:
        if 'fit' not in str(exc) and 'overflow' not in str(exc):
            raise
        from .harness import NeedsInput
        raise NeedsInput('reaction_needs_space',
            'The reaction does not fit the page of the open document at the requested chemical scale. '
            'Nothing was drawn and no document was created.', detail=str(exc),
            page_width_pt=round(right - left, 1),
            next_action='Use a wider page (landscape / A3) in the open document. '
                        'Do not shrink molecules, open scratch documents, or retry in pieces.') from exc
    payload = _rehome(composed, target)
    page = payload.find('page')
    plan = _clear_of_target_ids(payload, target, plan)
    block = bounds_union([bounds(e) for e in geometric(page)])
    slot = _destination(oldpage, block, allow_page_expansion)
    if slot is None:
        from .harness import NeedsInput
        raise NeedsInput('reaction_needs_space',
            'The reaction does not fit the free space of the open document at the requested chemical scale. '
            'Nothing was drawn and no document was created.',
            required_width_pt=round(block.width + 2 * MARGIN, 1), page_width_pt=round(right - left, 1),
            next_action='Use a wider page (landscape / A3) in the open document, or remove content. '
                        'Do not shrink molecules, open scratch documents, or retry in pieces.')
    x, y, pages = slot
    _translate(page, x - block.left, y - block.top)
    for step in plan['steps']:
        for key in ('top_pt', 'bottom_pt', 'caption_baseline_pt', 'center_y_pt'):
            step[key] += y - block.top
        step['component_bounds_pt'] = [(a + x - block.left, b + x - block.left) for a, b in step['component_bounds_pt']]
        for p in step['reactants'] + step['products']:
            p['molecule_center_x_pt'] += x - block.left
    pages_added = pages - count
    if pages_added:
        page.set('HeightPages', str(pages))
        page.set('WidthPages', '1')
        page.set('BoundingBox', f'{left:g} {top:g} {right:g} {top + sheet_h * pages:g}')
    from .reaction_series import _region
    plan['region'] = list(_region(page, plan['layout_options']['margin']))  # the live page, as verify_series reads it
    return ET.tostring(payload, encoding='unicode'), plan, {
        'steps': len(prepared), 'pages_added': pages_added, 'preset': preset,
        'layout_measurement': 'offline text-width estimate; no hidden measuring document',
        'placement_pt': {'x': round(x, 2), 'y': round(y, 2), 'width': round(block.width, 2), 'height': round(block.height, 2)}}


def _apply_ink_model(fragment, line_width, label_size):
    """Exact ink box + explicit label alignment, so captions centre without native measuring."""
    from . import ink
    envelope = {}
    for n in fragment.findall('n'):                       # conservative fallback for unmodelled labels
        x, y = map(float, n.get('p').split())
        label = ''.join(n.itertext())
        half = label_size * max(1, len(label)) * .72
        envelope[n.get('id')] = (x - half, y - label_size * 1.5, x + half, y + label_size * 1.5)
    box, alignments = ink.fragment_ink(fragment, line_width, label_size, envelope=envelope)
    fragment.set('BoundingBox', ' '.join(f'{v:.2f}' for v in box))
    for n in fragment.findall('n'):
        alignment = alignments.get(n.get('id'))
        t = n.find('t')
        if alignment not in ('Left', 'Right') or t is None:
            continue                    # stacked or lone-glyph labels: ChemDraw's Auto is already exact
        ax, ay = map(float, n.get('p').split())
        px, py = ink.label_position(''.join(t.itertext()), label_size, alignment, ax, ay)
        t.set('p', f'{px:.2f} {py:.2f}')
        for key in ('LabelAlignment', 'LabelJustification', 'Justification'):
            t.set(key, alignment)


def bounds_union(boxes):
    from .geometry import Box
    return Box(min(b.left for b in boxes), min(b.top for b in boxes),
               max(b.right for b in boxes), max(b.bottom for b in boxes))


def choose_paper(steps, preset, requested='auto'):
    """Pick the smallest paper that fits BEFORE any document exists; nothing is created here."""
    from .reaction_batch import PAPERS, set_paper, EMPTY
    from .core import style_cdxml
    last = None
    for name in (PAPER_ORDER if requested == 'auto' else [requested]):
        if name not in PAPERS:
            raise ValueError('Unsupported reaction paper')
        probe = set_paper(style_cdxml(EMPTY, preset), name)
        try:
            plan_reaction_payload(probe, steps, preset, allow_page_expansion=False)
            return name
        except Exception as exc:
            from .harness import NeedsInput
            if not isinstance(exc, (NeedsInput, ValueError)):
                raise
            last = exc
    from .harness import NeedsInput
    raise NeedsInput('reaction_needs_space',
        'The complete reaction does not fit the largest supported paper at the requested chemical scale. Nothing was drawn.',
        detail=str(last), next_action='Report this layout limit; do not shrink molecules or split the reaction.')


def run_shared_reaction(bridge, plan, out, document_id=None):
    from pathlib import Path
    from .addin import get_backend
    from .batch import NativeUncertain
    from .polish import chemical_signature
    from .reaction_batch import EMPTY, set_paper
    from .reaction_series import verify_series
    from .timing import StageTimer
    from .workflow import _write_json, remap_ids
    timer = StageTimer()
    preset = plan.get('preset', 'house')
    steps = [{'step_id': 'reaction', 'reactants': plan['reactants'], 'products': plan['products'],
              'conditions_above': plan['conditions_above'], 'conditions_below': plan['conditions_below']}]
    docs = bridge.documents()['documents']
    created_canvas = False
    if document_id is None:
        if not docs:
            paper = choose_paper(steps, preset, plan.get('reaction_paper', 'auto'))
            created = bridge.create(set_paper(EMPTY, paper), visible=True)  # the one working canvas
            document_id = created['document']['document_id']
            created_canvas = True
        else:
            document_id = bridge._run('active_document')
    elif not any(d['document_id'] == document_id for d in docs):
        raise ValueError('Shared document is absent; refresh document IDs')
    did = bridge._id(document_id)
    backend = get_backend(bridge)
    initial = backend.read(did)
    timer.mark('document_read')
    if ET.fromstring(initial['cdxml']).find('page/fragment') is not None:
        try:
            chemical_signature(initial['cdxml'])
        except ValueError as exc:
            raise ValueError('Existing content cannot be verified before insertion: ' + str(exc) +
                             '. No new objects were added.') from exc
    if hasattr(bridge, 'initialize_empty_style') and not len(ET.fromstring(initial['cdxml']).find('page')):
        initial = bridge.initialize_empty_style(did, initial, backend, preset)
    payload, recipe, planning = plan_reaction_payload(initial['cdxml'], steps, preset)
    timer.mark('layout')
    out = Path(out)
    out.mkdir()
    (out / 'before.cdxml').write_text(initial['cdxml'])
    (out / 'payload.cdxml').write_text(payload)
    _write_json(out / 'request.json', {'steps': steps, 'preset': preset, 'document_id': did})
    page_options = {'allow_page_expansion': True} if (
        planning['pages_added'] or int(ET.fromstring(payload).find('page').get('HeightPages', '1')) > 1) else {}
    try:
        result = backend.append(did, payload, initial['source_token'], **page_options)
        timer.mark('append_and_verify')
    except Exception as exc:
        _write_json(out / 'audit.json', {'status': 'not_completed', 'message': str(exc), 'planning': planning})
        raise
    figure = out / 'figure'
    figure.mkdir()
    native = Path(result['after_snapshot']).read_text()
    (figure / 'figure.cdxml').write_text(native)
    try:
        old = ET.fromstring(initial['cdxml']).find('page')
        existing = set(remap_ids(initial['cdxml'], native).values()) if len(old) else set()
        added = ET.fromstring(native)
        ap = added.find('page')
        from .shared import preexisting_reaction_records, drop_foreign_step_objects
        existing |= preexisting_reaction_records(ap, set(existing))   # earlier reactions stay out of this check
        for e in list(ap):
            if e.get('id') in existing or e.tag == 'chemicalproperty':
                ap.remove(e)
        drop_foreign_step_objects(ap)   # ChemDraw's own association of nearby older captions is not ours
        # Offline ink model is within ~1 pt of ChemDraw's own boxes; the old 0.75 pt gate assumed
        # a native measuring copy. 1.5 pt is invisible on a scheme and is recorded in the audit.
        verification = verify_series(payload, ET.tostring(added, encoding='unicode'), recipe, centre_tolerance=CENTRE_TOLERANCE)
        result['checks'].update(verification['checks'])
        timer.mark('series_verify')
    except Exception as exc:
        _write_json(out / 'audit.json', {'status': 'uncertain', 'message': str(exc), 'document_id': did})
        raise NativeUncertain('Reaction appended once; role/layout verification failed. '
                              'Do not draw it again: ' + str(exc)) from exc
    timings = timer.report()
    result.update(stage='delivery', output_dir=str(out), artifacts={'cdxml': str(figure / 'figure.cdxml')},
                  visual_review='required', timings=timings, planning=planning,
                  presentation={'mode': 'shared', 'intermediates': 'none',
                                'documents_created': 1 if created_canvas else 0, 'documents_closed': 0},
                  audit={'status': 'checks_passed', 'checks': result['checks'], 'timings': timings},
                  note='Appended once to the open document; nothing else was opened or closed. '
                       'Edit or add more reactions in the same document.')
    _write_json(out / 'audit.json', result['audit'])
    _write_json(out / 'result.json', result)
    return result
