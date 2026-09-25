"""New canvas defaults must match subsequent manual editing."""
from contextlib import nullcontext
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.core import Bridge, style_cdxml
from test_api_drawing import EMPTY


def test_empty_defaults_are_native_guarded_and_reread():
    b=object.__new__(Bridge);b.lock=nullcontext();calls=[]
    b._run=lambda *args:calls.append(args)
    from chemdraw_macos.addin import source_token
    initial={'cdxml':EMPTY,'source_token':source_token(EMPTY),'document':{'file':''}}
    styled=style_cdxml(EMPTY,'house')
    class Backend:
        def read(self,did):
            assert did==42
            return {**initial,'cdxml':styled,'source_token':source_token(styled)}
    result=b.initialize_empty_style(42,initial,Backend(),'house')
    assert calls==[('empty_document_style',42,360,32,40,280,166,'Helvetica Neue',18,120,32,50)]
    assert result['cdxml']==styled


def test_populated_defaults_never_change():
    b=object.__new__(Bridge);b.lock=nullcontext()
    b._run=lambda *args:pytest.fail('Must not restyle existing content')
    text=EMPTY.replace('</page>','<t id="2" p="5 5"><s>keep</s></t></page>')
    # Fixture has a self-closing page.
    root=ET.fromstring(EMPTY);ET.SubElement(root.find('page'),'t',{'id':'2'})
    initial={'cdxml':ET.tostring(root,encoding='unicode')}
    assert b.initialize_empty_style(42,initial,object(),'house') is initial


def test_empty_defaults_failure_is_uncertain_not_retried():
    from chemdraw_macos.batch import NativeUncertain
    b=object.__new__(Bridge);b.lock=nullcontext();calls=[]
    def run(*args):calls.append(args);raise RuntimeError('timeout')
    b._run=run
    with pytest.raises(NativeUncertain):b.initialize_empty_style(42,{'cdxml':EMPTY},object(),'house')
    assert len(calls)==1


def test_empty_defaults_refuse_native_object_race_before_setters():
    script=(Path(__file__).parents[1]/'chemdraw_macos/native.applescript').read_text()
    branch=script.split('operation is "empty_document_style"')[1].split('else if operation')[0]
    assert branch.index('count of objects of targetDoc') < branch.index('set fixed length')
    assert 'activate' not in branch and 'save ' not in branch


def test_unused_native_default_font_is_verified_through_document_properties():
    b=object.__new__(Bridge);b.lock=nullcontext();b._run=lambda *args:None
    b.inspect=lambda did:{'settings':{'label_font':'Helvetica Neue','caption_font':'Helvetica Neue'}}
    root=ET.fromstring(style_cdxml(EMPTY,'house'));root.remove(root.find('fonttable'))
    class Backend:
        def read(self,did):return {'cdxml':ET.tostring(root,encoding='unicode')}
    assert b.initialize_empty_style(42,{'cdxml':EMPTY},Backend())['cdxml']
