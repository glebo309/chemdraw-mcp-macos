from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from test_reaction_batch import BatchBridge as ReactionBatchBridge


class BatchBridge(ReactionBatchBridge):
    def create(self,text,visible=False):
        result=super().create(text,visible=visible)
        did=result['document']['document_id'];root=ET.fromstring(self.docs[did])
        # The reaction oracle assumes centered labels; headings are left-aligned.
        for t in root.findall('page/t'):
            if t.get('Justification')=='Left':
                left,top,right,bottom=map(float,t.get('BoundingBox').split())
                x=float(t.get('p').split()[0]);t.set('BoundingBox',f'{x} {top} {x+right-left} {bottom}')
        self.docs[did]=ET.tostring(root,encoding='unicode')
        return result

PARENT='CC1C=Cc2c1c(=O)n(C)c(=O)n2C'
GROUPS=[{'label':'Substrate scope','compound_ids':[str(i) for i in range(15)]}]
SMILES=[PARENT]+['CC1C('+r+')=Cc2c1c(=O)n(C)c(=O)n2C' for r in
    ('C','CC','C(C)C','C(C)(C)C','F','Cl','Br','OC','O','N','C#N','C(F)(F)F','[N+](=O)[O-]','c3ccccc3')]
RECORDS=[{'compound_id':str(i),'label':'R = '+r,'smiles':s} for i,(r,s) in enumerate(zip(
    ('H','Me','Et','i-Pr','t-Bu','F','Cl','Br','OMe','OH','NH2','CN','CF3','NO2','Ph'),SMILES))]


def test_complete_fifteen_member_scope_is_one_final_document_and_two_batch_imports(tmp_path):
    from chemdraw_macos.scope_table import draw_scope_table
    b=BatchBridge(tmp_path/'work');before=b.docs.copy()
    result=draw_scope_table(b,RECORDS,tmp_path/'out',groups=GROUPS,columns=3,
        scaffold_smiles=PARENT,separators=False)
    assert result['status']=='completed'
    assert all(result['checks'].values())
    assert set(b.docs)-set(before)=={result['document']['document_id']}
    assert all(b.docs[k]==v for k,v in before.items())
    assert len([e for e in b.events if e[0]=='create'])==2
    assert not any(e[0] in ('import','clean') for e in b.events)
    assert len([e for e in b.events if e[0]=='export' and e[2]=='svg'])==1
    root=ET.parse(result['artifacts']['cdxml']).getroot()
    assert len(root.findall('page/fragment'))==15
    assert len(root.findall('page/graphic[@GraphicType="Rectangle"]'))==1
    assert any(''.join(t.itertext())=='Substrate scope' for t in root.findall('page/t'))
    assert result['timings']['total_seconds']>0


def test_table_uncertain_create_never_retries_or_closes(tmp_path):
    from chemdraw_macos.scope_table import draw_scope_table
    from chemdraw_macos.batch import NativeUncertain
    b=BatchBridge(tmp_path/'work');calls=[]
    def fail(*a,**kw):calls.append(1);raise RuntimeError('lost response')
    b.create=fail
    with pytest.raises(NativeUncertain):draw_scope_table(b,RECORDS,tmp_path/'out',groups=GROUPS)
    assert calls==[1]
    assert not any(e[0]=='close' for e in b.events)


def test_explicit_grouped_draw_routes_without_per_molecule_native_imports(tmp_path,monkeypatch):
    from chemdraw_macos import scope_table,draw
    b=BatchBridge(tmp_path/'work');calls=[]
    def run(bridge,structures,output_dir,**kw):calls.append(kw);return {'status':'completed'}
    monkeypatch.setattr(scope_table,'draw_scope_table',run)
    monkeypatch.setattr('chemdraw_macos.styles.require_style_fonts',lambda preset:None)
    draw.draw_structures(b,RECORDS,str(tmp_path/'out'),groups=GROUPS)
    assert len(calls)==1
    assert not b.events


def test_harness_routes_grouped_background_before_legacy_unsaved_guard(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'documents',lambda:pytest.fail('Legacy guard called'))
    monkeypatch.setattr(harness,'plan_request',lambda *a,**kw:{'workflow':'molecules',
        'structures':RECORDS,'groups':GROUPS,'preset':'house','columns':3,
        'scaffold_smiles':PARENT,'frame':True,'separators':False})
    calls=[]
    def capture(*a,**kw):calls.append(kw);return {'status':'batch-routed'}
    monkeypatch.setattr(harness,'draw_structures',capture)
    result=harness.run_drawing(b,{},str(tmp_path/'out'),presentation='background')
    assert result['status']=='batch-routed'
    assert calls[0]['presentation']=='background'


def test_native_object_reordering_does_not_swap_scope_labels():
    from chemdraw_macos.api_drawing import plan_addition
    from chemdraw_macos.scope_table import _layout
    from chemdraw_macos.reaction_batch import EMPTY,set_paper
    from chemdraw_macos.core import style_cdxml
    from test_reaction import measured
    seed,_=plan_addition(style_cdxml(set_paper(EMPTY,'A3 landscape'),'house'),RECORDS,
        columns=3,scaffold_smiles=PARENT,allow_page_expansion=True)
    native=ET.fromstring(measured(seed));page=native.find('page')
    fragments=page.findall('fragment')
    for f in fragments:page.remove(f)
    page.extend(reversed(fragments))
    arranged,_,plan,_,_=_layout(ET.tostring(native,encoding='unicode'),RECORDS,GROUPS,3,None,True,False,seed=seed)
    source=ET.fromstring(seed).find('page')
    for cell,fragment in zip(plan['layout']['cells'],source.findall('fragment')):
        assert cell['fragment_ids']==[fragment.get('id')]


def test_uncertain_final_create_does_not_report_closed_measurement_as_result(tmp_path):
    import json
    from chemdraw_macos.scope_table import draw_scope_table
    from chemdraw_macos.batch import NativeUncertain
    b=BatchBridge(tmp_path/'work');create=b.create;calls=[]
    def fail_second(*a,**kw):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('final response lost')
        return create(*a,**kw)
    b.create=fail_second
    with pytest.raises(NativeUncertain):
        draw_scope_table(b,RECORDS,tmp_path/'out',groups=GROUPS)
    audit=json.loads((tmp_path/'out/audit.json').read_text())
    assert audit.get('working_document_id') is None
    assert len(calls)==2


def test_interactive_grouped_call_shows_only_its_final_document(tmp_path,monkeypatch):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos import scope_table,shared
    from chemdraw_macos.draw import draw_structures
    b=Bridge(app_path=tmp_path,workspace=tmp_path);calls=[];b.managed.add(42)
    monkeypatch.setattr(shared,'run_shared',lambda *a:pytest.fail('Framed request sent to plain append'))
    monkeypatch.setattr(scope_table,'draw_scope_table',lambda *a,**kw:{'document':{'document_id':42},'status':'completed'})
    monkeypatch.setattr(b,'set_visibility',lambda did,visible:calls.append((did,visible)))
    result=draw_structures(b,RECORDS,str(tmp_path/'out'),groups=GROUPS,presentation='interactive')
    assert result['status']=='completed' and calls==[(42,True)]
