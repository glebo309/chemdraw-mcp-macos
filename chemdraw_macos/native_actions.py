"""Names for existing native commands, not reimplementations of their algorithms."""
from typing import Literal

NativeAction = Literal[
    'clean_structure', 'clean_reaction', 'align_left', 'align_right',
    'align_top', 'align_bottom', 'align_horizontal_centers',
    'align_vertical_centers', 'distribute_horizontal', 'distribute_vertical',
    'expand_labels', 'contract_labels',
]

ACTIONS = {
    'clean_structure': 'cleanStructure', 'clean_reaction': 'cleanReaction',
    'align_left': 'alignLeftEdges', 'align_right': 'alignRightEdges',
    'align_top': 'alignTopEdges', 'align_bottom': 'alignBottomEdges',
    'align_horizontal_centers': 'alignLeftRightCenters',
    'align_vertical_centers': 'alignTopBottomCenters',
    'distribute_horizontal': 'distributeObjectsHorizontally',
    'distribute_vertical': 'distributeObjectsVertically',
    'expand_labels': 'expandLabel', 'contract_labels': 'contractLabel',
}
