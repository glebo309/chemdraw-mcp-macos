import asyncio
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import plan_annotations, verify_annotations, annotate_document, annotation_inventory
from chemdraw_macos.editing import source_token
from test_batch import BatchBridge

SOURCE=(Path(__file__).parents[1]/'examples/sn2-annotation-input.cdxml').read_text()
ARROWS=[
    {'key':'attack','electrons':2,'source':{'kind':'symbol','id':'1500'},
     'target':{'kind':'atom','id':'2103','offset':[0,-14]},'controls':[[0,-33],[0,-28]]},
    {'key':'leaving','electrons':2,'source':{'kind':'bond','id':'2105','offset':[0,1]},
     'target':{'kind':'atom','id':'2104','offset':[4,13]},'controls':[[-5,26],[8,14]]},
]
# Bond-source head-rendering fixtures, not alternative SN2 mechanisms. A
# circled negative charge represents a pair and cannot be changed into a 1e donor.
HEAD_RENDER_ARROWS=[copy.deepcopy(ARROWS[1]),
    {'key':'product-bond-render','electrons':2,'source':{'kind':'bond','id':'3111','offset':[0,0]},
     'target':{'kind':'atom','id':'3110','offset':[4,13]},'controls':[[-5,26],[8,14]]}]


def test_sn2_fixture_uses_the_displayed_donor_not_the_atom_label():
    assert ARROWS[0]['source'] == {'kind':'symbol','id':'1500'}
    assert ARROWS[1]['source']['kind'] == 'bond'


def test_sn2_planning_matches_existing_native_reference():
    planned,audit=plan_annotations(SOURCE,ARROWS)
    curves=ET.fromstring(planned).find('page').findall('curve')
    assert len(curves)==2
    # Existing CircleMinus: centre (42.7,86), 10.5 pt handle, 2 pt native
    # LineWidth. Its calibrated outer radius is 10.5*4/9 + 0.8*2.
    tail_y=86-(10.5*4/9+0.8*2)
    expected=[[42.7,tail_y,42.7,tail_y,42.7,tail_y-33,116.28,58,116.28,86,116.28,86],
              [125.28,101,125.28,101,120.28,127,146.28,127,138.28,113,138.28,113]]
    for c,pts in zip(curves,expected):
        assert list(map(float,c.get('CurvePoints').split()))==pytest.approx(pts)
        assert c.get('ArrowheadHead')=='Full' and float(c.get('LineWidth'))==.9
    assert audit['arrows'][0]['source']=={'kind':'symbol','id':'1500'}
    assert len(ET.fromstring(planned).findall('.//graphic[@SymbolType="CircleMinus"]'))==2


def test_fishhook_has_single_electron_head():
    arrows=copy.deepcopy(HEAD_RENDER_ARROWS[:1]);arrows[0]['electrons']=1;arrows[0]['fishhook_side']='right'
    planned,_=plan_annotations(SOURCE,arrows)
    curve=ET.fromstring(planned).find('page/curve')
    assert curve.get('ArrowheadHead')=='HalfRight' and curve.get('CurveType')=='32'
    assert verify_annotations(planned,planned)['checks']['curve_geometry_preserved']


@pytest.mark.parametrize('field,value',[('electrons',True),('electrons',3),('controls',[[0,float('nan')],[0,2]]),('fishhook_side','up'),('other',7)])
def test_invalid_arrows_fail_before_planning(field,value):
    arrows=copy.deepcopy(ARROWS);arrows[0][field]=value
    with pytest.raises(ValueError):plan_annotations(SOURCE,arrows)


def test_missing_source_wrong_kind_and_label_collision_rejected():
    for ref in ({'kind':'atom','id':'9999','offset':[0,0]}, {'kind':'bond','id':'1100','offset':[0,0]}, {'kind':'atom','id':'1100','offset':[0,0]}):
        arrows=copy.deepcopy(ARROWS);arrows[0]['source']=ref
        with pytest.raises(ValueError):plan_annotations(SOURCE,arrows)
    arrows=copy.deepcopy(ARROWS);arrows[0]['target']={'kind':'atom','id':'2103','offset':[0,0]}
    with pytest.raises(ValueError,match='label'):plan_annotations(SOURCE,arrows)


def test_native_changed_head_points_or_charge_symbol_rejected():
    planned,_=plan_annotations(SOURCE,ARROWS)
    for kind in ('head','points','charge'):
        r=ET.fromstring(planned)
        if kind=='head':r.find('page/curve').set('ArrowheadHead','HalfLeft')
        elif kind=='points':r.find('page/curve').set('CurvePoints','0 0 '*6)
        else:r.find('.//graphic[@SymbolType="CircleMinus"]').set('LineWidth','.2')
        with pytest.raises(ValueError):verify_annotations(planned,ET.tostring(r,encoding='unicode'))


def test_existing_curves_retained_and_duplicate_keys_rejected():
    before,_=plan_annotations(SOURCE,ARROWS[:1])
    planned,_=plan_annotations(before,ARROWS[1:])
    assert len(ET.fromstring(planned).findall('page/curve'))==2
    with pytest.raises(ValueError):plan_annotations(SOURCE,[ARROWS[0],ARROWS[0]])


def test_document_workflow_preserves_source_and_emits_native_artifacts(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=SOURCE
    r=annotate_document(b,1,str(tmp_path/'out'),ARROWS,source_token(SOURCE))
    assert b.docs[1]==SOURCE and all(r['audit']['checks'].values())
    assert r['audit']['visual_review']=='required'
    assert r['document']['document_id'] in b.managed
    for f in ('before.cdxml','before.svg','before.png','figure.cdxml','figure.svg','figure.png','recipe.json','audit.json','review.html'):
        assert (tmp_path/'out'/f).is_file()


def test_stale_token_rejected_before_creating_document(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=SOURCE
    with pytest.raises(ValueError,match='stale'):annotate_document(b,1,str(tmp_path/'out'),ARROWS,'stale')
    assert not any(e[0]=='create' for e in b.events)


def test_uncertain_export_does_not_retry_or_close(tmp_path):
    b=BatchBridge(tmp_path/'work');b.docs[1]=SOURCE;old=b.export
    def fail(did,path,format,pixels=3200):
        if Path(path).name=='figure.svg':raise RuntimeError('timeout')
        return old(did,path,format,pixels)
    b.export=fail
    with pytest.raises(RuntimeError):annotate_document(b,1,str(tmp_path/'out'),ARROWS,source_token(SOURCE))
    assert len(b.managed)==1 and not any(e[0]=='close' for e in b.events)
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='uncertain'


def test_inventory_cli_and_mcp_callable(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import cli
    from chemdraw_macos.server import mcp
    info=annotation_inventory(SOURCE)
    assert any(a['id']=='1100' for a in info['atoms'])
    assert {'chemdraw_annotate_document','chemdraw_inspect_annotations'}<={t.name for t in asyncio.run(mcp.list_tools())}
    b=BatchBridge(tmp_path/'work');b.docs[1]=SOURCE
    monkeypatch.setattr(cli,'Bridge',lambda:b)
    path=tmp_path/'recipe.json';path.write_text(json.dumps({'arrows':ARROWS,'expected_source_token':source_token(SOURCE)}))
    assert cli.main(['annotate','--document','1','--recipe',str(path),'--output',str(tmp_path/'out')])==0
    assert json.loads(capsys.readouterr().out)['audit']['checks']['curve_geometry_preserved']


def test_file_annotation_rejects_existing_output_before_native_calls(tmp_path):
    from chemdraw_macos.annotations import annotate_file
    path=tmp_path/'source.cdxml';path.write_text(SOURCE);b=BatchBridge(tmp_path/'work')
    with pytest.raises(FileExistsError):annotate_file(b,path,str(tmp_path),ARROWS)
    assert not b.events


def test_file_source_mutation_during_import_is_rejected(tmp_path):
    from chemdraw_macos.annotations import annotate_file
    path=tmp_path/'source.cdxml';path.write_text(SOURCE);b=BatchBridge(tmp_path/'work');create=b.create
    def change(text):
        path.write_text(SOURCE+'\n')
        return create(text)
    b.create=change
    with pytest.raises(ValueError,match='Source file changed'):annotate_file(b,path,str(tmp_path/'out'),ARROWS)
