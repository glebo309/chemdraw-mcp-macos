import xml.etree.ElementTree as ET
import pytest
from chemdraw_macos.batch import _verify
from test_polish import SAMPLE

def drawing(explicit=True):
    root=ET.fromstring(SAMPLE);root.set('LineWidth','1.58')
    arrow=ET.SubElement(root.find('page'),'arrow',{'id':'50','Head3D':'220 80 0','Tail3D':'150 80 0','ArrowheadHead':'Full','ArrowheadType':'Solid'})
    if explicit:arrow.set('LineWidth','1.58')
    return root

def test_native_arrow_can_inherit_identical_document_stroke():
    _verify(ET.tostring(drawing(),encoding='unicode'),ET.tostring(drawing(False),encoding='unicode'))

@pytest.mark.parametrize('explicit',[False,True])
def test_effective_native_arrow_stroke_change_rejected(explicit):
    before=drawing(explicit);after=drawing(False);after.set('LineWidth','.5')
    with pytest.raises(ValueError,match='arrow.*LineWidth'):
        _verify(ET.tostring(before,encoding='unicode'),ET.tostring(after,encoding='unicode'))
