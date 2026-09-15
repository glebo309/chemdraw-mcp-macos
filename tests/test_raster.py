import importlib.util
import io
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

from chemdraw_macos.raster import rasterize_svg


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="50px" viewBox="0 0 100 50" style="background-color: #ffffff00">
<defs><clipPath id="shadow"><path clip-rule="evenodd" d="M0 0H100V50H0Z M20 10H80V40H20Z"/></clipPath></defs>
<path fill="#808080" fill-opacity="0.5" clip-path="url(#shadow)" d="M0 0H100V50H0Z"/>
</svg>'''


def fake_png(width=512, height=256):
    return b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)


def test_explicit_transparent_system_font_render_and_unchanged_svg(monkeypatch):
    calls = []
    png = fake_png()
    monkeypatch.setitem(sys.modules, 'resvg_py', SimpleNamespace(svg_to_bytes=lambda **kwargs: calls.append(kwargs) or png))
    original = SVG.encode()
    assert rasterize_svg(SVG, 512) == png
    assert SVG.encode() == original
    assert calls == [dict(svg_string=SVG, width=512, height=512, background=None,
                          dpi=96.0, skip_system_fonts=False, log_information=False)]


@pytest.mark.parametrize('pixels', [True, 255, 8193, 512.0, '512'])
def test_pixel_bounds_fail_before_renderer(monkeypatch, pixels):
    monkeypatch.setitem(sys.modules, 'resvg_py', None)
    with pytest.raises(ValueError): rasterize_svg(SVG, pixels)


@pytest.mark.parametrize('payload', [
    '<image href="file:///etc/passwd"/>', '<image href="https://example.com/a.png"/>',
    '<use href="#shadow"/>', '<script>alert(1)</script>', '<foreignObject/>',
    '<style>@import "https://example.com/a.css";</style>',
    '<path style="fill:url(file:///tmp/paint.svg)"/>',
    '<path fill="url(https://example.com/paint.svg)"/>',
    '<path clip-path="url(file:///tmp/clip.svg#x)"/>',
    '<path onload="anything"/>',
])
def test_external_resources_and_unsupported_features_fail_before_renderer(monkeypatch, payload):
    monkeypatch.setitem(sys.modules, 'resvg_py', None)
    with pytest.raises(ValueError): rasterize_svg(SVG.replace('</svg>', payload + '</svg>'), 512)


@pytest.mark.parametrize('width', ['0', '-1', 'NaN', '1e309', '100%', '1in'])
def test_unbounded_or_unsupported_dimensions_rejected(width):
    with pytest.raises(ValueError): rasterize_svg(SVG.replace('100px', width), 512)


def test_unsafe_xml_size_and_missing_dependency(monkeypatch):
    with pytest.raises(ValueError): rasterize_svg('x' * 10_000_001, 512)
    with pytest.raises(ValueError): rasterize_svg('<!DOCTYPE svg [<!ENTITY x "x">]>' + SVG.replace('</svg>', '&x;</svg>'), 512)
    monkeypatch.setitem(sys.modules, 'resvg_py', None)
    with pytest.raises(RuntimeError, match='resvg'): rasterize_svg(SVG, 512)


def test_native_numeric_clip_ids_are_preserved_and_references_must_exist(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, 'resvg_py', SimpleNamespace(svg_to_bytes=lambda **kw: calls.append(kw) or fake_png()))
    numeric = SVG.replace('id="shadow"', 'id="1"').replace('url(#shadow)', 'url(#1)')
    assert rasterize_svg(numeric, 512) == fake_png()
    assert calls[0]['svg_string'] == numeric
    with pytest.raises(ValueError, match='reference'):
        rasterize_svg(numeric.replace('url(#1)', 'url(#2)'), 512)


@pytest.mark.parametrize('png', [b'not png', fake_png(513, 256), fake_png(512, 512), fake_png(0, 256)])
def test_bad_renderer_result_not_silently_accepted(monkeypatch, png):
    monkeypatch.setitem(sys.modules, 'resvg_py', SimpleNamespace(svg_to_bytes=lambda **kw: png))
    with pytest.raises(RuntimeError): rasterize_svg(SVG, 512)


def test_actual_evenodd_hole_stays_transparent_and_shadow_has_alpha():
    pytest.importorskip('resvg_py')
    Image = pytest.importorskip('PIL.Image')
    picture = Image.open(io.BytesIO(rasterize_svg(SVG, 512)))
    assert picture.size == (512, 256) and picture.mode == 'RGBA'
    assert picture.getpixel((256, 128))[3] == 0
    assert 120 <= picture.getpixel((20, 20))[3] <= 135
    portrait = SVG.replace('100px', '50px').replace('50px" viewBox', '100px" viewBox')
    assert Image.open(io.BytesIO(rasterize_svg(portrait, 512))).size == (256, 512)


def test_worker_preserves_source_and_refuses_overwrite(tmp_path):
    pytest.importorskip('resvg_py')
    svg = tmp_path / 'source.svg'; svg.write_text(SVG)
    png = tmp_path / 'image.png'
    command = [sys.executable, '-m', 'chemdraw_macos.raster', str(svg), str(png), '512']
    result = subprocess.run(command, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert png.read_bytes().startswith(b'\x89PNG') and svg.read_text() == SVG
    original = png.read_bytes()
    assert subprocess.run(command, capture_output=True, timeout=20).returncode != 0
    assert png.read_bytes() == original
