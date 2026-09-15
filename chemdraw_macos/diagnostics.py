"""Read-only capability diagnostics, separate from destructive live tests."""
import importlib.util
import platform
import plistlib
from pathlib import Path

from .core import Bridge, app_location
from .native_lock import NativeBusy, shared_native_lock


def doctor(connect=True):
    result={'platform':platform.system(),'python':platform.python_version(),
            'chemistry_validator_available':importlib.util.find_spec('rdkit') is not None,
            'renderer':'native ChemDraw; PNG from unchanged native SVG with offline resvg',
            'rasterizer_available':importlib.util.find_spec('resvg_py') is not None,
            'network':'Only explicit opt-in resolver queries contact PubChem. Drawing and rasterization stay local. Connected AI clients have separate data policies.'}
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
            result['documents']=Bridge(app_path=app).documents()['documents']
            result['native_connection']='responding'
        else:result['native_connection']='not tested'
        result['status']='ready' if result['chemistry_validator_available'] else 'basic_only'
        result['compatibility']='Only ChemDraw 23.0.1 has been live-tested by this project; discovery is not verification of other versions.'
    except NativeBusy as exc:
        result.update(status='busy',native_connection='not tested: busy',error=str(exc),
                      help='Another cooperating client holds the native session. Wait for that workflow to finish before trying again.')
    except Exception as exc:
        result.update(status='unavailable',error=str(exc),
                      help='Check CHEMDRAW_APP, licence activation and macOS Automation permission. No automatic retries or permission changes are made.')
    return result
