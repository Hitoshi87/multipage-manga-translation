"""macOS supervisor for an explicitly started, checkpointed Photoshop job.

Photoshop performs all edits. This process only launches a single scripted
attempt, restarts after a confirmed process exit, and requests clean recycling
at script-defined page boundaries. It never force-quits an open document.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .io import read_json, write_json

try:
    import fcntl
except ImportError:  # The rest of the application also runs on Windows.
    fcntl = None


def photoshop_processes():
    out = subprocess.check_output(['/bin/ps', '-axo', 'pid=,comm='], text=True)
    result = []
    for line in out.splitlines():
        match = re.match(r'^\s*(\d+)\s+(.+\.app)/Contents/MacOS/Adobe Photoshop[^/]*$', line)
        if match:
            result.append((int(match.group(1)), match.group(2)))
    return result


def process_alive(pid, app_path):
    return (pid, app_path) in photoshop_processes()


def physical_memory_limit_kib():
    """Conservative RSS warning threshold; it is not a hard memory limit."""
    try:
        size = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'], text=True, timeout=5).strip())
        return max(1024 * 1024, min(6 * 1024 * 1024, int(size * .35 / 1024)))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 4 * 1024 * 1024


def process_rss_kib(pid):
    try:
        output = subprocess.check_output(['/bin/ps', '-o', 'rss=', '-p', str(pid)], text=True, timeout=2)
        return max(0, int(output.strip()))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def system_free_percent():
    """Return macOS's system-wide free percentage, or None if unavailable."""
    try:
        env = dict(os.environ, LC_ALL='C')
        output = subprocess.check_output(['/usr/bin/memory_pressure', '-Q'], text=True, timeout=5, env=env)
        match = re.search(r'System-wide memory free percentage:\s*(\d+(?:\.\d+)?)%', output)
        return float(match.group(1)) if match else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def applescript(script, *args, timeout=None):
    return subprocess.run(['/usr/bin/osascript', '-e', script, *map(str, args)],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def application_literal(app_path):
    # AppleScript needs a literal application at compile time to load the
    # Photoshop dictionary; a variable target cannot compile "do javascript".
    if '\n' in app_path or '\r' in app_path:
        raise ValueError('Đường dẫn Photoshop chứa xuống dòng không được hỗ trợ.')
    return '"' + app_path.replace('\\', '\\\\').replace('"', '\\"') + '"'


def launch_attempt(app_path, wrapper, *, started=None, cancel=None, pid=None, startup_timeout=120,
                   pressure=None, memory_limit_kib=None):
    script = '''on run argv
    with timeout of 2147483647 seconds
        tell application APP_LITERAL to do javascript (item 1 of argv)
    end timeout
end run'''.replace('APP_LITERAL', application_literal(app_path))
    code = '$.evalFile(new File(' + json.dumps(str(wrapper), ensure_ascii=True) + '));'
    if started is None:
        return applescript(script, code)
    command = ['/usr/bin/osascript', '-e', script, code]
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + startup_timeout
    timed_out = False
    peak_rss_kib, next_sample, next_system_sample = 0, 0, 0
    min_system_free_percent = None
    while process.poll() is None:
        now = time.monotonic()
        if pid is not None and now >= next_sample:
            peak_rss_kib = max(peak_rss_kib, process_rss_kib(pid))
            next_sample = now + 2
        if now >= next_system_sample:
            free = system_free_percent()
            if free is not None:
                min_system_free_percent = free if min_system_free_percent is None else min(min_system_free_percent, free)
            next_system_sample = now + 10
        if pressure is not None and ((memory_limit_kib and peak_rss_kib >= memory_limit_kib) or
                                     (min_system_free_percent is not None and min_system_free_percent < 20)):
            try:
                pressure.touch()
            except OSError:
                pass  # The next batch still shrinks from the measured peak.
        has_started = started.exists()
        if (not has_started and cancel.exists()) or (pid is not None and not process_alive(pid, app_path)):
            process.terminate()
            break
        if not has_started and time.monotonic() >= deadline:
            # The queued Apple event may still be delivered later. The wrapper
            # checks this marker before touching the project.
            cancel.touch()
            timed_out = True
            process.terminate()
            break
        time.sleep(.5)
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        # Only terminate the AppleScript client, never Photoshop or a document.
        process.kill()
        stdout, stderr = process.communicate()
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    result.startup_timed_out = timed_out
    result.peak_rss_kib = peak_rss_kib
    result.min_system_free_percent = min_system_free_percent
    return result


def quit_empty(app_path):
    script = '''on run argv
    tell application APP_LITERAL
        if (count of documents) is not 0 then error "Photoshop has open documents; automatic restart stopped."
        quit
    end tell
end run'''.replace('APP_LITERAL', application_literal(app_path))
    try:
        result = applescript(script, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Photoshop chưa thoát; có thể đang chờ hộp thoại. Đã dừng giám sát.') from exc
    if result.returncode:
        raise RuntimeError('Không thể khởi động lại Photoshop an toàn: ' + result.stderr.strip())


def select_process(app_path=None):
    processes = photoshop_processes()
    if app_path:
        processes = [p for p in processes if p[1] == app_path]
    if len(processes) != 1:
        raise RuntimeError('Cần đúng một Photoshop đang chạy; tìm thấy ' + str(len(processes)))
    return processes[0]


def start_photoshop(app_path, timeout=120):
    others = [p for p in photoshop_processes() if p[1] != app_path]
    if others:
        raise RuntimeError('Có Photoshop khác đang chạy; không tự mở thêm phiên bản.')
    opened = subprocess.run(['/usr/bin/open', '-a', app_path], capture_output=True, text=True)
    if opened.returncode:
        raise RuntimeError('Không mở được Photoshop: ' + opened.stderr.strip())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        processes = [p for p in photoshop_processes() if p[1] == app_path]
        if len(processes) == 1:
            script = 'tell application ' + application_literal(app_path) + ' to get name'
            try:
                ready = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True, timeout=10)
                if ready.returncode == 0:
                    return processes[0][0]
            except subprocess.TimeoutExpired:
                pass
        if len(processes) > 1:
            raise RuntimeError('Có nhiều Photoshop cùng phiên bản; dừng phục hồi.')
        time.sleep(1)
    raise RuntimeError('Photoshop không khởi động trong thời gian cho phép.')


def notify_user(state):
    messages = {
        'complete': 'Đã xử lý xong. Xem báo cáo trong thư mục kết quả.',
        'needs_attention': 'Còn trang chưa hoàn tất. Xem supervisor_status.json để xử lý.',
        'cancelled': 'Tác vụ đã dừng tại checkpoint.',
        'failed': 'Tác vụ đã dừng vì lỗi. Xem supervisor_status.json để tiếp tục.',
        'waiting_memory': 'Máy đang thiếu bộ nhớ; tác vụ chờ tại checkpoint.',
    }
    if sys.platform != 'darwin' or state not in messages:
        return
    script = '''on run argv
    display notification (item 1 of argv) with title "Manga Typesetter"
end run'''
    try:
        applescript(script, messages[state], timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass  # The durable status file is authoritative even without permission.


def run_job(job_path, *, sleep=time.sleep, max_crashes=3):
    job_path = Path(job_path).resolve()
    job = read_json(job_path)
    directory = job_path.parent
    if job.get('schema') != 1 or not Path(job['script']).is_file():
        raise ValueError('Cấu hình giám sát không hợp lệ.')
    ready = directory / 'ready'
    deadline = time.monotonic() + 60
    while not ready.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError('Giao diện Photoshop chưa đóng; không thể bắt đầu tác vụ giám sát.')
        sleep(.2)
    pid, app_path = select_process()
    status_path = directory / 'supervisor_status.json'
    cancel_path = directory / 'cancel'
    state = {'state': 'starting', 'cursor': 0, 'crashes': 0, 'total_crashes': 0, 'app': app_path,
             'batch_size': 4, 'memory_limit_kib': physical_memory_limit_kib(),
             'peak_photoshop_rss_kib': 0}
    low_memory_batches = 0
    write_json(status_path, state)

    def wait_for_memory():
        free = system_free_percent()
        if free is None or free >= 25:
            state['system_free_percent'] = free
            return not cancel_path.exists()
        deadline = time.monotonic() + 300
        notified = False
        while free is not None and free < 25:
            if cancel_path.exists():
                return False
            state.update(state='waiting_memory', system_free_percent=free,
                         message='Máy còn ít bộ nhớ; đang chờ trước khi mở trang tiếp theo.')
            write_json(status_path, state)
            if not notified:
                notify_user('waiting_memory')
                notified = True
            if time.monotonic() >= deadline:
                raise RuntimeError('Máy vẫn thiếu bộ nhớ sau 5 phút; đã dừng tại checkpoint. Hãy giải phóng RAM và chạy lại.')
            sleep(5)
            free = system_free_percent()
        state['system_free_percent'] = free
        return not cancel_path.exists()

    while True:
        if cancel_path.exists():
            state.update(state='cancelled')
            break
        if not wait_for_memory():
            state.update(state='cancelled')
            break
        attempt = uuid.uuid4().hex
        attempt_path = directory / ('attempt_' + attempt + '.json')
        started = directory / ('attempt_' + attempt + '.started')
        pressure = directory / ('attempt_' + attempt + '.pressure')
        bootstrap = directory / ('attempt_' + attempt + '.jsx')
        # Explicit string literals; no secrets in the bootstrap or job settings.
        bootstrap.write_text('if (!(new File('+json.dumps(str(cancel_path), ensure_ascii=True)+')).exists) {'+
                             'var started=new File('+json.dumps(str(started), ensure_ascii=True)+');'+
                             'if(!started.open("w"))throw Error("Cannot write start marker");started.write("started");started.close();'+
                             'if (!(new File('+json.dumps(str(cancel_path), ensure_ascii=True)+')).exists) {'+
                             '$.global.MTA_SUPERVISED_JOB=' + json.dumps(str(job_path), ensure_ascii=True) +
                             ';$.global.MTA_SUPERVISED_SCOPE=' + json.dumps(str(job.get('project', job_path)), ensure_ascii=True) +
                             ';$.global.MTA_SUPERVISED_RESULT=' + json.dumps(str(attempt_path), ensure_ascii=True) +
                             ';$.global.MTA_SUPERVISED_CURSOR=' + str(state['cursor']) +
                             ';$.global.MTA_SUPERVISED_BATCH_SIZE=' + str(state['batch_size']) +
                             ';$.global.MTA_SUPERVISED_PRESSURE=' + json.dumps(str(pressure), ensure_ascii=True) +
                             ';try{$.evalFile(new File(' + json.dumps(job['script'], ensure_ascii=True) + '));}'+
                             'finally{$.global.MTA_SUPERVISED_JOB=null;$.global.MTA_SUPERVISED_SCOPE=null;'+
                             '$.global.MTA_SUPERVISED_RESULT=null;$.global.MTA_SUPERVISED_CURSOR=null;'+
                             '$.global.MTA_SUPERVISED_BATCH_SIZE=null;$.global.MTA_SUPERVISED_PRESSURE=null;}}}', encoding='utf-8')
        state.update(state='running', pid=pid, attempt=attempt, message='')
        write_json(status_path, state)
        result = launch_attempt(app_path, bootstrap, started=started, cancel=cancel_path, pid=pid,
                                pressure=pressure, memory_limit_kib=state['memory_limit_kib'])
        peak = max(0, int(getattr(result, 'peak_rss_kib', 0) or 0))
        min_free = getattr(result, 'min_system_free_percent', None)
        state['last_photoshop_rss_kib'] = peak
        state['peak_photoshop_rss_kib'] = max(state['peak_photoshop_rss_kib'], peak)
        state['last_min_system_free_percent'] = min_free
        if min_free is not None:
            previous_min = state.get('min_system_free_percent')
            state['min_system_free_percent'] = min_free if previous_min is None else min(previous_min, min_free)
        write_json(status_path, state)
        if getattr(result, 'startup_timed_out', False):
            raise RuntimeError('Photoshop chưa bắt đầu script sau 120 giây; có thể đang chờ hộp thoại. Đã dừng và giữ checkpoint.')
        response = None
        if attempt_path.exists():
            try:
                response = read_json(attempt_path)
            except (OSError, ValueError):
                pass
        if response and response.get('state') in ('complete', 'needs_attention', 'failed', 'cancelled'):
            state.update(state=response['state'], message=response.get('message', ''))
            if 'summary' in response:
                state['summary'] = response['summary']
            if 'report' in response:
                state['report'] = response['report']
            if 'pending_pages' in response:
                state['pending_pages'] = response['pending_pages']
            break
        if response and response.get('state') == 'recycle':
            next_cursor = response.get('next_cursor')
            if not isinstance(next_cursor, int) or next_cursor <= state['cursor']:
                raise RuntimeError('Checkpoint giám sát không tiến triển; đã dừng.')
            state['cursor'] = next_cursor
            state['crashes'] = 0
            if peak >= state['memory_limit_kib'] or (min_free is not None and min_free < 20):
                state['batch_size'] = 1
                low_memory_batches = 0
            elif peak and state['batch_size'] < 4:
                low_memory_batches += 1
                if low_memory_batches >= 2:
                    state['batch_size'] = min(4, state['batch_size'] * 2)
                    low_memory_batches = 0
            else:
                low_memory_batches = 0
            state.update(state='restarting')
            write_json(status_path, state)
            if process_alive(pid, app_path):
                quit_empty(app_path)
                deadline = time.monotonic() + 60
                while process_alive(pid, app_path) and time.monotonic() < deadline:
                    sleep(1)
                if process_alive(pid, app_path):
                    raise RuntimeError('Photoshop chưa thoát; không khởi chạy bản thứ hai.')
            if cancel_path.exists():
                state.update(state='cancelled')
                break
            if not wait_for_memory():
                state.update(state='cancelled')
                break
            pid = start_photoshop(app_path)
            continue
        if cancel_path.exists():
            state.update(state='cancelled')
            break
        # Never replay a possibly running AppleScript against a live Photoshop.
        if process_alive(pid, app_path):
            raise RuntimeError('Photoshop còn chạy nhưng tác vụ không trả checkpoint: ' + result.stderr.strip())
        state['crashes'] += 1
        state['total_crashes'] += 1
        # Retry only one page at a time after a crash to reduce peak pressure
        # and avoid repeating the entire four-page scan group.
        state['batch_size'] = 1
        low_memory_batches = 0
        if state['crashes'] > max_crashes:
            raise RuntimeError('Photoshop thoát nhiều lần tại cùng một nhóm; đã dừng để tránh lặp vô hạn.')
        state.update(state='recovering', message=result.stderr.strip())
        write_json(status_path, state)
        sleep(min(30, 5 * state['crashes']))
        if cancel_path.exists():
            state.update(state='cancelled')
            break
        if not wait_for_memory():
            state.update(state='cancelled')
            break
        pid = start_photoshop(app_path)
    write_json(status_path, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('job', type=Path)
    args = parser.parse_args(argv)
    directory = args.job.resolve().parent
    if sys.platform != 'darwin' or fcntl is None:
        write_json(directory / 'supervisor_status.json', {'state': 'failed', 'message': 'Chế độ giám sát hiện chỉ hỗ trợ macOS.'})
        return 1
    # One supervisor may control this application at a time, even for different volumes.
    lock_path = Path.home() / '.manga_typesetter' / 'photoshop_supervisor.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            write_json(directory / 'supervisor_status.json', {'state': 'failed', 'message': 'Đã có một tác vụ giám sát Photoshop đang chạy.'})
            notify_user('failed')
            return 1
        try:
            result = run_job(args.job)
            notify_user(result['state'])
            return 0 if result['state'] in ('complete', 'cancelled') else 1
        except Exception as exc:
            status_path = directory / 'supervisor_status.json'
            try:
                status = read_json(status_path) if status_path.exists() else {}
                if not isinstance(status, dict):
                    status = {}
            except (OSError, ValueError):
                status = {}
            status.update(state='failed', message=str(exc))
            write_json(status_path, status)
            notify_user('failed')
            print(str(exc), file=sys.stderr, flush=True)
            return 1


if __name__ == '__main__':
    sys.exit(main())
