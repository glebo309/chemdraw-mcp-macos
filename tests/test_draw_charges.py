import json
import asyncio
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.draw import draw_structures


def test_invalid_charge_style_rejected_before_native(tmp_path):
    class NoNative:
        def __getattr__(self, name):
            raise AssertionError('Unexpected native call ' + name)
    with pytest.raises(ValueError, match='charge_style'):
        draw_structures(NoNative(), [{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],
                        str(tmp_path/'out'), charge_style='fake')


def test_charge_style_is_recorded_before_any_native_import(tmp_path):
    class Timeout:
        def documents(self): return {'documents':[]}
        def import_file(self, path): raise RuntimeError('import timeout')
    with pytest.raises(RuntimeError, match='import timeout'):
        draw_structures(Timeout(), [{'compound_id':'a','label':'Nitrobenzene','smiles':'O=[N+]([O-])c1ccccc1'}],
                        str(tmp_path/'out'), charge_style='circled')
    assert json.loads((tmp_path/'out/request.json').read_text())['charge_style']=='circled'


def test_charge_requests_use_formal_charge_not_label_and_skip_existing_symbols():
    from chemdraw_macos.draw import charge_requests
    from test_symbols import RAW, source
    requests=charge_requests(source())
    assert requests==[{'key':'charge-1100','kind':'charge','atom_id':'1100'},
                      {'key':'charge-4114','kind':'charge','atom_id':'4114'}]
    assert charge_requests(RAW)==[]


def test_multivalent_charge_rejected_instead_of_silently_omitted():
    from chemdraw_macos.draw import charge_requests
    with pytest.raises(ValueError, match='unit charges'):
        charge_requests('<CDXML><page><fragment><n id="2" Element="20" Charge="2"/></fragment></page></CDXML>')


def test_circled_mode_multivalent_input_rejected_before_native(tmp_path):
    class NoNative:
        def __getattr__(self, name): raise AssertionError('Unexpected native call')
    with pytest.raises(ValueError, match='unit charges'):
        draw_structures(NoNative(), [{'compound_id':'a','label':'Test','smiles':'C[S+2]C'}],
                        str(tmp_path/'out'), charge_style='circled')


def test_cli_forwards_charge_style(tmp_path,monkeypatch):
    from chemdraw_macos import cli
    calls=[]
    monkeypatch.setattr(cli,'Bridge',lambda:object())
    monkeypatch.setattr(cli,'draw_structures',lambda *a,**kw:calls.append(kw) or {})
    path=tmp_path/'input.json';path.write_text(json.dumps({'structures':[],'charge_style':'circled'}))
    assert cli.main(['draw','--manifest',str(path),'--output',str(tmp_path/'out')])==0
    assert calls[0]['charge_style']=='circled'


def test_mcp_advertises_and_forwards_charge_style(monkeypatch):
    from chemdraw_macos import server
    tool=next(t for t in asyncio.run(server.mcp.list_tools()) if t.name=='chemdraw_draw_structures')
    assert 'charge_style' in tool.inputSchema['properties']
    monkeypatch.setattr(server,'bridge',lambda:object())
    monkeypatch.setattr(server,'draw_structures',lambda *a,**kw: {'mode':a[-1]})
    assert server.chemdraw_draw_structures([], '/unused',charge_style='circled')['mode']=='circled'
