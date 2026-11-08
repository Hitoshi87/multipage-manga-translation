import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from manga_ai.io import write_json
from manga_ai.report import build_report, collect_items, reason_text, severity
from manga_ai.translation import service


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.project = self.dir / 'project.json'
        service.save_profile(self.project, {'group_size': 20})
        page = self.dir / 'p'
        page.mkdir()
        Image.new('RGB', (200, 300), 'white').save(page / 'original.png')
        regions = [{'id': 'B001', 'box': [20, 30, 60, 40], 'safe': [20, 30, 60, 40], 'fill': [255] * 3, 'auto_clean': False, 'source': 'ありがとう'},
                   {'id': 'B002', 'box': [100, 120, 60, 40], 'safe': [100, 120, 60, 40], 'fill': [255] * 3, 'auto_clean': False, 'source': 'さよなら'}]
        write_json(page / 'manifest.json', {'schema': 1, 'width': 200, 'height': 300, 'regions': regions})
        service.index_page(self.project, page / 'manifest.json', '01.jpg', 1)
        run = service.prepare(self.project)['data']
        provider = lambda p, s, payload: (json.dumps({'translations': [{'id': x['id'], 'vi': 'Cảm ơn <3 & "ok"' if 'ありが' in x['jp'] else 'Tạm biệt', 'flags': []} for x in payload['segments']]}), {})
        with patch.object(service, 'call_provider', side_effect=provider):
            service.run_group(self.project, run['id'], run['groups'][0]['id'])
        seg_b002 = next(x['id'] for x in service.load(self.project)['pages'][0]['segments'] if x['region_id'] == 'B002')
        self.log = {'run_id': run['id'], 'auto_excluded': 3, 'translation_failures': [],
                    'pages': [{'page': '01.jpg', 'status': 'draft', 'required': 2, 'mapped': 2, 'clean_skipped': ['B001'],
                               'review': [{'region_id': 'B002', 'segment_id': seg_b002, 'flags': ['speaker_unclear'], 'qa_warnings': ['long_for_bubble']}],
                               'art_inpaint_review': [], 'manual_text': [], 'layout_fallback': [], 'files': {}},
                              {'page': '02.jpg', 'status': 'draft', 'required': 1, 'mapped': 1, 'clean_skipped': [], 'review': [],
                               'art_inpaint_review': [], 'manual_text': [], 'layout_fallback': [], 'files': {}},
                              {'page': '03.jpg', 'status': 'failed', 'error': 'Thiếu mapping trang'}]}
        self.log_path = self.dir / 'draft_x.json'
        write_json(self.log_path, self.log)

    def test_reasons_are_plain_language_and_severity_orders_fix_before_look(self):
        self.assertEqual(reason_text('clean_skipped'), 'Chưa xoá được chữ gốc ở bong bóng này')
        self.assertEqual(severity(['speaker_unclear']), 'look')
        self.assertEqual(severity(['speaker_unclear', 'clean_skipped']), 'fix')
        self.assertEqual(severity([]), 'ok')

    def test_a_page_that_fell_back_to_one_clean_layer_is_reported(self):
        from manga_ai.report import collect_items
        page = dict(self.log['pages'][1], page='05.jpg', clean_applied=3, clean_layers=0)
        items, pages = collect_items({'pages': [page, dict(self.log['pages'][1], page='06.jpg', clean_applied=3, clean_layers=3)]}, {})
        status = {p['page']: (p['status'], p['reasons']) for p in pages}
        self.assertEqual(status['05.jpg'], ('look', ['clean_single_layer']))
        self.assertEqual(status['06.jpg'], ('ok', []))
        self.assertIn('không tách theo từng bong bóng', reason_text('clean_single_layer'))

    def test_generic_model_doubts_are_light_notes_and_do_not_make_a_page_worth_a_look(self):
        from manga_ai.report import collect_items, summarise
        page = dict(self.log['pages'][1], page='07.jpg', review=[{'region_id': 'B009', 'flags': ['ambiguous_reference', 'needs_review']}])
        items, pages = collect_items({'pages': [page]}, {})
        self.assertEqual(pages[0]['status'], 'ok')
        self.assertEqual([i['severity'] for i in items], ['note'])
        self.assertEqual(summarise(pages, items)['items_note'], 1)
        # a real problem next to a note still decides the page
        page2 = dict(page, page='08.jpg', review=[{'region_id': 'B009', 'flags': ['ambiguous_reference', 'speaker_unclear']}])
        self.assertEqual(collect_items({'pages': [page2]}, {})[1][0]['status'], 'look')

    def test_notes_appear_in_a_quiet_section_and_not_in_the_review_queue(self):
        from manga_ai.report import review_queue
        self.log['pages'][1]['review'] = [{'region_id': 'B001', 'flags': ['ambiguous_reference']}]
        write_json(self.log_path, self.log)
        html = Path(build_report(self.project, self.log_path)['html']).read_text(encoding='utf8')
        self.assertIn('Ghi chú nhẹ (1)', html)
        keys = [i['key'] for i in review_queue(self.project, self.log_path)['items']]
        self.assertNotIn('02.jpg|B001', keys)

    def test_pdf_size_is_reported_with_a_hint_when_heavy(self):
        for page in self.log['pages'][:2]:
            page['pdf_mb'] = 41.0
        write_json(self.log_path, self.log)
        html = Path(build_report(self.project, self.log_path)['html']).read_text(encoding='utf8')
        self.assertIn('Dung lượng PDF: trung bình 41.0 MB mỗi trang', html)
        self.assertIn('chọn kiểu PDF Phẳng', html)
        for page in self.log['pages'][:2]:
            page['pdf_mb'] = 6.0
        write_json(self.log_path, self.log)
        self.assertNotIn('chọn kiểu PDF Phẳng', Path(build_report(self.project, self.log_path)['html']).read_text(encoding='utf8'))

    def test_items_and_page_status(self):
        items, pages = collect_items(self.log, {})
        status = {p['page']: p['status'] for p in pages}
        self.assertEqual(status, {'01.jpg': 'fix', '02.jpg': 'ok', '03.jpg': 'fix'})
        self.assertEqual([i['severity'] for i in items], ['fix', 'fix', 'look'])        # fixes first
        look = next(i for i in items if i['region'] == 'B002')
        self.assertEqual(look['codes'], ['speaker_unclear', 'long_for_bubble'])

    def test_html_is_written_with_summary_thumbnails_and_escaped_text(self):
        result = build_report(self.project, self.log_path)
        html = Path(result['html']).read_text(encoding='utf8')
        self.assertEqual(result['summary'], {'pages': 3, 'ok': 1, 'look': 0, 'fix': 2, 'items_fix': 2, 'items_look': 1, 'items_note': 0})
        self.assertIn('Cần sửa trước', html)
        self.assertIn('data:image/jpeg;base64,', html)                                   # bubble crop embedded
        self.assertIn('Cảm ơn &lt;3 &amp; &quot;ok&quot;', html)                          # model text is escaped
        self.assertIn('Máy đã tự bỏ qua 3 vùng không phải thoại', html)
        self.assertIn('Trang 01.jpg · bong bóng B001', html)
        self.assertIn('prefers-color-scheme:dark', html)

    def test_queue_is_urgent_first_and_remembers_what_was_done(self):
        from manga_ai.report import mark_reviewed, review_queue
        state = self.dir / 'review_state.json'
        queue = review_queue(self.project, self.log_path, state)
        self.assertEqual(queue['open'], 3)
        self.assertEqual([i['severity'] for i in queue['items']], ['fix', 'fix', 'look'])
        first = queue['items'][0]
        self.assertEqual(first['key'], f"{first['page']}|{first['region']}")
        self.assertIn('Chưa xoá được chữ gốc ở bong bóng này', next(i for i in queue['items'] if i['region'] == 'B001')['reasons'])
        mark_reviewed(state, [first['key']])
        after = review_queue(self.project, self.log_path, state)
        self.assertEqual(after['open'], 2)
        self.assertTrue(next(i for i in after['items'] if i['key'] == first['key'])['done'])
        mark_reviewed(state, [first['key']], 'open')
        self.assertEqual(review_queue(self.project, self.log_path, state)['open'], 3)
        with self.assertRaises(ValueError):
            mark_reviewed(state, ['x'], 'bogus')

    def test_review_file_prefers_the_layered_photoshop_pdf_over_the_psd(self):
        from manga_ai.report import review_queue
        self.log['pages'][0]['files'] = {'pdf': '/o/01.pdf', 'psd': '/o/01.psd'}
        self.log['pages'].append(dict(self.log['pages'][1], page='04.jpg', clean_skipped=['B009'], files={'psd': '/o/04.psd'}))
        write_json(self.log_path, self.log)
        files = {i['page']: i['file'] for i in review_queue(self.project, self.log_path)['items'] if i['region']}
        self.assertEqual(files['01.jpg'], '/o/01.pdf')
        self.assertEqual(files['04.jpg'], '/o/04.psd')          # no PDF for that page: fall back to the PSD

    def test_items_carry_what_the_review_dialog_needs(self):
        from manga_ai.report import review_queue
        item = next(i for i in review_queue(self.project, self.log_path)['items'] if i['region'] == 'B002')
        self.assertEqual(item['vi'], 'Tạm biệt')
        self.assertEqual(item['jp'], 'さよなら')
        self.assertTrue(item['segment_id'])


if __name__ == '__main__':
    unittest.main()

