import io
import struct
import xml.etree.ElementTree as ET

import pytest

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="72px" height="36px" viewBox="0 0 72 36"><path d="M9 18H27" stroke="black" stroke-width="1"/></svg>'


def test_physical_svg_changes_only_units_not_geometry():
    from chemdraw_macos.physical_export import physical_svg
    result, size = physical_svg(SVG)
    original, physical = ET.fromstring(SVG), ET.fromstring(result)
    assert size == (72, 36)
    assert physical.get('width') == '72pt'
    assert physical.get('height') == '36pt'
    assert physical.get('viewBox') == original.get('viewBox')
    assert ET.tostring(physical[0]) == ET.tostring(original[0])


def test_same_bond_has_same_pixels_in_different_crops_and_embedded_dpi():
    from chemdraw_macos.physical_export import physical_png
    Image = pytest.importorskip('PIL.Image')
    for width, expected in [(72, 600), (144, 1200)]:
        svg = SVG.replace('72px', f'{width}px').replace('0 0 72 36', f'0 0 {width} 36')
        png = physical_png(svg, dpi=600)
        img = Image.open(io.BytesIO(png))
        assert img.size == (expected, 300)
        assert img.info['dpi'] == pytest.approx((600, 600), abs=.02)
        assert img.mode == 'RGBA'
        assert 149 <= img.getbbox()[2] - img.getbbox()[0] <= 151


@pytest.mark.parametrize('dpi', [True, 0, 71, 1201, float('nan'), '600'])
def test_invalid_dpi_rejected(dpi):
    from chemdraw_macos.physical_export import physical_png
    with pytest.raises(ValueError): physical_png(SVG, dpi=dpi)


def test_unsupported_svg_or_distorted_coordinates_rejected():
    from chemdraw_macos.physical_export import physical_svg
    for bad in [SVG.replace('</svg>', '<image href="https://example.com/a"/></svg>'),
                SVG.replace('0 0 72 36', '0 0 144 36')]:
        with pytest.raises(ValueError): physical_svg(bad)


def test_export_tool_and_cli_share_physical_workflow(monkeypatch, tmp_path, capsys):
    from chemdraw_macos import server, cli, physical_export
    calls = []
    def run(bridge, document_id, output_dir, dpi=600):
        calls.append((document_id, output_dir, dpi)); return {'status': 'completed'}
    monkeypatch.setattr(physical_export, 'export_figure', run)
    monkeypatch.setattr(server, 'bridge', lambda: object())
    assert server.chemdraw_export_figure(123, str(tmp_path/'a'), dpi=300)['status']=='completed'
    cli.main(['export-figure', '123', '--output', str(tmp_path/'b'), '--dpi', '600'])
    assert calls == [(123,str(tmp_path/'a'),300),(123,str(tmp_path/'b'),600)]


def test_pdf_uses_owned_hidden_copy_and_preserves_source(monkeypatch,tmp_path):
    import threading
    from types import SimpleNamespace
    from chemdraw_macos import addin
    from chemdraw_macos.physical_export import export_figure
    from chemdraw_macos.api_drawing import plan_addition
    from test_api_drawing import EMPTY
    xml,_=plan_addition(EMPTY,[{'compound_id':'a','label':'Example','smiles':'CCO'}])
    calls=[]
    class Bridge:
        lock=threading.RLock()
        _id=staticmethod(int)
        def create(self,text,visible):
            assert text==xml and visible is False
            calls.append('create');return {'document':{'document_id':456}}
        def export(self,did,path,fmt):
            from pathlib import Path
            calls.append((did,fmt));Path(path).write_text(SVG if fmt=='svg' else '%PDF-1.4')
        def close(self,did):
            assert did==456;calls.append('close')
    monkeypatch.setattr(addin,'get_backend',lambda b: SimpleNamespace(read=lambda did: {'cdxml':xml}))
    result=export_figure(Bridge(),123,str(tmp_path/'out'),dpi=300,include_pdf=True)
    assert result['source_preserved']
    assert result['artifacts']['pdf'].endswith('figure.pdf')
    assert calls==[(123,'svg'),'create',(456,'pdf'),'close']


def test_multiple_pages_export_separately_without_fit_or_rescale():
    from chemdraw_macos.physical_export import page_svgs
    xml='<CDXML><page BoundingBox="0 0 72 72" WidthPages="1" HeightPages="2"/></CDXML>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="72px" height="72px" viewBox="0 0 72 72"><path transform="matrix(0.05 0 0 0.05 -10 -20)" d="M180 360H540" stroke="black"/></svg>'
    pages=page_svgs(svg,xml)
    assert len(pages)==2
    assert [ET.fromstring(p).get('viewBox') for p in pages]==['-10 -20 72 36','-10 16 72 36']
    assert all(ET.fromstring(p).get('width')=='72px' for p in pages)
    assert all(ET.tostring(ET.fromstring(p)[0])==ET.tostring(ET.fromstring(svg)[0]) for p in pages)
    with pytest.raises(ValueError):page_svgs(svg.replace('0.05 0 0 0.05','0.1 0 0 0.05'),xml)
