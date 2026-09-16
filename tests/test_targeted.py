import copy
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import style_cdxml
from chemdraw_macos.editing import source_token
from chemdraw_macos.polish import chemical_signature


def sheet():
    return style_cdxml('<CDXML><page id="1"><fragment id="10"><n id="11" p="100 100"/><n id="12" Element="7" NumHydrogens="2" p="118 100"><t><s>NH2</s></t></n><b id="13" B="11" E="12"/></fragment><fragment id="20"><n id="21" p="280 180"/><n id="22" Element="8" NumHydrogens="1" p="298 180"><t><s>OH</s></t></n><b id="23" B="21" E="22"/></fragment><t id="30" p="90 150"><s>Keep this caption</s></t></page></CDXML>', 'house')


def chiral_sheet():
    return style_cdxml('<CDXML><page id="1"><fragment id="10"><n id="11" p="100 100"/><n id="12" Element="9" p="82 100"><t><s>F</s></t></n><n id="14" Element="17" p="109 84.4115"><t><s>Cl</s></t></n><n id="16" Element="35" p="109 115.5885"><t><s>Br</s></t></n><b id="13" B="11" E="12"/><b id="15" B="11" E="14"/><b id="17" B="11" E="16"/></fragment></page></CDXML>', 'house')


def test_inventory_and_selection_do_not_pretend_native_highlighting():
    from chemdraw_macos.targeted import inspect_targets, prepare_selection
    text = sheet()
    found = inspect_targets(text)
    assert [a['id'] for a in found['atoms'] if a['element'] == 'N'] == ['12']
    selected = prepare_selection(text, 'atom', ['12'], source_token(text))
    assert selected['ids'] == ['12']
    assert selected['native_ui_selection'] is False
    assert selected['objects'][0]['element'] == 'N'
    assert selected['source_token'] == source_token(text)


@pytest.mark.parametrize('kind,ids,token', [('atom',['missing'],None), ('bond',['12'],None), ('atom',['12','12'],None), ('atom',['12'],'stale')])
def test_selection_rejects_invalid_or_stale_targets(kind,ids,token):
    from chemdraw_macos.targeted import prepare_selection
    with pytest.raises(ValueError):
        prepare_selection(sheet(),kind,ids,token or source_token(sheet()))


def test_ring_attaches_at_exact_nitrogen_and_keeps_other_molecule_and_caption():
    from chemdraw_macos.targeted import prepare_selection, plan_target_edit
    text=sheet(); selected=prepare_selection(text,'atom',['12'],source_token(text))
    planned,report=plan_target_edit(text,selected,{'kind':'attach_ring','size':6,'angle_degrees':0})
    old=ET.fromstring(text);new=ET.fromstring(planned)
    assert ET.tostring(old.find(".//fragment[@id='20']"))==ET.tostring(new.find(".//fragment[@id='20']"))
    assert ET.tostring(old.find(".//t[@id='30']"))==ET.tostring(new.find(".//t[@id='30']"))
    assert chemical_signature(planned)==['CNC1CCCCC1','CO']
    assert report['added_atoms']==6 and report['added_bonds']==7
    for node in old.findall('.//n'):
        assert node.get('p')==new.find(f".//n[@id='{node.get('id')}']").get('p')


def test_dashed_wedge_is_oriented_from_explicit_atom_and_stereo_is_reported():
    from chemdraw_macos.targeted import prepare_selection, plan_target_edit
    text=chiral_sheet(); selected=prepare_selection(text,'bond',['13'],source_token(text))
    op={'kind':'bond_display','display':'hashed_wedge','from_atom_id':'11','allow_stereo_change':True}
    planned,report=plan_target_edit(text,selected,op)
    assert ET.fromstring(planned).find(".//b[@id='13']").get('Display')=='WedgedHashBegin'
    assert '@' in chemical_signature(planned)[0]
    assert report['stereo_change_authorized'] is True
    for bid in ('15','17'):
        assert ET.tostring(ET.fromstring(text).find(f".//b[@id='{bid}']"))==ET.tostring(ET.fromstring(planned).find(f".//b[@id='{bid}']"))


@pytest.mark.parametrize('op',[
    {'kind':'bond_display','display':'hashed_wedge','from_atom_id':'11'},
    {'kind':'bond_display','display':'hashed_wedge','from_atom_id':'missing','allow_stereo_change':True},
    {'kind':'bond_display','display':'unknown','from_atom_id':'11','allow_stereo_change':True},
])
def test_wedge_rejects_ambiguous_or_unapproved_stereo(op):
    from chemdraw_macos.targeted import prepare_selection, plan_target_edit
    text=chiral_sheet(); selected=prepare_selection(text,'bond',['13'],source_token(text))
    with pytest.raises(ValueError):plan_target_edit(text,selected,op)


@pytest.mark.parametrize('op',[
    {'kind':'attach_ring','size':True,'angle_degrees':0},
    {'kind':'attach_ring','size':6,'angle_degrees':float('nan')},
    {'kind':'attach_ring','size':6,'angle_degrees':180},
    {'kind':'attach_ring','size':6,'angle_degrees':0,'fused':True},
])
def test_ring_rejects_invalid_geometry_overlap_or_unknown_fields(op):
    from chemdraw_macos.targeted import prepare_selection, plan_target_edit
    text=sheet();selected=prepare_selection(text,'atom',['12'],source_token(text))
    with pytest.raises(ValueError):plan_target_edit(text,selected,op)


def test_native_target_verifier_rejects_changed_untargeted_coordinates():
    from chemdraw_macos.targeted import verify_targeted
    source=sheet();root=ET.fromstring(source)
    root.find(".//n[@id='21']").set('p','281 180')
    with pytest.raises(ValueError):verify_targeted(source,ET.tostring(root,encoding='unicode'))


def test_stale_selection_rejected_before_native_create(tmp_path):
    from chemdraw_macos.targeted import edit_targets_document, prepare_selection
    from contextlib import nullcontext
    text=sheet();selected=prepare_selection(text,'atom',['12'],source_token(text))
    class Fake:
        lock=nullcontext()
        def _new_path(self,*a):return tmp_path/'snapshot.cdxml'
        def export(self,*a): (tmp_path/'snapshot.cdxml').write_text(text.replace('118 100','119 100'))
        def create(self,*a):pytest.fail('Stale source reached native creation')
    with pytest.raises(ValueError,match='stale'):
        edit_targets_document(Fake(),42,str(tmp_path/'out'),selected,{'kind':'attach_ring','size':6,'angle_degrees':0})


def test_api_and_cli_are_reachable(monkeypatch,tmp_path):
    from chemdraw_macos import server,cli,targeted
    calls=[]
    monkeypatch.setattr(targeted,'inspect_targets_document',lambda b,d:calls.append(d) or {'ok':True})
    monkeypatch.setattr(server,'bridge',lambda:None)
    monkeypatch.setattr(cli,'Bridge',lambda:None)
    assert server.chemdraw_inspect_targets(42)=={'ok':True}
    assert cli.main(['inspect-targets','42'])==0
    assert calls==[42,42]


def test_alignment_preflight_accepts_only_explicit_molecules_and_native_actions():
    from chemdraw_macos.targeted import prepare_selection, validate_alignment
    text=sheet();selection=prepare_selection(text,'molecule',['10','20'],source_token(text))
    assert validate_alignment(text,selection,{'kind':'native_align','action':'align_top'})['ids']==['10','20']
    for operation in ({'kind':'native_align','action':'quit'}, {'kind':'native_align','action':'align_top','extra':True}):
        with pytest.raises(ValueError):validate_alignment(text,selection,operation)
    atom=prepare_selection(text,'atom',['12'],source_token(text))
    with pytest.raises(ValueError):validate_alignment(text,atom,{'kind':'native_align','action':'align_top'})


def test_native_bond_warning_is_retained_and_reported_not_treated_as_chemistry():
    from chemdraw_macos.targeted import inspect_targets
    root=ET.fromstring(sheet())
    root.find('.//b').set('Warning','Native diagnostic')
    info=inspect_targets(ET.tostring(root,encoding='unicode'))
    assert info['warnings']==[{'kind':'b','id':'13','message':'Native diagnostic'}]
