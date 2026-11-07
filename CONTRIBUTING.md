# Phát triển và kiểm thử

Dùng Python 3.12 và Node.js 22. Cài `requirements.txt` và `requirements-ai.txt` trong virtualenv; unit tests không cần weights. Một số test OCR cần Tesseract và bộ ngôn ngữ Nhật/Trung/Hàn như trong `.github/workflows/tests.yml`.

```sh
python -m unittest discover -s tests -q
node tests/test_windows_launcher.js
node tests/test_engine_review_ui.js
node tests/test_ui_modes.js
node tests/chapter_dialog.js
node tests/test_native_smoke.js
python scripts/build_source_bundle.py --check
```

## Thay đổi engine

- Registry trong `manga_ai/engines/__init__.py` là nguồn lựa chọn cho JSX. Handler, registry, job và report phải ghi cùng version; không tự fallback version.
- Giữ region ID, lựa chọn bỏ clean và phân biệt model confidence/OCR evidence với điểm heuristic hoặc clean decision.
- Không lấy bubble polygon làm text mask. Mọi pixel sửa phải thuộc compositing mask; head/artwork guard cần test riêng.
- Thay thuật toán phải có regression đúng nguồn ảnh, config và model hash; so sánh cả composite Photoshop, không chỉ CLI hoặc tổng số proposal.
- Giữ Baseline mặc định đến khi thay đổi mặc định được duyệt. Các thay đổi giao diện, cache và xuất file không được lặng lẽ đổi quyền clean.

Xem [engine API](manga_ai/engines/README.md), [data contracts](docs/architecture/data_contracts.md) và [native smoke](docs/validation/photoshop-smoke.md).

## Ranh giới bản phát hành

`scripts/build_source_bundle.py` chọn source theo allowlist. Runtime Python được giữ nguyên; chỉ tool được duy trì, unit/Node tests và hai native smoke portable được xuất. Các runner P0.x, script benchmark gắn page ID, output đã duyệt và test cần snapshot riêng không thuộc source public. Test component của benchmark v2 đã nghỉ cũng không thuộc bộ kiểm tra phát hành.

Tạo package mới bằng `python scripts/build_source_bundle.py --out work/releases/source`. Folder đích phải chưa tồn tại; đi kèm ZIP và manifest SHA-256. Chạy tests ngay trong bản export để bắt thiếu file/dependency.

Không commit weights, manga, PSD, credentials, model compile cache hoặc đường dẫn riêng của máy. Gắn revision/hash/notice cho model mới; inference không tự tải hoặc thực thi model code.
