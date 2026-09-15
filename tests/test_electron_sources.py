"""Electron donation must identify displayed electrons, not an atom label."""
from pathlib import Path

import pytest

from chemdraw_macos.annotations import plan_annotations
from chemdraw_macos.route_suggestions import suggest_routes


SOURCE = (Path(__file__).parents[1] / 'examples/sn2-annotation-input.cdxml').read_text()


@pytest.mark.parametrize('electrons', [1, 2])
def test_explicit_arrows_reject_atom_label_sources(electrons):
    arrow = dict(key='invalid-donor', electrons=electrons,
                 source=dict(kind='atom', id='1100', offset=[-2, -9]),
                 target=dict(kind='atom', id='2103', offset=[0, -14]),
                 controls=[[0, -33], [0, -28]])
    with pytest.raises(ValueError, match='displayed.*donating bond'):
        plan_annotations(SOURCE, [arrow])


@pytest.mark.parametrize('electrons', [1, 2])
def test_route_search_rejects_atom_sources_instead_of_silent_no_route(electrons):
    with pytest.raises(ValueError, match='displayed.*donating bond'):
        suggest_routes(SOURCE, dict(kind='atom', id='1100'),
                       dict(kind='atom', id='2103'), electrons=electrons)
