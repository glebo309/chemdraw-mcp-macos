import xml.etree.ElementTree as ET
import pytest

from test_drawing_speed import drawing_backend, plan
from test_scope_table_batch import BatchBridge, RECORDS, GROUPS, PARENT


def test_ordinary_shared_drawing_defaults_to_canvas():
    from chemdraw_macos.harness import plan_request
    request={'molecules':[{'format':'smiles','value':'CCO'}]}
    assert plan_request(request,shared=True)['exports']=='canvas'


def test_advanced_shared_default_does_not_export(drawing_backend,tmp_path):
    from chemdraw_macos.api_drawing import run_api_drawing
    bridge,_,events=drawing_backend
    request=plan('canvas');request.pop('exports')
    result=run_api_drawing(bridge,request,tmp_path/'out',42)
    assert set(result['artifacts'])=={'cdxml'}
    assert events==['read','append']


def test_framed_frontdoor_is_explicit_and_canvas_first(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    request={'molecules':[{'format':'smiles','value':r['smiles'],'label':r['label']} for r in RECORDS],
             'panel':'framed','heading':'Substrate scope'}
    calls=[]
    monkeypatch.setattr(harness,'draw_structures',lambda *a,**kw:calls.append(kw) or {'status':'completed'})
    result=harness.run_drawing(object(),request,str(tmp_path/'out'))
    assert result['status']=='completed'
    assert calls[0]['groups']==[{'label':'Substrate scope','compound_ids':[str(i) for i in range(1,16)]}]
    assert calls[0]['frame'] is True and calls[0]['separators'] is False
    assert calls[0]['exports']=='canvas' and calls[0]['presentation']=='interactive'
    result=harness.run_drawing(object(),request,str(tmp_path/'out2'),document_id=42)
    assert result['status']=='needs_input'
    assert len(calls)==1


@pytest.mark.parametrize('mode,formats',[('canvas',{'cdxml'}),('preview',{'cdxml','svg','preview'}),('full',{'cdxml','svg','png','preview'})])
def test_framed_batch_export_is_explicit(tmp_path,mode,formats):
    from chemdraw_macos.scope_table import draw_scope_table
    b=BatchBridge(tmp_path/'work')
    result=draw_scope_table(b,RECORDS,tmp_path/'out',groups=GROUPS,scaffold_smiles=PARENT,exports=mode)
    assert set(result['artifacts'])==formats
    assert result['delivery']['mode']==mode
    root=ET.parse(result['artifacts']['cdxml']).getroot()
    assert root.find('page/graphic[@RectangleType="RoundEdge Shadow"]') is not None
    assert any(e[0]=='export' and e[2]=='svg' for e in b.events)==(mode!='canvas')


def test_measurement_validation_failure_closes_only_known_staging(tmp_path,monkeypatch):
    from chemdraw_macos import api_drawing
    from chemdraw_macos.harness import NeedsInput
    b=BatchBridge(tmp_path/'work');before=b.docs.copy()
    monkeypatch.setattr(api_drawing,'center_measured_payload',lambda *a:(_ for _ in ()).throw(ValueError('ambiguous object')))
    with pytest.raises(NeedsInput,match='ambiguous object'):
        api_drawing.measure_table_payload(b,'<CDXML><page id="1"/></CDXML>')
    assert b.docs==before


def test_measurement_uncertain_export_retains_staging(tmp_path):
    from chemdraw_macos.api_drawing import measure_table_payload
    from chemdraw_macos.batch import NativeUncertain
    b=BatchBridge(tmp_path/'work')
    b.export=lambda *a:(_ for _ in ()).throw(RuntimeError('lost response'))
    with pytest.raises(NativeUncertain):measure_table_payload(b,'<CDXML><page id="1"/></CDXML>')
    assert not any(e[0]=='close' for e in b.events)


def test_constrained_geminal_nitrile_does_not_overlap_locked_methyl():
    from chemdraw_macos.api_drawing import plan_addition
    from test_api_drawing import EMPTY,assert_core_orientation
    from chemdraw_macos.polish import numbers
    import math
    parent,_=plan_addition(EMPTY,[RECORDS[0]])
    records=[{'compound_id':'1','label':'S1: CN','smiles':'Cn1c2c(c(=O)n(C)c1=O)C(C)(C#N)C=C2'}]
    payload,_=plan_addition(parent,records,scaffold_smiles=PARENT)
    positions=[numbers(n.get('p'),2) for n in ET.fromstring(payload).findall('page/fragment/n')]
    assert min(math.dist(a,b) for i,a in enumerate(positions) for b in positions[i+1:])>5
    assert_core_orientation(parent,payload,PARENT)
    from chemdraw_macos.polish import bond_lengths
    assert all(17.5<length<18.5 for length in bond_lengths(ET.fromstring(payload).find('page/fragment')))
    bonds=ET.fromstring(payload).findall('page/fragment/b')
    assert all(b.get('Z') is not None for b in bonds)
    assert len({b.get('Z') for b in bonds})==len(bonds)


def test_later_export_accepts_unchanged_rounded_frame_but_not_changed_or_unknown_graphics(tmp_path):
    from chemdraw_macos.scope_table import draw_scope_table
    from chemdraw_macos.api_drawing import verify_export_snapshot
    from pathlib import Path
    b=BatchBridge(tmp_path/'work')
    result=draw_scope_table(b,RECORDS,tmp_path/'out',groups=GROUPS,exports='canvas')
    before=Path(result['artifacts']['cdxml']).read_text()
    verify_export_snapshot(before,before)
    root=ET.fromstring(before);root.find('page/graphic').set('ShadowSize','800')
    with pytest.raises(ValueError):verify_export_snapshot(before,ET.tostring(root,encoding='unicode'))
    root.find('page/graphic').set('GraphicType','Unknown')
    bad=ET.tostring(root,encoding='unicode')
    with pytest.raises(ValueError):verify_export_snapshot(bad,bad)


def test_advanced_mcp_accepts_canvas_export_mode(tmp_path,monkeypatch):
    from chemdraw_macos import server
    calls=[]
    monkeypatch.setattr(server,'bridge',lambda:object())
    monkeypatch.setattr(server,'draw_structures',lambda *a,**kw:calls.append(kw) or {'status':'completed'})
    server.chemdraw_draw_structures(RECORDS,str(tmp_path/'out'),groups=GROUPS,
        presentation='interactive',exports='canvas')
    assert calls[0]['exports']=='canvas'


def test_later_export_reads_explicit_document_without_active_tab_workaround(tmp_path,monkeypatch):
    from chemdraw_macos import addin
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.physical_export import export_figure
    from chemdraw_macos.api_drawing import plan_addition
    from test_api_drawing import EMPTY
    from test_physical_export import SVG
    from types import SimpleNamespace
    from pathlib import Path
    xml,_=plan_addition(EMPTY,[RECORDS[0]])
    b=Bridge(app_path=tmp_path,workspace=tmp_path);events=[]
    backend=SimpleNamespace(_ready=lambda:events.append('ready'),
        read=lambda did:pytest.fail('Unbound active-tab read'))
    monkeypatch.setattr(addin,'get_backend',lambda b:backend)
    monkeypatch.setattr(addin,'read_preserving_active',lambda b,did:events.append(did) or {'cdxml':xml})
    monkeypatch.setattr(b,'export',lambda did,path,fmt:Path(path).write_text(SVG))
    result=export_figure(b,42,tmp_path/'out')
    assert result['source_preserved'] and events==['ready',42,42]


def test_preservation_read_connects_before_guarded_document_selection(monkeypatch):
    from chemdraw_macos import addin
    from threading import RLock
    from types import SimpleNamespace
    current=[1];events=[]
    def native(op,*args):
        if op=='active_document':return current[0]
        target,expected=args
        assert current[0]==expected
        current[0]=target;events.append(('select',target))
    opened=[False]
    def ready():
        if not opened[0]:current[0]=2;opened[0]=True;events.append('connect')
    def read(did):
        ready()
        assert current[0]==did
        return {'cdxml':'snapshot'}
    backend=SimpleNamespace(_ready=ready,read=read)
    monkeypatch.setattr(addin,'get_backend',lambda b:backend)
    result=addin.read_preserving_active(SimpleNamespace(lock=RLock(),_run=native),1)
    assert result=={'cdxml':'snapshot'}
    assert events==['connect',('select',1),('select',2)]
