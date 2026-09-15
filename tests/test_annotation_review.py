"""Independent fail-closed regressions for native electron annotations."""
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.annotations import annotation_inventory, plan_annotations, verify_annotations
from test_annotations import SOURCE, ARROWS


def text(root):
    return ET.tostring(root, encoding='unicode')


def test_unknown_charge_graphic_style_rejected_before_planning():
    root = ET.fromstring(SOURCE)
    root.find('.//graphic[@SymbolType="CircleMinus"]').set('LineType', 'Dashed')
    with pytest.raises(ValueError):
        plan_annotations(text(root), ARROWS)


def test_native_charge_style_outside_supported_subset_rejected():
    planned, _ = plan_annotations(SOURCE, ARROWS)
    native = ET.fromstring(planned)
    native.find('.//graphic[@SymbolType="CircleMinus"]').set('LineType', 'Dashed')
    with pytest.raises(ValueError):
        verify_annotations(planned, text(native))


@pytest.mark.parametrize('width', ['nan', 'inf', '-1', '0'])
def test_malformed_existing_curve_width_rejected_during_inventory(width):
    planned, _ = plan_annotations(SOURCE, ARROWS)
    root = ET.fromstring(planned)
    root.find('page/curve').set('LineWidth', width)
    with pytest.raises(ValueError):
        annotation_inventory(text(root))


def test_malformed_existing_charge_width_rejected_during_inventory():
    root = ET.fromstring(SOURCE)
    root.find('.//graphic[@SymbolType="CircleMinus"]').set('LineWidth', '-1')
    with pytest.raises(ValueError):
        annotation_inventory(text(root))
