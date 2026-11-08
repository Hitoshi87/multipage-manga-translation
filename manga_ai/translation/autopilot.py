"""Long-run translation driver: retries, backoff, parking, resume and a time budget.

A volume is hundreds of provider calls. Transient failures (gateway errors, rate
limits, malformed JSON from the model) are retried with backoff; a group that
keeps failing is parked in the report and the run continues with the next group.
Systemic failures (missing key, authentication) stop the run at once.

Each call is idempotent and checkpointed by service.run_group, so the driver can
be interrupted and called again, including in short slices (budget_seconds) for
callers such as the Photoshop bridge that wait a limited time per request.
"""
import time

from . import service

PERMANENT = ('Chưa có API key', 'API HTTP 4', 'Nguồn đã thay đổi', 'Nguồn hoặc profile', 'Profile đã thay đổi',
             'Đã hủy', 'Lượt cũ chưa lưu prompt', 'Payload vision vượt giới hạn', 'Không tìm thấy')
SYSTEMIC = ('Chưa có API key', 'API HTTP 401', 'API HTTP 403', 'Đã hủy')


def classify_error(message):
    """Return 'systemic', 'permanent' or 'transient' for an error message."""
    text = str(message)
    if any(marker in text for marker in SYSTEMIC):
        return 'systemic'
    if any(marker in text for marker in PERMANENT) and 'API HTTP 429' not in text:
        return 'permanent'
    return 'transient'


def _failed_attempts(group):
    return sum(1 for a in group.get('attempts', []) if a.get('status') == 'failed')


def run_group_with_retry(path, run_id, group_id, *, max_attempts=3, deadline=None, cancel=None,
                         sleep=time.sleep, now=time.monotonic):
    """Run one group, retrying transient failures. Never raises for provider errors."""
    state = service.load(path)
    run = next(r for r in state['runs'] if r['id'] == run_id)
    group = next(g for g in run['groups'] if g['id'] == group_id)
    already = _failed_attempts(group)
    tries = 0
    last = ''
    kind = 'transient'
    while already + tries < max_attempts:
        if deadline is not None and now() >= deadline:
            return {'group_id': group_id, 'status': 'pending', 'attempts': tries, 'error': last, 'kind': kind}
        tries += 1
        try:
            service.run_group(path, run_id, group_id, cancel)
            return {'group_id': group_id, 'status': 'completed', 'attempts': tries, 'error': '', 'kind': ''}
        except Exception as exc:  # provider, schema and source errors all arrive as exceptions
            last = str(exc)
            kind = classify_error(last)
            if kind != 'transient':
                break
            if already + tries < max_attempts:
                delay = min(2 ** tries, 8)
                if deadline is not None:
                    delay = min(delay, max(0, deadline - now()))
                if delay:
                    sleep(delay)
    return {'group_id': group_id, 'status': 'failed', 'attempts': tries, 'error': last, 'kind': kind}


def autopilot(path, run_id=None, *, max_attempts=3, budget_seconds=None, max_consecutive=5, auto_exclude=True,
              cancel=None, progress=None, sleep=time.sleep, now=time.monotonic):
    """Translate every pending group of the latest (or given) run.

    Returns a report; `done` is True when nothing is left to do (all groups
    completed or parked after `max_attempts` failures).
    """
    started = now()
    deadline = started + budget_seconds if budget_seconds else None
    excluded = None
    if run_id is None:
        if auto_exclude:
            from .triage import auto_exclude as triage_exclude
            excluded = triage_exclude(path)
        run = service.resume_or_prepare(path)['data']
        run_id = run['id']
    state = service.load(path)
    run = next((r for r in state['runs'] if r['id'] == run_id), None)
    if not run:
        raise ValueError('Không tìm thấy run')
    failed, consecutive, aborted, reason = [], 0, False, ''
    for index, group in enumerate(run['groups'], 1):
        if group['status'] == 'completed':
            continue
        if _failed_attempts(group) >= max_attempts:
            failed.append({'group_id': group['id'], 'error': _last_error(group), 'attempts': _failed_attempts(group), 'parked': True})
            continue
        if deadline is not None and now() >= deadline:
            break
        if cancel and _exists(cancel):
            aborted, reason = True, 'Đã hủy'
            break
        result = run_group_with_retry(path, run_id, group['id'], max_attempts=max_attempts, deadline=deadline,
                                      cancel=cancel, sleep=sleep, now=now)
        if progress:
            progress({'index': index, 'total': len(run['groups']), **result})
        if result['status'] == 'completed':
            consecutive = 0
        elif result['status'] == 'failed':
            consecutive += 1
            failed.append({'group_id': group['id'], 'error': result['error'], 'attempts': result['attempts'],
                           'parked': _failed_attempts_now(path, run_id, group['id']) >= max_attempts or result['kind'] != 'transient'})
            if result['kind'] == 'systemic':
                aborted, reason = True, result['error']
                break
            if consecutive >= max_consecutive:
                aborted, reason = True, 'Quá nhiều nhóm thất bại liên tiếp; kiểm tra kết nối hoặc API'
                break
    state = service.load(path)
    run = next(r for r in state['runs'] if r['id'] == run_id)
    pending = [g['id'] for g in run['groups'] if g['status'] != 'completed' and _failed_attempts(g) < max_attempts]
    completed = sum(1 for g in run['groups'] if g['status'] == 'completed')
    parked = [{'group_id': g['id'], 'error': _last_error(g), 'attempts': _failed_attempts(g)}
              for g in run['groups'] if g['status'] != 'completed' and _failed_attempts(g) >= max_attempts]
    return {'run_id': run_id, 'total': len(run['groups']), 'completed': completed, 'pending': len(pending),
            'parked': parked, 'failed': failed, 'aborted': aborted, 'abort_reason': reason,
            'done': not pending and not aborted, 'auto_excluded': excluded, 'seconds': round(now() - started, 1)}


def estimate(path, run_id=None):
    """Work left, time and (if prices are configured) cost, from measured attempts."""
    state = service.load(path)
    run = next((r for r in state['runs'] if r['id'] == run_id), None) if run_id else (state['runs'][-1] if state['runs'] else None)
    if not run:
        raise ValueError('Chưa có run; tạo lượt dịch trước')
    profile = next(p for p in state['profiles'] if p['revision'] == run['profile_revision'])['values']
    pending = [g for g in run['groups'] if g['status'] != 'completed']
    latencies, tokens_in, tokens_out = [], [], []
    for g in run['groups']:
        if g['status'] != 'completed':
            continue
        ok = [a for a in g.get('attempts', []) if a.get('status') == 'completed']
        if not ok:
            continue
        a = ok[-1]
        if a.get('latency_ms'):
            latencies.append(a['latency_ms'] / 1000)
        usage = a.get('usage') or {}
        if usage.get('prompt_tokens') is not None:
            tokens_in.append(usage['prompt_tokens'])
        if usage.get('completion_tokens') is not None:
            tokens_out.append(usage['completion_tokens'])
    avg = lambda values: sum(values) / len(values) if values else None
    sec, t_in, t_out = avg(latencies), avg(tokens_in), avg(tokens_out)
    cost = None
    p_in, p_out = profile.get('input_price_per_million'), profile.get('output_price_per_million')
    if t_in is not None and t_out is not None and p_in is not None and p_out is not None:
        cost = len(pending) * (t_in * p_in + t_out * p_out) / 1_000_000
    return {'run_id': run['id'], 'groups': len(run['groups']), 'completed': len(run['groups']) - len(pending),
            'pending': len(pending), 'pending_input_chars': sum(g.get('input_chars', 0) for g in pending),
            'avg_seconds_per_group': round(sec, 1) if sec is not None else None,
            'eta_seconds': round(sec * len(pending)) if sec is not None else None,
            'avg_prompt_tokens': round(t_in) if t_in is not None else None,
            'avg_completion_tokens': round(t_out) if t_out is not None else None,
            'estimated_cost': round(cost, 6) if cost is not None else None,
            'basis': 'measured from completed groups' if latencies else 'no completed group yet'}


def _last_error(group):
    for attempt in reversed(group.get('attempts', [])):
        if attempt.get('status') == 'failed':
            return attempt.get('error', '')
    return ''


def _failed_attempts_now(path, run_id, group_id):
    run = next(r for r in service.load(path)['runs'] if r['id'] == run_id)
    return _failed_attempts(next(g for g in run['groups'] if g['id'] == group_id))


def _exists(path):
    from pathlib import Path
    return Path(path).exists()
