"""Opt-in native complete-table pagination and physical export acceptance."""
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_ADDIN_LIVE_TEST')!='1',reason='Requires local native add-in')


def test_native_same_document_pagination_and_physical_export(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.addin import get_backend
    from chemdraw_macos.harness import run_drawing
    from chemdraw_macos.physical_export import export_figure
    from test_api_drawing import EMPTY
    b=Bridge();backend=get_backend(b)
    baseline=b.documents()['documents']
    created=b.create(EMPTY);did=created['document']['document_id']
    smiles='CCN(CC)C(=O)[C@H]1CN([C@@H]2CC3=CNC4=CC=CC(=C34)C2=C1)C'
    try:
        parent=run_drawing(b,{'molecules':[{'format':'smiles','value':smiles,'label':'Reference'}]},str(tmp_path/'parent'),presentation='shared',document_id=did)
        assert parent['status']=='completed',parent
        request={'molecules':[{'format':'smiles','value':smiles,'label':f'Cell {i+1}'} for i in range(17)]}
        table=run_drawing(b,request,str(tmp_path/'table'),presentation='shared',document_id=did)
        assert table['status']=='completed',table
        assert table['document']['document_id']==did and table['document']['molecule_count']==18
        for check in ('existing_content_preserved','page_expansion_verified','native_table_centres_and_baselines_verified'):
            assert table['checks'][check]
        root=ET.parse(table['artifacts']['cdxml']).getroot()
        count=int(root.find('page').get('HeightPages'))
        assert count>1
        output=export_figure(b,did,str(tmp_path/'exports'),600,include_pdf=True)
        assert len(output['pages'])==count and output['source_preserved']
        assert Path(output['artifacts']['pdf']).read_bytes().startswith(b'%PDF')
        from PIL import Image
        for page in output['pages']:
            picture=Image.open(page['png'])
            assert picture.info['dpi']==pytest.approx((600,600),abs=.02)
            assert picture.mode=='RGBA'
        assert {d['document_id'] for d in b.documents()['documents']}=={did,*[d['document_id'] for d in baseline]}
        (tmp_path/'native-acceptance.json').write_text(json.dumps({'table':table,'exports':output},indent=2))
        b.close(did)
    finally:backend.close()
