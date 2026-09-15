import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.scope_job import plan_scope_job, build_scope_job, arrange_scope_groups
from chemdraw_macos.scope import prepare_scope, arrange_scope, verify_scope
from chemdraw_macos.polish import chemical_signature
from chemdraw_macos.batch import NativeUncertain
from test_scope import measured, CELLS
from test_polish import SAMPLE
from test_batch import BatchBridge


JOB = {'schema_version':1,'parent_smiles':'CC(=O)[c:1]1ccccc1','handle_atom_map':1,
       'groups':[{'label':'Reference','categories':['reference']},
                 {'label':'Donors','categories':['electron_donating']},
                 {'label':'Withdrawers','categories':['electron_withdrawing','halogen']},
                 {'label':'Bulky / positional','categories':['steric','positional']}],
       'accept_all':True,'columns':4}


def test_complete_plan_retains_memberships_and_null_yields():
    plan = plan_scope_job(JOB)
    assert plan['selection_required'] is False and plan['selected_count'] == 14
    assert len(plan['structures']) == 14
    assert [g['label'] for g in plan['groups']] == [g['label'] for g in JOB['groups']]
    assert len({c['candidate_id'] for c in plan['selected_candidates']}) == 14
    para = next(c for c in plan['selected_candidates'] if c['display_label']=='4-Me relative to parent')
    assert para['assigned_group']=='Donors' and 'positional' in para['secondary_categories']
    assert all(c['yield_percent'] is None for c in plan['selected_candidates'])
    assert plan['scaffold_smiles']=='CC(=O)c1ccccc1'
    assert plan == plan_scope_job(JOB)
    json.dumps(plan,allow_nan=False)


def test_offline_preview_requires_explicit_build_selection(tmp_path):
    job = {k:v for k,v in JOB.items() if k!='accept_all'}
    assert plan_scope_job(job)['selection_required'] is True
    class NoNative:
        def __getattr__(self,name):pytest.fail('Native accessed before selection')
    with pytest.raises(ValueError,match='selection|accept_all'):
        build_scope_job(NoNative(),job,str(tmp_path/'out'))
    assert not (tmp_path/'out').exists()


def test_explicit_selection_is_exact_and_order_comes_from_groups():
    proposal = plan_scope_job(JOB)['proposal']['candidates']
    selected = [proposal[4]['candidate_id'],proposal[0]['candidate_id']]
    job = {k:v for k,v in JOB.items() if k!='accept_all'};job['selected_candidate_ids'] = selected
    plan = plan_scope_job(job)
    assert plan['selected_count']==2
    assert {c['candidate_id'] for c in plan['selected_candidates']}==set(selected)
    assert len(plan['groups'])==2


@pytest.mark.parametrize('change', [
    {'selected_candidate_ids':['unknown']}, {'accept_all':'yes'}, {'columns':True},
    {'groups':[]}, {'groups':[{'label':'Only donors','categories':['electron_donating']}]},
    {'groups':[{'label':'Unknown','categories':['imagined']}]},
    {'yield_percent':95}, {'frame':'yes'}, {'pixels':True},
])
def test_invalid_jobs_rejected(change):
    with pytest.raises(ValueError):plan_scope_job({**JOB,**change})


def test_duplicate_selected_ids_are_rejected():
    cid = plan_scope_job(JOB)['selected_candidates'][0]['candidate_id']
    job = {k:v for k,v in JOB.items() if k!='accept_all'};job['selected_candidate_ids']=[cid,cid]
    with pytest.raises(ValueError):plan_scope_job(job)


def measured_scope():
    prepared,state = prepare_scope(SAMPLE,CELLS)
    text,plan = arrange_scope(measured(prepared),state['cells'],columns=2)
    return measured(text),plan['cells']


def test_groups_get_real_separate_rows_and_remain_chemically_identical():
    text,cells = measured_scope()
    groups = [{'label':'First','compound_ids':['3a']},{'label':'Second','compound_ids':['3b']}]
    arranged,plan = arrange_scope_groups(text,cells,groups,columns=2)
    assert chemical_signature(arranged)==chemical_signature(text)
    assert plan['layout']['cells'][0]['structure_center_y'] < plan['layout']['cells'][1]['structure_center_y']
    assert len(plan['decoration_groups'])==2
    assert plan['layout']['rows']==2
    assert [c['row'] for c in plan['layout']['cells']]==[0,1]
    assert verify_scope(arranged,measured(arranged),plan['layout'])['checks']['caption_alignment']


def fake_draw(monkeypatch,b,tmp_path):
    text,cells = measured_scope()
    def draw(bridge,structures,output_dir,**kwargs):
        assert kwargs['scaffold_smiles']=='CC(=O)c1ccccc1'
        assert kwargs['layout']=={'h_gap':18.,'v_gap':24.,'label_gap':10.,'margin':48.}
        folder=Path(output_dir);folder.mkdir()
        # The fake tests lifecycle only; portable layout uses known measured fixture graphs.
        actual=copy.deepcopy(cells)
        for c,r in zip(actual,structures):
            c['compound_id']=r['compound_id'];c['yield_percent']=None
        root=ET.fromstring(text)
        for c in actual:root.find(f'page/t[@id="{c["metadata_id"]}"]/s').text=c['compound_id']
        native=measured(ET.tostring(root,encoding='unicode'));result=b.create(native)
        return {**result,'audit':{'grid_audit':{'verification':{'cells':actual}}}}
    monkeypatch.setattr('chemdraw_macos.scope_job.draw_structures',draw)


def small_job():
    candidates = plan_scope_job(JOB)['proposal']['candidates']
    chosen = [candidates[0]['candidate_id'], next(c['candidate_id'] for c in candidates if 'electron_donating' in c['categories'])]
    return {**{k:v for k,v in JOB.items() if k!='accept_all'},'selected_candidate_ids':chosen,'columns':2}


def test_job_runs_draw_group_layout_and_decoration_to_visible_output(tmp_path,monkeypatch):
    b=BatchBridge(tmp_path/'work');fake_draw(monkeypatch,b,tmp_path)
    result=build_scope_job(b,small_job(),str(tmp_path/'job'))
    assert result['audit']['status']=='checks_passed'
    assert (tmp_path/'job/review.html').exists()
    assert (tmp_path/'job/figure/figure.cdxml').exists()
    assert len(b.managed)==1 and b.docs[1]==SAMPLE
    assert result['audit']['checks']['group_bands_verified']


def test_job_uncertainty_never_closes_or_retries_owned_documents(tmp_path,monkeypatch):
    b=BatchBridge(tmp_path/'work');fake_draw(monkeypatch,b,tmp_path)
    def fail(*args,**kwargs):raise NativeUncertain('uncertain decoration')
    monkeypatch.setattr('chemdraw_macos.scope_job.decorate_scope_document',fail)
    with pytest.raises(NativeUncertain):build_scope_job(b,small_job(),str(tmp_path/'job'))
    assert not any(e[0]=='close' for e in b.events)
    assert json.loads((tmp_path/'job/audit.json').read_text())['status']=='uncertain'


def test_layout_overrides_are_validated_and_used():
    spacing={'h_gap':25,'v_gap':30,'label_gap':12,'margin':40}
    job={**JOB,'layout':spacing}
    assert plan_scope_job(job)['layout']==spacing
    text,cells=measured_scope()
    groups=[{'label':'Both','compound_ids':['3a','3b']}]
    _,plan=arrange_scope_groups(text,cells,groups,2,spacing)
    assert plan['layout']['h_gap']==25 and plan['layout']['margin']==40
    assert plan['layout']['v_gap']==30
    for bad in ({'h_gap':True},{'margin':0},{'label_gap':float('nan')},{'magic':1}):
        with pytest.raises(ValueError):plan_scope_job({**JOB,'layout':bad})
