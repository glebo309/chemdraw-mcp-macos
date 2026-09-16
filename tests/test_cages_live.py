import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires licensed running ChemDraw')


def test_native_cage_drawings_keep_identity_and_crossing_order(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.draw import draw_structures
    bridge = Bridge()
    baseline = bridge.documents()
    final = None
    try:
        result = draw_structures(bridge, [
            {'compound_id': 'cubane', 'label': 'Cubane', 'smiles': 'C12C3C4C1C5C2C3C45'},
            {'compound_id': 'bullvalene', 'label': 'Bullvalene', 'smiles': 'C1=CC2C3C2C=CC1C=C3'},
            {'compound_id': 'adamantane', 'label': 'Adamantane', 'smiles': 'C1C2CC3CC1CC(C2)C3'},
        ], str(tmp_path / 'cages'), columns=3)
        final = result['document']['document_id']
        assert result['audit']['status'] == 'checks_passed'
        reports = result['audit']['grid_audit']['verification']['molecule_checks']
        assert all(r['crossing_order_verified'] for r in reports.values())
        assert 'CrossingBonds=' in Path(result['artifacts']['cdxml']).read_text()
        print('CAGE_REVIEW=' + result['review'])
    finally:
        if final is not None:
            bridge.close(final)
    assert bridge.documents() == baseline
