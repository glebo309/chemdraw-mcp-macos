import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest


def test_bridge_lock_shared_across_workspaces(tmp_path):
    from chemdraw_macos.core import Bridge
    a=Bridge(workspace=tmp_path/'a');b=Bridge(workspace=tmp_path/'b')
    assert a.lock is b.lock


def test_reentrant_lock_and_exception_release(tmp_path):
    from chemdraw_macos.native_lock import NativeSessionLock
    lock=NativeSessionLock(tmp_path/'native.lock',timeout=.1)
    with pytest.raises(ValueError):
        with lock:
            with lock: raise ValueError('test')
    with lock: pass
    assert (tmp_path/'native.lock').exists()  # Never unlink a coordination inode.


def test_another_process_busy_then_released_without_stale_lock(tmp_path):
    from chemdraw_macos.native_lock import NativeSessionLock, NativeBusy
    path=tmp_path/'native.lock'
    script='from chemdraw_macos.native_lock import NativeSessionLock; import sys\nwith NativeSessionLock(sys.argv[1]):\n print("held",flush=True)\n sys.stdin.readline()\n'
    child=subprocess.Popen([sys.executable,'-c',script,str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='held'
        with pytest.raises(NativeBusy,match='No native operation'):
            with NativeSessionLock(path,timeout=.05): pytest.fail('Concurrent entry')
        child.stdin.write('\n');child.stdin.flush();assert child.wait(timeout=3)==0
        with NativeSessionLock(path,timeout=.1): pass
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=3)
        child.stdin.close();child.stdout.close()


def test_process_exit_releases_kernel_lock(tmp_path):
    from chemdraw_macos.native_lock import NativeSessionLock
    path=tmp_path/'native.lock'
    script='from chemdraw_macos.native_lock import NativeSessionLock; import os,sys\nwith NativeSessionLock(sys.argv[1]): os._exit(0)'
    subprocess.run([sys.executable,'-c',script,str(path)],check=True,timeout=3)
    with NativeSessionLock(path,timeout=.1): pass


def test_thread_timeout_and_no_reentrant_leak(tmp_path):
    from chemdraw_macos.native_lock import NativeSessionLock, NativeBusy
    lock=NativeSessionLock(tmp_path/'native.lock',timeout=.05);results=[]
    def attempt():
        try:
            with lock:results.append('entered')
        except NativeBusy:results.append('busy')
    with lock:
        thread=threading.Thread(target=attempt);thread.start();thread.join(timeout=2)
        assert not thread.is_alive() and results==['busy']
    with lock: pass


def test_symlink_lock_rejected_without_touching_target(tmp_path):
    from chemdraw_macos.native_lock import NativeSessionLock
    target=tmp_path/'target';target.write_text('keep')
    path=tmp_path/'lock';path.symlink_to(target)
    with pytest.raises(OSError):
        with NativeSessionLock(path): pytest.fail('Symlink accepted')
    assert target.read_text()=='keep'


@pytest.mark.parametrize('timeout',[-1,True,float('nan'),float('inf'),61])
def test_invalid_wait_bound_rejected(tmp_path,timeout):
    from chemdraw_macos.native_lock import NativeSessionLock
    with pytest.raises(ValueError):NativeSessionLock(tmp_path/'lock',timeout=timeout)


def test_contention_is_not_reported_as_uncertain_write():
    from chemdraw_macos.batch import _native
    from chemdraw_macos.native_lock import NativeBusy
    def busy():raise NativeBusy('No native operation was dispatched')
    with pytest.raises(NativeBusy):_native(busy)


@pytest.mark.parametrize('operation',['create','import_file','close'])
def test_whole_low_level_transaction_holds_gate(tmp_path,monkeypatch,operation):
    from chemdraw_macos.core import Bridge
    class Gate:
        active=False
        def __enter__(self):self.active=True
        def __exit__(self,*args):self.active=False
    b=Bridge(workspace=tmp_path);b.lock=Gate()
    def opened(path):
        assert b.lock.active
        return {'document_id':123}
    monkeypatch.setattr(b,'_open_working',opened)
    monkeypatch.setattr(b,'export',lambda *a,**k: None)
    def run(*args):assert b.lock.active
    monkeypatch.setattr(b,'_run',run)
    if operation=='create':b.create('<CDXML/>')
    elif operation=='import_file':
        p=tmp_path/'source.cdxml';p.write_text('<CDXML/>');b.import_file(p)
    else:b.managed.add(123);b.close(123)


def test_busy_gate_dispatches_no_native_command(tmp_path,monkeypatch):
    from chemdraw_macos.core import Bridge
    from chemdraw_macos.native_lock import NativeSessionLock, NativeBusy
    b=Bridge(app_path=tmp_path,workspace=tmp_path/'work')
    b.lock=NativeSessionLock(tmp_path/'gate',timeout=.02)
    def forbidden(*a,**k):pytest.fail('Native subprocess dispatched while busy')
    monkeypatch.setattr(subprocess,'run',forbidden)
    with NativeSessionLock(tmp_path/'gate'):
        with pytest.raises(NativeBusy):b.documents()


def test_doctor_distinguishes_busy_from_installation_problem(monkeypatch):
    from chemdraw_macos import diagnostics
    from chemdraw_macos.native_lock import NativeBusy
    def busy(self):raise NativeBusy('No native operation was dispatched')
    monkeypatch.setattr(diagnostics.Bridge,'documents',busy)
    result=diagnostics.doctor()
    assert result['status']=='busy'
    assert 'permission' not in result['help'].lower()


@pytest.mark.parametrize('module,name',[
    ('editing','edit_file'),('annotations','annotate_file'),('symbols','symbols_file'),
    ('scope_decoration','decorate_scope_file'),('workflow','analyze_document'),
    ('symbols','inspect_symbols_document'),('annotations','inspect_annotations_document'),
    ('route_suggestions','annotate_selected_route_document'),('route_suggestions','annotate_selected_route_file'),
])
def test_file_and_inspection_transactions_reject_busy_before_work(module,name):
    import importlib,inspect
    from chemdraw_macos.native_lock import NativeBusy
    class BusyGate:
        def __enter__(self):raise NativeBusy('No native operation was dispatched')
        def __exit__(self,*args):pass
    class B:lock=BusyGate()
    fn=getattr(importlib.import_module('chemdraw_macos.'+module),name)
    args={p.name:None for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty}
    args['bridge']=B()
    with pytest.raises(NativeBusy):fn(**args)


def test_cli_holds_native_gate_through_dispatch(tmp_path,monkeypatch):
    from chemdraw_macos import cli
    class Gate:
        active=False
        def __enter__(self):self.active=True
        def __exit__(self,*args):self.active=False
    gate=Gate()
    class B:lock=gate
    monkeypatch.setattr(cli,'Bridge',B)
    def draw(*a,**kw):
        assert gate.active
        return {}
    monkeypatch.setattr(cli,'draw_structures',draw)
    p=tmp_path/'request.json';p.write_text('{"structures":[]}')
    assert cli.main(['draw','--manifest',str(p),'--output',str(tmp_path/'out')])==0
    assert not gate.active
