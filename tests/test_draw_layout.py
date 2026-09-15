import json
import pytest
from chemdraw_macos.draw import draw_structures

STRUCTURES=[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}]

@pytest.mark.parametrize('layout',[{'unknown':2},{'label_gap':float('nan')},{'h_gap':True},{'margin':0}])
def test_invalid_layout_rejected_before_native(tmp_path,layout):
    class NoNative:
        def __getattr__(self,name):raise AssertionError('Unexpected native call')
    with pytest.raises(ValueError,match='layout'):
        draw_structures(NoNative(),STRUCTURES,str(tmp_path/'out'),layout=layout)

def test_layout_persisted_before_native_import(tmp_path):
    class Timeout:
        def documents(self):return {'documents':[]}
        def import_file(self,path):raise RuntimeError('timeout')
    with pytest.raises(RuntimeError,match='timeout'):
        draw_structures(Timeout(),STRUCTURES,str(tmp_path/'out'),layout={'label_gap':8})
    request=json.loads((tmp_path/'out/request.json').read_text())
    assert request['layout']=={'label_gap':8}
