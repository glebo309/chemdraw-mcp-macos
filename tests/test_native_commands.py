"""Named ChemDraw commands, dialogs, NMR, checks and settings without a live app."""
import asyncio
from pathlib import Path

import pytest

from chemdraw_macos import cli, server
from chemdraw_macos.core import Bridge


SCRIPT = (Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()


def branch(name):
    return SCRIPT.split(f'operation is "{name}" then',1)[1].split('operation is "',1)[0]


# Command policy ------------------------------------------------------------

@pytest.mark.parametrize('name', [
    'undo','redo','mapReactionAtoms','autoNumberReaction','flipObjectsHorizontal',
    'toggleKekulization','analyzeStoichiometry','showScaleDialog','cleanStructure',
    'convertStructureToName','insertChemicalName','zoomToFit','group','bringToFront'])
def test_ordinary_commands_are_allowed(name):
    from chemdraw_macos.commands import command_policy
    assert command_policy(name)==(True,None)


@pytest.mark.parametrize('name,hint', [
    ('quit','application'),('saveDocument','file'),('saveDocumentAs','file'),('openDocument','file'),
    ('closeDocument','file'),('print','file'),('newDocument','file'),('copy','clipboard'),('paste','clipboard'),
    ('copyAsSMILES','clipboard'),('pasteAsSMILES','clipboard'),('cut','clipboard'),
    ('predict1H_NMR_Shifts','chemdraw_predict_nmr'),('predict13C_NMR_Shifts','chemdraw_predict_nmr'),
    ('convertNameToStructure','chemdraw_draw_name'),('askForFileToInsert','file'),
    ('availableStationery /Applications/ChemDraw.app/x.cds','file'),
    ('https://example.org/addin','network'),('Add-in Manager...','add-in'),
    ('showApplicationPreferences','preferences'),('fakeMove','internal'),('disabledDummyCommand','internal'),
    ('openInChemDrawPlus','file'),('saveToSignals','file'),('checkStructure','chemdraw_check_structure')])
def test_lifecycle_clipboard_network_and_dedicated_commands_are_refused(name,hint):
    from chemdraw_macos.commands import command_policy
    allowed,reason=command_policy(name)
    assert allowed is False and hint in reason


def test_list_commands_filters_and_marks_policy(tmp_path,monkeypatch):
    from chemdraw_macos.commands import list_commands
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    rows={'names':['undo','redo','quit','mapReactionAtoms','copyAsSMILES'],
          'enabled':[True,False,True,False,True],
          'descriptions':['Undo','Redo','Quit','Map','Copy']}
    monkeypatch.setattr(b,'_run',lambda op:[rows['names'],rows['enabled'],rows['descriptions']])
    result=list_commands(b,pattern='^(un|re)do$|map')
    assert [r['name'] for r in result['commands']]==['undo','redo','mapReactionAtoms']
    assert result['commands'][0]=={'name':'undo','enabled':True,'description':'Undo','allowed':True}
    enabled=list_commands(b,enabled_only=True)
    assert [r['name'] for r in enabled['commands']]==['undo','quit','copyAsSMILES']
    assert enabled['commands'][1]['allowed'] is False
    assert list_commands(b,limit=2)['shown']==2 and list_commands(b,limit=2)['count']==5
    with pytest.raises(ValueError):list_commands(b,pattern='(')


# Command dispatch ----------------------------------------------------------

def _row(did=12):return [did,'doc','',True,1]


def fake_bridge(tmp_path,monkeypatch,polls,dialogs=()):
    """polls[0] is the state returned with the dispatch; later items answer command_state."""
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w');calls=[]
    count=len(dialogs)
    def run(op,*args):
        calls.append((op,*args))
        if op=='dispatch_command':
            return [_row(),True,[3,3,1,0,0],[12],['doc'],polls.pop(0),count]
        if op=='command_state':
            return [polls.pop(0),count]
        raise AssertionError(op)
    monkeypatch.setattr(b,'_run',run)
    from chemdraw_macos import dialogs as dialog_module
    monkeypatch.setattr(dialog_module,'read_dialogs',lambda bridge:list(dialogs))
    return b,calls


def test_run_command_dispatches_once_and_reports_counts(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    b,calls=fake_bridge(tmp_path,monkeypatch,[[_row(),[3,3,1,0,1],[12],['doc']]])
    result=run_command(b,12,'mapReactionAtoms',selection='all')
    assert calls[0]==('dispatch_command',12,'mapReactionAtoms','all','ChemDraw')
    assert [c[0] for c in calls].count('dispatch_command')==1
    assert result['status']=='completed'
    assert result['counts_before']=={'atoms':3,'bonds':3,'molecules':1,'captions':0,'arrows':0}
    assert result['counts_after']['arrows']==1
    assert result['new_documents']==[] and result['dialogs']==[]
    assert 'undo' in result['undo']


def test_run_command_refuses_before_any_native_call(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    b,calls=fake_bridge(tmp_path,monkeypatch,[])
    with pytest.raises(ValueError,match='clipboard'):run_command(b,12,'paste')
    with pytest.raises(ValueError,match='selection'):run_command(b,12,'undo',selection='guess')
    assert calls==[]


def test_disabled_command_is_not_reported_as_applied(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    monkeypatch.setattr(b,'_run',lambda op,*a:[_row(),False,[0,0,0,0,0],[12],['doc']])
    from chemdraw_macos import dialogs as dialog_module
    monkeypatch.setattr(dialog_module,'read_dialogs',lambda bridge:pytest.fail('no dialog read for a disabled command'))
    result=run_command(b,12,'undo')
    assert result['status']=='not_enabled'


def test_sheet_dialog_is_reported_with_contents(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    sheet={'index':0,'kind':'sheet','window':'doc','text':['Scale the selected objects:'],
           'buttons':['Cancel','Scale'],'fields':[{'index':1,'value':'1.058 cm'}],
           'radio_buttons':[],'checkboxes':[]}
    b,_=fake_bridge(tmp_path,monkeypatch,[[_row(),[3,3,1,0,0],[12],['Scale','doc']]],[sheet])
    result=run_command(b,12,'showScaleDialog')
    assert result['status']=='dialog_open'
    assert result['dialogs']==[sheet]
    assert 'chemdraw_dialog' in result['next']


def test_modal_alert_is_detected_while_chemdraw_is_blocked(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    alert={'index':0,'kind':'dialog','window':'','text':['No reaction center was found.'],
           'buttons':['OK'],'fields':[],'radio_buttons':[],'checkboxes':[]}
    b,_=fake_bridge(tmp_path,monkeypatch,['busy'],[alert])
    result=run_command(b,12,'cleanReaction')
    assert result['status']=='dialog_open' and result['dialogs'][0]['text']==['No reaction center was found.']
    assert result['counts_after'] is None


def test_new_documents_opened_by_a_command_are_listed(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    b,_=fake_bridge(tmp_path,monkeypatch,[[_row(),[3,3,1,0,0],[12,77],['Spectrum','doc']]])
    monkeypatch.setattr(b,'_run',(lambda run:lambda op,*a:[[12,'doc','',True,1],[77,'Spectrum','',True,0]] if op=='list' else run(op,*a))(b._run))
    result=run_command(b,12,'analyzeStoichiometry')
    assert result['new_documents']==[{'document_id':77,'name':'Spectrum','file':'','modified':True,'molecule_count':0}]


def test_still_running_after_wait_is_uncertain_not_completed(tmp_path,monkeypatch):
    from chemdraw_macos import commands
    from chemdraw_macos.commands import run_command
    monkeypatch.setattr(commands,'POLL_INTERVAL',.002)
    b,_=fake_bridge(tmp_path,monkeypatch,['busy']*100000)
    result=run_command(b,12,'cleanStructure',wait_seconds=0.01)
    assert result['status']=='still_running'


def test_dispatch_script_guards_document_and_does_not_wait():
    body=branch('dispatch_command')
    assert 'set index of window of targetDoc to 1' in body
    assert body.index('id of document 1') < body.index('ignoring application responses')
    assert 'enabled of command nativeCommand' in body
    assert 'if enabled of command "selectAll" then do command "selectAll"' in body
    assert 'Unknown ChemDraw command' in body
    assert 'set stateResult to my commandState(wantedID)' in body and 'my dialogCount(' in body
    assert 'with timeout of 2 seconds' in SCRIPT.split('on commandState',1)[1].split('end commandState',1)[0]


def test_native_action_select_all_checks_enabled_first():
    body=branch('native_action')
    assert 'if enabled of command "selectAll" then do command "selectAll"' in body


# Dialogs -------------------------------------------------------------------

def test_dialog_response_validates_before_pressing(tmp_path,monkeypatch):
    from chemdraw_macos import dialogs
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    sheet={'index':0,'kind':'sheet','window':'doc','text':['Scale'],'buttons':['Cancel','Scale'],
           'fields':[{'index':1,'value':'1.0 cm'}],'radio_buttons':[{'name':'Scale by','selected':False}],
           'checkboxes':[]}
    state={'open':[sheet]};pressed=[]
    monkeypatch.setattr(dialogs,'read_dialogs',lambda bridge:list(state['open']))
    def act(bridge,request):
        pressed.append(request);state['open']=[]
    monkeypatch.setattr(dialogs,'_act',act)
    monkeypatch.setattr(b,'_run',lambda op,*a:[len(state['open'])])
    with pytest.raises(ValueError,match='button'):dialogs.respond_dialog(b,button='Delete')
    with pytest.raises(ValueError,match='field'):dialogs.respond_dialog(b,button='Scale',fields={'7':'x'})
    with pytest.raises(ValueError,match='radio'):dialogs.respond_dialog(b,button='Scale',choose='Nope')
    assert pressed==[]
    result=dialogs.respond_dialog(b,button='Scale',fields={'1':'1.2 cm'},choose='Scale by')
    assert pressed==[{'dialog':0,'kind':'sheet','window':'doc','button':'Scale',
                      'fields':{'1':'1.2 cm'},'choose':'Scale by','check':{}}]
    assert result=={'pressed':'Scale','remaining_dialogs':[]}


def test_dialog_without_open_dialog_is_explicit(tmp_path,monkeypatch):
    from chemdraw_macos import dialogs
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    monkeypatch.setattr(dialogs,'read_dialogs',lambda bridge:[])
    assert dialogs.respond_dialog(b)=={'dialogs':[]}
    with pytest.raises(ValueError,match='No ChemDraw dialog'):dialogs.respond_dialog(b,button='OK')


def test_accessibility_denial_is_named(tmp_path,monkeypatch):
    import subprocess
    from chemdraw_macos import dialogs
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    def denied(*a,**k):raise subprocess.CalledProcessError(1,'osascript',stderr='Error: osascript is not allowed assistive access. (-25211)')
    monkeypatch.setattr(subprocess,'run',denied)
    with pytest.raises(RuntimeError,match='Accessibility'):dialogs.read_dialogs(b)


# NMR -----------------------------------------------------------------------

PROTOCOL_1H = '''Protocol of the H-1 NMR Prediction (Lib=SU Solvent=DMSO 300 MHz):


Node     Shift    Base + Inc.   Comment (ppm rel. to TMS)

CH3  1.21              0.86      methyl
                      0.35      1 alpha -C(=O)O
CH2  4.11              1.37      methylene
                      2.74      1 alpha -OC(=O)C
CH  7.34              7.34      benzene

1H NMR Coupling Constant Prediction

shift   atom index  coupling partner, constant and vector

7.34	       1
	                   2	  7.5		H-C*C-H
'''


def test_nmr_protocol_parsing_keeps_rows_and_conditions():
    from chemdraw_macos.nmr import parse_protocol
    parsed=parse_protocol(PROTOCOL_1H)
    assert parsed['conditions']=='Lib=SU Solvent=DMSO 300 MHz'
    assert parsed['nucleus']=='1H'
    assert [(r['group'],r['shift_ppm']) for r in parsed['shifts']]==[('CH3',1.21),('CH2',4.11),('CH',7.34)]
    assert parsed['shifts'][0]['increments']==['0.86 methyl','0.35 1 alpha -C(=O)O']
    assert 'Coupling' in parsed['couplings_text']


def test_carbon_protocol_header_has_colon_before_conditions():
    from chemdraw_macos.nmr import parse_protocol
    parsed=parse_protocol('Protocol of the C-13 NMR Prediction: (Lib=S)\n\n\nNode     Shift    Base + Inc.   Comment (ppm rel. to TMS)\n\nC  170.2              166.0      1-carboxyl\n')
    assert parsed['nucleus']=='13C' and parsed['conditions']=='Lib=S'
    assert parsed['shifts']==[{'group':'C','shift_ppm':170.2,'increments':['166.0 1-carboxyl']}]


def test_nmr_rejects_unknown_nucleus_and_ambiguous_input(tmp_path):
    from chemdraw_macos.nmr import predict_nmr
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    with pytest.raises(ValueError,match='nucleus'):predict_nmr(b,document_id=1,nucleus='19F')
    with pytest.raises(ValueError,match='exactly one'):predict_nmr(b)
    with pytest.raises(ValueError,match='exactly one'):predict_nmr(b,document_id=1,smiles='C')


# Structure check, settings, changes ----------------------------------------

def test_structure_check_reports_native_warnings():
    from chemdraw_macos.checks import structure_warnings
    cdxml=('<CDXML><page id="1"><fragment id="10"><n id="11" p="0 0" '
           'Warning="There are too many bonds to this unlabeled Carbon."/><n id="12" p="1 1"/>'
           '<b id="20" B="11" E="12" Warning="Unusual bond"/></fragment>'
           '<t id="30"><s>caption</s></t></page></CDXML>')
    result=structure_warnings(cdxml)
    assert result['ok'] is False
    assert result['warnings']==[
        {'object':'atom','id':'11','warning':'There are too many bonds to this unlabeled Carbon.'},
        {'object':'bond','id':'20','warning':'Unusual bond'}]
    assert structure_warnings('<CDXML><page id="1"/></CDXML>')=={'ok':True,'warnings':[]}


def test_document_settings_convert_units_and_validate(tmp_path,monkeypatch):
    from chemdraw_macos.settings import document_settings
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w');calls=[]
    native=[_row(),[288,32,40,200,200,'Arial','Times',18,120,32,50,100]]
    def run(op,*a):
        calls.append((op,*a));return native
    monkeypatch.setattr(b,'_run',run)
    read=document_settings(b,12)
    assert read['settings']['bond_length_pt']==14.4 and read['settings']['line_width_pt']==1.6
    assert read['settings']['label_font']=='Arial' and read['settings']['chain_angle_deg']==120
    assert calls==[('get_settings',12)]
    document_settings(b,12,{'bond_length_pt':17,'label_font':'Helvetica'})
    assert calls[1]==('set_settings',12,'fixed length','340','label font','Helvetica')
    for bad in ({'bond_length_pt':0},{'bond_length_pt':'x'},{'nope':1},{'chain_angle_deg':500},{'label_font':''}):
        with pytest.raises(ValueError):document_settings(b,12,bad)


def test_changes_since_previous_read():
    from chemdraw_macos.changes import summarize, diff
    a=summarize({'graphs':['CCO','c1ccccc1'],'captions':['1','2'],'counts':{'fragment':2,'t':2}})
    b=summarize({'graphs':['CCO','CCN'],'captions':['1','3'],'counts':{'fragment':2,'t':2,'arrow':1}})
    d=diff(a,b)
    assert d['molecules_added']==['CCN'] and d['molecules_removed']==['c1ccccc1']
    assert d['captions_added']==['3'] and d['captions_removed']==['2']
    assert d['object_count_changes']=={'arrow':[0,1]}
    assert d['changed'] is True
    assert diff(a,a)['changed'] is False


def test_stationery_styles_are_listed(tmp_path,monkeypatch):
    from chemdraw_macos import styles
    app=tmp_path/'ChemDraw.app';folder=app/'Contents/Resources/SpecialPurpose/Stationery';folder.mkdir(parents=True)
    (folder/'Wiley Document.cds').write_bytes(b'x');(folder/'Nature Research Document.cds').write_bytes(b'x')
    assert styles.stationery_styles(app)==[
        {'name':'Nature Research Document','path':str(folder/'Nature Research Document.cds')},
        {'name':'Wiley Document','path':str(folder/'Wiley Document.cds')}]


# Exposure ------------------------------------------------------------------

NEW = {'chemdraw_list_commands','chemdraw_run_command','chemdraw_dialog','chemdraw_predict_nmr',
       'chemdraw_check_structure','chemdraw_document_settings','chemdraw_preview','chemdraw_document_changes'}


@pytest.mark.parametrize('profile',['core','full'])
def test_new_tools_are_in_core_and_full(profile,monkeypatch):
    monkeypatch.setattr(server,'bridge',lambda:pytest.fail('Discovery must not connect'))
    tools={t.name:t for t in asyncio.run(server.get_server(profile).list_tools())}
    assert NEW<=set(tools)
    assert tools['chemdraw_run_command'].annotations.destructiveHint
    assert tools['chemdraw_list_commands'].annotations.readOnlyHint
    assert tools['chemdraw_check_structure'].annotations.readOnlyHint


def test_drawing_profile_stays_small():
    tools={t.name for t in asyncio.run(server.get_server('drawing').list_tools())}
    assert not tools & NEW


def test_undo_and_redo_are_native_actions():
    from chemdraw_macos.native_actions import ACTIONS
    assert ACTIONS['undo']=='undo' and ACTIONS['redo']=='redo'
    assert '"undo", "redo"' in branch('native_action')


def test_cli_run_command_uses_same_implementation(monkeypatch):
    from chemdraw_macos import commands
    calls=[]
    monkeypatch.setattr(cli,'Bridge',lambda:'bridge')
    monkeypatch.setattr(commands,'run_command',lambda *a,**k:calls.append((a,k)) or {'status':'completed'})
    assert cli.main(['command','--document-id','12','--name','undo'])==0
    assert calls==[(('bridge',12,'undo'),{'selection':'current','wait_seconds':15.0})]


def test_missing_accessibility_is_reported_not_hidden(tmp_path,monkeypatch):
    from chemdraw_macos.commands import run_command
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'w')
    monkeypatch.setattr(b,'_run',lambda op,*a:[_row(),True,[1,0,1,0,0],[12],['doc'],[_row(),[1,0,1,0,0],[12],['doc']],-1])
    result=run_command(b,12,'undo')
    assert result['status']=='completed' and 'Accessibility' in result['dialog_check']
