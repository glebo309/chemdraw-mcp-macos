import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.scope_decoration import (
    plan_scope_decoration, verify_scope_decoration,
    decorate_scope_document, decorate_scope_file,
)
from chemdraw_macos.editing import source_token
from chemdraw_macos.polish import transform
from chemdraw_macos.batch import NativeUncertain
from test_batch import BatchBridge
from test_polish import SAMPLE
from test_scope import measured


GROUPS = [{'label': '', 'fragment_ids': ['1'], 'caption_ids': ['10']},
          {'label': '', 'fragment_ids': ['20'], 'caption_ids': ['30']}]


def source():
    root = ET.fromstring(SAMPLE)
    page = root.find('page');page.set('BoundingBox', '0 0 600 800')
    for e in page:
        transform(e, dx=80, dy=80 if e.get('id') in ('1', '10') else 260)
    return measured(ET.tostring(root, encoding='unicode'))


def test_frame_and_true_dotted_separator_preserve_source():
    original = source()
    decorated, plan = plan_scope_decoration(original, GROUPS)
    root = ET.fromstring(decorated)
    frame = root.find('page/graphic[@GraphicType="Rectangle"]')
    assert frame.get('RectangleType') == 'RoundEdge Shadow'
    assert frame.get('CornerRadius') == '600' and frame.get('ShadowSize') == '400'
    dots = root.findall('page/graphic[@GraphicType="Oval"]')
    assert len(dots) > 2
    assert all(g.get('OvalType') == 'Circle Filled' for g in dots)
    assert len({g.get('Center3D').split()[1] for g in dots}) == 1
    assert verify_scope_decoration(original, decorated, plan)['checks']['source_objects_preserved']


def test_named_group_labels_fit_existing_gaps_without_moving_molecules():
    groups = copy.deepcopy(GROUPS)
    groups[0]['label'] = 'Donating';groups[1]['label'] = 'Withdrawing'
    decorated, plan = plan_scope_decoration(source(), groups)
    labels = [t for t in ET.fromstring(decorated).findall('page/t') if t.get('id') in plan['label_ids']]
    assert [''.join(t.itertext()) for t in labels] == ['Donating', 'Withdrawing']
    assert verify_scope_decoration(source(), decorated, plan)['checks']['labels_and_page_fit']


def test_frame_and_separators_are_independently_optional():
    for frame, separators in [(False, True), (True, False), (False, False)]:
        text, plan = plan_scope_decoration(source(), GROUPS, frame, separators)
        root = ET.fromstring(text)
        assert bool(root.findall('page/graphic[@GraphicType="Rectangle"]')) == frame
        assert bool(root.findall('page/graphic[@GraphicType="Oval"]')) == separators
        assert verify_scope_decoration(source(), text, plan)['checks']['decoration_geometry_preserved']


@pytest.mark.parametrize('groups', [[], GROUPS[:1], GROUPS + GROUPS[:1], list(reversed(GROUPS)),
    [{**GROUPS[0], 'caption_ids': []}, GROUPS[1]],
    [{**GROUPS[0], 'extra': True}, GROUPS[1]],
    [{**GROUPS[0], 'label': 'bad\nlabel'}, GROUPS[1]]])
def test_group_ownership_and_order_fail_closed(groups):
    with pytest.raises(ValueError):plan_scope_decoration(source(), groups)


def test_missing_measurement_and_overflow_fail_closed():
    root = ET.fromstring(source());root.find('page/fragment').attrib.pop('BoundingBox')
    with pytest.raises(ValueError, match='measured'):plan_scope_decoration(ET.tostring(root, encoding='unicode'), GROUPS)
    root = ET.fromstring(source());root.find('page').set('BoundingBox', '0 0 180 380')
    with pytest.raises(ValueError, match='fit'):plan_scope_decoration(ET.tostring(root, encoding='unicode'), GROUPS)


@pytest.mark.parametrize('target,attribute,value', [
    ('page/graphic[@GraphicType="Rectangle"]', 'ShadowSize', '800'),
    ('page/graphic[@GraphicType="Rectangle"]', 'RectangleType', 'RoundEdge'),
    ('page/graphic[@GraphicType="Oval"]', 'Center3D', '0 0 0'),
    ('page/graphic[@GraphicType="Oval"]', 'OvalType', 'Circle'),
    ('page/fragment/n', 'p', '1 1'),
    ('page/t/s', 'size', '35'),
])
def test_changed_native_decoration_or_source_rejected(target, attribute, value):
    text, plan = plan_scope_decoration(source(), GROUPS);root = ET.fromstring(text)
    root.find(target).set(attribute, value)
    with pytest.raises(ValueError):verify_scope_decoration(source(), ET.tostring(root, encoding='unicode'), plan)


def test_extra_graphic_never_silently_stripped():
    text, plan = plan_scope_decoration(source(), GROUPS);root = ET.fromstring(text)
    ET.SubElement(root.find('page'), 'graphic', {'id': '99999', 'GraphicType': 'Rectangle', 'BoundingBox': '1 1 2 2'})
    with pytest.raises(ValueError):verify_scope_decoration(source(), ET.tostring(root, encoding='unicode'), plan)


def test_native_renumbering_is_supported():
    text, plan = plan_scope_decoration(source(), GROUPS);root = ET.fromstring(text)
    for e in root.find('page').iter():
        for key in ('id', 'B', 'E'):
            if e.get(key):e.set(key, str(int(e.get(key)) + 10000))
    assert verify_scope_decoration(source(), ET.tostring(root, encoding='unicode'), plan)['checks']['source_objects_preserved']


def test_document_workflow_leaves_only_new_final_copy(tmp_path):
    b = BatchBridge(tmp_path/'work');b.docs[1] = source()
    result = decorate_scope_document(b, 1, str(tmp_path/'out'), GROUPS, source_token(source()))
    assert result['audit']['status'] == 'checks_passed'
    assert b.docs[1] == source() and len(b.managed) == 1
    assert (tmp_path/'out/review.html').exists()


def test_stale_token_rejected_before_new_copy(tmp_path):
    b = BatchBridge(tmp_path/'work');b.docs[1] = source()
    with pytest.raises(ValueError, match='stale'):decorate_scope_document(b, 1, str(tmp_path/'out'), GROUPS, 'stale')
    assert not b.managed


def test_file_freeze_and_native_uncertainty(tmp_path):
    p = tmp_path/'source.cdxml';p.write_text(source());b = BatchBridge(tmp_path/'work')
    export = b.export
    def fail(did,path,format,pixels=3200):
        if Path(path).name == 'figure.svg':raise RuntimeError('timeout')
        return export(did,path,format,pixels)
    b.export = fail
    with pytest.raises(NativeUncertain):decorate_scope_file(b, str(p), str(tmp_path/'out'), GROUPS)
    assert len(b.managed) == 2 and not any(e[0] == 'close' for e in b.events)
    assert (tmp_path/'out/source-input.cdxml').read_text() == source()
    assert json.loads((tmp_path/'out/audit.json').read_text())['status'] == 'uncertain'


def test_file_source_mutation_is_not_a_success(tmp_path):
    p = tmp_path/'source.cdxml';p.write_text(source());b = BatchBridge(tmp_path/'work');export = b.export
    def change(did,path,format,pixels=3200):
        if Path(path).name == 'figure.png':p.write_text(source()+'\n')
        return export(did,path,format,pixels)
    b.export = change
    with pytest.raises(ValueError, match='Source file'):decorate_scope_file(b, str(p), str(tmp_path/'out'), GROUPS)
    assert json.loads((tmp_path/'out/audit.json').read_text())['status'] == 'failed'


def test_uncertain_final_close_after_file_mutation_does_not_close_source(tmp_path):
    p = tmp_path/'source.cdxml';p.write_text(source());b = BatchBridge(tmp_path/'work');export = b.export
    def change(did,path,format,pixels=3200):
        if Path(path).name == 'figure.png':p.write_text(source()+'\n')
        return export(did,path,format,pixels)
    closes = []
    def uncertain_close(did):
        closes.append(did)
        raise RuntimeError('uncertain close')
    b.export = change;b.close = uncertain_close
    with pytest.raises(NativeUncertain):decorate_scope_file(b, str(p), str(tmp_path/'out'), GROUPS)
    assert len(closes) == 1
    assert json.loads((tmp_path/'out/audit.json').read_text())['status'] == 'uncertain'


def test_old_atom_label_typography_and_new_label_alignment_are_preserved():
    groups = copy.deepcopy(GROUPS);groups[0]['label'] = 'Donating'
    text, plan = plan_scope_decoration(source(), groups)
    for selector,attribute,value in [('page/fragment/n/t/s','size','40'),
                                   (f'page/t[@id="{plan["label_ids"][0]}"]','Justification','Right')]:
        root = ET.fromstring(text);root.find(selector).set(attribute,value)
        with pytest.raises(ValueError):verify_scope_decoration(source(), ET.tostring(root,encoding='unicode'), plan)


def test_render_side_effects_are_checked_after_final_export(tmp_path):
    b = BatchBridge(tmp_path/'work');b.docs[1] = source();export = b.export
    def change(did,path,format,pixels=3200):
        result = export(did,path,format,pixels)
        if Path(path).name == 'figure.png':
            root = ET.fromstring(b.docs[did]);root.find('page/fragment/n').set('p','0 0')
            b.docs[did] = ET.tostring(root,encoding='unicode')
        return result
    b.export = change
    with pytest.raises(ValueError):decorate_scope_document(b,1,str(tmp_path/'out'),GROUPS,source_token(source()))
    assert json.loads((tmp_path/'out/audit.json').read_text())['status'] == 'failed'


def test_native_omits_default_black_and_inherited_frame_width():
    text, plan = plan_scope_decoration(source(), GROUPS);root = ET.fromstring(text)
    for g in root.findall('page/graphic'):g.attrib.pop('color')
    root.find('page/graphic[@GraphicType="Rectangle"]').attrib.pop('LineWidth')
    assert verify_scope_decoration(source(), ET.tostring(root,encoding='unicode'), plan)['checks']['decoration_geometry_preserved']
    root.set('color','2')
    with pytest.raises(ValueError):verify_scope_decoration(source(), ET.tostring(root,encoding='unicode'), plan)


def test_native_named_heading_numeric_size_and_explicit_helvetica_bold():
    original = source().replace('name="Arial"','name="Helvetica"')
    groups = copy.deepcopy(GROUPS);groups[0]['label'] = 'Group 1'
    text, plan = plan_scope_decoration(original,groups);root = ET.fromstring(text)
    ET.SubElement(root.find('fonttable'),'font',{'id':'238','name':'Helvetica Bold'})
    heading = root.find(f'page/t[@id="{plan["label_ids"][0]}"]/s')
    heading.set('font','238');heading.set('size','10')
    assert verify_scope_decoration(original,ET.tostring(root,encoding='unicode'),plan)['checks']['labels_and_page_fit']
    for attribute,value in [('size','11'),('face','0')]:
        bad = copy.deepcopy(root);bad.find(f'page/t[@id="{plan["label_ids"][0]}"]/s').set(attribute,value)
        with pytest.raises(ValueError):verify_scope_decoration(original,ET.tostring(bad,encoding='unicode'),plan)
    root.find('fonttable/font[@id="238"]').set('name','Arial Bold')
    with pytest.raises(ValueError):verify_scope_decoration(original,ET.tostring(root,encoding='unicode'),plan)
