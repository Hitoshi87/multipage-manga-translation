import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from manga_ai.io import write_json
from manga_ai.translation import service
from manga_ai.translation.continuity import dialogue_memory, review


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project.json'
        service.save_profile(self.project, {'group_size': 1, 'context_segments': 0, 'dialogue_review': True,
                                           'address_policy': 'A nói với B: A xưng tớ, gọi B là cậu.'})
        for number in range(1, 4):
            page = self.root / str(number)
            page.mkdir()
            (page / 'original.png').write_bytes(b'page' + bytes([number]))
            write_json(page / 'manifest.json', {'schema': 1, 'width': 10, 'height': 10, 'regions': [
                {'id': 'B001', 'box': [1, 1, 8, 8], 'safe': [1, 1, 8, 8], 'fill': [255, 255, 255],
                 'auto_clean': False, 'source': 'こんにちは'}]})
            service.index_page(self.project, page / 'manifest.json', 'page' + str(number), number)

    @staticmethod
    def answer(payload, text='Tớ chào cậu.', flags=()):
        return json.dumps({'translations': [{'id': row['id'], 'vi': text, 'flags': list(flags)}
                                             for row in payload['segments']]}), {}

    def test_second_pass_preserves_original_flags_and_accounts_for_both_calls(self):
        run = service.prepare(self.project)['data']
        def provider(profile, system, payload):
            self.assertIn('A nói với B', system)
            if 'draft_translations' in payload:
                self.assertEqual(profile['retries'], 0)
                self.assertLessEqual(profile['timeout'], 90)
                raw, _ = self.answer(payload, 'Tôi chào cậu.')
                return raw, {'usage': {'prompt_tokens': 20, 'completion_tokens': 4, 'total_tokens': 24}}
            raw, _ = self.answer(payload, flags=['ambiguous_reference'])
            return raw, {'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
        with patch.object(service, 'call_provider', side_effect=provider) as call:
            data = service.run_group(self.project, run['id'], run['groups'][0]['id'])['data']
        row = data['results'][0]
        self.assertEqual(call.call_count, 2)
        self.assertEqual(row['semantic_translation'], 'Tôi chào cậu.')
        self.assertEqual(row['dialogue_original_translation'], 'Tớ chào cậu.')
        self.assertIn('ambiguous_reference', row['flags'])
        self.assertIn('address_terms_changed', row['qa_warnings'])
        self.assertIn('needs_review', row['flags'])
        self.assertEqual(data['attempts'][-1]['usage'], {'prompt_tokens': 30, 'completion_tokens': 9, 'total_tokens': 39})

    def test_failed_review_keeps_the_draft_and_resume_does_not_pay_again(self):
        run = service.prepare(self.project)['data']
        def provider(profile, system, payload):
            if 'draft_translations' in payload:
                raise ValueError('API unavailable')
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider) as call:
            data = service.run_group(self.project, run['id'], run['groups'][0]['id'])['data']
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(data['results'][0]['semantic_translation'], 'Tớ chào cậu.')
        self.assertIn('dialogue_review_failed', data['results'][0]['qa_warnings'])
        self.assertEqual(data['attempts'][-1]['dialogue_review']['status'], 'failed')

    def test_invalid_second_pass_ids_cannot_replace_valid_draft(self):
        run = service.prepare(self.project)['data']
        def provider(profile, system, payload):
            if 'draft_translations' in payload:
                return '{"translations":[{"id":"wrong","vi":"Em","flags":[]}]}', {}
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider):
            result = service.run_group(self.project, run['id'], run['groups'][0]['id'])['data']['results'][0]
        self.assertEqual(result['semantic_translation'], 'Tớ chào cậu.')
        self.assertIn('dialogue_review_failed', result['qa_warnings'])

    def test_memory_uses_past_only_even_when_groups_finish_out_of_order(self):
        service.save_profile(self.project, {'group_size': 1, 'context_segments': 0, 'dialogue_review': False})
        run = service.prepare(self.project)['data']
        payloads = []
        def provider(profile, system, payload):
            payloads.append(payload)
            self.assertLessEqual(len(system) + len(json.dumps(payload, ensure_ascii=False)), profile['max_input_chars'])
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider):
            for index in (2, 0, 1):
                service.run_group(self.project, run['id'], run['groups'][index]['id'])
        self.assertNotIn('dialogue_memory', payloads[0])
        self.assertNotIn('dialogue_memory', payloads[1])
        self.assertEqual([row['id'] for row in payloads[2]['dialogue_memory']], [run['groups'][0]['targets'][0]['id']])
        self.assertEqual(payloads[2]['dialogue_memory'][0]['speaker']['status'], 'unknown')

    def test_stale_or_uncertain_draft_is_not_promoted_to_dialogue_memory(self):
        service.save_profile(self.project, {'group_size': 1, 'context_segments': 0, 'dialogue_review': False})
        run = service.prepare(self.project)['data']
        with patch.object(service, 'call_provider', side_effect=lambda p, s, b: self.answer(b, flags=['speaker_unclear'])):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        seen = []
        def provider(profile, system, payload):
            seen.append(payload)
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][1]['id'])
        self.assertNotIn('dialogue_memory', seen[0])
        service.edit_source(self.project, run['groups'][1]['targets'][0]['id'], 'さようなら')
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][2]['id'])
        self.assertNotIn('dialogue_memory', seen[1])

    def test_human_correction_becomes_context_without_inventing_a_speaker(self):
        service.save_profile(self.project, {'group_size': 1, 'context_segments': 0, 'dialogue_review': False})
        run = service.prepare(self.project)['data']
        with patch.object(service, 'call_provider', side_effect=lambda p, s, b: self.answer(b, flags=['speaker_unclear'])):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        sid = run['groups'][0]['targets'][0]['id']
        service.accept(self.project, run['id'], [{'id': sid, 'text': 'Mình chào cậu.'}])
        seen = []
        def provider(profile, system, payload):
            seen.append(payload)
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][1]['id'])
        memory = seen[0]['dialogue_memory'][0]
        self.assertEqual(memory['vi'], 'Mình chào cậu.')
        self.assertEqual(memory['status'], 'human_approved')
        self.assertEqual(memory['addressee']['status'], 'unknown')

    def test_memory_edit_during_request_invalidates_the_result(self):
        service.save_profile(self.project, {'group_size': 1, 'context_segments': 0, 'dialogue_review': False})
        run = service.prepare(self.project)['data']
        with patch.object(service, 'call_provider', side_effect=lambda p, s, b: self.answer(b)):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        def provider(profile, system, payload):
            service.accept(self.project, run['id'], [{'id': run['groups'][0]['targets'][0]['id'], 'text': 'Chào nhé.'}])
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider):
            with self.assertRaisesRegex(ValueError, 'Ngữ cảnh bản dịch đã thay đổi'):
                service.run_group(self.project, run['id'], run['groups'][1]['id'])
        self.assertEqual(service.load(self.project)['runs'][-1]['groups'][1]['results'], [])

    def test_legacy_run_does_not_gain_a_paid_review_pass(self):
        run = service.prepare(self.project)['data']
        state = service.load(self.project)
        state['runs'][-1]['translation_quality_version'] = 2
        service.save(self.project, state)
        with patch.object(service, 'call_provider', side_effect=lambda p, s, b: self.answer(b)) as call:
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        self.assertEqual(call.call_count, 1)

    def test_input_limit_skips_review_without_sending_oversized_payload(self):
        rows = [{'id': 'a', 'vi': 'Tớ chào cậu.', 'flags': []}]
        def unexpected(*args):
            self.fail('Oversized review must not call API')
        result, meta = review({'max_input_chars': 10}, 'system', {'segments': []}, rows, [], unexpected)
        self.assertEqual(meta['status'], 'skipped_input_limit')
        self.assertIn('dialogue_review_skipped', result[0]['_qa_warnings'])

    def test_cancel_between_passes_does_not_save_a_partial_group(self):
        run = service.prepare(self.project)['data']
        cancel = self.root / 'cancel'
        def provider(profile, system, payload):
            cancel.touch()
            return self.answer(payload)
        with patch.object(service, 'call_provider', side_effect=provider) as call:
            with self.assertRaisesRegex(ValueError, 'Đã hủy'):
                service.run_group(self.project, run['id'], run['groups'][0]['id'], cancel=cancel)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(service.load(self.project)['runs'][-1]['groups'][0]['results'], [])

    def test_legacy_profile_roundtrip_keeps_all_existing_revisions(self):
        state = service.load(self.project)
        values = state['profiles'][-1]['values']
        values.pop('address_policy')
        values.pop('dialogue_review')
        state['profiles'][-1]['revision'] = service.digest(values)
        service.save(self.project, state)
        saved = service.save_profile(self.project, values)['data']
        self.assertEqual(saved['revision'], state['profiles'][-1]['revision'])

    def test_memory_is_bounded_and_prefers_a_human_correction(self):
        sources = [{'id': str(i), 'page_id': 'p1', 'page_ordinal': 1, 'order': i, 'jp': 'こんにちは',
                    'source_status': 'verified', 'source_revision': 'r'} for i in range(20)]
        last = {'id': 'current', 'page_id': 'p2', 'page_ordinal': 2, 'jp': 'はい', 'source_revision': 'r'}
        groups = []
        for source in sources:
            snapshot = {**source, 'segment_version': service.segment_version(source)}
            groups.append({'id': 'g' + source['id'], 'status': 'completed', 'targets': [snapshot],
                           'results': [{**snapshot, 'semantic_translation': 'Chào.', 'flags': [],
                                        'status': 'human_approved' if source['id'] == '0' else 'validated'}]})
        current = {'id': 'current', 'targets': [last], 'status': 'pending'}
        groups.append(current)
        memory = dialogue_memory({'pages': [{'ordinal': 1, 'segments': sources}, {'ordinal': 2, 'segments': [last]}]},
                                 {'groups': groups}, current)
        self.assertEqual(len(memory), 12)
        self.assertEqual(memory[0]['id'], '0')
        self.assertEqual(memory[-1]['id'], '19')
        self.assertEqual([int(r['id']) for r in memory], sorted(int(r['id']) for r in memory))

    def test_missing_usage_does_not_create_a_misleading_complete_cost(self):
        service.save_profile(self.project, {'group_size': 1, 'dialogue_review': True,
                                           'input_price_per_million': 1, 'output_price_per_million': 2})
        run = service.prepare(self.project)['data']
        def provider(profile, system, payload):
            raw, _ = self.answer(payload)
            return raw, {'usage': {'prompt_tokens': 20, 'completion_tokens': 4}} if 'draft_translations' in payload else {}
        with patch.object(service, 'call_provider', side_effect=provider):
            group = service.run_group(self.project, run['id'], run['groups'][0]['id'])['data']
        attempt = group['attempts'][-1]
        self.assertFalse(attempt['usage_complete'])
        self.assertNotIn('estimated_cost', attempt)


if __name__ == '__main__':
    unittest.main()
