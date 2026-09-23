import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires licensed running ChemDraw')


def test_native_nitro_charges_keep_size_and_owners(tmp_path):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.draw import draw_structures
    bridge = Bridge()
    baseline = bridge.documents()
    final = None
    try:
        result = draw_structures(bridge, [
            {'compound_id': 'nitro', 'label': 'Nitrobenzene', 'smiles': 'O=[N+]([O-])c1ccccc1'},
        ], str(tmp_path / 'nitro'), charge_style='circled', presentation='background')
        final = None if result.get('document_closed') else result['document']['document_id']
        assert result['audit']['status'] == 'checks_passed'
        root = ET.parse(result['artifacts']['cdxml']).getroot()
        graphics = root.findall('page/fragment/graphic')
        assert len(graphics) == 2
        # Native CDXML rounds widths to hundredths; preserve calibrated tolerance.
        assert len({g.get('LineWidth') for g in graphics}) == 1
        assert all(float(g.get('LineWidth')) == pytest.approx(1.975, abs=.01) for g in graphics)
        for g in graphics:
            atom = root.find(f'.//n[@id="{g[0].get("object")}"]')
            assert atom.get('Charge') == ('1' if g.get('SymbolType') == 'CirclePlus' else '-1')
            assert atom.get('Element') == ('7' if g.get('SymbolType') == 'CirclePlus' else '8')
        print('NITRO_REVIEW=' + result['review'])
    finally:
        if final is not None:
            bridge.close(final)
    assert bridge.documents() == baseline
