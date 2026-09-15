import copy
import json
import os
from pathlib import Path

import pytest

from chemdraw_macos.annotations import plan_annotations
from chemdraw_macos.batch import batch_export
from chemdraw_macos.core import Bridge
from test_annotations import HEAD_RENDER_ARROWS

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')


def test_native_batch_exports_supported_mechanism_heads(tmp_path):
    root=Path(__file__).parents[1]
    source=(root/'examples/sn2-annotation-input.cdxml').read_text()
    arrows=json.loads((root/'examples/sn2-annotation-recipe.json').read_text())['arrows']
    items=[]
    for head in ('full','left','right'):
        spec=copy.deepcopy(arrows)
        if head!='full':
            # Geometric fishhook fixture only; charge-symbol sources denote pairs.
            spec=copy.deepcopy(HEAD_RENDER_ARROWS)
            for arrow in spec:arrow.update(electrons=1,fishhook_side=head)
        text,_=plan_annotations(source,spec)
        file=tmp_path/f'{head}.cdxml';file.write_text(text)
        items.append({'key':head,'source':str(file),'formats':['pdf','cdx']})
    bridge=Bridge(workspace=tmp_path/'workspace');baseline=bridge.documents()
    result=batch_export(bridge,items,str(tmp_path/'batch'))
    assert result['status']=='completed',result
    assert bridge.documents()==baseline
    assert all(i['checks']['curve_geometry_preserved'] and i['checks']['existing_charge_symbols_preserved'] for i in result['items'])
    assert all((tmp_path/'batch'/i['key']/f"{i['key']}.pdf").is_file() for i in items)
    print('BATCH_ANNOTATION_REVIEW='+str(tmp_path/'batch/review.html'))
