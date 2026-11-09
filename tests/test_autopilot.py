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

    def test_streaming_reuses_previous_results_and_context_without_future_pages(self):
        requests=[]
        def provider(profile,system,payload):
            requests.append(payload)
            return self.ok(profile,system,payload)
        with patch.object(service,'call_provider',side_effect=provider):
            first=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=1)
            self.assertTrue(first['done'])
            self.assertEqual(len(requests),1)
            second=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=2)
            self.assertEqual(second['run_id'],first['run_id'])
            self.assertEqual(len(requests),2)
            self.assertEqual([s['page_id'] for s in requests[1]['context_only']],['page1'])
            self.assertEqual([s['page_id'] for s in requests[1]['segments']],['page2'])
            again=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=2)
            self.assertEqual(again['run_id'],first['run_id'])
            self.assertEqual(len(requests),2)
        run=service.load(self.project)['runs'][-1]
        self.assertEqual(len(run['groups']),2)
        self.assertNotIn('page3',[t['page_id'] for g in run['groups'] for t in g['targets']])
        (self.dir/'3'/'original.png').unlink()  # unrelated future page must not block this export
        mapping=service.export_mapping(self.project,first['run_id'],draft=True,page_ids=['page2'])
        self.assertEqual([p['page_id'] for p in mapping['data']['pages']],['page2'])

    def test_streaming_rejects_changed_prior_source(self):
        with patch.object(service,'call_provider',side_effect=self.ok):
            first=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=1)
        state=service.load(self.project);segment=state['pages'][0]['segments'][0]
        service.edit_source(self.project,segment['id'],'変更された文章')
        with self.assertRaisesRegex(ValueError,'Nguồn đã thay đổi'):
            autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=2)
        self.assertEqual(service.load(self.project)['runs'][-1]['id'],first['run_id'])

    def test_failed_page_can_be_indexed_later_without_future_context(self):
        state=service.load(self.project)
        state['pages']=[page for page in state['pages'] if page['page_id']!='page2']
        service.save(self.project,state)
        calls=[]
        def provider(profile,system,payload):
            calls.append(payload)
            return self.ok(profile,system,payload)
        with patch.object(service,'call_provider',side_effect=provider):
            first=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=3)
            service.index_page(self.project,self.dir/'2'/'manifest.json','page2',2)
            again=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=3)
        self.assertEqual(first['run_id'],again['run_id'])
        self.assertEqual([x['page_id'] for x in calls[-1]['segments']],['page2'])
        self.assertEqual([x['page_id'] for x in calls[-1]['context_only']],['page1'])
        self.assertEqual(len(calls),3)

    def test_quote_from_previous_batch_is_visible_in_review_queue(self):
        state=service.load(self.project)
        service.edit_source(self.project,state['pages'][0]['segments'][0]['id'],'みにゃさん、こんにちは')
        service.edit_source(self.project,state['pages'][1]['segments'][0]['id'],'「みにゃさん」って何ですか')
        with patch.object(service,'call_provider',side_effect=self.ok):
            autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=1)
            autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=2)
        run=service.load(self.project)['runs'][-1]
        row=next(r for g in run['groups'] for r in g['results'] if r['id']==state['pages'][1]['segments'][0]['id'])
        self.assertIn('quote_cross_batch',row['qa_warnings'])
        from manga_ai import report
        self.assertEqual(report.severity(row['qa_warnings']),'look')

    def test_one_group_and_one_attempt_per_slice_remains_resumable(self):
        calls=[]
        def flaky(profile,system,payload):
            calls.append(payload['segments'][0]['jp'])
            if len(calls)==1:raise ValueError('API tạm thời lỗi HTTP 503')
            return self.ok(profile,system,payload)
        with patch.object(service,'call_provider',side_effect=flaky):
            first=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=3,max_groups=1,max_slice_attempts=1,sleep=lambda _:None)
            self.assertFalse(first['done']);self.assertEqual(len(calls),1)
            second=autopilot.autopilot(self.project,run_id=first['run_id'],auto_exclude=False,max_groups=1,max_slice_attempts=1,sleep=lambda _:None)
            self.assertFalse(second['done']);self.assertEqual(second['completed'],1)
            third=autopilot.autopilot(self.project,run_id=first['run_id'],auto_exclude=False,max_groups=1,max_slice_attempts=1,sleep=lambda _:None)
            self.assertEqual(third['completed'],2)
        self.assertEqual(calls[0],calls[1])

    def test_unrecorded_validation_failures_eventually_park(self):
        with patch.object(service,'run_group',side_effect=ValueError('Nguồn đã thay đổi')):
            first=autopilot.autopilot(self.project,auto_exclude=False,max_page_ordinal=1,max_groups=1,max_slice_attempts=1)
            second=autopilot.autopilot(self.project,run_id=first['run_id'],auto_exclude=False,max_groups=1,max_slice_attempts=1)
            third=autopilot.autopilot(self.project,run_id=first['run_id'],auto_exclude=False,max_groups=1,max_slice_attempts=1)
        self.assertFalse(first['done']);self.assertFalse(second['done'])
        self.assertTrue(third['done']);self.assertEqual(len(third['parked']),1)

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
