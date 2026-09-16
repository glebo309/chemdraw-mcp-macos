"""Preserve bond crossing references and relative foreground order."""
import itertools


def validate_crossings(fragment):
    bonds = {b.get('id'): b for b in fragment.findall('b')}
    for bond in bonds.values():
        refs = bond.get('CrossingBonds', '').split()
        if (len(refs) != len(set(refs)) or bond.get('id') in refs
                or any(ref not in bonds for ref in refs)):
            raise ValueError('Invalid crossing bond references within fragment')


def remap_crossings(element, mapping):
    if element.get('CrossingBonds'):
        element.set('CrossingBonds', ' '.join(mapping[v] for v in element.get('CrossingBonds').split()))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def crossing_order(fragment, atom_map=None, required=()):
    validate_crossings(fragment)
    atoms = {n.get('id'): tuple(map(float, n.get('p').split())) for n in fragment.findall('n')}
    atom_map = atom_map or {aid: aid for aid in atoms}
    result = {}
    for a, b in itertools.combinations(fragment.findall('b'), 2):
        ae, be = (a.get('B'), a.get('E')), (b.get('B'), b.get('E'))
        if set(ae) & set(be):
            continue
        p, q = (atoms[v] for v in ae)
        r, s = (atoms[v] for v in be)
        geometric = (_cross(p, q, r) * _cross(p, q, s) < -1e-5
                     and _cross(r, s, p) * _cross(r, s, q) < -1e-5)
        declared = b.get('id') in a.get('CrossingBonds', '').split() or a.get('id') in b.get('CrossingBonds', '').split()
        keys = [tuple(sorted(atom_map[v] for v in ends)) for ends in (ae, be)]
        pair = tuple(sorted(keys))
        if not geometric and not declared and pair not in required:
            continue
        try:
            delta = int(a.get('Z', '0')) - int(b.get('Z', '0'))
        except ValueError as exc:
            raise ValueError('Invalid crossing bond Z order') from exc
        if not delta:
            raise ValueError('Ambiguous crossing bond foreground order')
        result[pair] = (1 if delta > 0 else -1) * (1 if keys[0] < keys[1] else -1)
    return result


def verify_crossings(old, new, atom_map):
    # Native saving recomputes this cache, including near-touching thick ink.
    # Compare foreground order for the union, not equality of cached ID arrays.
    pairs = set(crossing_order(old, atom_map)) | set(crossing_order(new))
    if crossing_order(old, atom_map, pairs) != crossing_order(new, required=pairs):
        raise ValueError('Native crossing bond foreground order changed')
