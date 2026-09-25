import pytest
from pathlib import Path
from test_scope_job import measured_scope
from test_batch import BatchBridge
from chemdraw_macos.draw import draw_structures


def test_grouped_output_uses_native_shadow_frame_and_separators(tmp_path):
    from chemdraw_macos.grouped_draw import group_drawn_structures
    text,cells=measured_scope()
    b=BatchBridge(tmp_path/'work');source=b.create(text)
    groups=[{'label':'Reference','compound_ids':['3a']}, {'label':'Withdrawers','compound_ids':['3b']}]
    result=group_drawn_structures(b,source['document']['document_id'],text,cells,groups,
                                 str(tmp_path/'grouped'),columns=2)
    assert result['audit']['status']=='checks_passed'
    assert len(result['group_plan']['group_bands'])==2
    assert result['audit']['plan']['frame'] is True
    assert len(result['audit']['plan']['separator_y_pt'])==1
    assert Path(result['artifacts']['svg']).exists()
    assert source['document']['document_id'] in b.managed


@pytest.mark.parametrize('groups',[
    [],[{'label':'Bad','compound_ids':['unknown']}],
    [{'label':'Bad','compound_ids':['a','a']}],
    [{'label':'Bad\nlabel','compound_ids':['a']}],
])
def test_invalid_draw_groups_rejected_before_native(tmp_path,groups):
    class NoNative:
        def __getattr__(self,key):pytest.fail('Native used during preflight')
    with pytest.raises(ValueError):
        draw_structures(NoNative(),[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],
                        str(tmp_path/'output'),groups=groups)


def test_reference_scaffold_mode_reuses_native_core_before_second_import(tmp_path,monkeypatch):
    from test_alignment import ACETOPHENONE
    import chemdraw_macos.scaffold_seed as seeds
    calls=[]
    class Stop(RuntimeError):pass
    class Backend:
        def documents(self):return {'documents':[]}
        def import_file(self,path):
            calls.append(('import',Path(path).read_text()))
            if len([v for v in calls if v[0]=='import'])==2:raise Stop('stop at second import')
            return {'document':{'document_id':1}}
        def export(self,did,path,fmt):Path(path).write_text(ACETOPHENONE)
        def clean(self,did):calls.append(('clean',did))
        def close(self,did):pass
    original=seeds.seed_from_native_scaffold
    def record(*args):
        calls.append(('constrain',args[1]));return original(*args)
    monkeypatch.setattr(seeds,'seed_from_native_scaffold',record)
    with pytest.raises(RuntimeError,match='second import'):
        draw_structures(Backend(),[{'compound_id':str(i),'label':'Parent','smiles':'CC(=O)c1ccccc1'} for i in range(2)],
                        str(tmp_path/'out'),scaffold_smiles='CC(=O)c1ccccc1',scaffold_layout='reference')
    assert [c[0] for c in calls]==['import','clean','constrain','import']


def test_mcp_exposes_grouping_reference_layout_and_presentation():
    import inspect
    from chemdraw_macos.server import chemdraw_draw_structures
    params=inspect.signature(chemdraw_draw_structures).parameters
    assert {'groups','frame','separators','scaffold_layout','presentation'}<=set(params)


def test_grouping_reuses_measured_auto_columns_instead_of_hardcoded_three(tmp_path):
    from test_draw import ETHANOL
    from test_scope import measured
    class Native(BatchBridge):
        def create(self,text,visible=False):
            assert visible is False
            import xml.etree.ElementTree as ET
            root=ET.fromstring(measured(text))
            # The shared oracle centres all text; native group headings are left aligned.
            for t in root.findall('page/t[@Justification="Left"]'):
                x,y=map(float,t.get('p').split());l,top,r,bottom=map(float,t.get('BoundingBox').split())
                t.set('BoundingBox',f'{x} {top} {x+r-l} {bottom}')
            return super().create(ET.tostring(root,encoding='unicode'))
        def import_file(self,path):return self.create(ETHANOL)
        def clean(self,did):pass
        def export(self,did,path,fmt,pixels=3200):
            if fmt=='svg':
                Path(path).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"/>')
            else:super().export(did,path,fmt,pixels)
    records=[{'compound_id':str(i),'label':'Long caption '+str(i)+' with additional detail','smiles':'CCO'} for i in range(4)]
    result=draw_structures(Native(tmp_path/'work'),records,str(tmp_path/'out'),
        groups=[{'label':'Structures','compound_ids':[str(i) for i in range(4)]}])
    assert result['group_plan']['layout']['columns']==result['audit']['planning']['columns']
