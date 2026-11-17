"""ChemDraw's own 1H/13C NMR prediction (ChemNMR), returned as parsed text.

ChemDraw opens the predicted spectrum as a new document. Its protocol caption
holds the shift table and, for 1H, coupling constants; that caption is read
through the desktop API and parsed. Prediction quality is ChemDraw's estimate,
not a measured spectrum.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

COMMANDS = {'1H': 'predict1H_NMR_Shifts', '13C': 'predict13C_NMR_Shifts'}
_HEADER = re.compile(r'Protocol of the (H-1|C-13) NMR Prediction:?(?:\s*\(([^)]*)\))?')
_ROW = re.compile(r'^(\S+)\s+(-?\d+(?:\.\d+)?)\s+(.*)$')
_INCREMENT = re.compile(r'^\s{4,}(.+)$')


def parse_protocol(text: str) -> dict:
    header = _HEADER.search(text)
    if not header:
        raise ValueError('Not a ChemNMR prediction protocol')
    nucleus = '1H' if header.group(1) == 'H-1' else '13C'
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.lstrip().startswith('Node'))
    except StopIteration:
        start = len(lines)
    shifts, end = [], len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        if 'Coupling Constant' in line or line.startswith('shift'):
            end = i
            break
        row = _ROW.match(line)
        if row and not line[0].isspace():
            parts = re.split(r'\s{2,}', row.group(3).strip())
            shifts.append({'group': row.group(1), 'shift_ppm': float(row.group(2)),
                           'increments': [' '.join(parts)] if parts and parts[0] else []})
            continue
        more = _INCREMENT.match(line)
        if more and shifts:
            shifts[-1]['increments'].append(' '.join(re.split(r'\s{2,}', more.group(1).strip())))
    couplings = '\n'.join(lines[end:]).strip()
    return {'nucleus': nucleus, 'conditions': header.group(2) or '', 'shifts': shifts,
            'couplings_text': couplings[:8000]}


def _protocol_from_cdxml(cdxml: str) -> str:
    root = ET.fromstring(cdxml)
    for t in root.iter('t'):
        text = ''.join(t.itertext())
        if _HEADER.search(text):
            return text
    raise RuntimeError('The spectrum document has no ChemNMR protocol caption')


def predict_nmr(bridge, document_id=None, smiles=None, nucleus='1H', selection='all',
                keep_open=True, output_dir=None, wait_seconds=60) -> dict:
    if nucleus not in COMMANDS:
        raise ValueError('nucleus must be 1H or 13C')
    if (document_id is None) == (smiles is None):
        raise ValueError('Supply exactly one of document_id or smiles')
    if type(keep_open) is not bool:
        raise ValueError('keep_open must be a boolean')
    out = None
    if output_dir is not None:
        out = Path(output_dir).expanduser()
        if not out.is_absolute() or not out.parent.is_dir():
            raise ValueError('output_dir must be absolute with an existing parent')
        if out.exists() or out.is_symlink():
            raise FileExistsError('output_dir already exists')
    from .commands import execute
    from .addin import read_preserving_active
    with bridge.lock:
        temporary = None
        if smiles is not None:
            from .draw import prepare_structures
            item = prepare_structures([{'compound_id': 'nmr', 'label': 'nmr', 'smiles': smiles}])[0]
            mol = bridge._new_path('.mol')
            mol.write_text(item['molblock'], encoding='utf-8')
            temporary = bridge.import_file(str(mol))['document']['document_id']
            document_id, selection = temporary, 'all'
        try:
            run = execute(bridge, document_id, COMMANDS[nucleus], selection, wait_seconds)
        finally:
            if temporary is not None:
                bridge._run('close', temporary)
                bridge.managed.discard(temporary)
        if run['status'] == 'not_enabled':
            raise ValueError('ChemDraw has NMR prediction disabled here: select one structure (selection=current) '
                             'or use selection=all on a document with structures')
        if run['status'] != 'completed' or len(run['new_documents']) != 1:
            return {**run, 'status': run['status'] if run['status'] != 'completed' else 'no_spectrum',
                    'message': 'ChemDraw did not open exactly one spectrum document; inspect ChemDraw.'}
        spectrum = run['new_documents'][0]
        sid = spectrum['document_id']
        cdxml = read_preserving_active(bridge, sid)['cdxml']
        parsed = parse_protocol(_protocol_from_cdxml(cdxml))
        result = {'status': 'completed', **parsed, 'spectrum_document': spectrum,
                  'source': 'ChemDraw ChemNMR estimate', 'measured': False}
        if smiles is not None:
            result['smiles'] = smiles
        if out is not None:
            from .raster import rasterize_svg
            out.mkdir()
            (out/'spectrum.cdxml').write_text(cdxml, encoding='utf-8')
            svg = out/'spectrum.svg'
            bridge.export(sid, str(svg), 'svg')
            (out/'spectrum.png').write_bytes(rasterize_svg(svg.read_text(encoding='utf-8'), 1600, background='white'))
            result['artifacts'] = {'cdxml': str(out/'spectrum.cdxml'), 'svg': str(svg), 'png': str(out/'spectrum.png')}
        if not keep_open:
            bridge._run('close', sid)
            result['spectrum_document_closed'] = True
        return result
