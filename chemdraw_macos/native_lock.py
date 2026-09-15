"""Cooperative, per-user native session gate shared by CLI and MCP processes."""
import fcntl
import math
import os
from pathlib import Path
import stat
import threading
import time
from contextlib import nullcontext
from functools import wraps


class NativeBusy(RuntimeError):
    """The gate was unavailable; no native operation was dispatched by this call."""


class NativeSessionLock:
    def __init__(self,path,timeout=2):
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<=timeout<=60:
            raise ValueError('Native lock wait must be finite and between 0 and 60 seconds')
        self.path=Path(path);self.timeout=timeout
        self._thread=threading.RLock();self._depth=0;self._fd=None;self._pid=os.getpid()

    def _busy(self):
        return NativeBusy('ChemDraw is busy in another cooperating client. No native operation was dispatched by this call; try again after that workflow finishes.')

    def __enter__(self):
        if os.getpid()!=self._pid:raise RuntimeError('Recreate the native lock after forking')
        deadline=time.monotonic()+self.timeout
        if not self._thread.acquire(timeout=self.timeout):raise self._busy()
        try:
            if self._depth:
                self._depth+=1
                return self
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            self._fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
            info=os.fstat(self._fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1:
                raise OSError('Native lock must be an owned regular file with one link')
            while True:
                try:
                    fcntl.flock(self._fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise self._busy()
                    time.sleep(min(.025,remaining))
            self._depth=1
            return self
        except BaseException:
            if self._fd is not None:os.close(self._fd);self._fd=None
            self._thread.release()
            raise

    def __exit__(self,*exc):
        try:
            self._depth-=1
            if not self._depth:
                try:fcntl.flock(self._fd,fcntl.LOCK_UN)
                finally:os.close(self._fd);self._fd=None
        finally:self._thread.release()


_shared=None
_guard=threading.Lock()


def shared_native_lock():
    global _shared
    with _guard:
        if _shared is None:
            _shared=NativeSessionLock(Path.home()/'Library/Caches/chemdraw-mcp-macos/native.lock')
        return _shared


def _after_fork():
    global _shared,_guard
    if _shared is not None and _shared._fd is not None:os.close(_shared._fd)
    _shared=None;_guard=threading.Lock()


os.register_at_fork(after_in_child=_after_fork)


def native_transaction(fn):
    """Keep snapshot/import, inner workflow and final cleanup in one session."""
    @wraps(fn)
    def locked(bridge,*args,**kwargs):
        with getattr(bridge,'lock',nullcontext()):return fn(bridge,*args,**kwargs)
    return locked
