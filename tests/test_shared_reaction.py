"""Reactions go into the ONE open document: no scratch documents, no close, no clipboard."""
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytest.importorskip('rdkit')
from chemdraw_macos.addin import append_document, source_token
from chemdraw_macos.reaction_batch import set_paper
from chemdraw_macos.shared_reaction import plan_reaction_payload, choose_paper, estimate_text_width
from chemdraw_macos.polish import bounds, chemical_signature

EMPTY = ('<CDXML BondLength="14.4" LineWidth="0.6" LabelFont="3" LabelSize="10" CaptionFont="3" CaptionSize="10">'
         '<fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable>'
         '<page id="1" BoundingBox="0 0 523 770" WidthPages="1" HeightPages="1"/></CDXML>')

AMIDE = [{'step_id': 'reaction',
          'reactants': [{'compound_id': '1', 'label': '4-Fluorobenzoic acid', 'smiles': 'O=C(O)c1ccc(F)cc1'},
                        {'compound_id': '2', 'label': 'Benzylamine', 'smiles': 'NCc1ccccc1'}],
          'products': [{'compound_id': '3', 'label': 'Amide', 'smiles': 'O=C(NCc1ccccc1)c1ccc(F)cc1'}],
          'conditions_above': 'HATU, DIPEA', 'conditions_below': 'DMF, rt'}]
SUZUKI = [{'step_id': 'reaction',
           'reactants': [{'compound_id': '1', 'label': '4-Bromoanisole', 'smiles': 'COc1ccc(Br)cc1'},
                         {'compound_id': '2', 'label': 'Phenylboronic acid', 'smiles': 'OB(O)c1ccccc1'}],
           'products': [{'compound_id': '3', 'label': '4-Methoxybiphenyl', 'smiles': 'COc1ccc(-c2ccccc2)cc1'}],
           'conditions_above': 'Pd(dppf)Cl2, K2CO3', 'conditions_below': 'dioxane/H2O, 80 °C'}]


class Channel:
    """Stands in for the add-in: addCDXML returns the resulting document."""
    def request(self, op, **kw):
        assert op in ('read', 'append')
        if op == 'read':
            return {'cdxml': self.doc, 'version': '1.6'}
        self.writes += 1
        self.doc = kw['cdxml']
        return {'cdxml': self.doc}


class Bridge:
    lock = __import__('contextlib').nullcontext()
    def __init__(self, channel, tmp):
        self.channel, self.tmp, self.n = channel, tmp, 0
    def _id(self, d): return d
    def _run(self, op, *a):
        return 7 if op == 'active_document' else (7, 'x', False, None, None, None, None)[:1] + ()  # noqa
    def _new_path(self, suffix, category='scratch'):
        self.n += 1
        folder = self.tmp / category
        folder.mkdir(exist_ok=True)
        return folder / f'{self.n}{suffix}'
    def documents(self): return {'documents': [{'document_id': 7, 'file': None}]}


def landscape():
    return set_paper(EMPTY, 'A4 landscape')


def test_text_width_estimate_is_generous_for_capitals():
    assert estimate_text_width('HATU, DIPEA', 10) > 11 * 10 * .62   # caps average above lowercase


def test_amide_plans_on_one_landscape_sheet_with_one_arrow_and_scheme():
    payload, plan, report = plan_reaction_payload(landscape(), AMIDE)
    page = ET.fromstring(payload).find('page')
    assert [e.tag for e in page].count('arrow') == 1 and page.find('scheme/step') is not None
    assert report['layout_measurement'].startswith('offline')
    assert chemical_signature(payload) == sorted(['O=C(O)c1ccc(F)cc1', 'NCc1ccccc1', 'O=C(NCc1ccccc1)c1ccc(F)cc1'])


def test_does_not_fit_portrait_and_says_nothing_was_drawn():
    from chemdraw_macos.harness import NeedsInput
    with pytest.raises(NeedsInput) as e:
        plan_reaction_payload(EMPTY, AMIDE)
    assert e.value.code == 'reaction_needs_space' and 'Nothing was drawn' in str(e.value)


def test_paper_is_chosen_before_any_document_exists():
    assert choose_paper(AMIDE, 'house') == 'A4 landscape'


def merged(before, prepared):
    """What addCDXML does: add the supplied objects (and any new fonts) to the live document."""
    doc = ET.fromstring(before)
    new = ET.fromstring(prepared)
    for font in new.findall('fonttable/font'):
        table = doc.find('fonttable')
        if table is None:
            table = ET.SubElement(doc, 'fonttable')
        if table.find(f'font[@id="{font.get("id")}"]') is None:
            table.append(copy.deepcopy(font))
    page, incoming = doc.find('page'), new.find('page')
    for key in ('BoundingBox', 'WidthPages', 'HeightPages'):
        page.set(key, incoming.get(key, page.get(key)))
    for child in incoming:
        page.append(copy.deepcopy(child))
    return ET.tostring(doc, encoding='unicode')


def test_two_reactions_append_into_same_document_through_real_gates():
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    doc, writes = landscape(), 0
    for steps in (AMIDE, SUZUKI):
        before = doc
        payload, plan, _ = plan_reaction_payload(before, steps)
        prepared = prepare_payload(before, payload, allow_page_expansion=True)
        doc = merged(before, prepared)
        writes += 1
        verify_append(before, doc, prepared, exact_coordinates=True, allow_page_expansion=True)
    page = ET.fromstring(doc).find('page')
    assert writes == 2
    assert [e.tag for e in page].count('arrow') == 2
    assert len(page.findall('scheme')) == 2
    ids = {e.get('id') for e in page.iter() if e.get('id')}
    for s in page.findall('scheme/step'):         # step roles still address live objects after id remapping
        for key in ('ReactionStepReactants', 'ReactionStepProducts', 'ReactionStepArrows'):
            assert set(s.get(key).split()) <= ids
    rows = sorted(bounds(e).top for e in page if e.tag == 'arrow')
    assert rows[1] > rows[0] + 100                 # second reaction sits below the first
    assert len(chemical_signature(doc)) == 6


def _fake_native(tmp_path, start):
    """Backend + bridge that count every document operation and simulate addCDXML."""
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    log = {'create': 0, 'close': 0, 'append': 0}

    class Backend:
        doc = start
        def read(self, did):
            return {'cdxml': self.doc, 'source_token': source_token(self.doc)}
        def append(self, did, payload, token, **options):
            log['append'] += 1
            before = self.doc
            prepared = prepare_payload(before, payload, **options)
            self.doc = merged(before, prepared)
            checks = verify_append(before, self.doc, prepared, exact_coordinates=True, **options)
            path = tmp_path / f'after{log["append"]}.cdxml'
            path.write_text(self.doc)
            return {'status': 'completed', 'document': {'document_id': did}, 'after_snapshot': str(path),
                    'source_token': source_token(self.doc), 'checks': dict(checks)}

    backend = Backend()

    class FakeBridge:
        def _id(self, d): return d
        def documents(self): return {'documents': [{'document_id': 42, 'file': None}] if backend.doc else []}
        def _run(self, op, *a): assert op == 'active_document'; return 42
        def create(self, text, visible=True):
            log['create'] += 1
            backend.doc = text
            return {'document': {'document_id': 42}}
        def initialize_empty_style(self, did, initial, be, preset='house'):
            # What the real blank-canvas initialisation leaves in the document root.
            from chemdraw_macos.core import preset_settings
            spec = preset_settings(preset)
            root = ET.fromstring(be.doc)
            for key in ('BondLength', 'LineWidth', 'BoldWidth', 'LabelSize', 'CaptionSize'):
                root.set(key, spec[key])
            table = root.find('fonttable') if root.find('fonttable') is not None else ET.SubElement(root, 'fonttable')
            ET.SubElement(table, 'font', id='3', name=spec['font'], charset='Unicode')
            root.set('LabelFont', '3')
            root.set('CaptionFont', '3')
            be.doc = ET.tostring(root, encoding='unicode')
            return be.read(did)
        def close(self, *a): log['close'] += 1; raise AssertionError('no document may be closed')
    return backend, FakeBridge(), log


def _plan(steps):
    s = steps[0]
    return {'workflow': 'reaction', 'reactants': s['reactants'], 'products': s['products'], 'preset': 'house',
            'conditions_above': s['conditions_above'], 'conditions_below': s['conditions_below'],
            'reaction_paper': 'auto'}


def test_runner_creates_at_most_one_canvas_and_never_closes(tmp_path, monkeypatch):
    from chemdraw_macos import shared_reaction
    backend, bridge, log = _fake_native(tmp_path, None)
    monkeypatch.setattr('chemdraw_macos.addin.get_backend', lambda b: backend)
    first = shared_reaction.run_shared_reaction(bridge, _plan(AMIDE), tmp_path / 'one')
    second = shared_reaction.run_shared_reaction(bridge, _plan(SUZUKI), tmp_path / 'two')
    assert first['status'] == second['status'] == 'completed'
    assert log == {'create': 1, 'close': 0, 'append': 2}
    assert first['presentation']['documents_created'] == 1 and second['presentation']['documents_created'] == 0
    assert first['presentation']['documents_closed'] == 0
    assert first['checks']['explicit_step_roles'] is True
    assert len(ET.fromstring(backend.doc).findall('page/arrow')) == 2


def test_front_door_routes_reactions_to_shared_path(tmp_path, monkeypatch):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos import harness, shared
    seen = []
    monkeypatch.setattr(shared, 'run_shared', lambda *a, **k: seen.append(a[1]['workflow']) or {'status': 'completed'})
    bridge = object.__new__(Bridge)
    request = {'molecules': [{'format': 'smiles', 'value': 'CC(=O)O'}, {'format': 'smiles', 'value': 'NCc1ccccc1'}],
               'products': [{'format': 'smiles', 'value': 'CC(=O)NCc1ccccc1'}], 'conditions_above': 'HATU'}
    for mode in ('auto', 'interactive'):
        out = harness.run_drawing(bridge, request, str(tmp_path / mode), presentation=mode)
        assert out['status'] == 'completed'
    assert seen == ['reaction', 'reaction']


FIXTURE = Path(__file__).parent / 'fixtures' / 'native-reaction-append'


def test_real_chemdraw_second_reaction_append_passes_verification():
    """Evidence from a live ChemDraw 23 append (before / payload / after): ids of arrows and
    schemes are renumbered and every new arrow gains a companion graphic."""
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    before = (FIXTURE / 'before.cdxml').read_text()
    after = (FIXTURE / 'after.cdxml').read_text()
    prepared = prepare_payload(before, (FIXTURE / 'payload.cdxml').read_text())
    checks = verify_append(before, after, prepared, exact_coordinates=True)
    assert checks['existing_content_preserved'] and checks['added_chemistry_and_geometry_verified']


def test_real_chemdraw_third_row_with_native_step_association_passes():
    """Live evidence: with two earlier reactions in the document, ChemDraw attached an older
    caption (id 290) to the new step's above-arrow list. That inference is not ours to fail on,
    but every explicit role must still match."""
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    third = Path(__file__).parent / 'fixtures' / 'native-reaction-append-third'
    before = (third / 'before.cdxml').read_text()
    after = (third / 'after.cdxml').read_text()
    prepared = prepare_payload(before, (third / 'payload.cdxml').read_text())
    checks = verify_append(before, after, prepared, exact_coordinates=True)
    assert checks['native_inferred_step_objects'] == ['290']


def test_missing_explicit_role_is_still_caught_when_native_adds_objects():
    from chemdraw_macos.addin import prepare_payload
    from chemdraw_macos.shared import verify_append
    third = Path(__file__).parent / 'fixtures' / 'native-reaction-append-third'
    before = (third / 'before.cdxml').read_text()
    after = (third / 'after.cdxml').read_text()
    prepared = prepare_payload(before, (third / 'payload.cdxml').read_text())
    broken = ET.fromstring(after)
    step = broken.findall('page/scheme/step')[-1]
    step.set('ReactionStepProducts', '302')            # a product silently turned into a reactant
    with pytest.raises(ValueError, match='scheme'):
        verify_append(before, ET.tostring(broken, encoding='unicode'), prepared, exact_coordinates=True)


NITRO = [{'step_id': 'reaction',
          'reactants': [{'compound_id': '1', 'label': '4-Nitrotoluene', 'smiles': 'Cc1ccc([N+](=O)[O-])cc1'}],
          'products': [{'compound_id': '2', 'label': 'p-Toluidine', 'smiles': 'Cc1ccc(N)cc1'}],
          'conditions_above': 'SnCl2', 'conditions_below': 'EtOH, 80 °C'}]


def test_ink_never_touches_the_page_margin_even_for_charged_groups():
    """Live: a nitro group's ink landed 0.7 pt outside the 36 pt region at the exact margin."""
    payload, plan, _ = plan_reaction_payload(landscape(), NITRO)
    left, top, right, bottom = plan['region']
    page = ET.fromstring(payload).find('page')
    for e in page:
        if e.tag in ('fragment', 't', 'arrow'):
            b = bounds(e)
            assert b.left >= left + 1.5 and b.top >= top + 1.5 and b.right <= right - 1.5 and b.bottom <= bottom - 1.5


def test_fresh_canvas_with_small_page_id_does_not_collide():
    """Live: a new blank document had page id 8 and font id 59; composer ids started at 2."""
    from chemdraw_macos.addin import prepare_payload
    blank = set_paper(EMPTY, 'A4 landscape').replace('<page id="1"', '<page id="8"').replace('<font id="3"', '<font id="59"')
    payload, plan, _ = plan_reaction_payload(blank, AMIDE)
    prepare_payload(blank, payload)                       # no duplicate-id rejection
    page = ET.fromstring(payload).find('page')
    ids = [int(e.get('id')) for e in page.iter() if e is not page and e.get('id')]
    assert min(ids) > 59
    step = page.find('scheme/step')                       # references moved with the ids
    assert set(step.get('ReactionStepArrows').split()) <= {e.get('id') for e in page}
    assert plan['steps'][0]['arrow_id'] == step.get('ReactionStepArrows')
