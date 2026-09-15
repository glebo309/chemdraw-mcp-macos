import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import plan_annotations
from chemdraw_macos.batch import NativeUncertain
from chemdraw_macos.editing import source_token
from chemdraw_macos.ownership import (
    build_ownership, plan_move, move_document, move_file, plan_native_groups,
)
from chemdraw_macos.polish import numbers
from chemdraw_macos.symbols import plan_symbols, verify_symbols
from test_batch import BatchBridge
from test_polish import SAMPLE

OWNERS = [dict(key='a', fragment_ids=['1'], caption_ids=['10']),
          dict(key='b', fragment_ids=['20'], caption_ids=['30'])]
MOVE = [dict(owner_key='a', delta=[15, 20])]


def lone_pair_source():
    text,_ = plan_symbols(SAMPLE,[dict(key='oxygen-pair',kind='lone_pair',atom_id='3')])
    sid = ET.fromstring(text).find('page/fragment/graphic').get('id')
    return text,dict(kind='symbol',id=sid)


def test_move_translates_only_explicit_owner_and_retains_source():
    state = build_ownership(SAMPLE, OWNERS)
    frozen = copy.deepcopy(state)
    planned, after, audit = plan_move(SAMPLE, state, MOVE)
    root = ET.fromstring(planned)
    assert numbers(root.find('.//n[@id="2"]').get('p'), 2) == (45, 65)
    assert numbers(root.find('.//t[@id="10"]').get('p'), 2) == (64, 120)
    assert numbers(root.find('.//n[@id="21"]').get('p'), 2) == (260, 115)
    assert state == frozen and after['source_token'] == source_token(planned)
    assert audit['checks']['planned_chemistry_preserved']
    assert audit['native_manual_drag_attachment'] == 'not_verified'


@pytest.mark.parametrize('owners', [OWNERS[:1], OWNERS + OWNERS[:1],
    [dict(key='a', fragment_ids=['1'], caption_ids=['30']), OWNERS[1]]])
def test_incomplete_duplicate_ownership_rejected(owners):
    with pytest.raises(ValueError): build_ownership(SAMPLE, owners)


def test_stale_and_unbounded_moves_fail_without_mutation():
    state = build_ownership(SAMPLE, OWNERS)
    with pytest.raises(ValueError, match='stale'): plan_move(SAMPLE + ' ', {**state, 'source_token':'bad'}, MOVE)
    for delta in ([0, 0], [True, 1], [float('nan'), 0], [501, 0], [-100, 0]):
        with pytest.raises(ValueError): plan_move(SAMPLE, state, [dict(owner_key='a', delta=delta)])


def test_owned_lone_pair_and_internal_curve_follow_molecule():
    dotted, _ = plan_symbols(SAMPLE, [dict(key='pair', kind='lone_pair', atom_id='3')])
    dot = ET.fromstring(dotted).find('page/fragment/graphic')
    arrow = dict(key='local', electrons=2, source=dict(kind='symbol', id=dot.get('id')),
                 target=dict(kind='atom', id='2', offset=[0, -5]), controls=[[0, -20], [0, -20]])
    text, added = plan_annotations(dotted, [arrow])
    curves = [dict(curve_id=added['arrows'][0]['curve_id'],
                   source=dict(kind='symbol', id=dot.get('id')), target=dict(kind='atom', id='2'))]
    state = build_ownership(text, OWNERS, curves)
    planned, _, _ = plan_move(text, state, MOVE)
    before_root, after_root = ET.fromstring(text), ET.fromstring(planned)
    old = numbers(before_root.find('page/curve').get('CurvePoints'))
    new = numbers(after_root.find('page/curve').get('CurvePoints'))
    assert list(new) == pytest.approx([v + (15 if i % 2 == 0 else 20) for i, v in enumerate(old)])
    assert numbers(after_root.find('page/fragment/graphic').get('BoundingBox')) == pytest.approx(
        [v + (15 if i % 2 == 0 else 20) for i, v in enumerate(numbers(dot.get('BoundingBox')))])


def test_cross_owner_curve_rejects_partial_move_but_accepts_joint_translation():
    dotted,donor = lone_pair_source()
    arrow = dict(key='cross', electrons=2, source=donor,
                 target=dict(kind='atom', id='21', offset=[0, -5]), controls=[[0, -20], [0, -20]])
    text, plan = plan_annotations(dotted, [arrow])
    with pytest.raises(ValueError, match='curve'): build_ownership(text, OWNERS)
    state = build_ownership(text, OWNERS, [dict(curve_id=plan['arrows'][0]['curve_id'],
        source=donor, target=dict(kind='atom', id='21'))])
    with pytest.raises(ValueError, match='Cross-owner'): plan_move(text, state, MOVE)
    moved, _, _ = plan_move(text, state, MOVE + [dict(owner_key='b', delta=[15,20])])
    old_points=numbers(ET.fromstring(text).find('page/curve').get('CurvePoints'))
    assert numbers(ET.fromstring(moved).find('page/curve').get('CurvePoints')) == pytest.approx(
        [v+(15 if i%2==0 else 20) for i,v in enumerate(old_points)])


def test_native_group_probe_is_exact_and_does_not_claim_manual_attachment():
    state = build_ownership(SAMPLE, OWNERS)
    grouped, report = plan_native_groups(SAMPLE, state)
    root = ET.fromstring(grouped)
    groups = root.findall('page/group')
    assert len(groups) == 2 and all(g.get('Integral') == 'yes' for g in groups)
    assert [[e.get('id') for e in g] for g in groups] == [['1','10'], ['20','30']]
    assert report['native_manual_drag_attachment'] == 'not_verified'
    for group in groups:
        for child in list(group): root.find('page').append(child)
        root.find('page').remove(group)
    verify_symbols(SAMPLE, ET.tostring(root, encoding='unicode'))


def test_native_group_probe_keeps_cross_owner_curves_outside_both_groups():
    dotted,donor = lone_pair_source()
    arrows = [dict(key='local',electrons=2,source=donor,
                   target=dict(kind='atom',id='2',offset=[0,-5]),controls=[[0,-20],[0,-20]]),
              dict(key='cross',electrons=2,source=donor,
                   target=dict(kind='atom',id='21',offset=[0,-5]),controls=[[0,-20],[0,-20]])]
    text, added = plan_annotations(dotted,arrows)
    curves = [dict(curve_id=p['curve_id'],source={'kind':a['source']['kind'],'id':a['source']['id']},
                   target={'kind':a['target']['kind'],'id':a['target']['id']}) for a,p in zip(arrows,added['arrows'])]
    state = build_ownership(text,OWNERS,curves)
    original = copy.deepcopy(state)
    grouped, report = plan_native_groups(text,state)
    root = ET.fromstring(grouped)
    assert root.find('page/group/curve').get('id') == curves[0]['curve_id']
    assert root.find('page/curve').get('id') == curves[1]['curve_id']
    assert report['ungrouped_cross_owner_curve_ids'] == [curves[1]['curve_id']]
    assert state == original


def test_document_move_and_persistent_sidecar(tmp_path):
    bridge = BatchBridge(tmp_path/'work')
    state = build_ownership(SAMPLE, OWNERS)
    result = move_document(bridge, 1, str(tmp_path/'out'), state, MOVE, source_token(SAMPLE))
    assert result['audit']['status'] == 'checks_passed' and bridge.docs[1] == SAMPLE
    sidecar = json.loads((tmp_path/'out/ownership.json').read_text())
    assert sidecar['source_token'] == source_token((tmp_path/'out/figure.cdxml').read_text())
    assert result['ownership'] == sidecar and len(bridge.managed) == 1


def test_final_render_mutation_fails_and_uncertainty_never_closes(tmp_path):
    for uncertain in (False, True):
        bridge = BatchBridge(tmp_path/f'work{uncertain}'); export = bridge.export
        def change(did, path, fmt, pixels=3200):
            if Path(path).name == 'figure.png':
                if uncertain: raise RuntimeError('timeout')
                bridge.docs[did] = bridge.docs[did].replace('45.000000 65.000000', '46 65')
            return export(did, path, fmt, pixels)
        bridge.export = change
        with pytest.raises(NativeUncertain if uncertain else ValueError):
            move_document(bridge, 1, str(tmp_path/f'out{uncertain}'), build_ownership(SAMPLE,OWNERS), MOVE, source_token(SAMPLE))
        assert bridge.docs[1] == SAMPLE
        if uncertain: assert not any(e[0] == 'close' for e in bridge.events)


def test_file_move_uses_frozen_source_and_remaps_sidecar(tmp_path):
    path = tmp_path/'source.cdxml'; path.write_text(SAMPLE)
    bridge = BatchBridge(tmp_path/'work'); create = bridge.create
    def renumber(text):
        root = ET.fromstring(text)
        for e in root.find('page').iter():
            for name in ('id','B','E'):
                if e.get(name): e.set(name, str(int(e.get(name))+1000))
        return create(ET.tostring(root, encoding='unicode'))
    bridge.create = renumber
    result = move_file(bridge, str(path), str(tmp_path/'out'), build_ownership(SAMPLE,OWNERS), MOVE)
    assert path.read_text() == SAMPLE and len(bridge.managed) == 1
    assert result['ownership']['owners'][0]['fragment_ids'] == ['2001']


def test_scheme_vertical_move_rejected_before_creating_native_copy(tmp_path):
    # Native v0.9 regression: moving bromide/substrate down 30 pt caused
    # ChemDraw to remove ReactionStepReactants, not merely renumber its IDs.
    text = (Path(__file__).parents[1]/'examples/sn2-annotation-input.cdxml').read_text()
    owners = [dict(key=key,fragment_ids=[fid],caption_ids=[tid]) for key,fid,tid in
              [('bromide','1001','970'),('substrate','2002','971'),('product','3003','972'),('iodide','4004','973')]]
    state = build_ownership(text,owners)
    path = tmp_path/'source.cdxml'; path.write_text(text)
    bridge = BatchBridge(tmp_path/'work')
    with pytest.raises(ValueError,match='vertical.*reaction scheme'):
        move_file(bridge,str(path),str(tmp_path/'out'),state,
                  [dict(owner_key='bromide',delta=[0,30]),dict(owner_key='substrate',delta=[0,30])])
    assert bridge.events == [] and path.read_text() == text and not (tmp_path/'out').exists()
    # A horizontal move retains all declared roles in its plan. Native saving
    # must still independently retain them, otherwise production fails closed.
    planned,_,_ = plan_move(text,state,[dict(owner_key='bromide',delta=[10,0])])
    assert ET.fromstring(planned).find('page/scheme/step').attrib == ET.fromstring(text).find('page/scheme/step').attrib
