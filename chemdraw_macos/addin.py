"""Experimental desktop add-in transport. No clipboard, key events or renderer.

Only a locally installed HTML add-in holding the per-session secret can claim a
job. Delivery is at most once. A missing response poisons the channel: a timed-out
native write must never be replayed, even after a late callback.
"""
import copy
import hashlib
import hmac
import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import xml.etree.ElementTree as ET
import zipfile

from .core import validate_cdxml, document_row
from .shared import _page, fingerprint
from .polish import bounds, chemical_signature


def source_token(text):
    return hashlib.sha256(json.dumps(fingerprint(text)).encode()).hexdigest()


def prepare_payload(before, addition, *, allow_page_expansion=False):
    """Keep target settings and absolute placement; refuse unsafe flat additions."""
    target, page = _page(before,vertical_pages=allow_page_expansion)
    incoming, added = _page(addition,vertical_pages=allow_page_expansion)
    if allow_page_expansion:
        from .shared import validate_page_expansion
        validate_page_expansion(page,added)
    chemical_signature(addition)
    if not len(added):
        raise ValueError('Empty addition')
    ignored={'Name','CreationProgram','WindowPosition','WindowSize','BoundingBox','MacPrintInfo'}
    for key,value in incoming.attrib.items():
        if key not in ignored and target.get(key)!=value:
            raise ValueError('Addition must use working-document settings: '+key)
    for table in ('fonttable','colortable'):
        a=incoming.find(table);b=target.find(table)
        if table=='fonttable' and a is not None:
            old={f.get('id'):dict(f.attrib) for f in b} if b is not None else {}
            new={f.get('id'):dict(f.attrib) for f in a}
            if len(new)!=len(a) or any(new.get(k)!=v for k,v in old.items()):
                raise ValueError('Addition cannot replace existing font definitions')
            continue
        if a is not None and (b is None or ET.tostring(a)!=ET.tostring(b)):
            raise ValueError('Addition must use working-document '+table)
    extent=bounds(added if allow_page_expansion else page)
    boxes=[bounds(e) for e in added]
    def overlaps(a,b):
        return not (a.right+2<=b.left or b.right+2<=a.left or a.bottom+2<=b.top or b.bottom+2<=a.top)
    for i,box in enumerate(boxes):
        if not all(math.isfinite(x) for x in (box.left,box.top,box.right,box.bottom)) or box.width<0 or box.height<0:
            raise ValueError('Invalid supplied bounds')
        if box.left<extent.left or box.top<extent.top or box.right>extent.right or box.bottom>extent.bottom:
            raise ValueError('Addition exceeds page')
        if any(overlaps(box,bounds(e)) for e in page) or any(overlaps(box,b) for b in boxes[:i]):
            raise ValueError('Addition would overlap existing or supplied objects')
    for obj in added:
        box=bounds(obj)
        for e in obj.iter():
            if e.get('p'):
                values=list(map(float,e.get('p').split()))
                if len(values)!=2 or not all(math.isfinite(v) for v in values):raise ValueError('Invalid XY coordinate')
                x,y=values
                if not (box.left-.03<=x<=box.right+.03 and box.top-.03<=y<=box.bottom+.03):
                    raise ValueError('Object coordinate exceeds supplied bounds')
    result=copy.deepcopy(target);dest=result.find('page')
    if allow_page_expansion:
        for key in ('BoundingBox','WidthPages','HeightPages'):dest.set(key,added.get(key,'1'))
    if incoming.find('fonttable') is not None:
        if result.find('fonttable') is not None:result.remove(result.find('fonttable'))
        result.append(copy.deepcopy(incoming.find('fonttable')))
    for child in list(dest):dest.remove(child)
    ids=[int(e.get('id')) for e in target.iter() if e.get('id')]
    counter=max(ids,default=0)+1
    mapping={}
    for e in added.iter():
        if e is added:continue
        if e.get('id'):
            mapping[e.get('id')]=str(counter);counter+=1
    for child in added:
        child=copy.deepcopy(child)
        for e in child.iter():
            for key in ('id','B','E'):
                if e.get(key) in mapping:e.set(key,mapping[e.get(key)])
            if e.get('CrossingBonds'):
                e.set('CrossingBonds',' '.join(mapping[v] for v in e.get('CrossingBonds').split()))
        dest.append(child)
    return ET.tostring(result,encoding='unicode')


class AddinChannel:
    MAX_BYTES=10_000_000

    def __init__(self,secret=None,port=0):
        self.secret=secret or secrets.token_urlsafe(32)
        self._lock=threading.Lock();self._event=threading.Event()
        self._job=None;self._claimed=False;self._result=None;self._poisoned=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def authorized(self):
                return (self.headers.get('Host')==owner.address
                        and self.headers.get('Origin') in (None,'null','file://')
                        and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.secret))
            def reply(self,status,value):
                body=json.dumps(value).encode();self.send_response(status)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Cache-Control','no-store')
                if self.headers.get('Origin') in ('null','file://'):
                    self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
                self.end_headers();self.wfile.write(body)
            def do_OPTIONS(self):
                if self.headers.get('Host')!=owner.address or self.headers.get('Origin') not in ('null','file://'):
                    return self.reply(403,{})
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
                self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
                self.send_header('Access-Control-Allow-Methods','GET, POST')
                self.end_headers()
            def do_GET(self):
                if not self.authorized():return self.reply(403,{})
                if self.path!='/job':return self.reply(404,{})
                with owner._lock:
                    job={}
                    if owner._job is not None and not owner._claimed and not owner._poisoned:
                        job=owner._job;owner._claimed=True
                self.reply(200,job)
            def do_POST(self):
                if not self.authorized():return self.reply(403,{})
                if self.path!='/result':return self.reply(404,{})
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=owner.MAX_BYTES:raise ValueError()
                    if self.headers.get('Content-Type')!='application/json':raise ValueError()
                    value=json.loads(self.rfile.read(size))
                    if not isinstance(value,dict):raise ValueError()
                except (ValueError,UnicodeError):return self.reply(400,{})
                with owner._lock:
                    if (owner._poisoned or not owner._claimed or owner._job is None or
                            value.get('id')!=owner._job['id'] or owner._result is not None):
                        return self.reply(409,{})
                    owner._result=value;owner._event.set()
                self.reply(200,{'ok':True})
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads=True
        self.address='127.0.0.1:'+str(self.server.server_port)
        self.url='http://'+self.address
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def request(self,operation,*,timeout=20,**data):
        if operation not in ('read','append','close') or set(data)-{'expected','cdxml'}:
            raise ValueError('Unsupported add-in operation')
        if operation=='append' and (not data.get('expected') or not data.get('cdxml')):
            raise ValueError('Append requires an expected snapshot and CDXML')
        if operation!='append' and data:raise ValueError('Unexpected operation arguments')
        with self._lock:
            if self._poisoned:raise RuntimeError('Native state uncertain; inspect before reconnecting')
            if self._job is not None:raise RuntimeError('Add-in request already in progress')
            self._event.clear();self._result=None;self._claimed=False
            self._job={'id':secrets.token_hex(16),'operation':operation,**data}
        if not self._event.wait(timeout):
            with self._lock:self._poisoned=True;self._job=None
            raise RuntimeError('Add-in response timed out; native state uncertain; no retry')
        with self._lock:
            result=self._result;self._job=None
        return result

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class AddinReadError(RuntimeError):
    """Safe, bounded failure context without document contents or native messages."""
    def __init__(self, code, stage):
        self.code = code if code in ('no_open_document', 'native_api_error',
            'invalid_read_response', 'invalid_cdxml', 'document_changed', 'invalid_document_id') else 'native_api_error'
        self.stage = stage if stage in ('api_version', 'active_document', 'document_cdxml',
            'cdxml_validation', 'document_identity', 'document_id') else 'document_read'
        message = 'Active document changed during read' if self.code == 'document_changed' else 'Add-in read failed: '+self.code
        super().__init__(message+' ('+self.stage+')')


def read_preserving_active(bridge, document_id):
    """Internal preservation read of an explicit document, restoring tab order.

    Public reads/writes keep their strict active-target contract. Never activate
    the application, touch selection, save an untitled original, or steal focus
    back if another actor changed the active document during this read.
    """
    with bridge.lock:
        backend=get_backend(bridge)
        # Opening the modeless connection can change ChemDraw's active tab.
        # Establish it first, then bind and restore the explicit read target.
        ready=getattr(backend,'_ready',None)
        if ready is not None:ready()
        active=bridge._run('active_document')
        switched=active!=document_id
        if switched:bridge._run('select_document',document_id,active)
        try:return backend.read(document_id)
        finally:
            if switched and bridge._run('active_document')==document_id:
                bridge._run('select_document',active,document_id)


def read_document(bridge, channel, document_id):
    try:did=bridge._id(document_id)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AddinReadError('invalid_document_id', 'document_id') from exc
    with bridge.lock:
        active=bridge._run('active_document')
        if active is None:raise AddinReadError('no_open_document', 'active_document')
        if active!=did:raise AddinReadError('document_changed', 'active_document')
        result=channel.request('read')
        if result.get('error'):
            raise AddinReadError(result.get('error_code'), result.get('error_stage'))
        if not isinstance(result.get('cdxml'), str):
            raise AddinReadError('invalid_read_response', 'document_cdxml')
        try:validate_cdxml(result['cdxml'])
        except (ValueError, TypeError) as exc:
            raise AddinReadError('invalid_cdxml', 'cdxml_validation') from exc
        state=bridge._run('active_document_state')
        if state is None or state[0]!=did:raise AddinReadError('document_changed', 'document_identity')
        doc=document_row(state)
        return {'document':doc,'cdxml':result['cdxml'],'selection_cdxml':result.get('selection'),
                'source_token':source_token(result['cdxml']),'api_version':result.get('version'),
                'transport':'desktop_addin','selection_changed':False}


def append_document(bridge,channel,document_id,cdxml,expected_source_token,*,allow_page_expansion=False):
    from .shared import verify_append
    from .batch import NativeUncertain
    with bridge.lock:
        initial=read_document(bridge,channel,document_id)
        if initial['source_token']!=expected_source_token:
            raise ValueError('Working document changed; read it again before appending')
        before=initial['cdxml'];payload=prepare_payload(before,cdxml,allow_page_expansion=allow_page_expansion)
        backup=bridge._new_path('.cdxml','backups');backup.write_text(before)
        result=channel.request('append',expected=before,cdxml=payload)
        if result.get('error'):
            if result.get('write_attempted'):raise NativeUncertain('API append uncertain: '+result['error'])
            raise ValueError('API append refused before write: '+result['error'])
        try:
            after=result['cdxml']
            snapshot=bridge._new_path('.cdxml','backups');snapshot.write_text(after)
            if bridge._run('active_document')!=document_id:raise ValueError('Active document changed')
            checks=verify_append(before,after,payload,exact_coordinates=True,allow_page_expansion=allow_page_expansion)
            doc=next(d for d in bridge.documents()['documents'] if d['document_id']==document_id)
            if doc['file']!=initial['document']['file']:raise ValueError('Document file binding changed')
        except Exception as exc:
            raise NativeUncertain('API append occurred but verification failed; do not retry: '+str(exc)) from exc
        return {'status':'completed','document':doc,'checks':checks,'source_token':source_token(after),
                'before_snapshot':str(backup),'after_snapshot':str(snapshot),
                'transport':'desktop_addin','visual_review':'required',
                'note':'Same-document append at supplied coordinates. ChemDraw may autosave named documents.'}


def prepare_addin(channel,directory,*,install_assets=True):
    """Generate a private per-session package. Credentials never enter repository assets."""
    directory=Path(directory)
    if install_assets:directory.mkdir(parents=True,exist_ok=True)
    metadata={'name':'ChemDraw MCP Native API','description':'Local MCP desktop API bridge','version':'0.1',
              'menuItemText':'ChemDraw MCP Native API','minimumAPIVersion':'1.6','url':'main.html',
              'isModalDialog':False,'canBeUninstalled':True}
    script=Path(__file__).with_name('addin_client.js').read_text()
    config=json.dumps({'url':channel.url,'secret':channel.secret})
    html=('<!doctype html><meta charset="utf-8"><title>ChemDraw MCP</title>'
          '<style>body{margin:10px;background:#29252f;color:#eee9e5;font:12px -apple-system,sans-serif}'
          'p{margin:0;line-height:1.4}p:before{content:"";display:inline-block;width:6px;height:6px;'
          'border-radius:50%;background:#e8a9ca;margin-right:8px}</style>'
          '<p id="status" role="status">Waiting for local MCP</p><script>const config='+config+';\n'+script+'</script>')
    for name,text in [('main.html',html),('chemdraw-addin-metadata.json',json.dumps(metadata))]:
        if not install_assets:continue
        path=directory/name
        if path.is_symlink():raise ValueError('Refusing symlinked add-in asset')
        # Assets belong to this installed bridge; refresh the local session endpoint.
        with open(path,'w',opener=lambda p,flags: os.open(p,flags,0o600)) as f:f.write(text)
        path.chmod(0o600)
    # The source ZIP must survive the installer's replacement of its destination.
    staging=directory.with_name(directory.name+' Installer')
    if staging.is_symlink():raise ValueError('Refusing symlinked installer directory')
    staging.mkdir(parents=True,exist_ok=True,mode=0o700)
    package=staging/'ChemDraw MCP Native API.chemdrawaddin'
    if package.is_symlink():raise ValueError('Refusing symlinked package')
    import tempfile
    fd,temporary=tempfile.mkstemp(prefix='.addin-',dir=staging)
    try:
        with os.fdopen(fd,'wb') as handle:
            with zipfile.ZipFile(handle,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('main.html',html);z.writestr('chemdraw-addin-metadata.json',json.dumps(metadata))
        with zipfile.ZipFile(temporary) as z:
            if z.testzip() is not None:raise ValueError('Generated add-in ZIP check failed')
        os.replace(temporary,package)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    package.chmod(0o600)
    return package


def installed_addin_directory(directory):
    """Locate our old filename-suffixed installs without adopting another key."""
    directory = Path(directory)
    if all((directory/name).is_file() for name in ('main.html', 'chemdraw-addin-metadata.json')):
        return directory
    connection = directory.with_name(directory.name + '.connection.json')
    if not connection.is_file() or connection.is_symlink(): return directory
    config = json.loads(connection.read_text())
    expected_url = 'http://127.0.0.1:' + str(config['port'])
    matches = []
    for candidate in directory.parent.iterdir():
        if not re.fullmatch(re.escape(directory.name) + r'-[0-9a-f]{8}', candidate.name): continue
        if candidate.is_symlink() or not candidate.is_dir(): continue
        metadata, html = candidate/'chemdraw-addin-metadata.json', candidate/'main.html'
        if any(p.is_symlink() or not p.is_file() for p in (metadata, html)): continue
        try:
            info = json.loads(metadata.read_text())
            if info.get('name') != 'ChemDraw MCP Native API' or info.get('url') != 'main.html': continue
            text = html.read_text()
            marker = 'const config='
            if marker not in text: continue
            embedded, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
            if (embedded.get('url') == expected_url and isinstance(embedded.get('secret'), str)
                    and hmac.compare_digest(embedded['secret'], config['secret'])):
                matches.append(candidate)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    if len(matches) > 1:
        raise ValueError('Multiple matching ChemDraw MCP add-ins are installed. Keep one entry in Add-in Manager.')
    return matches[0] if matches else directory


class DesktopAddin:
    """One persistent modeless add-in per MCP process, opened only on demand."""
    def __init__(self,bridge,directory=None,*,setup=False):
        self.bridge=bridge
        self.directory=Path(directory) if directory is not None else (
            Path.home()/'Library/Application Support/com.revvity.ChemDraw/Add-ins/ChemDraw MCP Native API')
        self.base_directory = self.directory
        self.directory.parent.mkdir(parents=True,exist_ok=True)
        connection=self.directory.with_name(self.directory.name+'.connection.json')
        if connection.is_symlink():raise ValueError('Refusing symlinked add-in credentials')
        if connection.exists():
            if connection.stat().st_mode & 0o077:raise ValueError('Add-in credentials must be private (mode 600)')
            config=json.loads(connection.read_text())
            if (set(config)!={'secret','port'} or not isinstance(config['secret'],str) or
                    len(config['secret'])<40 or type(config['port']) is not int or not 1024<=config['port']<=65535):
                raise ValueError('Invalid local add-in credentials')
            self.channel=AddinChannel(**config)
        else:
            self.channel=AddinChannel()
            try:
                with open(connection,'x',opener=lambda p,flags:os.open(p,flags,0o600)) as f:
                    json.dump({'secret':self.channel.secret,'port':self.channel.server.server_port},f)
            except Exception:
                self.channel.close();raise
        self.opened=False;self.closed=False
        try:
            self.directory = installed_addin_directory(self.base_directory)
            existing=all((self.directory/name).is_file() for name in ('main.html','chemdraw-addin-metadata.json'))
            self.package=prepare_addin(self.channel,self.directory,install_assets=not setup or existing)
        except Exception:
            self.channel.close();raise

    def connect(self):
        with self.bridge.lock:
            if self.opened:return {'status':'connected','transport':'desktop_addin'}
            self.directory = installed_addin_directory(self.base_directory)
            if not self.bridge._run('addin_available',str(self.directory)):
                return {'status':'needs_setup','code':'addin_command_unavailable','package':str(self.package),
                        'message':'Local add-in files are present, but ChemDraw has not exposed the add-in command. This does not establish that the add-in is uninstalled.',
                        'next_action':'Check Add-in Manager for an enabled entry. In Preferences > Directories, ensure the ChemDraw Items search paths include '+str(self.directory.parent.parent)+'. An empty search list prevents local add-ins loading after restart. If the entry is absent, install the supplied package through Add-in Manager > Add from file. Restart ChemDraw after correcting its search path, preserving any unsaved work.',
                        'note':'Private session package. Do not upload or share it.'}
            self.bridge._run('addin_open',str(self.directory));self.opened=True
            return {'status':'connected','transport':'desktop_addin',
                    'note':'Native API readiness is verified by the next document read.'}

    def _ready(self):
        status=self.connect()
        if status['status']!='connected':raise ValueError(status['message']+' '+status['next_action']+' Package: '+str(self.package))

    def read(self,document_id):
        self._ready();return read_document(self.bridge,self.channel,document_id)

    def append(self,document_id,cdxml,expected_source_token,*,allow_page_expansion=False):
        self._ready();return append_document(self.bridge,self.channel,document_id,cdxml,expected_source_token,allow_page_expansion=allow_page_expansion)

    def close(self):
        if self.closed:return
        self.closed=True
        if self.opened:
            try:self.channel.request('close',timeout=.5)
            except RuntimeError:pass
        self.channel.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def get_backend(bridge,*,setup=False):
    """Share one authenticated connection across ordinary and explicit API tools."""
    import atexit
    backend=getattr(bridge,'_desktop_addin',None)
    if backend is None or backend.closed:
        backend=DesktopAddin(bridge,setup=True) if setup else DesktopAddin(bridge)
        bridge._desktop_addin=backend
        atexit.register(backend.close)
    return backend
