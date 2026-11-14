import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from manga_ai.io import read_json, write_json
from manga_ai import photoshop_supervisor as supervisor


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        memory = patch.object(supervisor, 'system_free_percent', return_value=100)
        memory.start()
        self.addCleanup(memory.stop)

    def make_job(self, directory):
        root = Path(directory)
        script = root / 'Photoshop_Typeset.jsx'
        script.write_text('// test', encoding='utf8')
        job = root / 'job.json'
        write_json(job, {'schema': 1, 'script': str(script)})
        (root / 'ready').touch()
        return job

    def test_auth_wait_retries_only_after_key_change_or_manual_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = {}
            status = root / 'status.json'
            progress = root / 'progress.json'
            write_json(progress, {'message': 'Trang 143'})
            with patch.object(supervisor, 'credential_version', return_value=('file', (2,))), \
                 patch.object(supervisor, 'notify_user'):
                self.assertTrue(supervisor.wait_for_auth_repair({'progress': str(progress)}, root, state, status, ('file', (1,)), sleep=lambda _: None))
            self.assertEqual(read_json(status)['state'], 'waiting_auth')
            self.assertEqual(read_json(progress)['state'], 'waiting_auth')
            self.assertNotIn('143', read_json(progress)['message'])
            (root / 'resume').touch()
            with patch.object(supervisor, 'notify_user'):
                self.assertTrue(supervisor.wait_for_auth_repair({}, root, state, status, ('missing', None), sleep=lambda _: None))
            self.assertFalse((root / 'resume').exists())
            (root / 'cancel').touch()
            with patch.object(supervisor, 'notify_user'):
                self.assertFalse(supervisor.wait_for_auth_repair({}, root, state, status, ('missing', None), sleep=lambda _: None))

    def test_credential_version_respects_environment_precedence(self):
        from manga_ai.translation import providers
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(providers, 'key_file', return_value=Path(tmp) / 'key'), \
             patch.dict(os.environ, {'TEST_SUPERVISOR_KEY': ''}):
            self.assertEqual(supervisor.credential_version('TEST_SUPERVISOR_KEY'), ('missing', None))
            (Path(tmp) / 'key').write_text('secret', encoding='utf8')
            self.assertEqual(supervisor.credential_version('TEST_SUPERVISOR_KEY')[0], 'file')
            os.environ['TEST_SUPERVISOR_KEY'] = 'secret'
            self.assertEqual(supervisor.credential_version('TEST_SUPERVISOR_KEY'), ('environment', None))

    def test_auth_failure_waits_then_retries_same_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            attempts = []
            def attempt(app, wrapper, **kwargs):
                attempts.append(Path(wrapper).read_text(encoding='utf8'))
                response = {'state': 'failed', 'message': 'Đã dừng dịch: API HTTP 401'} if len(attempts) == 1 else {'state': 'complete'}
                write_json(Path(wrapper).with_suffix('.json'), response)
                return SimpleNamespace(stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'wait_for_auth_repair', return_value=True) as wait:
                result = supervisor.run_job(job, sleep=lambda _: None)
            self.assertEqual(result['state'], 'complete')
            self.assertEqual(len(attempts), 2)
            self.assertTrue(all('MTA_SUPERVISED_CURSOR=0' in attempt for attempt in attempts))
            wait.assert_called_once()

    def test_upstream_outage_cools_down_then_resumes_same_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            attempts = []
            def attempt(app, wrapper, **kwargs):
                attempts.append(Path(wrapper).read_text())
                write_json(Path(wrapper).with_suffix('.json'),
                           {'state': 'failed', 'message': 'API upstream temporarily unavailable'} if len(attempts)<3 else {'state': 'complete'})
                return SimpleNamespace(stderr='')
            delays = []
            def sleep(seconds):
                delays.append(seconds)
                self.assertEqual(read_json(job.parent/'supervisor_status.json')['state'], 'waiting_api')
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt):
                result = supervisor.run_job(job, sleep=sleep)
            self.assertEqual(result['state'], 'complete')
            self.assertEqual(sum(delays), 90)
            self.assertTrue(all('MTA_SUPERVISED_CURSOR=0' in a for a in attempts))

    def test_crash_retries_same_cursor_then_recycles_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            attempts = []
            def attempt(app, wrapper, **kwargs):
                text = Path(wrapper).read_text(encoding='utf8')
                attempts.append(text)
                if len(attempts) == 2:
                    write_json(Path(wrapper).with_suffix('.json'), {'state': 'recycle', 'next_cursor': 4})
                elif len(attempts) == 3:
                    write_json(Path(wrapper).with_suffix('.json'), {'state': 'complete'})
                return SimpleNamespace(returncode=1, stderr='crash')
            # crashed attempt is dead; recycled attempt is still alive, then exits.
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'process_alive', side_effect=[False, True, False, False]), \
                 patch.object(supervisor, 'start_photoshop', side_effect=[12, 13]) as start, \
                 patch.object(supervisor, 'quit_empty') as quit_empty:
                result = supervisor.run_job(job, sleep=lambda _: None)
            self.assertEqual(result['state'], 'complete')
            self.assertEqual(result['crashes'], 0, 'a completed batch resets the consecutive crash counter')
            self.assertEqual(result['total_crashes'], 1, 'recovered crashes remain visible in the status')
            self.assertIn('MTA_SUPERVISED_CURSOR=0', attempts[0])
            self.assertIn('MTA_SUPERVISED_CURSOR=0', attempts[1])
            self.assertIn('MTA_SUPERVISED_CURSOR=4', attempts[2])
            self.assertIn('MTA_SUPERVISED_BATCH_SIZE=4', attempts[0])
            self.assertIn('MTA_SUPERVISED_BATCH_SIZE=1', attempts[1])
            self.assertEqual(start.call_count, 2)
            quit_empty.assert_called_once_with('/Photoshop.app')
            self.assertEqual(read_json(job.parent / 'supervisor_status.json')['state'], 'complete')

    def test_live_photoshop_without_response_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', return_value=SimpleNamespace(stderr='error')), \
                 patch.object(supervisor, 'process_alive', return_value=True), \
                 patch.object(supervisor, 'start_photoshop') as start:
                with self.assertRaisesRegex(RuntimeError, 'còn chạy'):
                    supervisor.run_job(job, sleep=lambda _: None)
                start.assert_not_called()

    def test_transient_minus_600_retries_only_after_safe_barrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            wrappers = []
            def attempt(app, wrapper, **kwargs):
                wrappers.append(Path(wrapper))
                if len(wrappers)==1:
                    return SimpleNamespace(stderr='execution error: application not running. (-600)')
                write_json(Path(wrapper).with_suffix('.json'), {'state':'complete'})
                return SimpleNamespace(stderr='')
            with patch.object(supervisor,'select_process',return_value=(11,'/Photoshop.app')), \
                 patch.object(supervisor,'launch_attempt',side_effect=attempt), \
                 patch.object(supervisor,'process_alive',return_value=True), \
                 patch.object(supervisor,'javascript_barrier',side_effect=[False,True]) as barrier, \
                 patch.object(supervisor,'start_photoshop') as restart:
                result=supervisor.run_job(job,sleep=lambda _:None)
            self.assertEqual(result['state'],'complete')
            self.assertEqual(result['cursor'],0)
            self.assertEqual(len(wrappers),2)
            self.assertTrue(wrappers[0].with_suffix('.revoked').exists())
            self.assertEqual(barrier.call_count,2)
            restart.assert_not_called()

    def test_minus_600_never_retries_if_script_started_or_barrier_fails(self):
        for mode in ('started','barrier_failure','starts_during_barrier'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                job=self.make_job(tmp)
                def attempt(app,wrapper,**kwargs):
                    if mode=='started':kwargs['started'].touch()
                    return SimpleNamespace(stderr='application not running (-600)')
                def barrier(app):
                    if mode=='starts_during_barrier':
                        next(Path(tmp).glob('attempt_*.jsx')).with_suffix('.started').touch()
                    return mode!='barrier_failure'
                with patch.object(supervisor,'select_process',return_value=(11,'/Photoshop.app')), \
                     patch.object(supervisor,'launch_attempt',side_effect=attempt) as launch, \
                     patch.object(supervisor,'process_alive',return_value=True), \
                     patch.object(supervisor,'javascript_barrier',side_effect=barrier), \
                     patch.object(supervisor,'start_photoshop') as restart:
                    with self.assertRaises(RuntimeError):supervisor.run_job(job,sleep=lambda _:None)
                self.assertEqual(launch.call_count,1)
                restart.assert_not_called()

    def test_crash_loop_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', return_value=SimpleNamespace(stderr='crash')) as attempt, \
                 patch.object(supervisor, 'process_alive', return_value=False), \
                 patch.object(supervisor, 'start_photoshop', return_value=12):
                with self.assertRaisesRegex(RuntimeError, 'nhiều lần'):
                    supervisor.run_job(job, sleep=lambda _: None, max_crashes=2)
                self.assertEqual(attempt.call_count, 3)

    def test_high_rss_shrinks_batches_then_recovers_gradually(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            batches, cursors = [], [4, 5, 6, 8, 10]
            def attempt(app, wrapper, **kwargs):
                text = Path(wrapper).read_text()
                import re
                batches.append(int(re.search(r'MTA_SUPERVISED_BATCH_SIZE=(\d+)', text).group(1)))
                if len(batches) <= len(cursors):
                    write_json(Path(wrapper).with_suffix('.json'), {'state':'recycle', 'next_cursor':cursors[len(batches)-1]})
                else:
                    write_json(Path(wrapper).with_suffix('.json'), {'state':'complete'})
                return SimpleNamespace(returncode=0, stderr='', peak_rss_kib=1200 if len(batches)==1 else 700)
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'physical_memory_limit_kib', return_value=1000), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'process_alive', return_value=False), \
                 patch.object(supervisor, 'start_photoshop', return_value=12):
                result = supervisor.run_job(job, sleep=lambda _:None)
            self.assertEqual(batches, [4, 1, 1, 2, 2, 4])
            self.assertEqual(result['peak_photoshop_rss_kib'], 1200)
            self.assertEqual(result['memory_limit_kib'], 1000)

    def test_system_pressure_shrinks_next_batch_even_when_photoshop_rss_is_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            sizes=[]
            def attempt(app, wrapper, **kwargs):
                import re
                sizes.append(int(re.search(r'MTA_SUPERVISED_BATCH_SIZE=(\d+)',Path(wrapper).read_text()).group(1)))
                response={'state':'recycle','next_cursor':4} if len(sizes)==1 else {'state':'complete'}
                write_json(Path(wrapper).with_suffix('.json'),response)
                return SimpleNamespace(returncode=0,stderr='',peak_rss_kib=100,
                                       min_system_free_percent=15 if len(sizes)==1 else 40)
            with patch.object(supervisor,'select_process',return_value=(11,'/Photoshop.app')), \
                 patch.object(supervisor,'physical_memory_limit_kib',return_value=1000), \
                 patch.object(supervisor,'launch_attempt',side_effect=attempt), \
                 patch.object(supervisor,'process_alive',return_value=False), \
                 patch.object(supervisor,'start_photoshop',return_value=12):
                result=supervisor.run_job(job,sleep=lambda _:None)
            self.assertEqual(sizes,[4,1])
            self.assertEqual(result['state'],'complete')
            self.assertEqual(result['min_system_free_percent'],15)
            self.assertEqual(result['last_min_system_free_percent'],40)

    def test_cancellation_before_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            (job.parent / 'cancel').touch()
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt') as attempt:
                self.assertEqual(supervisor.run_job(job)['state'], 'cancelled')
                attempt.assert_not_called()

    def test_waits_for_system_memory_before_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def attempt(app, wrapper, **kwargs):
                write_json(Path(wrapper).with_suffix('.json'), {'state':'complete'})
                return SimpleNamespace(returncode=0, stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11,'/Photoshop.app')), \
                 patch.object(supervisor, 'system_free_percent', side_effect=[18,19,35]), \
                 patch.object(supervisor, 'notify_user') as notify, \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt) as launch:
                result = supervisor.run_job(job, sleep=lambda _:None)
            self.assertEqual(result['state'],'complete')
            self.assertEqual(result['system_free_percent'],35)
            notify.assert_called_once_with('waiting_memory')
            launch.assert_called_once()

    def test_cancellation_while_waiting_for_memory_never_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def cancel_wait(_):
                (job.parent/'cancel').touch()
            with patch.object(supervisor, 'select_process', return_value=(11,'/Photoshop.app')), \
                 patch.object(supervisor, 'system_free_percent', return_value=10), \
                 patch.object(supervisor, 'notify_user'), \
                 patch.object(supervisor, 'launch_attempt') as launch:
                result = supervisor.run_job(job, sleep=cancel_wait)
            self.assertEqual(result['state'],'cancelled')
            launch.assert_not_called()

    def test_unfinished_pages_are_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def attempt(app, wrapper, **kwargs):
                write_json(Path(wrapper).with_suffix('.json'),
                           {'state':'needs_attention','message':'Trang chưa hoàn tất',
                            'pending_pages':[{'page':'088.jpeg','reason':'output_invalid'}]})
                return SimpleNamespace(returncode=0,stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11,'/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'start_photoshop') as start:
                result=supervisor.run_job(job)
            self.assertEqual(result['state'],'needs_attention')
            self.assertEqual(result['pending_pages'][0]['page'],'088.jpeg')
            start.assert_not_called()

    def test_attention_notification_mentions_unfinished_pages(self):
        with patch.object(supervisor.sys, 'platform', 'darwin'), \
             patch.object(supervisor, 'applescript') as notify:
            supervisor.notify_user('needs_attention')
        self.assertIn('chưa hoàn tất', notify.call_args.args[1])

    def test_cancel_while_recycling_does_not_reopen_photoshop(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def attempt(app, wrapper, **kwargs):
                write_json(Path(wrapper).with_suffix('.json'), {'state': 'recycle', 'next_cursor': 4})
                return SimpleNamespace(returncode=0, stderr='')
            def quit_empty(app):
                (job.parent / 'cancel').touch()
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'process_alive', side_effect=[True, False, False]), \
                 patch.object(supervisor, 'quit_empty', side_effect=quit_empty), \
                 patch.object(supervisor, 'start_photoshop') as start:
                result = supervisor.run_job(job, sleep=lambda _: None)
            self.assertEqual(result['state'], 'cancelled')
            self.assertEqual(result['cursor'], 4)
            start.assert_not_called()

    def test_cancel_after_start_marker_before_script_is_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def attempt(app, wrapper, **kwargs):
                kwargs['started'].touch()
                kwargs['cancel'].touch()
                return SimpleNamespace(returncode=0, stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt), \
                 patch.object(supervisor, 'start_photoshop') as start:
                result = supervisor.run_job(job)
            self.assertEqual(result['state'], 'cancelled')
            start.assert_not_called()

    def test_cancel_during_crash_backoff_does_not_reopen_photoshop(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def cancel_during_wait(_):
                (job.parent / 'cancel').touch()
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', return_value=SimpleNamespace(stderr='crash')), \
                 patch.object(supervisor, 'process_alive', return_value=False), \
                 patch.object(supervisor, 'start_photoshop') as start:
                result = supervisor.run_job(job, sleep=cancel_during_wait)
            self.assertEqual(result['state'], 'cancelled')
            start.assert_not_called()

    def test_worker_scope_is_stable_across_jobs_for_same_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = str(root / 'shared-project.json')
            wrappers = []
            def attempt(app, wrapper, **kwargs):
                wrappers.append(Path(wrapper).read_text())
                write_json(Path(wrapper).with_suffix('.json'), {'state': 'complete'})
                return SimpleNamespace(returncode=0, stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt):
                for name in ('one', 'two'):
                    directory = root / name
                    directory.mkdir()
                    job = self.make_job(directory)
                    data = read_json(job); data['project'] = project; write_json(job, data)
                    supervisor.run_job(job)
            self.assertEqual(len(wrappers), 2)
            for wrapper in wrappers:
                self.assertIn('MTA_SUPERVISED_SCOPE=' + json.dumps(project), wrapper)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the JSX wrapper test')
    def test_wrapper_cleans_globals_even_when_eval_throws(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(tmp)
            def attempt(app, wrapper, **kwargs):
                js = r'''
const vm=require('vm'),fs=require('fs'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
function File(path){this.path=path;this.exists=false;}
File.prototype.open=function(){return true};File.prototype.write=function(){};File.prototype.close=function(){};
const ctx={File,$:{global:{},evalFile(){throw Error('script failure')}}};
assert.throws(()=>vm.runInNewContext(source,ctx),/script failure/);
 for(const key of ['MTA_SUPERVISED_JOB','MTA_SUPERVISED_SCOPE','MTA_SUPERVISED_RESULT','MTA_SUPERVISED_CURSOR','MTA_SUPERVISED_BATCH_SIZE','MTA_SUPERVISED_PRESSURE'])assert.strictEqual(ctx.$.global[key],null);
let cancelled=false,called=false;
function CancelFile(path){this.path=path;Object.defineProperty(this,'exists',{get(){return /\/cancel$/.test(path)&&cancelled}})}
CancelFile.prototype.open=function(){return true};CancelFile.prototype.write=function(){};CancelFile.prototype.close=function(){cancelled=true};
const ctx2={File:CancelFile,$:{global:{},evalFile(){called=true}}};vm.runInNewContext(source,ctx2);
assert.strictEqual(called,false);assert.deepStrictEqual(ctx2.$.global,{});
let opened=false;
function RevokedFile(path){this.exists=/\.revoked$/.test(path)}
RevokedFile.prototype.open=function(){opened=true;return true};
const ctx3={File:RevokedFile,$:{global:{},evalFile(){throw Error('revoked event ran')}}};
vm.runInNewContext(source,ctx3);assert.strictEqual(opened,false);assert.deepStrictEqual(ctx3.$.global,{});
'''
                subprocess.run(['node', '-e', js, str(wrapper)], check=True)
                write_json(Path(wrapper).with_suffix('.json'), {'state': 'complete'})
                return SimpleNamespace(returncode=0, stderr='')
            with patch.object(supervisor, 'select_process', return_value=(11, '/Photoshop.app')), \
                 patch.object(supervisor, 'launch_attempt', side_effect=attempt):
                self.assertEqual(supervisor.run_job(job)['state'], 'complete')

    def test_startup_timeout_cancels_queued_apple_event(self):
        class PendingProcess:
            returncode = None
            def poll(self):
                return self.returncode
            def terminate(self):
                self.returncode = -15
            def communicate(self, timeout=None):
                return '', ''
        with tempfile.TemporaryDirectory() as tmp:
            started, cancel = Path(tmp) / 'started', Path(tmp) / 'cancel'
            with patch.object(supervisor.subprocess, 'Popen', return_value=PendingProcess()), \
                 patch.object(supervisor, 'process_alive', return_value=True), \
                 patch.object(supervisor, 'process_rss_kib', return_value=0):
                result = supervisor.launch_attempt('/Photoshop.app', '/wrapper.jsx',
                                                   started=started, cancel=cancel, pid=11, startup_timeout=0)
            self.assertTrue(result.startup_timed_out)
            self.assertTrue(cancel.exists())

    def test_rss_threshold_signals_page_checkpoint(self):
        class RunningProcess:
            returncode = 0
            checks = 0
            def poll(self):
                self.checks += 1
                return None if self.checks == 1 else 0
            def communicate(self, timeout=None):
                return '', ''
        with tempfile.TemporaryDirectory() as tmp:
            started, cancel, pressure = (Path(tmp) / n for n in ('started', 'cancel', 'pressure'))
            started.touch()
            with patch.object(supervisor.subprocess, 'Popen', return_value=RunningProcess()), \
                 patch.object(supervisor, 'process_alive', return_value=True), \
                 patch.object(supervisor, 'process_rss_kib', return_value=1500), \
                 patch.object(supervisor.time, 'sleep'):
                result = supervisor.launch_attempt('/Photoshop.app', '/wrapper.jsx', started=started,
                                                   cancel=cancel, pid=11, pressure=pressure, memory_limit_kib=1000)
            self.assertTrue(pressure.exists())
            self.assertEqual(result.peak_rss_kib, 1500)

    def test_system_pressure_also_signals_checkpoint(self):
        class RunningProcess:
            returncode = 0
            checks = 0
            def poll(self):
                self.checks += 1
                return None if self.checks == 1 else 0
            def communicate(self, timeout=None):
                return '', ''
        with tempfile.TemporaryDirectory() as tmp:
            started, cancel, pressure = (Path(tmp)/n for n in ('started','cancel','pressure'))
            started.touch()
            with patch.object(supervisor.subprocess, 'Popen', return_value=RunningProcess()), \
                 patch.object(supervisor, 'process_alive', return_value=True), \
                 patch.object(supervisor, 'process_rss_kib', return_value=100), \
                 patch.object(supervisor, 'system_free_percent', return_value=15), \
                 patch.object(supervisor.time, 'sleep'):
                result = supervisor.launch_attempt('/Photoshop.app','/wrapper.jsx',started=started,
                                                   cancel=cancel,pid=11,pressure=pressure,memory_limit_kib=1000)
            self.assertTrue(pressure.exists())
            self.assertEqual(result.min_system_free_percent,15)

    @unittest.skipIf(supervisor.fcntl is None, 'Requires POSIX file locking')
    def test_failed_restart_preserves_last_checkpoint_in_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = self.make_job(root)
            def fail_after_checkpoint(path):
                write_json(root / 'supervisor_status.json',
                           {'state': 'restarting', 'cursor': 8, 'crashes': 1, 'attempt': 'abc'})
                raise RuntimeError('Photoshop blocked')
            with patch.object(supervisor.sys, 'platform', 'darwin'), \
                 patch.object(supervisor.Path, 'home', return_value=root), \
                 patch.object(supervisor, 'run_job', side_effect=fail_after_checkpoint), \
                 patch.object(supervisor, 'notify_user') as notify:
                self.assertEqual(supervisor.main([str(job)]), 1)
            notify.assert_called_once_with('failed')
            status = read_json(root / 'supervisor_status.json')
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['cursor'], 8)
            self.assertEqual(status['crashes'], 1)
            self.assertEqual(status['attempt'], 'abc')
            self.assertEqual(status['message'], 'Photoshop blocked')


class SystemMemoryProbeTest(unittest.TestCase):
    def test_parses_system_available_percentage_and_handles_unknown(self):
        with patch.object(supervisor.subprocess, 'check_output', return_value='System-wide memory free percentage: 23.5%\n'):
            self.assertEqual(supervisor.system_free_percent(), 23.5)
        with patch.object(supervisor.subprocess, 'check_output', return_value='unrecognized output'):
            self.assertIsNone(supervisor.system_free_percent())


if __name__ == '__main__':
    unittest.main()
