"""Adversarial review cases: chemistry must not disappear behind a green audit."""
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.polish import chemical_signature, normalize_cdxml
from chemdraw_macos.workflow import remap_ids


PAIR = '''<CDXML><page id="100">
<fragment id="1"><n id="2" p="0 0"/><n id="3" p="30 0" Element="8"/>
<b id="4" B="2" E="3"/></fragment>
</page></CDXML>'''


@pytest.mark.parametrize('query', [
    'SubstituentsExactly="2"',
    'SubstituentsUpTo="2"',
    'RingBondCount="2"',
    'UnsaturatedBonds="yes"',
])
def test_atom_queries_that_parser_ignores_are_rejected(query):
    source = PAIR.replace('id="2"', f'id="2" {query}')
    with pytest.raises(ValueError, match='Unsupported'):
        normalize_cdxml(source)


def test_polymer_repeat_semantics_are_not_validated_as_an_ordinary_molecule():
    source = PAIR.replace('</page>', '''
    <bracketedgroup id="20" BracketedObjectIDs="1" BracketUsage="SRU"
     RepeatCount="n" BoundingBox="-10 -10 40 10"/>
    </page>''')
    with pytest.raises(ValueError, match='Unsupported'):
        normalize_cdxml(source)


def test_id_remapping_does_not_assign_a_caption_to_different_chemistry():
    # Overall molecules and coordinates survive, but identities at those
    # coordinates have exchanged. Coordinate-only matching assigns wrong names.
    root = ET.fromstring(PAIR)
    fragment = ET.SubElement(root.find('page'), 'fragment', {'id': '10'})
    ET.SubElement(fragment, 'n', {'id': '11', 'p': '100 0'})
    ET.SubElement(fragment, 'n', {'id': '12', 'p': '130 0', 'Element': '7'})
    ET.SubElement(fragment, 'b', {'id': '13', 'B': '11', 'E': '12'})
    before = ET.tostring(root, encoding='unicode')
    root.find('.//n[@id="3"]').set('Element', '7')
    root.find('.//n[@id="12"]').set('Element', '8')
    after = ET.tostring(root, encoding='unicode')
    assert chemical_signature(before) == chemical_signature(after)
    with pytest.raises(ValueError, match='match|chemistry|identity'):
        remap_ids(before, after)


def test_explicit_hydrogen_is_retained_by_validation_and_normalization():
    source = '''<CDXML><page id="100"><fragment id="1">
    <n id="2" p="0 0" Element="8" NumHydrogens="1"/>
    <n id="3" p="30 0" Element="1"/>
    <b id="4" B="2" E="3"/>
    </fragment></page></CDXML>'''
    normalized, report = normalize_cdxml(source)
    assert chemical_signature(normalized) == chemical_signature(source)
    assert ET.fromstring(normalized).find('.//n[@Element="1"]') is not None
    assert report['checks']['chemistry_preserved']


def test_signature_distinguishes_opposite_tetrahedral_stereochemistry():
    source = '''<CDXML><page id="100"><fragment id="1">
    <n id="2" p="0 0"/><n id="3" p="0 -30" Element="9"/>
    <n id="4" p="30 0" Element="17"/><n id="5" p="0 30" Element="35"/>
    <n id="6" p="-30 0" Element="53"/>
    <b id="7" B="2" E="3" Display="WedgeBegin"/>
    <b id="8" B="2" E="4"/><b id="9" B="2" E="5"/>
    <b id="10" B="2" E="6"/></fragment></page></CDXML>'''
    opposite = source.replace('WedgeBegin', 'WedgedHashBegin')
    assert chemical_signature(source) != chemical_signature(opposite)
    normalized, _ = normalize_cdxml(source)
    assert chemical_signature(source) == chemical_signature(normalized)


def test_bond_topology_query_that_parser_ignores_is_rejected():
    source = PAIR.replace('id="4"', 'id="4" Topology="Ring"')
    with pytest.raises(ValueError, match='Unsupported'):
        normalize_cdxml(source)


def test_unchanged_source_claim_checks_unsaved_content_not_just_metadata(tmp_path):
    from test_workflow import FakeBridge
    from chemdraw_macos.workflow import polish_document

    bridge = FakeBridge(tmp_path / 'work')
    inspect = bridge.inspect
    create = bridge.create

    def inspect_modified(did):
        result = inspect(did)
        if did == 1:
            result['document']['modified'] = True
        return result

    def change_source_during_create(text):
        # An already-modified document can change again while its name, path,
        # modified flag and molecular count all remain the same.
        bridge.docs[1] = bridge.docs[1].replace('Methanol', 'Source altered')
        return create(text)

    bridge.inspect = inspect_modified
    bridge.create = change_source_during_create
    with pytest.raises(RuntimeError, match='Source|source'):
        polish_document(bridge, 1, str(tmp_path / 'out'))


def test_overlap_audit_does_not_ignore_page_graphics(tmp_path):
    from test_workflow import FakeBridge
    from chemdraw_macos.workflow import polish_document

    bridge = FakeBridge(tmp_path / 'work')
    bridge.docs[1] = bridge.docs[1].replace('</page>', '''
    <graphic id="80" GraphicType="Rectangle" RectangleType="Plain"
      BoundingBox="0 0 400 250" FillType="Solid"/>
    </page>''')
    # Either unsupported graphical content must fail closed, or its overlap
    # must prevent a successful all-interobject-overlaps audit.
    try:
        result = polish_document(bridge, 1, str(tmp_path / 'out'))
    except ValueError as exc:
        assert 'Unsupported' in str(exc)
    else:
        assert result['audit']['status'] == 'needs_review'
        assert not result['audit']['checks']['no_interobject_overlaps']
