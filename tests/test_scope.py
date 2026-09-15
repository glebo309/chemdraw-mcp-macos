import asyncio
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.scope import prepare_scope, arrange_scope, verify_scope, grid_document, validate_cells
from chemdraw_macos.editing import source_token
from chemdraw_macos.polish import bounds, numbers, chemical_signature
from test_polish import SAMPLE
from test_workflow import FakeBridge

CELLS=[{'compound_id':'3a','fragment_ids':['1'],'caption_id':'10','yield_percent':0},
       {'compound_id':'3b','fragment_ids':['20'],'caption_id':'30','yield_percent':None}]


def measured(text):
    """Synthetic measurement oracle for unit tests only, never production."""
    r=ET.fromstring(text)
    for t in r.iter('t'):
        x,y=numbers(t.get('p'),2);size=float(t.find('s').get('size','10'))
        w=len(''.join(t.itertext()).strip())*size*.55
        t.set('BoundingBox',f'{x-w/2} {y-size*.8} {x+w/2} {y+size*.2}')
    for f in r.findall('page/fragment'):
        points=[numbers(n.get('p'),2) for n in f.findall('n')]
        boxes=[bounds(t) for t in f.iter('t')]
        f.set('BoundingBox',' '.join(map(str,[min([p[0] for p in points]+[b.left for b in boxes])-1,
            min([p[1] for p in points]+[b.top for b in boxes])-1,
            max([p[0] for p in points]+[b.right for b in boxes])+1,
            max([p[1] for p in points]+[b.bottom for b in boxes])+1])))
    return ET.tostring(r,encoding='unicode')


class MeasuredBridge(FakeBridge):
    def create(self,text):return super().create(measured(text))


def test_zero_yield_is_visible_missing_yield_not_invented():
    text,state=prepare_scope(SAMPLE,CELLS)
    r=ET.fromstring(text)
    assert ''.join(r.find(f'.//t[@id="{state["cells"][0]["metadata_id"]}"]').itertext())=='3a · 0%'
    assert ''.join(r.find(f'.//t[@id="{state["cells"][1]["metadata_id"]}"]').itertext())=='3b'
    assert chemical_signature(text)==chemical_signature(SAMPLE)


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),-1,101,'80%'])
def test_invalid_yields_rejected(value):
    cells=copy.deepcopy(CELLS);cells[0]['yield_percent']=value
    with pytest.raises(ValueError):prepare_scope(SAMPLE,cells)


def test_complete_unique_fragment_caption_and_compound_ownership():
    for cells in (CELLS[:1],CELLS+[CELLS[0]],
                  [{**CELLS[0],'caption_id':None},CELLS[1]],
                  [CELLS[0],{**CELLS[1],'compound_id':'3a'}],
                  [CELLS[0],{**CELLS[1],'fragment_ids':['1']}],
                  [CELLS[0],{**CELLS[1],'unexpected':True}]):
        with pytest.raises(ValueError):validate_cells(SAMPLE,cells)


def test_uniform_grid_preserves_order_names_and_chemical_scale():
    text,state=prepare_scope(SAMPLE,list(reversed(CELLS)))
    arranged,plan=arrange_scope(measured(text),state['cells'],columns=2)
    report=verify_scope(arranged,measured(arranged),plan)
    assert report['checks']['page_fit']
    assert report['checks']['compound_bindings_preserved']
    assert [c['compound_id'] for c in plan['cells']]==['3b','3a']
    assert plan['cells'][0]['center_x']<plan['cells'][1]['center_x']
    assert plan['cells'][0]['name_baseline']==plan['cells'][1]['name_baseline']
    assert plan['cells'][0]['metadata_baseline']==plan['cells'][1]['metadata_baseline']
    assert all(abs(v-18)<.03 for v in report['median_bond_lengths_pt'])


def test_page_fit_includes_long_names_and_refuses_shrinking():
    text,state=prepare_scope(SAMPLE.replace('Methanol','Very long caption '*12),CELLS)
    with pytest.raises(ValueError,match='fit|overflow'):
        arrange_scope(measured(text),state['cells'],columns=2,width=120)


def test_native_measured_bounds_required():
    text,state=prepare_scope(SAMPLE,CELLS)
    with pytest.raises(ValueError,match='bounds'):
        arrange_scope(text,state['cells'],columns=2)


@pytest.mark.parametrize('columns',[True,0,-1,2.5,9])
def test_bad_column_requests_rejected(columns):
    text,state=prepare_scope(SAMPLE,CELLS)
    with pytest.raises(ValueError):arrange_scope(measured(text),state['cells'],columns=columns)


def test_unowned_reaction_objects_are_not_silently_dropped():
    source=SAMPLE.replace('</page>','<arrow id="90" Head3D="80 60 0" Tail3D="40 60 0"/></page>')
    with pytest.raises(ValueError):prepare_scope(source,CELLS)


def test_multiple_fragments_of_one_compound_translate_together():
    r=ET.fromstring(SAMPLE);page=r.find('page');page.remove(page.find('t[@id="30"]'))
    cells=[{'compound_id':'pair','fragment_ids':['1','20'],'caption_id':'10'}]
    text,state=prepare_scope(ET.tostring(r,encoding='unicode'),cells)
    before=measured(text);arranged,plan=arrange_scope(before,state['cells'],columns=1)
    old,new=ET.fromstring(before),ET.fromstring(arranged)
    shifts=[]
    for aid in ('2','21'):
        a=numbers(old.find(f'.//n[@id="{aid}"]').get('p'),2)
        b=numbers(new.find(f'.//n[@id="{aid}"]').get('p'),2)
        shifts.append(tuple(y-x for x,y in zip(a,b)))
    assert shifts[0]==pytest.approx(shifts[1])


def test_post_native_caption_shift_is_not_silently_accepted():
    text,state=prepare_scope(SAMPLE,CELLS)
    arranged,plan=arrange_scope(measured(text),state['cells'],columns=2)
    r=ET.fromstring(measured(arranged));t=r.find('page/t')
    x,y=numbers(t.get('p'),2);t.set('p',f'{x+12} {y}')
    with pytest.raises(ValueError):verify_scope(arranged,ET.tostring(r,encoding='unicode'),plan)


def test_workflow_delivers_native_review_and_keeps_source(tmp_path):
    b=MeasuredBridge(tmp_path/'work')
    result=grid_document(b,1,str(tmp_path/'scope'),CELLS,source_token(SAMPLE),columns=2)
    assert b.docs[1]==SAMPLE
    assert all(result['audit']['checks'].values())
    assert result['audit']['visual_review']=='required'
    for name in ('before.cdxml','before.svg','before.png','figure.cdxml','figure.svg','figure.png','recipe.json','audit.json','review.html'):
        assert (tmp_path/'scope'/name).is_file()
    assert len(b.managed)==1


def test_stale_grid_snapshot_is_rejected_before_native_create(tmp_path):
    b=MeasuredBridge(tmp_path/'work')
    with pytest.raises(ValueError,match='stale'):
        grid_document(b,1,str(tmp_path/'scope'),CELLS,'0'*64)
    assert not any(e[0]=='create' for e in b.events)


def test_cli_and_mcp_expose_scope_grid(capsys):
    from chemdraw_macos.cli import main
    from chemdraw_macos.server import mcp
    with pytest.raises(SystemExit) as exc:main(['grid','--help'])
    assert exc.value.code==0 and '--recipe' in capsys.readouterr().out
    assert 'chemdraw_grid_document' in {t.name for t in asyncio.run(mcp.list_tools())}


def test_multi_molecule_analysis_has_top_level_source_token(tmp_path):
    from chemdraw_macos.workflow import analyze_document
    b=MeasuredBridge(tmp_path/'work')
    report=analyze_document(b,1)
    assert report['source_token']==source_token(SAMPLE)


def test_cli_grid_recipe_works_on_a_file(tmp_path,monkeypatch,capsys):
    from chemdraw_macos.cli import main
    source=tmp_path/'source.cdxml';source.write_text(SAMPLE)
    recipe=tmp_path/'recipe.json';recipe.write_text(json.dumps({'schema_version':1,'cells':CELLS,'columns':2}))
    b=MeasuredBridge(tmp_path/'work');b.import_file=lambda path:b.create(Path(path).read_text())
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:b)
    assert main(['grid','--input',str(source),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    assert json.loads(capsys.readouterr().out)['audit']['status']=='checks_passed'
