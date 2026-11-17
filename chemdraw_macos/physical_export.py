"""Physical-scale exports of native ChemDraw artwork, never fit-to-square."""
import json
import math
import copy
import re
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

from .raster import _validate
from .native_lock import native_transaction

WINDOWS = sys.platform == 'win32'
_MATRIX = re.compile(r'matrix\(([^)]+)\)')


def native_units_per_point(root):
    """SVG units per drawing point, from ChemDraw's own element transforms.

    ChemDraw draws in 20 internal units per point and scales every element with one matrix.
    On macOS that matrix is 0.05 (one SVG unit per point). Windows ChemDraw writes display
    pixels instead (observed matrix 0.133333, i.e. 192 DPI at 200 % scaling), so the unit
    depends on the display and is read from the transforms rather than assumed.
    """
    if not WINDOWS:
        return 1.0
    scales = set()
    for element in root.iter():
        match = _MATRIX.fullmatch((element.get('transform') or '').strip())
        if not match:
            continue
        values = [float(v) for v in match[1].replace(',', ' ').split()]
        if len(values) != 6:
            raise ValueError('Unsupported native SVG transform; cannot establish the physical scale')
        a, b, c, d = values[:4]
        scales.add(math.sqrt(abs(a * d - b * c)))
    if not scales or max(scales) - min(scales) > 1e-6 or min(scales) <= 0:
        raise ValueError('Cannot establish one native SVG scale; the physical size would be wrong')
    dpi = scales.pop() * 20 * 72
    return (round(dpi) if abs(dpi - round(dpi)) < .01 else dpi) / 72


def physical_svg(svg):
    # ChemDraw's native SVG uses one drawing point per viewBox unit on macOS, although
    # its root dimensions say px; Windows uses display pixels (native_units_per_point).
    # Retain every path, glyph and transform.
    _validate(svg, 256)
    root = ET.fromstring(svg)
    width = float(root.get('width').removesuffix('px'))
    height = float(root.get('height').removesuffix('px'))
    view = list(map(float, root.get('viewBox', f'0 0 {width} {height}').split()))
    if view[2:] != [width, height]:
        raise ValueError('Native SVG coordinates do not have the supported 1:1 point scale')
    scale = native_units_per_point(root)
    width, height = width / scale, height / scale
    root.set('width', f'{width:g}pt'); root.set('height', f'{height:g}pt')
    root.set('viewBox', ' '.join(f'{v:g}' for v in view))
    return ET.tostring(root, encoding='unicode'), (width, height)


def validate_dpi(dpi):
    if type(dpi) is not int or not 72 <= dpi <= 1200:
        raise ValueError('DPI must be an integer from 72 through 1200')


def physical_png(svg, dpi=600):
    validate_dpi(dpi)
    fonts = {}
    if WINDOWS:
        # Render text with the faces Windows ChemDraw measured (native_faces).
        from . import native_faces
        svg = native_faces.match_native_faces(svg)
        fonts = native_faces.resvg_font_options()
    physical, (w, h) = physical_svg(svg)
    if max(w, h)*dpi/72 > 16000 or w*h*(dpi/72)**2 > 64_000_000:
        raise ValueError('Export exceeds 64 megapixels or 16000 pixels per side; use a lower DPI or SVG')
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=physical, dpi=float(dpi), background=None,
                                skip_system_fonts=False, log_information=False, **fonts)
    if (not isinstance(png, bytes) or len(png) < 33 or png[:8] != b'\x89PNG\r\n\x1a\n'
            or png[24:26] != b'\x08\x06'):
        raise RuntimeError('Rasterizer did not produce RGBA PNG')
    actual = struct.unpack('>II', png[16:24])
    if any(abs(a - p*dpi/72) > 1 for a, p in zip(actual, (w, h))):
        raise RuntimeError('Rasterizer changed the requested physical scale')
    # pHYs lets image-placement applications retain size in inches, not merely
    # pixel dimensions. Replace any existing chunk rather than emit duplicates.
    ppm = round(dpi / .0254)
    body = b'pHYs' + struct.pack('>IIB', ppm, ppm, 1)
    chunk = struct.pack('>I', 9) + body + struct.pack('>I', zlib.crc32(body))
    output = png[:33] + chunk
    pos = 33
    while pos < len(png):
        length = struct.unpack('>I', png[pos:pos+4])[0]
        end = pos + 12 + length
        if png[pos+4:pos+8] != b'pHYs': output += png[pos:end]
        pos = end
    return output


def page_svgs(svg,cdxml):
    """Clip native artwork to defined drawing sheets without fitting it."""
    from .core import validate_cdxml
    from .polish import bounds
    doc=validate_cdxml(cdxml);pages=doc.findall('page')
    if len(pages)!=1:raise ValueError('Expected one ChemDraw drawing canvas')
    page=pages[0];count=int(page.get('HeightPages','1'))
    if not 1<=count<=20 or page.get('WidthPages','1')!='1':
        raise ValueError('Page export supports 1 through 20 vertical drawing sheets')
    if count==1:return [svg]
    _validate(svg,256);root=ET.fromstring(svg);offsets=set()
    scale=native_units_per_point(root)
    for path in root.iter('{http://www.w3.org/2000/svg}path'):
        value=path.get('transform','')
        match=re.fullmatch(r'matrix\(([^)]+)\)',value)
        if not match:continue
        matrix=list(map(float,match[1].replace(',',' ').split()))
        expected=[.05,0,0,.05] if scale==1 else [scale/20,0,0,scale/20]
        if len(matrix)!=6 or (matrix[:4]!=expected if scale==1 else any(abs(v-w)>1e-6 for v,w in zip(matrix[:4],expected))):
            raise ValueError('Unsupported native SVG page-coordinate transform')
        offsets.add(tuple(matrix[4:]))
    if len(offsets)!=1:raise ValueError('Cannot establish one native page-coordinate origin')
    dx,dy=offsets.pop();extent=bounds(page);height=extent.height/count
    result=[]
    for index in range(count):
        sheet=copy.deepcopy(root)
        if scale==1:
            sheet.set('width',f'{extent.width:g}px');sheet.set('height',f'{height:g}px')
            sheet.set('viewBox',f'{extent.left+dx:g} {extent.top+dy+index*height:g} {extent.width:g} {height:g}')
        else:  # Windows: page geometry in points, SVG coordinates in display pixels
            sheet.set('width',f'{extent.width*scale:g}px');sheet.set('height',f'{height*scale:g}px')
            sheet.set('viewBox',f'{extent.left*scale+dx:g} {(extent.top+index*height)*scale+dy:g} {extent.width*scale:g} {height*scale:g}')
        result.append(ET.tostring(sheet,encoding='unicode'))
    return result


@native_transaction
def export_figure(bridge, document_id, output_dir, dpi=600, include_pdf=False):
    """Export the complete live drawing, cropped natively, at original scale."""
    from .addin import get_backend
    from .api_drawing import verify_export_snapshot
    validate_dpi(dpi)
    if type(include_pdf) is not bool:raise ValueError('include_pdf must be a boolean')
    if include_pdf:
        from .core import require_export_formats
        require_export_formats(bridge,['pdf'])
    out = Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():
        raise ValueError('Output must be absolute with an existing parent')
    if out.exists() or out.is_symlink(): raise FileExistsError('Output already exists')
    did = bridge._id(document_id)
    backend = get_backend(bridge)
    from .core import Bridge
    if isinstance(bridge,Bridge):
        from .addin import read_preserving_active
        # Establish the connection before selecting a known document. Export
        # targets an explicit ID, even if a previous operation changed tabs.
        backend._ready()
        read=lambda:read_preserving_active(bridge,did)
    else:read=lambda:backend.read(did)
    before = read()
    out.mkdir()
    (out/'figure.cdxml').write_text(before['cdxml'],encoding='utf-8',newline='')
    bridge.export(did, str(out/'native.svg'), 'svg')
    after = read()
    verify_export_snapshot(before['cdxml'], after['cdxml'])
    native = (out/'native.svg').read_text(encoding='utf-8')
    svg, size = physical_svg(native)
    (out/'figure.svg').write_text(svg,encoding='utf-8',newline='')
    pages=page_svgs(native,before['cdxml'])
    page_artifacts=[]
    for index,page in enumerate(pages,1):
        stem='figure' if len(pages)==1 else f'page-{index:02}'
        (out/f'{stem}.png').write_bytes(physical_png(page,dpi))
        (out/f'{stem}.svg').write_text(physical_svg(page)[0],encoding='utf-8',newline='')
        page_artifacts.append({'page':index,'svg':str(out/f'{stem}.svg'),'png':str(out/f'{stem}.png')})
    if include_pdf:
        # Export a named private copy, so an untitled source never acquires a
        # filename as a side effect of native PDF saving.
        copy=bridge.create(before['cdxml'],visible=False)
        copy_id=copy['document']['document_id']
        bridge.export(copy_id,str(out/'figure.pdf'),'pdf')
        bridge.close(copy_id)
        verify_export_snapshot(before['cdxml'],read()['cdxml'])
    result = {'status': 'completed', 'document_id': did, 'dpi': dpi,
              'physical_size_mm': [v*25.4/72 for v in size],
              'pixels_per_drawing_point': dpi/72,
              'crop': 'native drawing bounds' if len(pages)==1 else 'defined drawing sheets', 'scale': 'original drawing points',
              'source_preserved': True, 'renderer': 'native ChemDraw',
              'artifacts': {fmt: str(out/f'figure.{fmt}') for fmt in ('cdxml','svg')},
              'pages':page_artifacts,
              'note': 'No fit-to-width or molecule resizing. Insert at original size in your document. Visual review required.'}
    if include_pdf:result['artifacts']['pdf']=str(out/'figure.pdf')
    if len(pages)==1:result['artifacts']['png']=str(out/'figure.png')
    (out/'export.json').write_text(json.dumps(result, indent=2)+'\n',encoding='utf-8',newline='')
    return result


def preview_png(bridge, document_id, pixels=1200) -> bytes:
    """White-background PNG of the live document from ChemDraw's own SVG export."""
    from .raster import rasterize_svg
    if isinstance(pixels, bool) or not isinstance(pixels, int) or not 256 <= pixels <= 4096:
        raise ValueError('pixels must be 256 through 4096')
    did = bridge._id(document_id)
    svg = bridge._new_path('.svg', 'previews')
    bridge.export(did, str(svg), 'svg')
    try:
        return rasterize_svg(svg.read_text(), pixels, background='white')
    finally:
        svg.unlink(missing_ok=True)
