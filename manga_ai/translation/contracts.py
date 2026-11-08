"""Versioned stage envelopes for translation workflow interoperation."""

SCHEMA_VERSION = '1.0'
STATUSES = frozenset(('pending', 'running', 'completed', 'partial', 'review_required', 'blocked', 'failed', 'cancelled'))


def envelope(stage, status, data=None, *, job_id=None, input_refs=None, output_refs=None, engine=None, issues=None):
    if not isinstance(stage, str) or not stage.strip() or status not in STATUSES:
        raise ValueError('Invalid stage or status')
    return {'schema_version': SCHEMA_VERSION, 'job_id': job_id, 'stage': stage,
            'status': status, 'input_refs': list(input_refs or []),
            'output_refs': list(output_refs or []), 'engine': engine,
            'issues': list(issues or []), 'data': {} if data is None else data}
