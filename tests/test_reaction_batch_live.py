"""Serial native acceptance for full-size reaction batching and real paper."""
import json
import os
from pathlib import Path
import struct
import time
import xml.etree.ElementTree as ET

import pytest

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires exclusive licensed ChemDraw')


def test_complete_glycoside_native_batch(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.reaction_batch import run_reaction_batch
    from test_reaction_batch import glycoside_reaction
    from PIL import Image
    bridge=Bridge();started=time.perf_counter()
    result=run_reaction_batch(bridge,glycoside_reaction(),tmp_path/'reaction')
    assert result['status']=='completed' and all(result['checks'].values())
    native=ET.parse(result['artifacts']['cdxml']).getroot()
    record=struct.unpack('>60h',bytes.fromhex(native.get('MacPrintInfo')))
    paper=result['planning']['paper']
    assert record[11]-record[9]==paper['width_pt']
    assert record[10]-record[8]==paper['height_pt']
    assert native.find('page').get('WidthPages')==native.find('page').get('HeightPages')=='1'
    symbols=native.findall('page/fragment/graphic')
    assert len(symbols)==4
    assert {g.get('SymbolType') for g in symbols}=={'CirclePlus','CircleMinus'}
    assert result['checks']['native_charge_clearance']
    assert result['checks']['native_charge_ownership']
    for g in symbols:
        atom=native.find(f'.//n[@id="{g[0].get("object")}"]')
        assert atom.get('Charge')==('1' if g.get('SymbolType')=='CirclePlus' else '-1')
        assert atom.get('Element')==('7' if g.get('SymbolType')=='CirclePlus' else '8')
    assert Image.open(result['artifacts']['png']).info['dpi']==pytest.approx((600,600),abs=.02)
    report={'seconds':time.perf_counter()-started,'result':result}
    (tmp_path/'native-result.json').write_text(json.dumps(report,indent=2))
    print('REACTION_BATCH_NATIVE='+str(tmp_path/'native-result.json'))


@pytest.mark.parametrize('paper',['A4 portrait','A4 landscape','A3 landscape'])
def test_native_physical_paper_roundtrip(tmp_path,paper):
    from chemdraw_macos.core import Bridge,style_cdxml
    from chemdraw_macos.reaction_batch import EMPTY,set_paper,PAPERS,_verify_paper
    b=Bridge();baseline=b.documents()
    with b.lock:
        did=b.create(set_paper(style_cdxml(EMPTY,'house'),paper),visible=False)['document']['document_id']
        path=tmp_path/'paper.cdxml';b.export(did,str(path),'cdxml')
        # The export completed deterministically. Close only this owned blank copy.
        b.close(did)
        w,h=PAPERS[paper]
        _verify_paper(path.read_text(),{'width_pt':w,'height_pt':h})
        page=ET.parse(path).getroot().find('page')
        assert page.get('WidthPages')==page.get('HeightPages')=='1'
        assert list(map(float,page.get('BoundingBox').split()))==[0,0,w,h]
        assert b.documents()==baseline
