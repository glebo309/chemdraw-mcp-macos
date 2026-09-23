import pytest

from chemdraw_macos import resolver
from test_resolver import record, replies


@pytest.fixture(autouse=True)
def clean_cache():
    resolver.clear_resolution_cache()
    yield
    resolver.clear_resolution_cache()


def test_cache_reuses_validated_result_without_mutable_alias_or_new_retrieval_time(monkeypatch):
    calls = replies(monkeypatch, [1], [record()])
    first = resolver.resolve_identifier('ethanol', allow_network=True, use_cache=True)
    stamp = first['provenance']['retrieved_at']
    first['candidates'][0]['identifiers']['canonical_smiles'] = 'INVALID'
    second = resolver.resolve_identifier('ethanol', allow_network=True, use_cache=True)
    assert len(calls) == 2
    assert second['candidates'][0]['identifiers']['canonical_smiles'] == 'CCO'
    assert second['provenance']['retrieved_at'] == stamp
    assert second['cache']['hit'] is True and second['cache']['age_seconds'] >= 0
    with pytest.raises(ValueError, match='allow_network'):
        resolver.resolve_identifier('ethanol', use_cache=True)


def test_ambiguous_candidates_remain_ambiguous_when_cached(monkeypatch):
    calls = replies(monkeypatch, [1, 2], [record(), record(2, 'CC=O')])
    for _ in range(2):
        result = resolver.resolve_identifier('ambiguous', allow_network=True, use_cache=True)
        assert result['ambiguous'] and result['selection_required']
        assert result['selected_candidate'] is None and len(result['candidates']) == 2
    assert len(calls) == 2


def test_cache_expiry_and_explicit_fresh_lookup(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(resolver.time, 'monotonic', lambda: clock[0])
    replies(monkeypatch, [1], [record()])
    resolver.resolve_identifier('ethanol', allow_network=True, use_cache=True)
    clock[0] += resolver.CACHE_TTL_SECONDS + 1
    calls = replies(monkeypatch, [2], [record(2)])
    assert resolver.resolve_identifier('ethanol', allow_network=True, use_cache=True)['candidates'][0]['cid'] == 2
    assert len(calls) == 2
    calls = replies(monkeypatch, [3], [record(3)])
    assert resolver.resolve_identifier('ethanol', allow_network=True, use_cache=False)['candidates'][0]['cid'] == 3
    assert len(calls) == 2


def test_rejected_results_are_not_cached(monkeypatch):
    replies(monkeypatch, [1], [record(smiles='bad')])
    resolver.resolve_identifier('fixture', allow_network=True, use_cache=True)
    calls = replies(monkeypatch, [1], [record()])
    assert resolver.resolve_identifier('fixture', allow_network=True, use_cache=True)['candidates'][0]['validation']['status'] == 'valid'
    assert len(calls) == 2


def test_bounded_cache_and_query_kind_separation(monkeypatch):
    monkeypatch.setattr(resolver, 'CACHE_MAX_ENTRIES', 2)
    for query in ('64-17-5', 'ethanol', 'alcohol'):
        replies(monkeypatch, [1], [record()])
        resolver.resolve_identifier(query, allow_network=True, use_cache=True)
    calls = replies(monkeypatch, [2], [record(2)])
    resolver.resolve_identifier('64-17-5', allow_network=True, use_cache=True)
    assert len(calls) == 2
    calls = replies(monkeypatch, [3], [record(3)])
    result = resolver.resolve_identifier('64-17-5', input_kind='cas', allow_network=True, use_cache=True)
    assert len(calls) == 2 and result['candidates'][0]['cid'] == 3
