from pathlib import Path
from contextlib import nullcontext
import pytest

from chemdraw_macos.core import Bridge


def test_production_keeps_intermediates_hidden_and_only_shows_final(tmp_path, monkeypatch):
    from chemdraw_macos.presentation import production_job
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'automatic_presentation',lambda:'interactive')
    calls=[]
    monkeypatch.setattr(b,'set_visibility',lambda did,visible:calls.append(('visibility',did,visible)))
    monkeypatch.setattr(b,'close',lambda did:calls.append(('close',did)))
    @production_job
    def inner(bridge):
        assert bridge._production_depth>0
        assert bridge.default_new_document_visible() is False
        return {'document':{'document_id':12}}
    @production_job
    def outer(bridge):
        inner(bridge)
        assert calls==[]
        return {'document':{'document_id':13}}
    b.managed.update((12,13))
    result=outer(b)
    assert calls==[('visibility',13,True)]
    assert result['presentation']['mode']=='interactive'
    assert b.default_new_document_visible() is True


def test_background_closes_only_successful_final_and_resets_on_failure(tmp_path,monkeypatch):
    from chemdraw_macos.presentation import production_job
    b=Bridge(app_path=tmp_path,workspace=tmp_path); b.managed.add(12)
    monkeypatch.setattr(b,'automatic_presentation',lambda:'background')
    calls=[];monkeypatch.setattr(b,'close',lambda did:calls.append(did) or {})
    @production_job
    def operation(bridge,fail=False):
        if fail:raise RuntimeError('uncertain native result')
        return {'document':{'document_id':12}}
    assert operation(b)['document_closed'] is True
    assert calls==[12]
    with pytest.raises(RuntimeError):operation(b,True)
    assert calls==[12]
    assert b.default_new_document_visible() is True


def test_auto_does_not_launch_app_to_check_visibility(tmp_path,monkeypatch):
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'app_running',lambda:False)
    monkeypatch.setattr(b,'_run',lambda *a:pytest.fail('Must not launch ChemDraw for detection'))
    assert b.automatic_presentation()=='background'


def test_auto_uses_visible_windows_not_merely_running_process(tmp_path,monkeypatch):
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'app_running',lambda:True)
    monkeypatch.setattr(b,'_run',lambda *a:[])
    assert b.automatic_presentation()=='background'
    monkeypatch.setattr(b,'_run',lambda *a:[12])
    assert b.automatic_presentation()=='interactive'


def test_hidden_import_and_create_share_policy(tmp_path,monkeypatch):
    from chemdraw_macos.presentation import production_job
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'work')
    monkeypatch.setattr(b,'automatic_presentation',lambda:'background')
    calls=[]
    monkeypatch.setattr(b,'_open_working',lambda path,visible=True:calls.append(visible) or {'document_id':12})
    monkeypatch.setattr(b,'close',lambda *a:{})
    text='<CDXML><page id="1"/></CDXML>'
    source=tmp_path/'input.cdxml';source.write_text(text)
    @production_job
    def operation(bridge):
        bridge.import_file(str(source))
        return bridge.create(text)
    operation(b)
    assert calls==[False,False]


def test_invalid_presentation_rejected_before_work(tmp_path):
    from chemdraw_macos.presentation import production_job
    @production_job
    def operation(bridge):pytest.fail('Must reject before work')
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    with pytest.raises(ValueError):operation(b,presentation='whatever')


def test_production_entrypoints_share_policy():
    from chemdraw_macos.draw import draw_structures
    from chemdraw_macos.reaction import build_reaction
    from chemdraw_macos.reaction_series import build_reaction_series
    from chemdraw_macos.scope_job import build_scope_job
    from chemdraw_macos.scope import grid_document,grid_file
    for fn in (draw_structures,build_reaction,build_reaction_series,build_scope_job,grid_document,grid_file):
        assert getattr(fn,'production_presentation',False)


def test_advanced_draw_auto_and_explicit_document_use_shared_delivery(tmp_path,monkeypatch):
    from chemdraw_macos import shared
    from chemdraw_macos.draw import draw_structures
    b=Bridge(app_path=tmp_path,workspace=tmp_path)
    monkeypatch.setattr(b,'automatic_presentation',lambda:'interactive')
    monkeypatch.setattr(b,'_run',lambda *a:pytest.fail('Must route to shared before generating a separate document'))
    calls=[]
    monkeypatch.setattr(shared,'run_shared',lambda *args:calls.append(args) or {'status':'completed'})
    structures=[{'compound_id':'1','label':'Example','smiles':'CCO'}]
    assert draw_structures(b,structures,str(tmp_path/'auto'))['status']=='completed'
    assert calls[-1][1]['structures']==structures and calls[-1][3] is None
    assert draw_structures(b,structures,str(tmp_path/'shared'),presentation='shared',document_id=42)['status']=='completed'
    assert calls[-1][3]==42
    assert calls[-1][1]['workflow']=='molecules'
