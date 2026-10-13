"""Pinned names bypass provider outages without broad or fuzzy substitution."""
import pytest

from chemdraw_macos import harness


@pytest.mark.parametrize('name', ['caffeine', 'Caffeine', 'CAFFEINE', 'caffein'])
@pytest.mark.parametrize('network', [True, False])
def test_caffeine_drawing_is_provider_independent(monkeypatch, name, network):
    monkeypatch.setattr(harness, 'resolve_identifier',
                        lambda *a, **kw: pytest.fail('Caffeine must not contact PubChem'))
    plan = harness.plan_request({'molecules': [{'format': 'name', 'value': name}]},
                                allow_network=network, shared=True)
    from chemdraw_macos.first_run import DEMO_STRUCTURES
    from chemdraw_macos.identifiers import inspect_identifier
    assert plan['structures'][0]['smiles'] == inspect_identifier(DEMO_STRUCTURES[0]['smiles'])['canonical_smiles']
    assert plan['structures'][0]['label'] == name
    source = plan['provenance'][0]
    assert source['provider'] == 'bundled_reference'
    assert source['reference_url'] == 'https://pubchem.ncbi.nlm.nih.gov/compound/2519'
    assert source['network_used'] is False
    assert source['identity']['inchi']['key'] == 'RYYVLZVUVIJVGH-UHFFFAOYSA-N'


@pytest.mark.parametrize('name', ['caffeine citrate', 'caffeine hydrochloride', 'decaffeinated', 'caffei'])
def test_only_exact_reviewed_aliases_are_offline(monkeypatch, name):
    monkeypatch.setattr(harness, 'resolve_identifier', lambda *a, **kw: pytest.fail('Offline'))
    with pytest.raises(harness.NeedsInput) as error:
        harness.plan_request({'molecules': [{'format': 'name', 'value': name}]}, allow_network=False)
    assert error.value.code == 'network_permission_required'


@pytest.mark.parametrize('extra,request_extra', [
    ({}, {'refresh_identifiers': True}),
    ({'selected_cid': 57362268}, {}),
])
def test_refresh_or_different_selected_record_is_not_overridden(monkeypatch, extra, request_extra):
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(args)
        raise RuntimeError('PubChem HTTP 503')
    monkeypatch.setattr(harness, 'resolve_identifier', unavailable)
    with pytest.raises(RuntimeError, match='503'):
        harness.plan_request({'molecules': [{'format': 'name', 'value': 'caffeine', **extra}],
                              **request_extra}, allow_network=True)
    assert len(calls) == 1


def test_bundled_caffeine_enters_regular_validated_drawing_planner(monkeypatch):
    from chemdraw_macos.api_drawing import plan_addition
    from test_api_drawing import EMPTY
    from rdkit import Chem
    monkeypatch.setattr(harness, 'resolve_identifier', lambda *a, **kw: pytest.fail('Offline'))
    plan = harness.plan_request({'molecules': [{'format': 'name', 'value': 'caffeine'}]}, shared=True)
    cdxml, report = plan_addition(EMPTY, plan['structures'])
    molecules = Chem.MolsFromCDXML(cdxml)
    assert len(molecules) == 1
    assert Chem.MolToSmiles(molecules[0]) == plan['structures'][0]['smiles']
    assert report['orientations'][0]['policy'] == 'axis_aligned_six_ring'
