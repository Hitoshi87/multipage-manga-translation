import multiprocessing as mp
import queue
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from manga_ai.project_lock import project_lock


def locked_worker(project, messages, release):
    with project_lock(project):
        messages.put('locked')
        release.wait(10)


def waiting_worker(project, cancel, messages):
    try:
        with project_lock(project, cancel, poll=.02):
            messages.put('acquired')
    except RuntimeError:
        messages.put('cancelled')


def scoped_worker(scope, label, messages, release):
    from manga_ai import cli
    def perform(request):
        messages.put(label)
        release.wait(10)
    cli._dispatch = perform
    cli.dispatch({'operation': 'scan', 'worker_scope': scope})


class ProjectLockTest(unittest.TestCase):
    def test_symlinked_project_uses_same_worker_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project.json'
            project.write_text('{}', encoding='utf8')
            alias = Path(tmp) / 'alias.json'
            try:
                alias.symlink_to(project)
            except (OSError, NotImplementedError):
                self.skipTest('Symlinks unavailable')
            messages, release1, release2 = mp.Queue(), mp.Event(), mp.Event()
            first = mp.Process(target=scoped_worker, args=(str(project), 'first', messages, release1))
            second = mp.Process(target=scoped_worker, args=(str(alias), 'second', messages, release2))
            first.start()
            try:
                self.assertEqual(messages.get(timeout=5), 'first')
                second.start()
                with self.assertRaises(queue.Empty):
                    messages.get(timeout=.2)
                release1.set()
                self.assertEqual(messages.get(timeout=5), 'second')
            finally:
                release1.set(); release2.set()
                first.join(5)
                if second.pid:
                    second.join(5)

    def test_scans_share_supervised_worker_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = str(Path(tmp) / 'job.json')
            messages, release1, release2 = mp.Queue(), mp.Event(), mp.Event()
            first = mp.Process(target=scoped_worker, args=(scope, 'first', messages, release1))
            second = mp.Process(target=scoped_worker, args=(scope, 'second', messages, release2))
            first.start()
            try:
                self.assertEqual(messages.get(timeout=5), 'first')
                second.start()
                with self.assertRaises(queue.Empty):
                    messages.get(timeout=.2)
                release1.set()
                self.assertEqual(messages.get(timeout=5), 'second')
            finally:
                release1.set(); release2.set()
                first.join(5)
                if second.pid:
                    second.join(5)

    def test_wait_cancel_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = str(Path(tmp) / 'project.json')
            cancel = Path(tmp) / 'cancel'
            messages, release = mp.Queue(), mp.Event()
            first = mp.Process(target=locked_worker, args=(project, messages, release))
            first.start()
            try:
                self.assertEqual(messages.get(timeout=5), 'locked')
                second = mp.Process(target=waiting_worker, args=(project, str(cancel), messages))
                second.start()
                try:
                    with self.assertRaises(queue.Empty):
                        messages.get(timeout=.2)
                    cancel.touch()
                    self.assertEqual(messages.get(timeout=5), 'cancelled')
                finally:
                    second.join(5)
                release.set()
                first.join(5)
                cancel.unlink()
                with project_lock(project, str(cancel), poll=.02):
                    pass
            finally:
                release.set()
                if first.is_alive():
                    first.terminate()
                first.join(5)

    def test_lock_is_released_when_worker_is_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = str(Path(tmp) / 'project.json')
            code = ('import sys,time; from manga_ai.project_lock import project_lock; '
                    'lock=project_lock(sys.argv[1]); lock.__enter__(); '
                    'print("ready",flush=True); time.sleep(60)')
            worker = subprocess.Popen([sys.executable, '-c', code, project], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(worker.stdout.readline().strip(), 'ready')
                worker.kill()
                worker.wait(timeout=5)
                with project_lock(project):
                    pass
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait(timeout=5)
                worker.stdout.close()


if __name__ == '__main__':
    unittest.main()
