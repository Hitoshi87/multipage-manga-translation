import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from manga_ai.io import write_json
from manga_ai.translation import autopilot, service


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.project = self.dir / 'project.json'
        service.save_profile(self.project, {'group_size': 1, 'input_price_per_million': 1.0, 'output_price_per_million': 2.0})
        for n in (1, 2, 3):
            page = self.dir / str(n)
            page.mkdir()
            (page / 'original.png').write_bytes(b'same image' + bytes([n]))
            region = {'id': 'B001', 'box': [1, 1, 8, 8], 'safe': [1, 1, 8, 8], 'fill': [255, 255, 255], 'auto_clean': False,
                      'source': 'こんにちは' + str(n)}
            write_json(page / 'manifest.json', {'schema': 1, 'width': 10, 'height': 10, 'regions': [region]})
            service.index_page(self.project, page / 'manifest.json', 'page' + str(n), n)

    def ok(self, profile, prompt, payload):
        rows = [{'id': x['id'], 'vi': 'Xin chào', 'flags': []} for x in payload['segments']]
        return json.dumps({'translations': rows}), {'usage': {'prompt_tokens': 100, 'completion_tokens': 20}, 'latency_ms': 2000, 'model_returned': 'm'}

    def test_transient_errors_are_retried_with_backoff_then_succeed(self):
        calls = {'n': 0}
        sleeps = []

        def flaky(profile, prompt, payload):
            calls['n'] += 1
            if calls['n'] <= 2:
                raise ValueError('API tạm thời lỗi HTTP 503')
            return self.ok(profile, prompt, payload)

        with patch.object(service, 'call_provider', side_effect=flaky):
            report = autopilot.autopilot(self.project, auto_exclude=False, sleep=sleeps.append)
        self.assertTrue(report['done'])
        self.assertEqual(report['completed'], 3)
        self.assertEqual(sleeps[:2], [2, 4])          # exponential backoff

    def test_a_group_that_keeps_failing_is_parked_and_the_run_continues(self):
        order = []

        def provider(profile, prompt, payload):
            order.append(payload['segments'][0]['jp'])
            if payload['segments'][0]['jp'].endswith('2'):
                return '{', {'finish_reason': 'stop'}          # invalid JSON every time
            return self.ok(profile, prompt, payload)

        with patch.object(service, 'call_provider', side_effect=provider):
            report = autopilot.autopilot(self.project, auto_exclude=False, sleep=lambda s: None, max_attempts=2)
        self.assertEqual(report['completed'], 2)
        self.assertEqual(len(report['parked']), 1)
        self.assertTrue(report['done'])                    # nothing left to try
        with patch.object(service, 'call_provider') as provider2:
            again = autopilot.autopilot(self.project, run_id=report['run_id'], auto_exclude=False, max_attempts=2)
            provider2.assert_not_called()                 # parked groups are not retried forever
        self.assertEqual(len(again['parked']), 1)

    def test_systemic_error_stops_the_run_at_once(self):
        with patch.object(service, 'call_provider', side_effect=ValueError('Chưa có API key trong biến môi trường X')) as provider:
            report = autopilot.autopilot(self.project, auto_exclude=False, sleep=lambda s: None)
        self.assertTrue(report['aborted'])
        self.assertEqual(provider.call_count, 1)

    def test_budget_returns_a_resumable_slice(self):
        clock = {'t': 0.0}
        now = lambda: clock['t']

        def provider(profile, prompt, payload):
            clock['t'] += 10
            return self.ok(profile, prompt, payload)

        with patch.object(service, 'call_provider', side_effect=provider):
            first = autopilot.autopilot(self.project, auto_exclude=False, budget_seconds=15, now=now, sleep=lambda s: None)
            self.assertFalse(first['done'])
            self.assertEqual(first['completed'], 2)
            second = autopilot.autopilot(self.project, run_id=first['run_id'], auto_exclude=False, budget_seconds=15, now=now)
        self.assertTrue(second['done'])
        self.assertEqual(second['completed'], 3)

    def test_estimate_uses_measured_latency_and_prices(self):
        with patch.object(service, 'call_provider', side_effect=self.ok):
            run = service.prepare(self.project)['data']
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        info = autopilot.estimate(self.project)
        self.assertEqual((info['completed'], info['pending']), (1, 2))
        self.assertEqual(info['avg_seconds_per_group'], 2.0)
        self.assertEqual(info['eta_seconds'], 4)
        self.assertAlmostEqual(info['estimated_cost'], 2 * (100 * 1.0 + 20 * 2.0) / 1_000_000, places=6)

    def test_error_classification(self):
        self.assertEqual(autopilot.classify_error('API tạm thời lỗi HTTP 503'), 'transient')
        self.assertEqual(autopilot.classify_error('Invalid translation schema'), 'transient')
        self.assertEqual(autopilot.classify_error('API HTTP 429'), 'transient')
        self.assertEqual(autopilot.classify_error('API HTTP 400'), 'permanent')
        self.assertEqual(autopilot.classify_error('API HTTP 401'), 'systemic')


if __name__ == '__main__':
    unittest.main()
