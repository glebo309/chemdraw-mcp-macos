"""Offline rasterization of a bounded native SVG subset, not chemical drawing."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
import re
import struct
import sys

from defusedxml import ElementTree as SafeET

MAX_SVG_BYTES = 10_000_000
_NS = 'http://www.w3.org/2000/svg'
_TAGS = {'svg', 'g', 'defs', 'clipPath', 'path', 'text', 'tspan', 'rect',
         'circle', 'ellipse', 'line', 'polyline', 'polygon'}
_ATTRS = {'id', 'version', 'width', 'height', 'viewBox', 'preserveAspectRatio',
          'x', 'y', 'dx', 'dy', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry',
          'd', 'points', 'transform', 'fill', 'fill-opacity', 'fill-rule',
          'stroke', 'stroke-width', 'stroke-opacity', 'stroke-linecap',
          'stroke-linejoin', 'stroke-miterlimit', 'stroke-dasharray',
          'stroke-dashoffset', 'opacity', 'clip-path', 'clip-rule', 'clipPathUnits',
          'font-family', 'font-size', 'font-style', 'font-weight', 'text-anchor',
          'text-decoration', 'style'}
_LOCAL_URL = re.compile(r'url\(#([A-Za-z0-9_][A-Za-z0-9_.:-]*)\)\Z')


def _dimension(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:px)?', value):
        raise ValueError('Native SVG dimensions require finite positive pixel values')
    number = float(value.removesuffix('px'))
    if not math.isfinite(number) or not 0 < number <= 1_000_000:
        raise ValueError('Native SVG dimensions are outside the supported bounds')
    return max(1, math.floor(number + .5))


def _validate(svg_text, pixels):
    if type(pixels) is not int or not 256 <= pixels <= 8192:
        raise ValueError('PNG longest side must be 256 through 8192 pixels')
    if not isinstance(svg_text, str) or len(svg_text.encode('utf-8')) > MAX_SVG_BYTES:
        raise ValueError('Native SVG must be UTF-8 text of at most 10 MB')
    if re.search(r'<\?(?!xml(?:\s|\?>))', svg_text, re.IGNORECASE):
        raise ValueError('SVG processing instructions are unsupported')
    try:
        root = SafeET.fromstring(svg_text, forbid_entities=True, forbid_external=True)
    except Exception as exc:
        raise ValueError(f'Invalid or unsafe native SVG: {exc}') from exc
    if root.tag != f'{{{_NS}}}svg':
        raise ValueError('Expected a namespaced native SVG document')
    width, height = _dimension(root.get('width')), _dimension(root.get('height'))
    if root.get('viewBox') is not None:
        try:
            view = [float(v) for v in root.get('viewBox').replace(',', ' ').split()]
        except ValueError as exc:
            raise ValueError('Invalid SVG viewBox') from exc
        if len(view) != 4 or not all(math.isfinite(v) for v in view) or min(view[2:]) <= 0:
            raise ValueError('Invalid SVG viewBox')
    identifiers = Counter(element.get('id') for element in root.iter() if element.get('id'))
    references = []
    for count, element in enumerate(root.iter(), 1):
        if count > 100_000:
            raise ValueError('Native SVG exceeds the supported object limit')
        if element.tag not in {f'{{{_NS}}}{tag}' for tag in _TAGS}:
            raise ValueError('Unsupported SVG element; images, scripts and external resources are not allowed')
        for name, value in element.attrib.items():
            if name not in _ATTRS:
                raise ValueError(f'Unsupported SVG attribute: {name}')
            if name == 'style':
                # ChemDraw emits this transparent canvas declaration. General
                # CSS, including imports, escapes and font-face URLs, is not accepted.
                if not re.fullmatch(r'\s*background-color\s*:\s*#[0-9a-fA-F]{6}00\s*;?\s*', value):
                    raise ValueError('Unsupported SVG style; only a transparent native canvas is allowed')
            if 'url' in value.lower():
                reference = _LOCAL_URL.fullmatch(value)
                if name not in ('fill', 'stroke', 'clip-path') or reference is None:
                    raise ValueError('SVG resource references must be local fragment URLs')
                references.append(reference[1])
            if '\\' in value or '@' in value:
                raise ValueError('Escaped CSS and external resource syntax are unsupported')
    if any(identifiers[reference] != 1 for reference in references):
        raise ValueError('SVG local resource reference must identify exactly one existing object')
    if width >= height:
        return pixels, math.ceil(pixels * height / width)
    return math.ceil(pixels * width / height), pixels


def rasterize_svg(svg_text: str, pixels: int = 3200) -> bytes:
    """Return transparent PNG bytes; preserve source SVG and use local system fonts.

    Call the module worker in a timed subprocess when an execution deadline is
    required. Font substitution and chemical correctness are not certified here.
    """
    expected_size = _validate(svg_text, pixels)
    try:
        import resvg_py
    except ImportError as exc:
        raise RuntimeError('PNG rasterization requires resvg-py; no renderer fallback is used') from exc
    png = resvg_py.svg_to_bytes(svg_string=svg_text, width=pixels, height=pixels,
                                background=None, dpi=96.0, skip_system_fonts=False,
                                log_information=False)
    # resvg fits proportionally inside the requested square. Check the actual
    # encoded dimensions and alpha format, rather than asserting the request won.
    if (not isinstance(png, bytes) or len(png) < 29 or png[:8] != b'\x89PNG\r\n\x1a\n'
            or png[12:16] != b'IHDR' or struct.unpack('>II', png[16:24]) != expected_size
            or png[24:26] != b'\x08\x06'):
        raise RuntimeError('Rasterizer did not produce the required RGBA PNG dimensions')
    return png


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Rasterize an existing native SVG offline')
    parser.add_argument('svg_path', type=Path)
    parser.add_argument('output_path', type=Path)
    parser.add_argument('pixels', type=int)
    args = parser.parse_args(argv)
    if args.output_path.exists() or args.output_path.is_symlink():
        raise FileExistsError(f'Will not overwrite {args.output_path}')
    with args.svg_path.open('rb') as handle:
        source = handle.read(MAX_SVG_BYTES + 1)
    if len(source) > MAX_SVG_BYTES:
        raise ValueError('Native SVG exceeds 10 MB limit')
    png = rasterize_svg(source.decode('utf-8'), args.pixels)
    with args.output_path.open('xb') as handle:
        handle.write(png)
    return 0


if __name__ == '__main__':
    sys.exit(main())
