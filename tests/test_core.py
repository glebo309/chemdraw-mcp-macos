from pathlib import Path
import json
import xml.etree.ElementTree as ET
import pytest
from chemdraw_macos.core import Bridge, style_cdxml, validate_cdxml, FORMATS

SAMPLE='''<CDXML BondLength="30"><page><fragment id="1"><n id="2" Element="8" p="30 20"><t><s font="3" size="10" color="4">OH</s></t></n><n id="3" p="0 20"/><b id="4" B="3" E="2" Display="WedgeBegin"/></fragment><t><s size="10">Caption</s></t></page></CDXML>'''

def test_style_preserves_chemistry_and_sets_explicit_labels():
    root=ET.fromstring(style_cdxml(SAMPLE,'house'))
    assert root.get('BondLength')=='18'
    assert float(root.get('LineWidth'))==pytest.approx(1.58)
    assert root.find('.//n/t/s').get('size')=='14'
    assert root.find('.//n/t/s').get('color')=='0'
    assert root.find('.//b').get('Display')=='WedgeBegin'
    assert root.find('.//n').get('p')=='30 20'
    assert root.find('.//page/t/s').get('size')=='8.28'

@pytest.mark.parametrize('xml',['<html/>','<!DOCTYPE x [<!ENTITY x "bad">]><CDXML/>','<CDXML>'])
def test_reject_invalid_xml(xml):
    with pytest.raises(ValueError):validate_cdxml(xml)

def test_unknown_style_rejected():
    with pytest.raises(ValueError):style_cdxml(SAMPLE,'fake')

def test_document_id_not_interpolated(tmp_path):
    b=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path)
    with pytest.raises(ValueError):b.inspect('1\nquit')

def test_timeout_is_not_retried(monkeypatch,tmp_path):
    import subprocess
    calls=[]
    def fail(*a,**kw):
        calls.append(1);raise subprocess.TimeoutExpired('osascript',1)
    monkeypatch.setattr(subprocess,'run',fail)
    b=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path)
    with pytest.raises(RuntimeError,match='not retried'):b.documents()
    assert len(calls)==1

def test_output_refuses_overwrite_and_wrong_extension(tmp_path):
    b=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path)
    file=tmp_path/'existing.pdf';file.write_text('keep')
    with pytest.raises(FileExistsError):b.output_path(str(file),'pdf')
    with pytest.raises(ValueError):b.output_path(str(tmp_path/'x.txt'),'svg')
    assert file.read_text()=='keep'

def test_native_export_names():
    assert FORMATS['svg']=='Scalable Vector Graphics (SVG)'
    assert FORMATS['cdxml']=='ChemDraw XML'

def test_import_always_copies_source(tmp_path,monkeypatch):
    src=tmp_path/'original.cdxml';src.write_text(SAMPLE)
    b=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path/'work')
    seen=[]
    monkeypatch.setattr(b,'_run',lambda op,*args: seen.append((op,args)) or [123,'copy','',False,1])
    b.import_file(str(src))
    assert seen[0][0]=='open'
    assert Path(seen[0][1][0])!=src
    assert src.read_text()==SAMPLE

def test_no_unrestricted_script_tool():
    from chemdraw_macos.server import mcp
    import asyncio
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert {'chemdraw_list_documents','chemdraw_import_file','chemdraw_clean',
            'chemdraw_apply_style','chemdraw_export','chemdraw_inspect_document'}<=names
    assert not any('execute_script' in n for n in names)


def test_delayed_open_is_reconciled_by_reading_without_opening_twice(tmp_path,monkeypatch):
    b=Bridge(app_path=Path('/Applications/ChemDraw 23.0.1.app'),workspace=tmp_path)
    calls=[];paths=[]
    def run(op,*args):
        calls.append(op)
        if op=='open':
            paths.append(args[0])
            raise RuntimeError('Could not identify the imported document uniquely')
        if calls.count('list')==1:return []
        return [[123,'working',paths[0],False,1]]
    monkeypatch.setattr(b,'_run',run)
    result=b.create(SAMPLE)
    assert result['document']['document_id']==123
    assert calls.count('open')==1 and calls.count('list')==2
