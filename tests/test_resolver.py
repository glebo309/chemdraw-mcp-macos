import io
import json
from urllib.error import HTTPError, URLError

import pytest

from chemdraw_macos import resolver


def record(cid=1, smiles='CCO', **extra):
    return {'CID': cid, 'SMILES': smiles, 'Title': 'fixture', **extra}


def replies(monkeypatch, cids, records):
    calls = []
    values = iter([{'IdentifierList': {'CID': cids}},
                   {'PropertyTable': {'Properties': records}}])
    def get(url):
        calls.append(url)
        return next(values)
    monkeypatch.setattr(resolver, '_request_json', get)
    return calls


def test_network_requires_literal_opt_in(monkeypatch):
    monkeypatch.setattr(resolver, '_request_json', lambda url: pytest.fail('network called'))
    for allow in (False, None, 1, 'true'):
        with pytest.raises(ValueError, match='allow_network=True'):
            resolver.resolve_identifier('caffeine', allow_network=allow)


@pytest.mark.parametrize('query,kind', [('', 'name'), (' x', 'name'), ('x\n', 'name'),
    ('a' * 201, 'name'), ('58-08-3', 'cas'), ('058-08-2', 'cas'), ('58–08–2', 'cas'),
    ('caffeine', 'cas'), ('CCO', 'smiles')])
def test_input_rejected_before_network(monkeypatch, query, kind):
    monkeypatch.setattr(resolver, '_request_json', lambda url: pytest.fail('network called'))
    with pytest.raises(ValueError):
        resolver.resolve_identifier(query, input_kind=kind, allow_network=True)


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(resolver, '_request_json', lambda url: pytest.fail('network called'))
    with pytest.raises(ValueError, match='provider'):
        resolver.resolve_identifier('caffeine', allow_network=True, provider='other')


def test_name_returns_all_candidates_and_provenance(monkeypatch):
    calls = replies(monkeypatch, [2, 1], [record(1), record(2, 'CC=O')])
    result = resolver.resolve_identifier('a/b & c', allow_network=True)
    assert result['status'] == 'candidates'
    assert result['ambiguous'] is True
    assert result['truncated'] is False
    assert result['total_candidates'] == 2
    assert result['selected_candidate'] is None
    assert [r['cid'] for r in result['candidates']] == [2, 1]
    assert result['candidates'][0]['validation']['status'] == 'valid'
    assert result['candidates'][0]['identifiers']['canonical_smiles'] == 'CC=O'
    assert '/name/a%2Fb%20%26%20c/cids/JSON?name_type=complete' in calls[0]
    assert '/property/SMILES,InChI,InChIKey,IUPACName,Title/JSON' in calls[1]
    assert result['provenance']['request_urls'] == calls
    assert result['provenance']['query'] == 'a/b & c'
    assert result['provenance']['input_kind'] == 'name'
    assert result['provenance']['provider'] == 'pubchem'
    assert result['provenance']['retrieved_at'].endswith('+00:00')


def test_cas_uses_typed_identifier_lookup(monkeypatch):
    calls = replies(monkeypatch, [2519], [record(2519)])
    result = resolver.resolve_identifier('58-08-2', input_kind='cas', allow_network=True)
    assert '/identifier/58-08-2/cids/JSON?identifier_type=CAS' in calls[0]
    assert result['ambiguous'] is False
    assert result['selection_required'] is True


def test_bound_is_explicit_and_no_candidates_autoselected(monkeypatch):
    cids = list(range(1, 24))
    calls = replies(monkeypatch, cids, [record(i) for i in cids[:20]])
    result = resolver.resolve_identifier('fixture', allow_network=True)
    assert len(result['candidates']) == 20
    assert result['total_candidates'] == 23
    assert result['truncated'] is True
    assert result['omitted_candidates'] == 3
    assert '/cid/' + ','.join(map(str, cids[:20])) + '/' in calls[1]


def test_rejected_smiles_candidate_is_retained(monkeypatch):
    replies(monkeypatch, [1, 2], [record(1, 'C |bad|'), record(2)])
    result = resolver.resolve_identifier('fixture', allow_network=True)
    assert len(result['candidates']) == 2
    assert result['candidates'][0]['validation']['status'] == 'rejected'
    assert result['candidates'][0]['identifiers'] is None
    assert result['ambiguous'] is True


def test_matching_inchi_is_not_claimed_exact_graph_equivalence(monkeypatch):
    # Standard InChI normalizes this keto/enol tautomer representation.
    from chemdraw_macos.identifiers import inspect_identifier
    data = inspect_identifier('O=C1CCCCN1')
    assert data['inchi']['graph_roundtrip_equivalent'] is False
    replies(monkeypatch, [1], [record(1, 'O=C1CCCCN1', InChI=data['inchi']['value'], InChIKey=data['inchi']['key'])])
    item = resolver.resolve_identifier('fixture', allow_network=True)['candidates'][0]
    assert item['validation']['inchi_matches'] is True
    assert item['validation']['inchi_graph_roundtrip_equivalent'] is False
    assert item['validation']['status'] == 'valid'


def test_mismatched_inchi_rejects_candidate(monkeypatch):
    replies(monkeypatch, [1], [record(InChI='InChI=1S/CH4/h1H4')])
    item = resolver.resolve_identifier('fixture', allow_network=True)['candidates'][0]
    assert item['validation']['status'] == 'rejected'
    assert item['validation']['inchi_matches'] is False


@pytest.mark.parametrize('records', [[], [record(2)], [record(), record()], [record(SMILES=None)]])
def test_missing_duplicate_unrequested_or_missing_smiles_records_fail(monkeypatch, records):
    replies(monkeypatch, [1], records)
    with pytest.raises(RuntimeError, match='response'):
        resolver.resolve_identifier('fixture', allow_network=True)


@pytest.mark.parametrize('cids', [[True], [0], ['1'], [1, 1], None])
def test_bad_cid_response_fails(monkeypatch, cids):
    replies(monkeypatch, cids, [])
    with pytest.raises(RuntimeError, match='response'):
        resolver.resolve_identifier('fixture', allow_network=True)


def test_not_found_differs_from_provider_error(monkeypatch):
    monkeypatch.setattr(resolver, '_request_json', lambda url: (_ for _ in ()).throw(resolver._NotFound()))
    result = resolver.resolve_identifier('fixture', allow_network=True)
    assert result['status'] == 'not_found'
    assert result['total_candidates'] == 0
    monkeypatch.setattr(resolver, '_request_json', lambda url: (_ for _ in ()).throw(RuntimeError('503')))
    with pytest.raises(RuntimeError, match='503'):
        resolver.resolve_identifier('fixture', allow_network=True)


class Response(io.BytesIO):
    status = 200


def test_transport_size_timeout_and_no_retry(monkeypatch):
    calls = []
    def open_url(request, timeout):
        calls.append((request, timeout))
        return Response(b' ' * (resolver.MAX_RESPONSE_BYTES + 1))
    monkeypatch.setattr(resolver, '_open_url', open_url)
    monkeypatch.setattr(resolver, '_throttle', lambda: None)
    with pytest.raises(RuntimeError, match='size'):
        resolver._request_json(resolver.API_BASE + '/compound/name/caffeine/cids/JSON')
    assert len(calls) == 1
    assert 0 < calls[0][1] <= 10


@pytest.mark.parametrize('payload', [b'not JSON', b'[]', b'{"Waiting": {}}'])
def test_bad_json_or_async_response_fails(monkeypatch, payload):
    monkeypatch.setattr(resolver, '_open_url', lambda *a, **k: Response(payload))
    monkeypatch.setattr(resolver, '_throttle', lambda: None)
    with pytest.raises(RuntimeError):
        resolver._request_json(resolver.API_BASE + '/compound/name/caffeine/cids/JSON')


@pytest.mark.parametrize('error', [URLError('offline'), TimeoutError('timeout'),
    HTTPError('url', 503, 'busy', {}, None)])
def test_transport_error_fails_without_retry(monkeypatch, error):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise error
    monkeypatch.setattr(resolver, '_open_url', fail)
    monkeypatch.setattr(resolver, '_throttle', lambda: None)
    with pytest.raises(RuntimeError):
        resolver._request_json(resolver.API_BASE + '/compound/name/caffeine/cids/JSON')
    assert len(calls) == 1


def test_throttle_spaces_requests(monkeypatch):
    clock = [10.0]
    sleeps = []
    monkeypatch.setattr(resolver, '_last_request', 10.0)
    monkeypatch.setattr(resolver.time, 'monotonic', lambda: clock[0])
    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay
    monkeypatch.setattr(resolver.time, 'sleep', sleep)
    resolver._throttle()
    resolver._throttle()
    assert sleeps == [0.25, 0.25]


def test_inchi_unavailable_is_explicit(monkeypatch):
    monkeypatch.setattr('chemdraw_macos.identifiers._inchi_backend', lambda: None)
    replies(monkeypatch, [1], [record(InChI='InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3')])
    item = resolver.resolve_identifier('fixture', allow_network=True)['candidates'][0]
    assert item['validation']['status'] == 'valid'
    assert item['validation']['inchi_matches'] is None
    assert item['validation']['inchi_graph_roundtrip_equivalent'] is None
    assert 'unavailable' in item['validation']['reason']


def test_missing_chemistry_stops_before_disclosure(monkeypatch):
    def fail():
        raise RuntimeError('chemistry missing')
    monkeypatch.setattr('chemdraw_macos.identifiers._chemistry', fail)
    monkeypatch.setattr(resolver, '_request_json', lambda url: pytest.fail('network called'))
    with pytest.raises(RuntimeError, match='chemistry missing'):
        resolver.resolve_identifier('fixture', allow_network=True)


def test_redirect_denied():
    with pytest.raises(RuntimeError, match='redirect'):
        resolver._RejectRedirects().redirect_request(None, None, 302, '', {}, 'https://other.example')


def test_transport_not_found_has_distinct_exception(monkeypatch):
    def fail(*a, **kw):
        raise HTTPError('url', 404, 'not found', {}, None)
    monkeypatch.setattr(resolver, '_open_url', fail)
    monkeypatch.setattr(resolver, '_throttle', lambda: None)
    with pytest.raises(resolver._NotFound):
        resolver._request_json(resolver.API_BASE + '/compound/name/caffeine/cids/JSON')


def test_property_not_found_does_not_erase_known_matches(monkeypatch):
    values = iter([{'IdentifierList': {'CID': [1]}}, None])
    def get(url):
        value = next(values)
        if value is None:
            raise resolver._NotFound()
        return value
    monkeypatch.setattr(resolver, '_request_json', get)
    with pytest.raises(RuntimeError, match='property response missing'):
        resolver.resolve_identifier('fixture', allow_network=True)
