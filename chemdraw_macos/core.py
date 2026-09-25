"""Small, bounded native bridge. No mouse, clipboard, or unrestricted script tool."""
from __future__ import annotations
import json
import os
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET
from .native_lock import shared_native_lock

FORMATS={'svg':'Scalable Vector Graphics (SVG)','pdf':'PDF','cdxml':'ChemDraw XML','cdx':'ChemDraw'}
PRESETS={
    'house':{'BondLength':'18','LineWidth':'1.58','BoldWidth':'2','LabelSize':'14',
             'CaptionSize':'8.28','font':'Helvetica Neue'},
    'acs-1996':{'BondLength':'14.4','LineWidth':'0.6','BoldWidth':'2',
                'LabelSize':'10','CaptionSize':'10','font':'Arial'},
}

def validate_cdxml(text: str):
    if len(text.encode('utf-8'))>10_000_000:raise ValueError('CDXML exceeds 10 MB limit')
    try:root=SafeET.fromstring(text,forbid_entities=True,forbid_external=True)
    except Exception as e:raise ValueError(f'Invalid or unsafe CDXML: {e}') from e
    if root.tag!='CDXML':raise ValueError('Expected a CDXML document')
    return root

def preset_settings(preset):
    if isinstance(preset,str):
        if preset not in PRESETS:raise ValueError(f'Unknown preset; choose {list(PRESETS)}')
        return dict(PRESETS[preset])
    from .styles import validate_style
    return validate_style(preset)

def style_cdxml(text: str,preset: str|dict)->str:
    from .styles import validate_style
    root=validate_cdxml(text);spec=validate_style(preset_settings(preset))
    fonttable=root.find('fonttable')
    if fonttable is None:fonttable=ET.SubElement(root,'fonttable')
    fontid=str(max([int(f.get('id','0')) for f in fonttable]+[2])+1)
    ET.SubElement(fonttable,'font',{'id':fontid,'name':spec['font'],'charset':'Unicode'})
    captionfontid=fontid
    if spec.get('CaptionFontName',spec['font'])!=spec['font']:
        captionfontid=str(int(fontid)+1)
        ET.SubElement(fonttable,'font',{'id':captionfontid,'name':spec['CaptionFontName'],'charset':'Unicode'})
    for key,value in spec.items():
        if key not in ('font','CaptionFontName'):root.set(key,value)
    root.attrib.update(LabelFont=fontid,CaptionFont=captionfontid,InterpretChemically='no',
        color='0',bgcolor='1')
    for key,value in {'BondSpacing':'18','ChainAngle':'120','MarginWidth':'1.6','HashSpacing':'2.5'}.items():root.set(key,spec.get(key,value))
    atomtexts={id(t) for n in root.iter('n') for t in n.iter('t')}
    for t in root.iter('t'):
        for s in t.iter('s'):
            atom=id(t) in atomtexts
            s.set('font',fontid if atom else captionfontid);s.set('size',spec['LabelSize'] if atom else spec['CaptionSize']);s.set('color','0')
            face=spec.get('LabelFace' if atom else 'CaptionFace')
            if face is not None:s.set('face',str((int(s.get('face','96' if atom else '0'))&~3)|(int(face)&3)))
    for e in root.iter():
        if e is not root:
            # Native objects may override document defaults. Replace the
            # supported local style fields too, retaining chemical script bits.
            for key in spec.keys() & e.attrib.keys():
                if key in ('font','CaptionFontName'):continue
                if key in ('LabelFace','CaptionFace'):
                    e.set(key,str((int(e.get(key))&~3)|(int(spec[key])&3)))
                else:e.set(key,spec[key])
            for key,value in [('LabelFont',fontid),('CaptionFont',captionfontid)]:
                if key in e.attrib:e.set(key,value)
        if e.tag in ('n','b'):e.set('color','0')
        if e.tag=='b':
            e.set('LineWidth',spec['LineWidth']);e.set('BoldWidth',spec['BoldWidth'])
        if e.tag=='graphic' and e.get('SymbolType') in ('CirclePlus','CircleMinus'):
            e.set('LineWidth',str(float(spec['LineWidth'])/0.8));e.set('color','0')
    # Coordinates, bond Display, charges and stereo are untouched. Native clean is separate.
    return ET.tostring(root,encoding='unicode')

def app_location()->Path:
    if os.environ.get('CHEMDRAW_DESKTOP_EXTENSION') == '1':
        from .desktop_setup import read_settings, validate_app
        settings = read_settings()
        if not settings.get('setup_complete'):
            raise RuntimeError('Finish the ChemDraw MCP setup window before using native tools')
        if settings.get('chemdraw_app'):
            return validate_app(settings['chemdraw_app'])
    explicit=os.environ.get('CHEMDRAW_APP')
    if explicit:return Path(explicit).expanduser().resolve()
    candidates=sorted(Path('/Applications').glob('ChemDraw*.app'))
    if len(candidates)!=1:raise RuntimeError('Set CHEMDRAW_APP to the installed ChemDraw .app path')
    return candidates[0]

def document_row(row):
    return dict(zip(('document_id','name','file','modified','molecule_count'),row))

class Bridge:
    def __init__(self,app_path:Path|None=None,workspace:Path|None=None,timeout:float=25):
        self.app=app_path or app_location()
        self.workspace=workspace or Path(os.environ.get('CHEMDRAW_MCP_WORKSPACE',str(Path.home()/'ChemDraw-MCP-Output')))
        self.timeout=timeout;self.lock=shared_native_lock();self.managed=set()

    def app_running(self):
        """Inspect running applications without sending ChemDraw a launch event."""
        with (self.app/'Contents/Info.plist').open('rb') as handle:
            bundle=plistlib.load(handle)['CFBundleIdentifier']
        script=('ObjC.import("AppKit"); '
                '$.NSRunningApplication.runningApplicationsWithBundleIdentifier('
                +json.dumps(bundle)+').count > 0')
        result=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],
                              capture_output=True,text=True,timeout=self.timeout,check=True)
        return result.stdout.strip()=='true'

    def automatic_presentation(self):
        if not self.app_running():return 'background'
        return 'interactive' if self._run('visible_documents') else 'background'

    def default_new_document_visible(self):
        return not getattr(self,'_production_depth',0)

    def _run(self,operation,*args):
        if not self.app.is_dir():raise RuntimeError(f'ChemDraw not found: {self.app}')
        template=Path(__file__).with_name('native.applescript').read_text()
        quoted='"'+str(self.app).replace('\\','\\\\').replace('"','\\"')+'"'
        script=template.replace('__APP__',quoted)
        with self.lock:
            try:
                p=subprocess.run(['/usr/bin/osascript','-']+[operation]+[str(a) for a in args],
                    input=script,capture_output=True,text=True,timeout=self.timeout,check=True)
            except subprocess.TimeoutExpired as e:
                raise RuntimeError('ChemDraw automation timed out, possibly due to a dialog. Operation was not retried; its outcome is uncertain. Inspect ChemDraw before retrying.') from e
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f'ChemDraw automation failed: {e.stderr.strip()}') from e
        try:return json.loads(p.stdout)
        except json.JSONDecodeError as e:raise RuntimeError(f'Invalid native response: {p.stdout[:500]}') from e

    @staticmethod
    def _id(value):
        if isinstance(value,bool):raise ValueError('Expected an integer document/object ID')
        try:n=int(value)
        except (TypeError,ValueError):raise ValueError('Expected an integer document/object ID')
        if str(n)!=str(value):raise ValueError('Expected an integer document/object ID')
        return n

    def documents(self):return {'documents':[document_row(r) for r in self._run('list')]}

    def inspect(self,document_id):
        row,molecules,settings=self._run('inspect',self._id(document_id))
        return {'document':document_row(row),'molecules':[{'molecule_index':m[0],'bounds_pt':m[1]} for m in molecules],
                'settings':dict(zip(('bond_length_twentieth_pt','line_width_twentieth_pt','label_size_twentieth_pt','label_font','caption_size_twentieth_pt','caption_font'),settings))}

    def initialize_empty_style(self,document_id,initial,backend,preset='house'):
        """Set editing defaults only before the first objects enter a blank canvas."""
        from .batch import NativeUncertain
        from .styles import require_style_fonts
        root=validate_cdxml(initial['cdxml']);pages=root.findall('page')
        if len(pages)!=1 or len(pages[0]):return initial
        spec=preset_settings(preset);require_style_fonts(preset)
        values=[round(float(spec[k])*20) for k in
                ('BondLength','LineWidth','BoldWidth','LabelSize','CaptionSize')]
        try:
            with self.lock:
                self._run('empty_document_style',self._id(document_id),*values,spec['font'],18,120,32,50)
                after=backend.read(document_id)
            saved=validate_cdxml(after['cdxml']);page=saved.find('page')
            if page is None or len(page):raise ValueError('Blank canvas changed while setting defaults')
            for key in ('BoundingBox','WidthPages','HeightPages'):
                if page.get(key)!=pages[0].get(key):raise ValueError('Canvas dimensions changed')
            if after.get('document',{}).get('file')!=initial.get('document',{}).get('file'):
                raise ValueError('Canvas file binding changed')
            for key in ('BondLength','LineWidth','BoldWidth','LabelSize','CaptionSize'):
                if abs(float(saved.get(key,'nan'))-float(spec[key]))>.026 or key not in saved.attrib:
                    raise ValueError('Native editing default did not match: '+key)
            fonts={f.get('id'):f.get('name') for f in saved.findall('fonttable/font')}
            for key in ('LabelFont','CaptionFont'):
                if saved.get(key) in fonts and fonts[saved.get(key)]!=spec['font']:
                    raise ValueError('Native editing fonts did not match')
            if any(saved.get(key) not in fonts for key in ('LabelFont','CaptionFont')):
                # ChemDraw omits an unused font from a blank document's XML table.
                settings=self.inspect(document_id)['settings']
                if any(settings[key]!=spec['font'] for key in ('label_font','caption_font')):
                    raise ValueError('Native editing fonts did not match')
            return after
        except Exception as exc:
            raise NativeUncertain('Blank-canvas defaults may have changed; no molecules appended. Inspect the document before retrying: '+str(exc)) from exc

    def _new_path(self,suffix,category='scratch'):
        folder=self.workspace/category;folder.mkdir(parents=True,exist_ok=True)
        return folder/(str(uuid.uuid4())+suffix)

    def import_file(self,path,visible=None):
        if visible is None:visible=self.default_new_document_visible()
        if type(visible) is not bool:raise ValueError('visible must be a boolean')
        source=Path(path).expanduser().resolve(strict=True)
        if source.suffix.lower() not in ('.cdxml','.cdx','.mol','.sdf'):raise ValueError('Supported imports: .cdxml, .cdx, .mol, .sdf')
        if source.stat().st_size>10_000_000:raise ValueError('Import exceeds 10 MB limit')
        if source.suffix.lower()=='.cdxml':validate_cdxml(source.read_text())
        with self.lock:
            copy=self._new_path(source.suffix);shutil.copyfile(source,copy)
            result=self._open_working(copy) if visible else self._open_working(copy,visible=False)
            self.managed.add(result['document_id'])
        return {'document':result,'source_untouched':str(source),'working_copy':str(copy)}

    def create(self,cdxml,visible=None):
        if visible is None:visible=self.default_new_document_visible()
        if type(visible) is not bool:raise ValueError('visible must be a boolean')
        validate_cdxml(cdxml)
        with self.lock:
            path=self._new_path('.cdxml');path.write_text(cdxml)
            result=self._open_working(path) if visible else self._open_working(path,visible=False)
            self.managed.add(result['document_id'])
        return {'document':result,'working_copy':str(path)}

    def _open_working(self,path,visible=True):
        try:
            args=() if visible else ('false',)
            return document_row(self._run('open',str(path),*args))
        except RuntimeError as exc:
            if 'Could not identify the imported document uniquely' not in str(exc):raise
            # The single open may finish asynchronously. Reconcile by reading;
            # never issue another open or retry an uncertain write.
            for _ in range(20):
                rows=[r for r in self._run('list') if r[2]==str(path)]
                if len(rows)==1:
                    if not visible:self.set_visibility(rows[0][0],False)
                    return document_row(rows[0])
                if len(rows)>1:raise RuntimeError(f'Multiple documents match working path {path}') from exc
                time.sleep(.05)
            raise RuntimeError(f'Opened document could not be reconciled; working copy: {path}') from exc

    def finish_scope(self,document_id,expected,arranged,decorated,decoration):
        from .scope_finish import finish_scope
        return finish_scope(self,document_id,expected,arranged,decorated,decoration)

    def set_visibility(self,document_id,visible):
        """Show/hide exactly the supplied document, never the whole application."""
        if type(visible) is not bool:raise ValueError('visible must be a boolean')
        row,actual=self._run('visibility',self._id(document_id),str(visible).lower())
        if actual is not visible:raise RuntimeError('ChemDraw did not apply requested window visibility')
        return {'document':document_row(row),'visible':actual}

    def output_path(self,path,format):
        if format not in (*FORMATS,'png'):raise ValueError(f'Unsupported format: {format}')
        target=Path(path).expanduser()
        if not target.is_absolute():raise ValueError('Output path must be absolute')
        if target.suffix.lower()!='.'+format:raise ValueError('Output extension must match format')
        if target.exists() or target.is_symlink():raise FileExistsError(f'Will not overwrite {target}')
        if not target.parent.is_dir():raise ValueError('Output parent directory must already exist')
        return target

    def export(self,document_id,path,format,pixels=3200):
        did=self._id(document_id);target=self.output_path(path,format)
        if not 256<=pixels<=8192:raise ValueError('PNG longest side must be 256 to 8192 pixels')
        with self.lock:
            # Recheck under the server lock; never overwrite existing outputs.
            self.output_path(path,format)
            if format=='png':
                svg=self._new_path('.svg')
                self._run('export',did,str(svg),FORMATS['svg'])
                subprocess.run([sys.executable,'-m','chemdraw_macos.raster',str(svg),str(target),str(pixels)],
                    check=True,capture_output=True,text=True,timeout=self.timeout)
            else:self._run('export',did,str(target),FORMATS[format])
            if not target.is_file() or not target.stat().st_size:raise RuntimeError('ChemDraw did not produce a nonempty export')
        result={'path':str(target),'format':format,'bytes':target.stat().st_size,'renderer':'native ChemDraw'}
        if format=='png':result['rasterizer']='resvg'
        return result

    def clean(self,document_id,molecule_index=None):
        did=self._id(document_id)
        mid='' if molecule_index is None else self._id(molecule_index)
        with self.lock:
            backup=self._new_path('.cdxml','backups')
            self.export(did,str(backup),'cdxml')
            result=document_row(self._run('clean',did,mid))
        return {'document':result,'backup':str(backup),'warning':'Native cleanup can change depiction; review stereochemistry and orientation before using the drawing.'}

    def convert_name(self, document_id):
        """Convert the sole caption in an owned, frontmost scratch document."""
        did = self._id(document_id)
        with self.lock:
            if did not in self.managed:
                raise ValueError('Name conversion requires a document owned by this server session')
            return {'document': document_row(self._run('convert_name', did))}

    def native_action(self, document_id, action, selection='current'):
        """Apply an allowlisted native menu command to an owned working document."""
        from .native_actions import ACTIONS
        did = self._id(document_id)
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError('Unsupported native action')
        if selection not in ('current', 'all'):
            raise ValueError('Selection must be current or all')
        with self.lock:
            if did not in self.managed:
                raise ValueError('Native actions require a document owned by this server session; import a copy first')
            backup = self._new_path('.cdxml', 'backups')
            self.export(did, str(backup), 'cdxml')
            row, applied = self._run('native_action', did, ACTIONS[action], selection)
        return {'document': document_row(row), 'backup': str(backup),
                'action': action, 'native_command': ACTIONS[action], 'selection': selection,
                'status': 'native_action_applied_review_required' if applied else 'unavailable_for_selection',
                'chemical_preservation_verified': False,
                'warning': 'Actual ChemDraw command. Existing selection or all objects as requested. Native cleanup, grouping and caption behavior require review; no workflow geometry/identity certificate.'}

    def apply_style(self,document_id,preset='house'):
        preset_settings(preset)
        from .styles import require_style_fonts
        require_style_fonts(preset)
        with self.lock:
            snapshot=self._new_path('.cdxml','backups');self.export(document_id,str(snapshot),'cdxml')
            planned=style_cdxml(snapshot.read_text(),preset)
            result=self.create(planned)
            if isinstance(preset,dict):
                from .styles import verify_custom_style
                saved=self._new_path('.cdxml','backups')
                # Verification addresses only this created copy. On an export
                # error retain the owned document, without retrying or closing.
                self.export(result['document']['document_id'],str(saved),'cdxml')
                result={**result,'styled_snapshot':str(saved),
                        'custom_style_verification':verify_custom_style(planned,saved.read_text(),preset)}
        return {**result,'preset':preset,'source_snapshot':str(snapshot),
                'note':'Styled copy. Coordinates and chemistry preserved; bond-length setting affects subsequent drawing/cleanup, not existing coordinates. Charge placement is retained, not recomputed.'}

    def close(self,document_id):
        did=self._id(document_id)
        with self.lock:
            if did not in self.managed:raise ValueError('Close is restricted to documents created/imported by this server session')
            backup=self._new_path('.cdxml','backups');self.export(did,str(backup),'cdxml')
            self._run('close',did);self.managed.remove(did)
        return {'closed_document_id':did,'backup':str(backup)}
