"""Use desktop ChemDraw's own Name to Structure engine, not a substitute resolver."""
from contextlib import nullcontext
import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .core import style_cdxml, validate_cdxml


def caption_document(name, preset='house'):
    if not isinstance(name, str) or not name.strip() or len(name) > 500 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError('Supply one chemical name of 1..500 characters without control characters')
    root = ET.Element('CDXML')
    page = ET.SubElement(root, 'page', {'id': '1', 'BoundingBox': '0 0 600 750'})
    caption = ET.SubElement(page, 't', {'id': '2', 'p': '100 150'})
    ET.SubElement(caption, 's').text = name
    return style_cdxml(ET.tostring(root, encoding='unicode'), preset)


def draw_name(bridge, name, output_dir, allow_network=False, preset='house', pixels=2400):
    """Generate a native interpretation and review bundle; do not certify its identity.

    ChemDraw can fall back to ChemACX. The scripting interface does not disclose
    whether that lookup was used or offer a verified per-call offline switch.
    """
    if allow_network is not True:
        raise ValueError('Native name conversion requires allow_network=True: ChemDraw may send the name to ChemACX')
    source = caption_document(name, preset)
    out = Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():
        raise ValueError('Use a new absolute output directory with an existing parent')
    if out.exists() or out.is_symlink():
        raise FileExistsError('Output directory already exists')
    if type(pixels) is not int or not 256 <= pixels <= 8192:
        raise ValueError('Pixels must be an integer from 256 through 8192')
    from .styles import require_style_fonts
    require_style_fonts(preset)
    audit = {'status': 'in_progress', 'name': name, 'renderer': 'native ChemDraw',
             'rdkit_used': False, 'chemical_identity_validation': 'not performed',
             'visual_review': 'required', 'owned_document_ids': [],
             'native_lookup': {'network_allowed': True, 'network_used': 'not observable',
                               'possible_provider': 'ChemDraw internal dictionaries or ChemACX'}}
    def save_audit():
        (out/'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=True))
    with getattr(bridge, 'lock', nullcontext()):
        baseline = bridge.documents()
        out.mkdir()
        (out/'request.json').write_text(json.dumps({'name': name, 'allow_network': True,
            'preset': preset, 'pixels': pixels}, indent=2, ensure_ascii=True))
        (out/'caption-input.cdxml').write_text(source)
        save_audit()
        try:
            created = bridge.create(source)
            did = created['document']['document_id']
            audit['owned_document_ids'].append(did)
            save_audit()
            converted = bridge.convert_name(did)
            bridge.export(did, str(out/'figure.cdxml'), 'cdxml')
            native = validate_cdxml((out/'figure.cdxml').read_text())
            fragments = native.findall('.//fragment')
            if not fragments or not native.findall('.//n') or converted['document']['molecule_count'] < 1:
                raise ValueError('Native name conversion produced no structure; inspect retained document')
            for fmt in ('svg', 'png'):
                bridge.export(did, str(out/f'figure.{fmt}'), fmt, pixels=pixels)
            remaining = [d for d in bridge.documents()['documents'] if d['document_id'] != did]
            if remaining != baseline['documents']:
                raise ValueError('Pre-existing document metadata changed')
            audit.update(status='native_generated_review_required',
                checks={'native_structure_present': True, 'preexisting_document_metadata_unchanged': True},
                fragment_count=len(fragments), atom_count=len(native.findall('.//n')),
                native_warnings=[{'id': e.get('id'), 'message': e.get('Warning')}
                                 for e in native.iter() if e.get('Warning')])
            save_audit()
            (out/'review.html').write_text('<!doctype html><meta charset="utf-8">'
                '<title>Native name to structure</title><style>body{font:16px system-ui;'
                'background:#eee;margin:32px}img{background:white;max-width:100%;max-height:75vh}</style>'
                '<h1>'+html.escape(name)+'</h1><p>ChemDraw native interpretation. Chemical identity '
                'and stereochemistry require review; no independent identity validation performed.</p>'
                '<img src="figure.png" alt="Native chemical structure"><p>'
                '<a href="figure.cdxml">Editable ChemDraw</a> · <a href="audit.json">Audit</a></p>')
            return {'status': audit['status'], 'document': converted['document'], 'audit': audit,
                    'review': str(out/'review.html'),
                    'artifacts': {fmt: str(out/f'figure.{fmt}') for fmt in ('cdxml','svg','png')}}
        except (Exception, KeyboardInterrupt) as exc:
            # A modal lookup/error dialog can leave an AppleEvent outcome unknown.
            # Retain owned copies and audit; never automatically retry or close.
            audit.update(status='uncertain', error=str(exc))
            save_audit()
            raise
