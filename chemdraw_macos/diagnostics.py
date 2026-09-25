"""Read-only capability diagnostics, separate from destructive live tests."""
import importlib.util
import importlib.metadata
import errno
import platform
import plistlib
import time
import hashlib
import sys
from pathlib import Path

from .core import Bridge, app_location
from .native_lock import NativeBusy, shared_native_lock


def _source_digest():
    digest=hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob('*')):
        if path.is_file() and path.suffix in ('.py','.js','.applescript','.json'):
            digest.update(str(path.relative_to(Path(__file__).parent)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


_LOADED_SOURCE_DIGEST=None if getattr(sys,'frozen',False) else _source_digest()


def runtime_info():
    if getattr(sys,'frozen',False):return {'mode':'packaged','restart_required':False}
    return {'mode':'checkout','source_directory':str(Path(__file__).resolve().parent.parent),
            'loaded_source_digest':_LOADED_SOURCE_DIGEST,
            'restart_required':_source_digest()!=_LOADED_SOURCE_DIGEST}


def _chemistry():
    result={'chemistry_validator_available':False,'cdxml_writer_available':False}
    try:
        from rdkit import Chem,rdBase
        result.update(chemistry_validator_available=True,rdkit_version=rdBase.rdkitVersion)
        if not hasattr(Chem,'MolToCDXMLBlock') or not Chem.HasChemDrawCDXSupport():
            raise RuntimeError('RDKit requires compiled ChemDraw CDXML support')
        mol=Chem.MolFromSmiles('CCO')
        from rdkit.Chem import rdDepictor
        rdDepictor.Compute2DCoords(mol)
        decoded=Chem.MolsFromCDXML(Chem.MolToCDXMLBlock(mol))
        if len(decoded)!=1 or Chem.MolToSmiles(decoded[0])!='CCO':
            raise RuntimeError('CDXML writer roundtrip failed')
        result['cdxml_writer_available']=True
    except Exception as exc:
        result['chemistry_help']=str(exc)+'. Run uv sync --locked --extra chemistry in the source directory.'
    return result


def _desktop_api(bridge,documents,progress=None):
    """Probe a current document, without inserting objects or installing an add-in."""
    if not documents:
        return {'status':'needs_document','code':'no_open_document',
                'help':'Open a blank ChemDraw document, then rerun doctor. No test document was created.'}
    from .addin import get_backend, installed_addin_directory
    progress = progress if progress is not None else {}
    progress['stage'] = 'addin_discovery'
    backend=getattr(bridge,'_desktop_addin',None)
    if backend is None or backend.closed:
        base=Path.home()/'Library/Application Support/com.revvity.ChemDraw/Add-ins/ChemDraw MCP Native API'
        directory=installed_addin_directory(base)
        files=[directory/'main.html',directory/'chemdraw-addin-metadata.json',
               base.with_name(base.name+'.connection.json')]
        if not all(p.is_file() for p in files):
            return {'status':'needs_setup','code':'addin_files_missing',
                    'help':'Run chemdraw-mac addin-connect and install the returned private package on this Mac. Do not copy another Mac\'s add-in.'}
        if not bridge._run('addin_available',str(directory)):
            return {'status':'needs_setup','code':'addin_command_unavailable',
                    'help':'Enable ChemDraw MCP Native API in Add-in Manager. Check Preferences > Directories includes '+str(directory.parent.parent)+'.'}
        try:backend=get_backend(bridge)
        except OSError as exc:
            if exc.errno!=errno.EADDRINUSE:raise
            return {'status':'busy','code':'endpoint_in_use',
                    'help':'Another MCP client owns the add-in connection. Close that client before testing this one; do not reinstall.'}
    if hasattr(backend, 'connect'):
        progress['stage'] = 'addin_open'
        connection = backend.connect()
        if connection.get('status') != 'connected':
            return {'status': connection['status'], 'code': connection.get('code'),
                    'help': connection.get('next_action', 'Enable the add-in in Add-in Manager.')}
    progress['stage'] = 'active_document'
    did = bridge._run('active_document')
    if did is None:
        return {'status':'needs_document','code':'no_open_document',
                'help':'Open a blank ChemDraw document, then test again. No document was created or changed.'}
    progress['stage'] = 'document_read'
    value=backend.read(did)
    return {'status':'responding','api_version':value.get('api_version'),
            'read_verified':True,'write_tested':False}


def doctor(connect=True,*,bridge=None):
    started = time.monotonic()
    progress = {'stage': 'application_discovery'}
    try:version=importlib.metadata.version('chemdraw-mcp-macos')
    except importlib.metadata.PackageNotFoundError:version='uninstalled source'
    result={'platform':platform.system(),'python':platform.python_version(),
            'macos':platform.mac_ver()[0],'architecture':platform.machine(),'package_version':version,
            'runtime':runtime_info(),
            'chemistry_validator_available':importlib.util.find_spec('rdkit') is not None,
            'renderer':'native ChemDraw; PNG from unchanged native SVG with offline resvg',
            'rasterizer_available':importlib.util.find_spec('resvg_py') is not None,
            'network':'Only explicit opt-in resolver queries contact PubChem. Drawing and rasterization stay local. Connected AI clients have separate data policies.',
            'desktop_api':{'status':'not_tested'},'shared_drawing_ready':False}
    result.update(_chemistry())
    gate=shared_native_lock()
    result['coordination']={'mode':'per-user cooperative process lock','path':str(gate.path),'wait_seconds':gate.timeout,
                            'limits':'Does not coordinate manual GUI edits, older clients or other automation software.'}
    try:
        if platform.system()!='Darwin':raise RuntimeError('Native automation requires macOS')
        app=app_location()
        if not app.is_dir():raise RuntimeError(f'ChemDraw app not found: {app}')
        plist=app/'Contents'/'Info.plist'
        metadata=plistlib.loads(plist.read_bytes())
        result.update(app=str(app),version=metadata.get('CFBundleShortVersionString','unknown'),
                      sips_available=Path('/usr/bin/sips').is_file())
        if connect:
            b=bridge if bridge is not None else Bridge(app_path=app)
            progress['stage'] = 'document_list'
            result['documents']=b.documents()['documents']
            result['document_count']=len(result['documents'])
            result['native_connection']='responding'
            result['desktop_api']={'status':'checking'}
            result['desktop_api']=_desktop_api(b,result['documents'],progress)
        else:result['native_connection']='not tested'
        dependencies=result['cdxml_writer_available'] and result['rasterizer_available']
        api=result['desktop_api']
        result['shared_drawing_ready']=bool(dependencies and api['status']=='responding')
        result['status']=('ready' if result['shared_drawing_ready'] else
                          api['status'] if connect and api['status']!='responding' else
                          'local_ready' if dependencies else 'basic_only')
        if api.get('help'):result['help']=api['help']
        result['compatibility']='Only ChemDraw 23.0.1 has been live-tested by this project; discovery is not verification of other versions.'
    except NativeBusy as exc:
        result.update(status='busy',native_connection='not tested: busy',error=str(exc),
                      help='Another cooperating client holds the native session. Wait for that workflow to finish before trying again.')
    except Exception as exc:
        result['failure_context'] = {'stage': progress['stage'], 'exception_type': type(exc).__name__}
        from .addin import AddinReadError
        if isinstance(exc, AddinReadError):
            result['failure_context'].update(stage=exc.stage, code=exc.code)
        if isinstance(exc, OSError):result['failure_context']['os_error_code'] = exc.errno
        if result['desktop_api']['status'] == 'checking':
            result['desktop_api'] = {'status':'failed','read_verified':False,'write_tested':False}
        result.update(status='unavailable',error=str(exc),
                      help='Check CHEMDRAW_APP, licence activation and macOS Automation permission. No automatic retries or permission changes are made.')
        if isinstance(exc, AddinReadError) and exc.code == 'no_open_document':
            result.update(status='needs_document',help='Open a blank ChemDraw document, then test again.')
            result['desktop_api'].update(status='needs_document',code=exc.code)
        elif isinstance(exc, AddinReadError):
            result['help'] = ('Keep the intended ChemDraw document active, then test again.'
                              if exc.code == 'document_changed' else
                              'ChemDraw responded, but the document read could not be verified. '
                              'Save or copy diagnostics to report the failing read step.')
    result['elapsed_ms'] = round((time.monotonic()-started)*1000)
    return result
