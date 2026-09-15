"""Explicit, bounded PubChem name/CAS candidates; never choose or draw one."""
from datetime import datetime, timezone
import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .identifiers import inspect_identifier

API_BASE = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug'
MAX_CANDIDATES = 20
MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT = 10
RESPONSE_DEADLINE = 15
_request_lock = threading.Lock()
_last_request = float('-inf')


class _NotFound(Exception):
    pass


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('PubChem redirect refused; no alternate endpoint was contacted')


def _open_url(request, timeout):
    # No environment proxy credentials, cookies, authentication or redirects.
    return build_opener(ProxyHandler({}), _RejectRedirects()).open(request, timeout=timeout)


def _throttle():
    global _last_request
    with _request_lock:
        delay = 0.25 - (time.monotonic() - _last_request)
        if delay > 0:
            time.sleep(delay)
        _last_request = time.monotonic()


def _request_json(url):
    _throttle()
    started = time.monotonic()
    request = Request(url, headers={'Accept': 'application/json',
                                   'User-Agent': 'chemdraw-mcp-macos resolver'})
    try:
        with _open_url(request, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                raise RuntimeError(f'Unexpected PubChem HTTP response {response.status}')
            chunks = []
            size = 0
            while True:
                if time.monotonic() - started > RESPONSE_DEADLINE:
                    raise RuntimeError('PubChem response deadline exceeded')
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise RuntimeError('PubChem response size exceeds 1000000 bytes; results unavailable')
            data = json.loads(b''.join(chunks))
    except HTTPError as exc:
        if exc.code == 404:
            raise _NotFound() from exc
        raise RuntimeError(f'PubChem HTTP {exc.code}; no retry or fallback performed') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError('PubChem request failed; no retry or fallback performed: ' + str(exc)) from exc
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError('Invalid PubChem JSON response') from exc
    if not isinstance(data, dict) or 'Fault' in data or 'Waiting' in data:
        raise RuntimeError('Unsupported PubChem response; no polling or fallback performed')
    return data


def _candidate(row, property_url):
    smiles = row['SMILES']
    result = {'cid': row['CID'], 'provider_record_url': f'https://pubchem.ncbi.nlm.nih.gov/compound/{row["CID"]}',
              'property_url': property_url, 'provider_smiles': smiles,
              'provider_inchi': row.get('InChI'), 'provider_inchikey': row.get('InChIKey'),
              'provider_title': row.get('Title'), 'provider_iupac_name': row.get('IUPACName'),
              'identifiers': None,
              'validation': {'status': 'rejected', 'reason': None, 'inchi_matches': None,
                             'inchikey_matches': None, 'inchi_graph_roundtrip_equivalent': None}}
    validation = result['validation']
    try:
        identifiers = inspect_identifier(smiles)
    except (ValueError, RuntimeError) as exc:
        validation['reason'] = str(exc)
        return result
    result['identifiers'] = identifiers
    inchi = identifiers['inchi']
    validation['status'] = 'valid'
    validation['inchi_graph_roundtrip_equivalent'] = inchi['graph_roundtrip_equivalent']
    if inchi['status'] == 'available':
        for field, generated, check in [('InChI', inchi['value'], 'inchi_matches'),
                                        ('InChIKey', inchi['key'], 'inchikey_matches')]:
            if field in row:
                validation[check] = row[field] == generated
                if not validation[check]:
                    validation.update(status='rejected', reason='Provider InChI/InChIKey disagrees with the strict SMILES graph')
    else:
        validation['reason'] = 'SMILES validated; InChI cross-validation unavailable: ' + str(inchi['reason'])
    return result


def resolve_identifier(query: str, input_kind: str = 'name', allow_network: bool = False,
                       provider: str = 'pubchem') -> dict:
    """Return reviewed-input candidates, with mandatory per-call network opt-in.

    PubChem matching is not authoritative CAS Registry validation. Even a single
    result needs caller selection before passing an explicit graph to drawing.
    """
    if allow_network is not True:
        raise ValueError('Resolution sends the query to PubChem; requires allow_network=True')
    if provider != 'pubchem':
        raise ValueError('provider must be pubchem')
    if input_kind not in ('name', 'cas'):
        raise ValueError('input_kind must be name or cas')
    if (not isinstance(query, str) or not 1 <= len(query) <= 200
            or query != query.strip() or any(not c.isprintable() for c in query)):
        raise ValueError('Query must be 1 through 200 printable characters without surrounding whitespace')
    if input_kind == 'cas':
        if not re.fullmatch(r'[1-9][0-9]{1,6}-[0-9]{2}-[0-9]', query):
            raise ValueError('CAS must have standard digits and hyphens without leading zeros')
        digits = query.replace('-', '')
        if sum(i * int(digit) for i, digit in enumerate(reversed(digits[:-1]), 1)) % 10 != int(digits[-1]):
            raise ValueError('CAS checksum is invalid')
    # Verify the optional local dependency before sending any query.
    from .identifiers import _chemistry
    _chemistry()
    escaped = quote(query, safe='')
    suffix = (f'name/{escaped}/cids/JSON?name_type=complete' if input_kind == 'name'
              else f'identifier/{escaped}/cids/JSON?identifier_type=CAS')
    query_url = API_BASE + '/compound/' + suffix
    result = {'status': 'not_found', 'candidates': [], 'total_candidates': 0,
              'ambiguous': False, 'truncated': False, 'omitted_candidates': 0,
              'selected_candidate': None, 'selection_required': True,
              'limits': {'max_candidates': MAX_CANDIDATES, 'max_response_bytes': MAX_RESPONSE_BYTES,
                         'socket_timeout_seconds': REQUEST_TIMEOUT, 'response_deadline_seconds': RESPONSE_DEADLINE,
                         'max_requests_per_second_per_process': 4},
              'provenance': {'provider': provider, 'query': query, 'input_kind': input_kind,
                             'request_urls': [query_url],
                             'retrieved_at': datetime.now(timezone.utc).isoformat()},
              'warnings': ['Provider associations require review; a name or CAS match does not certify the intended structure.',
                           'Standard InChI equality is separate from exact SMILES graph identity.']}
    try:
        data = _request_json(query_url)
    except _NotFound:
        return result
    cids = data.get('IdentifierList', {}).get('CID') if isinstance(data.get('IdentifierList'), dict) else None
    if (not isinstance(cids, list) or any(type(cid) is not int or cid <= 0 for cid in cids)
            or len(set(cids)) != len(cids)):
        raise RuntimeError('Malformed PubChem CID response')
    if not cids:
        return result
    chosen = cids[:MAX_CANDIDATES]
    property_url = (API_BASE + '/compound/cid/' + ','.join(map(str, chosen))
                    + '/property/SMILES,InChI,InChIKey,IUPACName,Title/JSON')
    result['provenance']['request_urls'].append(property_url)
    try:
        data = _request_json(property_url)
    except _NotFound as exc:
        raise RuntimeError('PubChem property response missing for matched CIDs') from exc
    rows = data.get('PropertyTable', {}).get('Properties') if isinstance(data.get('PropertyTable'), dict) else None
    if (not isinstance(rows, list) or len(rows) != len(chosen)
            or any(not isinstance(row, dict) or type(row.get('CID')) is not int
                   or not isinstance(row.get('SMILES'), str) or not row['SMILES']
                   or any(key in row and not isinstance(row[key], str)
                          for key in ('InChI', 'InChIKey', 'Title', 'IUPACName')) for row in rows)
            or set(row['CID'] for row in rows) != set(chosen)):
        raise RuntimeError('Incomplete or malformed PubChem property response')
    by_cid = {row['CID']: row for row in rows}
    result.update(status='candidates', total_candidates=len(cids), ambiguous=len(cids) > 1,
                  truncated=len(cids) > MAX_CANDIDATES, omitted_candidates=max(0, len(cids) - MAX_CANDIDATES),
                  candidates=[_candidate(by_cid[cid], property_url) for cid in chosen])
    if result['truncated']:
        result['warnings'].append('Candidate limit reached; omitted matches were not fetched or validated. Narrow the query.')
    result['provenance']['retrieved_at'] = datetime.now(timezone.utc).isoformat()
    return result
