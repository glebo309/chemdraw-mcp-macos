import struct
import xml.etree.ElementTree as ET
import pytest
from chemdraw_macos.styles import inspect_style_file, validate_style
from chemdraw_macos.core import style_cdxml
from chemdraw_macos.polish import normalize_cdxml
from test_polish import SAMPLE

def prop(tag,data):return struct.pack('<HH',tag,len(data))+data

def binary_style():
    fonts=struct.pack('<HHHHH',0,1,3,10000,5)+b'Arial'
    return (b'VjCD0100'+b'\x04\x03\x02\x01'+bytes(16)+struct.pack('<HI',0x8000,0)+
      prop(0x100,fonts)+b''.join(prop(t,struct.pack('<i',round(v*65536))) for t,v in
      [(0x805,18),(0x806,2),(0x807,1.58),(0x808,1.6),(0x809,2.5),(0x803,120)])+
      prop(0x804,struct.pack('<H',180))+prop(0x80a,struct.pack('<HHHH',3,96,280,0))+
      prop(0x80b,struct.pack('<HHHH',3,0,240,0))+prop(0x999,b'ab')+bytes(4))

def test_binary_stylesheet_import_records_values_and_ignored_properties(tmp_path):
    p=tmp_path/'test.cds';p.write_bytes(binary_style())
    r=inspect_style_file(str(p));s=r['preset']
    assert s['font']=='Arial' and s['CaptionFontName']=='Arial'
    assert float(s['LineWidth'])==pytest.approx(1.58,abs=2e-5)
    assert s['LabelSize']=='14' and s['CaptionSize']=='12'
    assert s['BondSpacing']=='18'
    assert '0x0999' in r['unapplied_properties']
    assert p.read_bytes()==binary_style()

def test_modern_native_22_byte_header(tmp_path):
    p=tmp_path/'native.cds';data=binary_style();p.write_bytes(data[:22]+data[28:])
    assert inspect_style_file(str(p))['preset']['LabelSize']=='14'

def test_custom_preset_reaches_polish_and_native_assembly(tmp_path,monkeypatch):
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts',lambda:['Arial'],raising=False)
    from test_workflow import FakeBridge
    from chemdraw_macos.workflow import polish_document
    from test_draw import ETHANOL
    from chemdraw_macos.draw import prepare_structures,combine_native_structures
    spec={'BondLength':'18','LineWidth':'1.2','BoldWidth':'2','LabelSize':'13','CaptionSize':'12','font':'Arial'}
    result=polish_document(FakeBridge(tmp_path/'work'),1,str(tmp_path/'out'),preset=spec)
    assert result['audit']['checks']['native_roundtrip_chemistry_preserved']
    records=prepare_structures([{'compound_id':'1','label':'Ethanol','smiles':'CCO'}])
    text,_=combine_native_structures([ETHANOL],records,spec)
    assert ET.fromstring(text).get('LabelSize')=='13'

def test_missing_custom_font_rejected_before_native_calls(tmp_path,monkeypatch):
    from chemdraw_macos.draw import draw_structures
    monkeypatch.setattr('chemdraw_macos.styles._installed_fonts',lambda:['Arial'],raising=False)
    class NoNative:
        def __getattr__(self,name):raise AssertionError('Native called before font preflight')
    spec={'BondLength':'18','LineWidth':'1','BoldWidth':'2','LabelSize':'14','CaptionSize':'12','font':'Missing Font'}
    with pytest.raises(ValueError,match='font'):
        draw_structures(NoNative(),[{'compound_id':'1','label':'Ethanol','smiles':'CCO'}],str(tmp_path/'new'),preset=spec)

def test_xml_import_custom_preset_normalizes_and_respects_spacing(tmp_path):
    p=tmp_path/'template.cdxml'
    p.write_text('<CDXML BondLength="22" LineWidth="1.2" BoldWidth="3" LabelSize="13" CaptionSize="12" LabelFont="3" CaptionFont="4" BondSpacing="15"><fonttable><font id="3" name="Arial"/><font id="4" name="Helvetica"/></fonttable><page/></CDXML>')
    r=inspect_style_file(str(p));s=r['preset']
    assert 'HashSpacing' in r['defaults_used']
    out,_=normalize_cdxml(SAMPLE,s);root=ET.fromstring(out)
    assert root.get('BondSpacing')=='15'
    assert root.get('LabelFont')!=root.get('CaptionFont')
    assert root.find('.//b').get('LineWidth')=='1.2'

@pytest.mark.parametrize('bad',[b'',binary_style()[:-3],binary_style()+b'x',b'VjCD0100'+bytes(20)+bytes(4)])
def test_malformed_binary_rejected(tmp_path,bad):
    p=tmp_path/'bad.cds';p.write_bytes(bad)
    with pytest.raises(ValueError):inspect_style_file(str(p))

def test_custom_unknown_nonfinite_and_absurd_values_rejected():
    base={'BondLength':'18','LineWidth':'1','BoldWidth':'2','LabelSize':'14','CaptionSize':'12','font':'Arial'}
    for change in ({'foo':'3'},{'LineWidth':'nan'},{'BondLength':'0'},{'font':'x\n'},{'LabelFace':'12345'}):
        with pytest.raises(ValueError):validate_style({**base,**change})

def test_incomplete_style_does_not_guess_core_parameters(tmp_path):
    p=tmp_path/'bad.cdxml';p.write_text('<CDXML/>')
    with pytest.raises(ValueError):inspect_style_file(str(p))
