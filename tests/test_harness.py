import json
from pathlib import Path
import pytest


def test_minimal_input_selects_native_pipeline_and_assigns_clean_numbers():
    from chemdraw_macos.harness import plan_request
    plan=plan_request({'molecules':[{'value':'CCO','format':'smiles'}]})
    assert plan['workflow']=='molecules'
    assert plan['structures']==[{'compound_id':'1','label':'1','smiles':'CCO'}]
    assert plan['columns'] is None
    assert plan['preset']=='house'


def test_related_panel_gets_enforced_layout_without_model_recipe():
    from chemdraw_macos.harness import plan_request
    smiles=['CC(=O)c1ccccc1','CC(=O)c1ccc(C)cc1','CC(=O)c1ccc(C#N)cc1','CC(=O)c1ccc(F)cc1']
    plan=plan_request({'molecules':[{'value':s,'format':'smiles'} for s in smiles]})
    assert plan['scaffold_smiles']=='CC(=O)c1ccccc1'
    assert plan['scaffold_layout']=='reference'
    assert plan['groups'] and plan['frame'] and plan['separators']


def test_products_dispatch_reaction_without_predicting_any():
    from chemdraw_macos.harness import plan_request
    plan=plan_request({'molecules':[{'value':'CCO','format':'smiles'}],
        'products':[{'value':'CC=O','format':'smiles'}]})
    assert plan['workflow']=='reaction'
    assert plan['products'][0]['smiles']=='CC=O'


def test_auto_shared_panel_selects_plain_grid_without_losing_core(tmp_path,monkeypatch):
    from chemdraw_macos import harness,shared
    from chemdraw_macos.core import Bridge
    smiles=['CC(=O)c1ccccc1','CC(=O)c1ccc(C)cc1','CC(=O)c1ccc(C#N)cc1','CC(=O)c1ccc(F)cc1']
    def capture(bridge,plan,out,document_id=None):
        assert plan['groups'] is None
        assert plan['scaffold_smiles']=='CC(=O)c1ccccc1'
        assert plan['decisions']['panel_layout']=='shared_plain_grid'
        return {'status':'captured'}
    monkeypatch.setattr(shared,'run_shared',capture)
    result=harness.run_drawing(object.__new__(Bridge),{'molecules':[{'value':s,'format':'smiles'} for s in smiles]},str(tmp_path/'out'))
    assert result['status']=='captured'


def test_name_without_network_permission_stops_before_native(tmp_path):
    from chemdraw_macos.harness import run_drawing
    class NoNative:
        def __getattr__(self,key):pytest.fail('Native called')
    result=run_drawing(NoNative(),{'molecules':[{'value':'ethanol','format':'name'}]},str(tmp_path/'out'))
    assert result['status']=='needs_input'
    assert result['code']=='network_permission_required'
    assert not (tmp_path/'out').exists()


def test_ambiguous_name_never_autoselects_first_candidate(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    monkeypatch.setattr(harness,'resolve_identifier',lambda *a,**kw:{'ambiguous':True,'truncated':False,
        'candidates':[{'cid':1},{'cid':2}],'total_candidates':2})
    result=harness.run_drawing(object(),{'molecules':[{'value':'ambiguous','format':'name'}]},str(tmp_path/'out'),allow_network=True)
    assert result['status']=='needs_input' and result['code']=='ambiguous_identifier'
    assert len(result['candidates'])==2


@pytest.mark.parametrize('payload',[
    {'molecules':[{'value':'CCO','format':'smiles','yield':42}]},
    {'molecules':[{'value':'CCO','format':'smiles'}],'skip_checks':True},
    {'molecules':[{'value':'CCO','format':'guess'}]},
    {'molecules':[{'value':'[Na+].[Cl-]','format':'smiles'}]},
])
def test_invalid_or_unsupported_request_is_structured_rejection(tmp_path,payload):
    from chemdraw_macos.harness import run_drawing
    result=run_drawing(object(),payload,str(tmp_path/'out'))
    assert result['status']=='rejected' and result['stage']=='input'
    assert 'message' in result


def test_harness_never_accepts_export_without_required_checks(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    monkeypatch.setattr(harness,'draw_structures',lambda *a,**kw:{'audit':{'status':'checks_passed','checks':{}},'artifacts':{}})
    result=harness.run_drawing(object(),{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'))
    assert result['status']=='rejected' and result['stage']=='verification'


def test_delivery_rejects_measured_intramolecular_collision(tmp_path):
    from chemdraw_macos.harness import _verify_delivery
    from test_draw import ETHANOL
    text=ETHANOL.replace('<t p="72 40">','<t p="72 40" BoundingBox="39 39 76 48">')
    artifacts={}
    for fmt,content in [('cdxml',text),('svg','<svg/>'),('png','placeholder')]:
        path=tmp_path/f'figure.{fmt}';path.write_text(content);artifacts[fmt]=str(path)
    audit={'status':'checks_passed','checks':{k:True for k in (
        'native_import_identity','native_cleanup_identity','preexisting_documents_unchanged','final_grid_checks')}}
    with pytest.raises(ValueError,match='placement collision'):
        _verify_delivery({'audit':audit,'artifacts':artifacts},
            {'workflow':'molecules','structures':[{'smiles':'CCO'}]},tmp_path)


def test_native_uncertainty_stops_without_retry_or_fallback(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    from chemdraw_macos.batch import NativeUncertain
    calls=[]
    def fail(*args,**kwargs):calls.append(1);raise NativeUncertain('lost native response')
    monkeypatch.setattr(harness,'draw_structures',fail)
    result=harness.run_drawing(object(),{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'))
    assert result['status']=='uncertain' and len(calls)==1
    assert result['retry_safe'] is False


def test_explicit_legacy_background_retains_unsaved_preservation_guard(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'automatic_presentation',lambda:'background')
    monkeypatch.setattr(b,'documents',lambda:{'documents':[{'document_id':3,'name':'Untitled','file':''}]})
    monkeypatch.setattr(harness,'draw_structures',lambda *a,**kw:pytest.fail('Must not start native production'))
    result=harness.run_drawing(b,{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'),presentation='background')
    assert result['status']=='needs_input' and result['code']=='unsaved_user_document'
    assert result['documents'][0]['document_id']==3
    assert not (tmp_path/'out').exists()


def test_explicit_background_still_uses_legacy_export_workflow(tmp_path,monkeypatch):
    from chemdraw_macos import harness
    from chemdraw_macos.core import Bridge
    b=Bridge(app_path=tmp_path,workspace=tmp_path);events=[]
    monkeypatch.setattr(b,'automatic_presentation',lambda:events.append('detect') or 'background')
    monkeypatch.setattr(b,'documents',lambda:events.append('list') or {'documents':[]})
    def execute(bridge,plan,out,**kwargs):
        events.append(kwargs['presentation']);out.mkdir();return {'status':'completed'}
    monkeypatch.setattr(harness,'_execute',execute)
    result=harness.run_drawing(b,{'molecules':[{'value':'CCO','format':'smiles'}]},str(tmp_path/'out'),presentation='background')
    assert result['status']=='completed'
    assert events==['list','background']


def test_explicit_sn2_participants_use_supported_ionic_reaction_pipeline():
    from chemdraw_macos.harness import plan_request
    plan=plan_request({'molecules':[{'value':'[Br-]','format':'smiles'},{'value':'CI','format':'smiles'}],
        'products':[{'value':'CBr','format':'smiles'},{'value':'[I-]','format':'smiles'}]})
    assert plan['workflow']=='reaction' and plan['expanded_reaction'] is True


def test_mcp_has_typed_front_door_and_reduced_drawing_profile():
    import asyncio
    from chemdraw_macos.server import get_server
    tools=asyncio.run(get_server('drawing').list_tools())
    assert {t.name for t in tools}=={'chemdraw_draw','chemdraw_doctor','chemdraw_export_figure'}
    tool=next(t for t in tools if t.name=='chemdraw_draw')
    assert 'request' in tool.inputSchema['properties']
    assert 'molecules' in str(tool.inputSchema)


def test_cli_calls_the_same_harness(tmp_path,monkeypatch,capsys):
    from chemdraw_macos import cli,harness
    source=tmp_path/'request.json';source.write_text(json.dumps({'molecules':[{'value':'CCO','format':'smiles'}]}))
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    calls=[]
    def run(*args,**kwargs):calls.append((args,kwargs));return {'status':'completed'}
    monkeypatch.setattr(harness,'run_drawing',run)
    assert cli.main(['produce','--request',str(source),'--output',str(tmp_path/'out')])==0
    assert len(calls)==1
