"""Serialize bridge requests that read or mutate the same translation project.

The lock belongs to the worker process, so the OS releases it even after a
crash. Never remove the lock file: unlinking it can create two independent locks.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import time


@contextmanager
def project_lock(project, cancel=None, poll=0.2):
    path = Path(project).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + '.lock')
    with lock_path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'\0')
                stream.flush()
            def acquire():
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    return True
                except OSError:
                    return False
            def release():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except BlockingIOError:
                    return False
            def release():
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        while True:
            if cancel and Path(cancel).exists():
                raise RuntimeError('Đã hủy trong khi chờ worker trước kết thúc.')
            if acquire():
                break
            time.sleep(poll)
        try:
            yield
        finally:
            release()
