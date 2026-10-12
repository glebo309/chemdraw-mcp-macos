"""Shared drawing into a real multi-page ChemDraw document (as opened from a poster-sized template)."""
import os
import sys
import xml.etree.ElementTree as ET

import pytest

pytestmark = [pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires licensed running ChemDraw'),
              pytest.mark.skipif(sys.platform != 'win32', reason='Automatic single-page switch is Windows (COM) only')]

PAGE = '<page id="1" BoundingBox="0 0 1440 1620" WidthPages="2" HeightPages="3">{}</page>'
DOC = ('<CDXML BondLength="18" LineWidth="1.59" LabelFont="3" LabelSize="14" CaptionFont="3" CaptionSize="14">'
       '<fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable>' + PAGE + '</CDXML>')
CHAIN = ('<fragment id="10"><n id="11" p="{x} 110"/><n id="12" p="{x2} 119"/><n id="13" p="{x3} 110"/>'
         '<b id="14" B="11" E="12"/><b id="15" B="12" E="13"/></fragment>')
ETHANOL = [{'compound_id': '1', 'label': 'ethanol', 'smiles': 'CCO'}]


def chain(x):
    return CHAIN.format(x=x, x2=x + 15.6, x3=x + 31.2)


def page_of(text):
    page = ET.fromstring(text).find('page')
    return page.get('WidthPages'), page.get('HeightPages'), page.get('BoundingBox')


@pytest.fixture
def ctx(tmp_path):
    from chemdraw_macos.api_drawing import get_backend
    from chemdraw_macos.core import Bridge
    b = Bridge(workspace=tmp_path / 'native')
    before = b.documents()['documents']
    owned = []
    yield b, get_backend(b), owned, tmp_path
    for did in owned:
        b.close(did)
    assert sorted(d['document_id'] for d in b.documents()['documents']) == sorted(d['document_id'] for d in before)


def draw(b, did, tmp_path, name):
    from chemdraw_macos.api_drawing import run_api_drawing
    return run_api_drawing(b, {'workflow': 'molecules', 'structures': ETHANOL}, tmp_path / name, did)


def test_empty_multi_page_document_is_set_to_one_page_then_drawn(ctx):
    b, backend, owned, tmp_path = ctx
    did = b.create(DOC.format(''), visible=True)['document']['document_id']; owned.append(did)
    assert page_of(backend.read(did)['cdxml'])[:2] == ('2', '3')
    result = draw(b, did, tmp_path, 'empty')
    assert result['status'] == 'completed'
    assert result['page_layout'] == {'before': '2 x 3 pages', 'after': '1 x 1 page'}
    assert page_of(backend.read(did)['cdxml'])[:2] == ('1', '1')


def test_first_page_content_survives_the_switch_unchanged(ctx):
    b, backend, owned, tmp_path = ctx
    did = b.create(DOC.format(chain(100)), visible=True)['document']['document_id']; owned.append(did)
    result = draw(b, did, tmp_path, 'first')
    assert result['status'] == 'completed' and result['page_layout']['before'] == '2 x 3 pages'
    assert result['checks']['existing_content_preserved'] is True
    assert ET.fromstring(backend.read(did)['cdxml']).find('page').findall('fragment').__len__() == 2


def test_content_beyond_the_first_page_is_refused_and_left_alone(ctx):
    b, backend, owned, tmp_path = ctx
    did = b.create(DOC.format(chain(1000)), visible=True)['document']['document_id']; owned.append(did)
    before = backend.read(did)['cdxml']
    with pytest.raises(ValueError, match='outside the first page'):
        draw(b, did, tmp_path, 'far')
    after = backend.read(did)['cdxml']
    assert page_of(after) == page_of(before)
    assert [ET.tostring(e) for e in ET.fromstring(after).find('page')] == [ET.tostring(e) for e in ET.fromstring(before).find('page')]
