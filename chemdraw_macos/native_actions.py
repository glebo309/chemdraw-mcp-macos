"""Names for existing native commands, not reimplementations of their algorithms."""
import sys
from typing import Literal

WINDOWS = sys.platform == 'win32'
ALL_ACTIONS = (
    'clean_structure', 'clean_reaction', 'align_left', 'align_right',
    'align_top', 'align_bottom', 'align_horizontal_centers',
    'align_vertical_centers', 'distribute_horizontal', 'distribute_vertical',
    'expand_labels', 'contract_labels', 'undo', 'redo',
)
# Alignment/distribution are submenu commands; Windows COM exposes no submenu items
# (observed on ChemDraw 26.1). They are not offered there and never dispatched.
WINDOWS_UNAVAILABLE = frozenset(a for a in ALL_ACTIONS if a.startswith(('align_', 'distribute_')))


def available_actions(windows=WINDOWS):
    return tuple(a for a in ALL_ACTIONS if not (windows and a in WINDOWS_UNAVAILABLE))


def require_available(action):
    if WINDOWS and action in WINDOWS_UNAVAILABLE:
        raise ValueError('ChemDraw alignment and distribution are submenu commands that Windows COM '
                         'automation does not expose; no command was dispatched')


NativeAction = Literal[available_actions()]

ACTIONS = {
    'clean_structure': 'cleanStructure', 'clean_reaction': 'cleanReaction',
    'align_left': 'alignLeftEdges', 'align_right': 'alignRightEdges',
    'align_top': 'alignTopEdges', 'align_bottom': 'alignBottomEdges',
    'align_horizontal_centers': 'alignLeftRightCenters',
    'align_vertical_centers': 'alignTopBottomCenters',
    'distribute_horizontal': 'distributeObjectsHorizontally',
    'distribute_vertical': 'distributeObjectsVertically',
    'expand_labels': 'expandLabel', 'contract_labels': 'contractLabel',
    'undo': 'undo', 'redo': 'redo',
}
