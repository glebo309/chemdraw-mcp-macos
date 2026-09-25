"""Serial native defaults acceptance on a private blank file only."""
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed ChemDraw')


def test_manual_edit_defaults_match_new_objects_without_replacing_document(tmp_path):
    from chemdraw_macos.core import Bridge
    from test_api_drawing import EMPTY
    b=Bridge(workspace=tmp_path/'native')
    with b.lock:
        before=b.documents()['documents']
        did=b.create(EMPTY,visible=False)['document']['document_id']
        class Backend:
            n=0
            def read(self,target):
                self.n+=1;path=tmp_path/f'read-{self.n}.cdxml'
                b.export(target,str(path),'cdxml')
                return {'cdxml':path.read_text(),'document':next(d for d in b.documents()['documents'] if d['document_id']==target)}
        backend=Backend()
        initial=backend.read(did)
        active=b._run('active_document')
        if active!=did:b._run('select_document',did,active)
        result=b.initialize_empty_style(did,initial,backend)
        root=ET.fromstring(result['cdxml'])
        assert float(root.get('LineWidth'))==pytest.approx(1.58,abs=.026)
        assert float(root.get('BondLength'))==18
        assert float(root.get('LabelSize'))==14
        assert not len(root.find('page'))
        b.close(did)
        assert sorted(b.documents()['documents'],key=lambda d:d['document_id'])==sorted(before,key=lambda d:d['document_id'])
