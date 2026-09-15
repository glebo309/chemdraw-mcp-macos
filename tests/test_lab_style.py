import copy
import json
from pathlib import Path

import pytest

from chemdraw_macos.lab_style import make_package, validate_package, save_package, load_package, styled_options

STYLE = {'BondLength':18,'LineWidth':1.58,'BoldWidth':2,'LabelSize':14,'CaptionSize':12,'font':'Arial'}

def package():
    return make_package('lab-standard','1.0.0',STYLE)

def test_package_portable_versioned_and_content_addressed(tmp_path):
    p=package()
    assert p['package_version']=='1.0.0'
    assert p['settings']['preset']['LineWidth']=='1.58'
    assert len(p['sha256'])==64
    output=tmp_path/'lab-style.json'
    save_package(p,output)
    assert load_package(output)==p
    assert '/Users/' not in output.read_text()
    with pytest.raises(FileExistsError):save_package(p,output)

def test_tampering_and_unknown_fields_rejected():
    p=package();p['settings']['preset']['LineWidth']='2'
    with pytest.raises(ValueError,match='hash'):validate_package(p)
    p=package();p['ignored_setting']=True
    with pytest.raises(ValueError):validate_package(p)

@pytest.mark.parametrize('name,version',[('../private','1.0.0'),('ok','latest'),('ok','1.0'),('ok','1.0.0\n')])
def test_names_and_versions_bounded(name,version):
    with pytest.raises(ValueError):make_package(name,version,STYLE)

@pytest.mark.parametrize('settings',[
    {'grid':{'h_gap':float('nan')}}, {'symbols':{'clearance':0}},
    {'reaction':{'row_gap':True}}, {'bad':{}}, {'grid':{'mystery':9}},
])
def test_unknown_or_unsafe_settings_rejected(settings):
    with pytest.raises(ValueError):make_package('lab','1.0.0',STYLE,**settings)

def test_styles_are_applied_not_advisory():
    p=package()
    draw=styled_options(p,'draw',{'structures':[]})
    assert draw['preset']==p['settings']['preset']
    assert draw['layout']==p['settings']['grid']
    grid=styled_options(p,'grid',{'cells':[]})
    assert grid['label_gap']==p['settings']['grid']['label_gap']
    reaction=styled_options(p,'reaction-series',{'steps':[]})
    assert reaction['layout']==p['settings']['reaction']
    scope=styled_options(p,'scope-job',{'accept_all':True})
    assert scope['layout']==p['settings']['grid']
    symbols=styled_options(p,'symbols',{'symbols':[]})
    assert symbols['line_width']==1.58
    assert symbols['span']==10.5
    assert 'preset' not in symbols

def test_reaction_default_separates_native_condition_inference_bands():
    assert package()['settings']['reaction']['row_gap']==120

def test_explicit_conflict_rejected_not_silently_overridden():
    p=package()
    with pytest.raises(ValueError,match='conflict'):styled_options(p,'draw',{'preset':'acs-1996'})
    with pytest.raises(ValueError,match='conflict'):styled_options(p,'draw',{'layout':{'h_gap':99}})
    assert styled_options(p,'draw',{'layout':{'h_gap':18}})['layout']['h_gap']==18
    with pytest.raises(ValueError):styled_options(p,'invented',{})

def test_reference_manifest_is_plain_data_and_never_executes_or_bundles_sources():
    p=make_package('lab','1.0.0',STYLE,references=[{'name':'scope','sha256':'a'*64,'description':'Reviewed scope example'}])
    assert p['references'][0]['name']=='scope'
    with pytest.raises(ValueError):make_package('lab','1.0.0',STYLE,references=[{'path':'/private/font.ttf'}])

def test_input_unchanged():
    p=package();original=copy.deepcopy(p);recipe={'structures':[]}
    styled_options(p,'draw',recipe)
    assert p==original and recipe=={'structures':[]}

def test_duplicate_json_keys_rejected(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(ValueError,match='Duplicate'):load_package(p)

def test_styled_job_consumes_settings_and_records_exact_package(tmp_path,monkeypatch):
    from chemdraw_macos.lab_style import run_styled_job
    import chemdraw_macos.draw
    calls=[]
    def draw(bridge,output_dir,**options):
        calls.append(options);Path(output_dir).mkdir()
        return {'output_dir':output_dir,'audit':{'status':'checks_passed'}}
    monkeypatch.setattr(chemdraw_macos.draw,'draw_structures',draw)
    p=package();out=tmp_path/'out'
    result=run_styled_job(object(),p,'draw',{'structures':[]},str(out))
    assert calls[0]['layout']==p['settings']['grid']
    assert load_package(out/'lab-style.json')==p
    assert result['audit']['lab_style']['sha256']==p['sha256']
    assert json.loads((out/'audit.json').read_text())==result['audit']

def test_styled_job_rejects_unknown_fields_before_native(tmp_path):
    from chemdraw_macos.lab_style import run_styled_job
    class NoNative:
        def __getattr__(self,name):raise AssertionError('Native called')
    with pytest.raises(ValueError,match='fields'):
        run_styled_job(NoNative(),package(),'draw',{'invented':True},str(tmp_path/'out'))

def test_styled_draw_forwards_explicit_charge_mode(tmp_path,monkeypatch):
    from chemdraw_macos.lab_style import run_styled_job
    import chemdraw_macos.draw
    def draw(bridge,output_dir,**options):
        assert options['charge_style']=='circled'
        Path(output_dir).mkdir()
        return {'audit':{}}
    monkeypatch.setattr(chemdraw_macos.draw,'draw_structures',draw)
    run_styled_job(object(),package(),'draw',{'structures':[],'charge_style':'circled'},str(tmp_path/'out'))
