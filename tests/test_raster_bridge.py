import sys
from pathlib import Path
from chemdraw_macos.core import Bridge

SVG='<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="50px"><path d="M0 0L10 0L10 10Z"/></svg>'

def test_png_uses_bounded_offline_raster_worker_and_retains_native_svg(tmp_path,monkeypatch):
    bridge=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path/'work')
    native=[];raster=[];out=tmp_path/'preview.png'
    def export(op,*args):
        assert op=='export' and args[-1]=='Scalable Vector Graphics (SVG)'
        native.append(Path(args[1]));native[-1].write_text(SVG)
    def run(command,**kwargs):
        raster.append((command,kwargs));out.write_bytes(b'fixture-png')
    monkeypatch.setattr(bridge,'_run',export)
    monkeypatch.setattr('chemdraw_macos.core.subprocess.run',run)
    result=bridge.export(123,str(out),'png',1600)
    assert raster[0][0]==[sys.executable,'-m','chemdraw_macos.raster',str(native[0]),str(out),'1600']
    assert raster[0][1]['timeout']==bridge.timeout
    assert raster[0][1]['check'] is True
    assert native[0].read_text()==SVG
    assert result['rasterizer']=='resvg'

def test_doctor_describes_opt_in_resolver_and_actual_rasterizer(monkeypatch):
    from chemdraw_macos.diagnostics import doctor
    report=doctor(connect=False)
    assert 'resvg' in report['renderer']
    assert 'opt-in' in report['network']
