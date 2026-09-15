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
