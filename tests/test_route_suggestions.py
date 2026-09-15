import copy
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import plan_annotations
from chemdraw_macos.editing import source_token
from chemdraw_macos.route_suggestions import suggest_routes, select_route, annotate_selected_route_document, annotate_selected_route_file
from chemdraw_macos.symbols import plan_symbols
from test_batch import BatchBridge
from test_polish import SAMPLE as PLAIN_SAMPLE

SAMPLE,_ = plan_symbols(PLAIN_SAMPLE,[{'key':'oxygen-pair','kind':'lone_pair','atom_id':'3'}])
SOURCE = {'kind':'symbol','id':ET.fromstring(SAMPLE).find('page/fragment/graphic').get('id')}
TARGET = {'kind':'atom','id':'21'}


def test_suggestions_are_bounded_ranked_unselected_and_usable_by_annotations():
    report = suggest_routes(SAMPLE,SOURCE,TARGET,max_candidates=3)
    assert report['status'] == 'suggestions' and 1 <= len(report['candidates']) <= 3
    assert report['source_token'] == source_token(SAMPLE) and report['selection_required']
    assert report['evaluated_candidates'] <= 24 and report['selected_candidate'] is None
    assert [c['score'] for c in report['candidates']] == sorted(c['score'] for c in report['candidates'])
    for candidate in report['candidates']:
        assert candidate['minimum_clearance_pt'] >= 2
        assert candidate['collision_check']['curve_approximation_error_bound_pt'] >= 0
        assert candidate['collision_check']['obstacle_counts']['labels'] == 4
        assert len(plan_annotations(SAMPLE,[candidate['arrow']])[1]['arrows']) == 1


def test_measured_caption_barrier_changes_route_and_fully_blocked_is_honest():
    ordinary = suggest_routes(SAMPLE,SOURCE,TARGET)
    root = ET.fromstring(SAMPLE); page = root.find('page')
    t = ET.SubElement(page,'t',{'id':'901','p':'150 25','BoundingBox':'85 0 230 85'})
    ET.SubElement(t,'s',{'font':'3','size':'10'}).text = 'Obstacle'
    blocked_above = ET.tostring(root,encoding='unicode')
    report = suggest_routes(blocked_above,SOURCE,TARGET)
    assert report['candidates'] and report['rejected_candidates'] > ordinary['rejected_candidates']
    t.set('BoundingBox','0 0 540 720')
    report = suggest_routes(ET.tostring(root,encoding='unicode'),SOURCE,TARGET)
    assert report['status'] == 'no_route' and report['candidates'] == []
    assert report['selected_candidate'] is None


def test_symbol_source_and_bond_source_respect_explicit_electron_kind():
    dotted,_ = plan_symbols(PLAIN_SAMPLE,[{'key':'dot','kind':'electron','atom_id':'3'}])
    dot = ET.fromstring(dotted).find('page/fragment/graphic').get('id')
    report = suggest_routes(dotted,{'kind':'symbol','id':dot},TARGET,electrons=1)
    assert report['candidates']
    assert all(c['arrow']['source'] == {'kind':'symbol','id':dot} for c in report['candidates'])
    with pytest.raises(ValueError): suggest_routes(dotted,{'kind':'symbol','id':dot},TARGET,electrons=2)
    report = suggest_routes(SAMPLE,{'kind':'bond','id':'4'},TARGET)
    assert report['candidates'] and report['intentional_contact_exceptions']


@pytest.mark.parametrize('kwargs', [{'electrons':True},{'electrons':3},{'max_candidates':0},
    {'max_candidates':11},{'clearance':0},{'clearance':float('nan')},{'line_width':0},
    {'fishhook_side':'right'},{'electrons':1,'fishhook_side':'bad'}])
def test_invalid_bounds_and_electron_kind_rejected(kwargs):
    with pytest.raises(ValueError): suggest_routes(SAMPLE,SOURCE,TARGET,**kwargs)


def test_missing_measured_geometry_wrong_ids_and_unexpected_endpoint_fields_rejected():
    with pytest.raises(ValueError): suggest_routes(SAMPLE.replace('BoundingBox="55 40 68 50"',''),SOURCE,TARGET)
    with pytest.raises(ValueError): suggest_routes(SAMPLE,{'kind':'atom','id':'999'},TARGET)
    with pytest.raises(ValueError): suggest_routes(SAMPLE,{**SOURCE,'offset':[0,-10]},TARGET)


def test_selection_checks_token_and_rejects_tampered_geometry():
    report = suggest_routes(SAMPLE,SOURCE,TARGET)
    selected = report['candidates'][0]
    assert select_route(report,selected['candidate_id'],SAMPLE) == selected['arrow']
    with pytest.raises(ValueError,match='stale'):
        select_route(report,selected['candidate_id'],SAMPLE.replace('30 45','31 45'))
    tampered = copy.deepcopy(report); tampered['candidates'][0]['arrow']['controls'][0][0] += 10
    with pytest.raises(ValueError,match='changed|tampered'):
        select_route(tampered,selected['candidate_id'],SAMPLE)


def test_explicit_selection_calls_existing_annotation_copy_workflow(tmp_path):
    bridge = BatchBridge(tmp_path/'work'); bridge.docs[1] = SAMPLE
    report = suggest_routes(SAMPLE,SOURCE,TARGET)
    result = annotate_selected_route_document(bridge,1,str(tmp_path/'out'),report,report['candidates'][0]['candidate_id'])
    assert result['audit']['status'] == 'checks_passed' and bridge.docs[1] == SAMPLE
    assert result['audit']['route_selection']['candidate_id'] == report['candidates'][0]['candidate_id']
    assert len(bridge.managed) == 1


def test_selected_file_route_retains_original_selection_and_native_id_mapping(tmp_path):
    path = tmp_path/'source.cdxml'; path.write_text(SAMPLE)
    bridge = BatchBridge(tmp_path/'work'); create = bridge.create
    def renumber(text):
        root = ET.fromstring(text)
        for e in root.find('page').iter():
            for key in ('id','B','E','object'):
                if e.get(key): e.set(key,str(int(e.get(key))+1000))
        return create(ET.tostring(root,encoding='unicode'))
    bridge.create = renumber
    report = suggest_routes(SAMPLE,SOURCE,TARGET)
    chosen = report['candidates'][0]
    result = annotate_selected_route_file(bridge,str(path),str(tmp_path/'out'),report,chosen['candidate_id'])
    selection = result['audit']['route_selection']
    assert selection['source_arrow'] == chosen['arrow']
    assert selection['native_planned_arrow']['source']['id'] == str(int(SOURCE['id'])+1000)
    assert selection['native_curve_id'] in {c.get('id') for c in ET.parse(tmp_path/'out/figure.cdxml').findall('page/curve')}
    assert (tmp_path/'out/route-suggestions.json').is_file()
    assert path.read_text() == SAMPLE and len(bridge.managed) == 1


def test_selected_file_route_rejects_stale_before_native_creation(tmp_path):
    path = tmp_path/'source.cdxml'; path.write_text(SAMPLE.replace('30 45','31 45'))
    bridge = BatchBridge(tmp_path/'work')
    report = suggest_routes(SAMPLE,SOURCE,TARGET)
    with pytest.raises(ValueError,match='stale'):
        annotate_selected_route_file(bridge,str(path),str(tmp_path/'out'),report,report['candidates'][0]['candidate_id'])
    assert bridge.events == [] and not (tmp_path/'out').exists()
