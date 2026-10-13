"""Offline ink boxes for ChemDraw fragments, so layout needs no native measuring copy.

ChemDraw places an atom label deterministically: with `Left` alignment the first
character of the element symbol is centred on the atom and the label runs right;
with `Right` the last character of the symbol is centred and the label runs left.
Calibrated on thousands of native 14 pt snapshots (see tests/test_ink.py): residuals
of well under 1 pt in x. Anything outside the model (stacked Above/Below labels,
four-plus neighbours, unknown glyphs) falls back to a conservative envelope instead
of guessing.
"""
import math
import re

# Arial advance widths in em.
ADVANCE = {**{c: .556 for c in '0123456789abdeghnopqu'}, **{c: .5 for c in 'ckvxyzs'},
           **{c: .222 for c in 'ijl'}, **{c: .278 for c in 'ft I,.:;/'}, 'm': .833, 'r': .333, 'w': .722,
           'A': .667, 'B': .667, 'C': .722, 'D': .722, 'E': .667, 'F': .611, 'G': .778, 'H': .722,
           'J': .5, 'K': .667, 'L': .556, 'M': .833, 'N': .722, 'O': .778, 'P': .667, 'Q': .778,
           'R': .722, 'S': .667, 'T': .611, 'U': .722, 'V': .667, 'W': .944, 'X': .667, 'Y': .667,
           'Z': .611, '-': .333, '(': .333, ')': .333, '+': .584, '=': .584}
BEARING = .75            # mean side bearing of the anchored glyph, points at 14 pt (fit: .27-1.07)
SUBSCRIPT = .75          # ChemDraw script scale for digits and charges
BASELINE = .357          # label baseline below the atom, in em
TOP, BOTTOM, SUB_BOTTOM, SUP_TOP = .366, .379, .57, .72   # vertical ink extents in em


def _split(text):
    """element symbol, remainder (hydrogens, digits, charges)."""
    m = re.fullmatch(r'(\d*)([A-Z][a-z]?)(.*)', text)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def _advance(char, size, script=False):
    return ADVANCE.get(char, .62) * size * (SUBSCRIPT if script else 1.)


def label_box(text, size, alignment, ax, ay):
    """(left, top, right, bottom) of one atom label's ink, or None outside the model."""
    parts = _split(text)
    if parts is None or alignment not in ('Left', 'Right', 'Above', 'Below'):
        return None
    isotope, symbol, rest = parts
    sym_adv = [_advance(c, size) for c in symbol]
    rest_adv = [_advance(c, size, script=c.isdigit() or c in '+-') for c in rest]
    iso_adv = [_advance(c, size, script=True) for c in isotope]
    total = sum(sym_adv) + sum(rest_adv) + sum(iso_adv)
    ink = total - 2 * BEARING * size / 14
    b = BEARING * size / 14
    if not rest and not isotope and len(symbol) == 1:
        # A lone glyph is centred on the atom whatever the alignment.
        half = sym_adv[0] / 2 - b
        return ax - half, ay - TOP * size, ax + half, ay + BOTTOM * size
    if alignment in ('Above', 'Below'):
        # Stacked label: symbol line centred on the atom, remainder on a second line.
        half = max(sum(sym_adv), sum(rest_adv)) / 2 - b
        top, bottom = ay - TOP * size, ay + BOTTOM * size
        if alignment == 'Above':
            top -= size
        else:
            bottom += size
        return ax - half, top, ax + half, bottom
    if alignment == 'Left':
        left = ax - sym_adv[0] / 2 - sum(iso_adv) + b
        right = left + ink
    else:
        right = ax + sym_adv[-1] / 2 - b
        left = right - ink
    top = ay - TOP * size
    bottom = ay + BOTTOM * size
    if any(c.isdigit() for c in rest):
        bottom = ay + SUB_BOTTOM * size
    if '+' in rest or '-' in rest:
        top = ay - SUP_TOP * size
    return left, top, right, bottom


def alignment_for(neighbours, ax, ay):
    """ChemDraw's Auto choice (Left/Right, or stacked Above/Below); None outside the model."""
    if not neighbours:
        return 'Left'
    if len(neighbours) == 1:
        return 'Right' if neighbours[0][0] > ax else 'Left'
    if len(neighbours) >= 4:
        return None
    ups = sum(1 for _, y in neighbours if y < ay - 1e-6)
    downs = sum(1 for _, y in neighbours if y > ay + 1e-6)
    if len(neighbours) == 2 and ups == 2:
        return 'Below'         # observed: both bonds up, ChemDraw hangs the label below
    if len(neighbours) == 2 and downs == 2:
        return 'Above'         # both bonds down, label stands above
    right = sum(1 for x, _ in neighbours if x > ax + 1e-6)
    left = sum(1 for x, _ in neighbours if x < ax - 1e-6)
    if len(neighbours) == 3:
        return 'Left'          # observed for N+/N with three bonds
    return 'Right' if right > left else 'Left'


def fragment_ink(fragment, line_width, label_size, envelope=None):
    """(left, top, right, bottom) of a fragment's ink using the label model.

    `envelope` is the caller's conservative per-atom box (used when a label is
    outside the model). Returns also the explicit alignments to write.
    """
    nodes = {n.get('id'): n for n in fragment.findall('n')}
    adj = {i: [] for i in nodes}
    for b in fragment.findall('b'):
        adj[b.get('B')].append(b.get('E'))
        adj[b.get('E')].append(b.get('B'))
    pad = line_width / 2 + .12
    xs, ys, boxes, alignments = [], [], [], {}
    for i, n in nodes.items():
        ax, ay = map(float, n.get('p').split())
        xs.append(ax)
        ys.append(ay)
        t = n.find('t')
        if t is None:
            boxes.append((ax - pad, ay - pad, ax + pad, ay + pad))
            continue
        text = ''.join(t.itertext())
        neigh = [tuple(map(float, nodes[j].get('p').split())) for j in adj[i] if j in nodes]
        alignment = alignment_for(neigh, ax, ay)
        box = label_box(text, label_size, alignment, ax, ay) if alignment else None
        if box is None:
            if envelope is None:
                raise ValueError(f'Label {text!r} is outside the ink model')
            boxes.append(envelope[i])
        else:
            boxes.append(box)
            alignments[i] = alignment
    # bond ink spans between atom coordinates
    left = min([b[0] for b in boxes] + [x - pad for x in xs])
    right = max([b[2] for b in boxes] + [x + pad for x in xs])
    top = min([b[1] for b in boxes] + [y - pad for y in ys])
    bottom = max([b[3] for b in boxes] + [y + pad for y in ys])
    return (left, top, right, bottom), alignments


def label_position(text, size, alignment, ax, ay):
    """Native `p` for an explicitly aligned label (baseline anchor)."""
    isotope, symbol, _ = _split(text)
    first = _advance(symbol[0], size)
    last = _advance(symbol[-1], size)
    iso = sum(_advance(c, size, script=True) for c in isotope)
    x = ax - first / 2 - iso if alignment == 'Left' else ax + last / 2
    return x, ay + BASELINE * size
