"""Liveness signal for a Photoshop worker; it does not claim task progress."""
from contextlib import contextmanager
from pathlib import Path
import threading


@contextmanager
def heartbeat(path, interval=5.0):
    """Refresh a worker-local file while dispatch runs, including long native calls."""
    path = Path(path)
    stopped = threading.Event()

    def signal():
        try:
            path.touch()
        except OSError:
            # The request can still complete; the bridge falls back to its
            # ordinary silence timeout when the signal cannot be written.
            pass

    def refresh():
        while not stopped.wait(interval):
            signal()

    signal()
    thread = threading.Thread(target=refresh, name='manga-worker-heartbeat', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)
