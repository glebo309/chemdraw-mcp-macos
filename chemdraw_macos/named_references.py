"""Small reviewed name/graph references, not a fuzzy naming service.

These public reference structures ship with the package. User queries are never
persisted here. Unlisted names, salts and derivatives still need normal resolution.
"""
from .identifiers import inspect_identifier


_REFERENCES = (
    {
        'aliases': ('caffeine', 'caffein'),
        # Same graph as the existing first-run native caffeine fixture.
        'smiles': 'Cn1c(=O)c2c(ncn2C)n(C)c1=O',
        'cid': 2519,
        'inchikey': 'RYYVLZVUVIJVGH-UHFFFAOYSA-N',
        'reference_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/2519',
        'reviewed_on': '2026-09-27',
    },
)


def resolve_bundled_name(query, selected_cid=None):
    for reference in _REFERENCES:
        if query.casefold() not in reference['aliases']:
            continue
        if selected_cid is not None and selected_cid != reference['cid']:
            return None
        identity = inspect_identifier(reference['smiles'])
        if identity['inchi']['key'] != reference['inchikey']:
            raise ValueError('Bundled name reference failed identity verification')
        return identity, {
            'kind': 'name', 'value': query, 'provider': 'bundled_reference',
            'selected_cid': reference['cid'], 'reference_url': reference['reference_url'],
            'reviewed_on': reference['reviewed_on'], 'network_used': False,
            'identity': identity,
        }
    return None
