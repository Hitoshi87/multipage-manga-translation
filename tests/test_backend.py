import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from manga_ai.cli import dispatch, doctor, main, natural_key
from manga_ai.engine import (Cancelled, analyse, bubble_candidates, check_cancel,
                             read_image, reading_order, render_clean, safe_rectangle)
from manga_ai.io import checked_mapping, import_text, parse_translations, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "demo_project/pages/001_page1/original.png"


class TextTests(unittest.TestCase):
    def test_vietnamese_page_markers_and_breaks(self):
        result = parse_translations("\ufeff[PAGE 1]\nXin chào!\\nBạn khỏe chứ?\n2\nĐường phố\n")
        self.assertEqual(result["pages"], {"1": ["Xin chào!\nBạn khỏe chứ?"], "2": ["Đường phố"]})
        self.assertTrue(result["marked"])

    def test_duplicate_marker_rejected(self):
        with self.assertRaises(ValueError):
            parse_translations("[PAGE 1]\nA\n[PAGE 1]\nB")

    def test_zero_page_rejected(self):
        with self.assertRaises(ValueError):
            parse_translations("[PAGE 0]\nA")

    def test_json_roundtrip_unicode_spaces_quotes(self):
        with tempfile.TemporaryDirectory(prefix="Tiếng Việt ' có dấu ") as tmp:
            path = Path(tmp) / "bản dịch.json"
            original = {"dịch": 'Xin chào!\n"Bạn" $() `', "values": [None, True, 1.5]}
            write_json(path, original)
            self.assertEqual(read_json(path), original)
            self.assertFalse(list(Path(tmp).glob(".json-*")))

    def test_utf16_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dịch.txt"
            path.write_text("Tiếng Việt", encoding="utf-16")
            self.assertEqual(import_text(path), "Tiếng Việt")

    def test_docx_runs_paragraphs_and_linebreaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bản dịch.docx"
            xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>[PAGE 1]</w:t></w:r></w:p><w:p><w:r><w:t>Xin </w:t></w:r><w:r><w:t>chào!</w:t><w:br/><w:t>Đường về</w:t></w:r></w:p></w:body></w:document>'
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            self.assertEqual(import_text(path), "[PAGE 1]\nXin chào!\nĐường về")

    def test_mapping_rejects_unknown_duplicate_and_nontext(self):
        manifest = {"regions": [{"id": "B001"}]}
        for mapping in [[{"id": "B002", "translation": "A"}],
                        [{"id": "B001", "translation": "A"}] * 2,
                        [{"id": "B001", "translation": 123}]]:
            with self.assertRaises(ValueError):
                checked_mapping(manifest, mapping)

    def test_blank_mapping_skips_region(self):
        self.assertEqual(checked_mapping({"regions": [{"id": "B001"}]}, [{"id": "B001", "translation": " "}]), [])

    def test_mapping_preserves_valid_font_role_and_rejects_unknown(self):
        manifest = {"regions": [{"id": "B001"}]}
        result = checked_mapping(manifest, [{"id": "B001", "translation": "Xin chào", "font_role": "shout"}])
        self.assertEqual(result[0]["font_role"], "shout")
        with self.assertRaises(ValueError):
            checked_mapping(manifest, [{"id": "B001", "translation": "Xin chào", "font_role": "invalid"}])

    def test_natural_sort(self):
        self.assertEqual(sorted(map(Path, ["10.png", "2.png", "1.png"]), key=natural_key), list(map(Path, ["1.png", "2.png", "10.png"])))


class GeometryTests(unittest.TestCase):
    def test_rectangle_inside_ellipse(self):
        mask = np.zeros((150, 230), np.uint8)
        cv2.ellipse(mask, (115, 75), (108, 67), 0, 0, 360, 255, -1)
        x, y, w, h = safe_rectangle(mask)
        self.assertTrue(np.all(mask[y:y+h, x:x+w] == 255))
        self.assertGreater(w * h, 9000)

    def test_closed_bubbles_from_geometry(self):
        gray = cv2.cvtColor(read_image(SAMPLE), cv2.COLOR_RGB2GRAY)
        bubbles = bubble_candidates(gray)
        self.assertEqual(len(bubbles), 2)
        self.assertTrue(all(b["safe"][2] > 170 for b in bubbles))

    def test_no_closed_bubble_for_page_background(self):
        self.assertEqual(bubble_candidates(np.full((300, 300), 255, np.uint8)), [])

    def test_reading_order_two_rows_and_directions(self):
        regions = [{"box": box, "id": key} for key, box in
                   [("left", [30, 20, 100, 100]), ("right", [200, 30, 100, 100]), ("bottom", [50, 260, 100, 100])]]
        self.assertEqual([r["id"] for r in reading_order(regions, True)], ["right", "left", "bottom"])
        self.assertEqual([r["id"] for r in reading_order(regions, False)], ["left", "right", "bottom"])

    def test_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancel = Path(tmp) / "cancel"
            cancel.touch()
            with self.assertRaises(Cancelled):
                check_cancel(cancel)

    def test_transparency_composited_on_white(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transparent.png"
            Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
            self.assertTrue(np.all(read_image(path) == 255))


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="manga thử nghiệm '")
        cls.folder = Path(cls.temp.name)
        cls.result = analyse(SAMPLE, cls.folder / "trang 1", "eng", True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_ocr_expected_two_bubbles(self):
        regions = self.result["regions"]
        self.assertEqual(len(regions), 2)
        self.assertIn("HELLO", regions[0]["source"])
        self.assertIn("WELCOME", regions[1]["source"])
        self.assertTrue(all(region["auto_clean"] for region in regions))

    def test_clean_only_mapped_bubble_preserves_outline_and_art(self):
        result = render_clean(self.result["manifest"], [{"id": "B001", "translation": "Xin chào", "clean": True}])
        original = read_image(SAMPLE)
        cleaned = read_image(Path(result["overlay"]).parent / "clean.png")
        overlay = np.array(Image.open(result["overlay"]))
        changed = np.any(original != cleaned, axis=2)
        self.assertTrue(np.any(changed))
        self.assertTrue(np.array_equal(original[overlay[:, :, 3] == 0], cleaned[overlay[:, :, 3] == 0]))
        # All changes are inside bubble 1, far from the outline and the second bubble.
        ys, xs = np.nonzero(changed)
        self.assertGreater(xs.min(), 530)
        self.assertLess(xs.max(), 795)
        self.assertGreater(ys.min(), 140)
        self.assertLess(ys.max(), 280)
        self.assertTrue(np.array_equal(original[400:], cleaned[400:]))

    def test_low_confidence_forces_manual_clean(self):
        path = self.folder / "uncertain"
        words = [{"text": "HELLO", "confidence": 22, "box": [555, 170, 100, 25]}]
        with patch("manga_ai.engine.ocr_words", return_value=words):
            result = analyse(SAMPLE, path)
        self.assertEqual(len(result["regions"]), 1)
        self.assertFalse(result["regions"][0]["auto_clean"])
        cleaned = render_clean(result["manifest"], [{"id": "B001", "translation": "A"}])
        self.assertEqual(cleaned["applied"], [])
        self.assertEqual(cleaned["skipped"], ["B001"])

    def test_sfx_outside_bubbles_never_creates_region(self):
        words = [{"text": "BOOM", "confidence": 95, "box": [200, 800, 120, 40]}]
        with patch("manga_ai.engine.ocr_words", return_value=words):
            result = analyse(SAMPLE, self.folder / "sfx")
        self.assertEqual(result["regions"], [])
        self.assertEqual(result["ignored_words"], 1)

    def test_existing_manifest_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            analyse(SAMPLE, self.folder / "trang 1")

    def test_batch_continues_after_bad_image_and_logs(self):
        folder = self.folder / "batch input"
        folder.mkdir()
        (folder / "1_bad.png").write_bytes(b"not an image")
        Image.open(SAMPLE).save(folder / "2_good.png")
        output = self.folder / "batch output"
        code = main(["scan", str(folder), "--out", str(output)])
        self.assertEqual(code, 1)
        log = read_json(next(output.glob("run_*/batch.json")))
        self.assertFalse(log[0]["ok"])
        self.assertTrue(log[1]["ok"])

    def test_worker_errors_write_response(self):
        request = self.folder / "request.json"
        response = self.folder / "response.json"
        write_json(request, {"operation": "not-supported"})
        process = subprocess.run([sys.executable, str(ROOT / "manga_typesetter.py"), "--request", str(request), "--response", str(response)], capture_output=True)
        self.assertEqual(process.returncode, 1)
        self.assertFalse(read_json(response)["ok"])

    def test_required_languages_installed(self):
        result = doctor()
        self.assertTrue(result["ready"])
        self.assertTrue(set(["eng", "jpn", "jpn_vert", "chi_sim", "chi_tra", "kor", "vie"]).issubset(result["languages"]))


if __name__ == "__main__":
    unittest.main()
