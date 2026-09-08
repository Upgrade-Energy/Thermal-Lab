"""OS-released local service lock; permits safe descriptor replacement after a crash."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def service_lease(descriptor):
    path=Path(descriptor).with_suffix('.lock');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        path.chmod(0o600)
        if path.stat().st_size==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)
