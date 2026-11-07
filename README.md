# Multipage Manga Translation

**MangaTypesetter Lite · Engine 1107** — công cụ local cho Photoshop: nhận diện bong bóng/chữ, OCR, clean, ghép bản dịch và xuất PSD giữ layer.

Luồng chính: **ảnh gốc → nhận diện & OCR → duyệt vùng → clean → typeset → PSD/PDF/JPEG CMYK**. Bạn cung cấp bản dịch; ứng dụng không tự dịch bằng LLM. Vùng khó có thể giữ lại để clean tay.

| Thành phần | Bản hiện tại |
| --- | --- |
| Giao diện Photoshop | `1107-ui.4` |
| Engine tùy chọn | `1107-shadow-0.4` — output cần duyệt |
| Engine mặc định | `baseline-1` |
| Máy đã kiểm thử thực tế | Apple M4, 16 GB, macOS ARM64, Photoshop 2025 |

## Cài đặt trên macOS

Cần Photoshop desktop hỗ trợ ExtendScript, Homebrew và Python 3.12.

```sh
git clone https://github.com/Hitoshi87/multipage-manga-translation.git
cd multipage-manga-translation
bash setup_macos.command --install
.venv/bin/python -m pip install -r requirements-ai.txt
.venv/bin/python scripts/download_models.py --profile 1107 --download
.venv/bin/python manga_typesetter.py doctor
```

Repo **không chứa weights hoặc ảnh truyện**. Lệnh download tải riêng bốn ONNX model của profile 1107, kiểm tra kích thước và SHA-256 theo revision được pin. Inference không tự tải weights. Các model nghiên cứu/LaMa/AOT/Baberu/Koharu là tùy chọn, không cần cài tất cả để chạy 1107. Xem [model manifest](models/manifest.json), [hướng dẫn weights](models/README.md) và [notices upstream](models/NOTICE.md).

`requirements*.lock.txt` ghi môi trường đã đo trên Mac; dùng các file requirements thường cho môi trường khác để pip chọn wheel tương thích.

## Chạy trong Photoshop

1. Mở **ảnh gốc**, chọn File → Scripts → Browse → `Photoshop_Typeset.jsx`.
2. Tab **Nguồn & nhận diện**: chọn tài liệu/folder và OCR đúng chữ gốc, ví dụ `jpn_vert` cho tiếng Nhật dọc.
3. Tab **Engine clean**: chọn `1107-shadow-0.4` để dùng engine mới; Baseline vẫn là mặc định. **Xem thử clean theo engine đang chọn** hiển thị đúng output của engine đó.
4. Kiểm tra mapping và lựa chọn clean từng region. Có thể chỉ clean cả chương, hoặc nhập bản dịch để typeset. Chế độ đã clean thủ công chỉ tạo chữ.
5. Tab **Typeset & xuất**: chọn PSD/PDF/JPEG. Tùy chọn CMYK dùng Color Settings hiện tại của Photoshop; chọn ICC theo nhà in. PNG preview vẫn RGB.

Mỗi lần clean tạo bản sao và layer riêng. `review` nghĩa là cần duyệt **output đã tạo**, không đồng nghĩa chưa chạy. Bỏ chọn một vùng được giữ nguyên; mapping Baseline không mang cờ `force` sang engine khác. Job/manifest/trace ghi riêng UI và engine version. Dữ liệu ghim version cũ sẽ báo không khớp; scan lại từ ảnh gốc để dùng engine mới.

Tab **Thử nghiệm nâng cao** chứa các công cụ tùy chọn. Công cụ mask/inpainting của Baseline bị khóa khi chọn 1107; checkbox ở tab này không thay thuật toán của engine đang chọn.

## Engine 1107 hiện làm gì?

Engine có các stage general recovery, border validation, text ownership và flat-background finish. Polygon là một tín hiệu hình học; ownership giúp hạn chế lấy chữ của bubble kế bên. Nền phẳng được dựng theo màu giấy cục bộ; text mask, vùng được bảo vệ và compositing mask giữ riêng.

Bản 0.4 sửa hình chữ nhạt còn lại sau fill theo stencil: loại toàn bộ text envelope khỏi donor, dựng trường nền liên tục trong vùng chữ đã có ownership/mask, giữ bảo vệ nét tối chưa xác minh, head và các region khác. Preview và clean từ JSX gọi cùng backend. [Changelog](CHANGELOG.md) · [Kiểm chứng vệt chữ 0.4](docs/validation/1107_flat_field.md).

Kết quả đã được thử trên mẫu truyện thật và Photoshop CMYK; chưa có ground truth độc lập toàn volume. Engine 1107 tiếp tục cần duyệt, nhất là bubble trong suốt, chữ sát artwork hoặc ảnh nén mạnh. Không dùng số proposal/mask pixels làm tỷ lệ chính xác.

## Hardware và bộ nhớ

Runtime detect OS/architecture/provider thay vì hardcode tên M4. macOS ARM64 thử CoreML cho các ONNX model đã kiểm nghiệm; model không phù hợp giữ CPU. Ngoài macOS ARM64, thử CUDA khi package/provider có sẵn, rồi CPU fallback khi accelerator lỗi. `MANGA_ACCEL=cpu` cho phép chạy CPU.

Windows/NVIDIA có đường xử lý nhưng chưa smoke test native. Không cam kết tốc độ CUDA hoặc GPU/ANE cho mọi node. Worker chạy theo từng RPC; cache CoreML không giữ toàn bộ model sống xuyên chapter. [Chi tiết hardware](docs/runtime/hardware.md).

## Kiểm tra và đóng gói

```sh
python -m unittest discover -s tests -q
node tests/test_windows_launcher.js
node tests/test_engine_review_ui.js
node tests/test_ui_modes.js
node tests/chapter_dialog.js
node tests/test_native_smoke.js
python scripts/build_source_bundle.py --check
```

Unit tests dùng fixture tổng hợp; CI không tải weights hoặc ảnh truyện. [Photoshop smoke test có cấu hình local](docs/validation/photoshop-smoke.md) kiểm tra scan → hộp duyệt → engine → layer → mở lại PSD; chất lượng ảnh vẫn cần xem riêng.

Bản phát hành chỉ gồm runtime, tool được duy trì, test chạy độc lập và tài liệu. Runner benchmark lịch sử dùng dữ liệu riêng được giữ ở workspace phát triển. `work/`, `output/`, `.venv*`, credentials và weights không thuộc Git. `scripts/clean_generated.py` chỉ dọn code cache/Finder metadata, mặc định dry-run.

[Đóng góp](CONTRIBUTING.md) · [Cấu trúc project](docs/architecture/layout.md) · [Data contracts](docs/architecture/data_contracts.md) · [Thêm engine](manga_ai/engines/README.md).

## License

Source code chưa được cấp license chung. Model và thành phần upstream có điều khoản riêng trong [models/NOTICE.md](models/NOTICE.md); không gán license source thay cho license weights. Không phân phối weights trong Git.
