# Multipage Manga Translation

**MangaTypesetter Lite · Engine 1107** — công cụ local chạy trong Photoshop: nhận diện bong bóng/chữ, OCR, clean, ghép bản dịch và xuất PSD giữ layer.

```
ảnh gốc → nhận diện & OCR → duyệt vùng → clean → typeset → PSD / PDF / JPEG
```

Bạn cung cấp bản dịch; ứng dụng không tự dịch bằng LLM. Vùng khó có thể giữ lại để clean tay. Mọi xử lý chạy trên máy bạn, không gửi ảnh ra ngoài.

| Thành phần | Bản hiện tại |
| --- | --- |
| Giao diện Photoshop | `1107-ui.4` |
| Engine tùy chọn | `1107-shadow-0.5` — output cần duyệt |
| Engine mặc định | `baseline-1` |
| Đã kiểm thử thực tế | Apple M4 (macOS ARM64, CoreML), NVIDIA RTX 3050 (Linux, CUDA). Windows/NVIDIA chưa xác thực native |

## Mục lục

1. [Yêu cầu chung](#1-yêu-cầu-chung)
2. [Cài đặt lần đầu — macOS (Apple Silicon / Intel)](#2-cài-đặt-lần-đầu--macos-apple-silicon--intel)
3. [Cài đặt lần đầu — NVIDIA CUDA (Windows / Linux)](#3-cài-đặt-lần-đầu--nvidia-cuda-windows--linux)
4. [Tải model weights](#4-tải-model-weights)
5. [Kiểm tra môi trường](#5-kiểm-tra-môi-trường)
6. [Luồng sử dụng trong Photoshop](#6-luồng-sử-dụng-trong-photoshop)
7. [Chọn phần cứng và tối ưu hiệu năng](#7-chọn-phần-cứng-và-tối-ưu-hiệu-năng)
8. [Xuất file và dung lượng](#8-xuất-file-và-dung-lượng)
9. [Engine 1107 làm gì](#9-engine-1107-làm-gì)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Phát triển, kiểm thử, đóng gói](#11-phát-triển-kiểm-thử-đóng-gói)

## 1. Yêu cầu chung

- Photoshop desktop có ExtendScript (File → Scripts → Browse).
- Python **3.12** trong thư mục `.venv` ngay tại gốc project (Photoshop chỉ gọi `.venv/bin/python` hoặc `.venv\Scripts\python.exe`).
- Tesseract OCR kèm ngôn ngữ `eng`, `jpn`, `jpn_vert`, `chi_sim`, `chi_tra`, `kor`, `vie`.
- Khoảng vài GB trống cho weights và môi trường Python.

Repo **không chứa weights hoặc ảnh truyện**.

```sh
git clone https://github.com/Hitoshi87/multipage-manga-translation.git
cd multipage-manga-translation
```

## 2. Cài đặt lần đầu — macOS (Apple Silicon / Intel)

Cần [Homebrew](https://brew.sh). Script cài `python@3.12`, `tesseract`, `tesseract-lang`, tạo `.venv` và cài dependency cơ bản.

```sh
# 1. Môi trường, Tesseract và dependency cơ bản
bash setup_macos.command --install

# 2. ONNX Runtime (có CoreML provider trên macOS ARM64)
.venv/bin/python -m pip install -r requirements-ai.txt

# 3. Weights profile 1107
.venv/bin/python manga_typesetter.py download-models --profile 1107

# 4. Kiểm tra
.venv/bin/python manga_typesetter.py doctor
```

Ghi chú Apple Silicon:

- CoreML được dùng cho `balloon`, `ctd`, `head`; các model còn lại chạy CPU. Không cần cấu hình thêm.
- **Lần chạy đầu chậm hơn**: CoreML biên dịch model và lưu cache tại `~/Library/Caches/MangaTypesetterLite/CoreML`. Các lần sau dùng lại cache.
- Chạy cả chương dài (30–100 trang) trên máy ít RAM/MacBook Air: chuyển **Tăng tốc → CPU** nếu máy nóng hoặc chậm dần.
- Muốn dùng công cụ preview thử nghiệm (Comic Text Mask, AOT): `.venv/bin/python scripts/setup_preview_models.py`.
- Lần đầu Photoshop có thể hỏi quyền cho script chạy Python; hãy cho phép.

## 3. Cài đặt lần đầu — NVIDIA CUDA (Windows / Linux)

Yêu cầu: card NVIDIA, driver mới, **CUDA 12.x + cuDNN 9** (cài hệ thống hoặc qua pip như bên dưới), Tesseract trong `PATH` kèm đủ ngôn ngữ ở mục 1.

- Linux (Debian/Ubuntu): `sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-jpn tesseract-ocr-jpn-vert tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-kor tesseract-ocr-vie`
- Windows: cài [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki), chọn đủ gói ngôn ngữ, thêm vào `PATH`.

```sh
# 1. Tạo môi trường ảo
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Dependency cơ bản
pip install -r requirements.txt

# 3. ONNX Runtime GPU — GỠ bản CPU trước, hai gói xung đột nhau
pip uninstall -y onnxruntime
pip install "onnxruntime-gpu>=1.23.2,<2"

# 4. Thư viện CUDA qua pip (bỏ qua nếu đã cài CUDA 12 + cuDNN 9 ở hệ thống)
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12 \
            nvidia-cufft-cu12 nvidia-curand-cu12

# 5. (Tùy chọn) PyTorch CUDA cho Comic Text Mask / AOT inpainting
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 6. Weights profile 1107 và kiểm tra
python manga_typesetter.py download-models --profile 1107
python manga_typesetter.py doctor
```

Ghi chú CUDA:

- Trong `doctor`, mục `hardware.available_onnx_providers` phải có `CUDAExecutionProvider`. Nếu không, bạn đang dùng `onnxruntime` CPU hoặc thiếu thư viện CUDA/cuDNN.
- Runtime tự nạp thư viện `nvidia/*/lib` cài bằng pip. Khi lỗi khởi tạo hoặc hết VRAM, nó tự fallback CPU và ghi log.
- Bảng tương thích phiên bản chính thức: [ORT CUDA Execution Provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
- Windows/NVIDIA chưa được xác thực native; hãy báo lại nếu gặp lỗi.

## 4. Tải model weights

```sh
python manga_typesetter.py download-models --profile 1107 --check-only   # kiểm tra offline
python manga_typesetter.py download-models --profile 1107                # tải về models/
```

Profile 1107 tải bốn ONNX model (bubble, text detector, CTD, head), kiểm tra kích thước và SHA-256 theo revision được pin. Inference không bao giờ tự tải weights. Các profile `preview`, `assist`, `aot` là tùy chọn. Xem [model manifest](models/manifest.json), [hướng dẫn weights](models/README.md), [notices upstream](models/NOTICE.md).

`requirements*.lock.txt` ghi môi trường đã đo trên Mac; môi trường khác dùng file requirements thường để pip chọn wheel tương thích.

## 5. Kiểm tra môi trường

```sh
.venv/bin/python manga_typesetter.py doctor        # Windows: .venv\Scripts\python.exe
```

Báo cáo `ready: true` nghĩa là đủ package, Tesseract và ngôn ngữ OCR. Bạn cũng có thể chạy `Photoshop_CheckPython.jsx` trong Photoshop để kiểm tra đường Photoshop → Python; kết quả lưu ở `work/environment.json`.

## 6. Luồng sử dụng trong Photoshop

1. **Mở ảnh gốc** (hoặc chọn folder cả chương), rồi File → Scripts → Browse → `Photoshop_Typeset.jsx`.
2. **Tab Nguồn & nhận diện**: chọn tài liệu/folder, ngôn ngữ OCR đúng với chữ gốc (ví dụ `jpn_vert` cho tiếng Nhật dọc), mức quét, và **Tăng tốc** (xem [mục 7](#7-chọn-phần-cứng-và-tối-ưu-hiệu-năng)). Bấm quét.
3. **Tab Engine clean**: chọn `1107-shadow-0.5` hoặc Baseline (mặc định). **Xem thử clean theo engine đang chọn** hiển thị đúng output của engine đó, cùng backend với clean thật.
4. **Duyệt vùng**: kiểm tra mapping và bỏ chọn vùng muốn giữ nguyên. Vùng bị bỏ chọn không bị đụng tới. Mapping Baseline không mang cờ `force` sang engine khác.
5. **Clean**: có thể chỉ clean cả chương, hoặc clean rồi nhập bản dịch để typeset. Chế độ "đã clean thủ công" chỉ tạo chữ. Mỗi lần clean tạo bản sao và layer riêng.
6. **Tab Typeset & xuất**: chọn font, nhập bản dịch, chọn PSD/PDF/PNG/JPEG. Tùy chọn CMYK dùng Color Settings hiện tại của Photoshop; chọn ICC theo nhà in. PNG preview luôn RGB.

Lưu ý:

- `review` nghĩa là cần duyệt **output đã tạo**, không phải chưa chạy.
- Job/manifest/trace ghi riêng UI và engine version. Dữ liệu ghim version cũ sẽ báo không khớp; scan lại từ ảnh gốc để dùng engine mới.
- Tab **Thử nghiệm nâng cao** chứa công cụ tùy chọn. Công cụ mask/inpainting của Baseline bị khóa khi chọn 1107.

### Chạy bằng CLI (không cần Photoshop)

```sh
python manga_typesetter.py --accel cpu scan /duong/dan/anh --out /duong/dan/xuat
```

`--accel` đặt trước tên lệnh con. Có thể dùng biến môi trường `MANGA_ACCEL` thay thế.

## 7. Chọn phần cứng và tối ưu hiệu năng

Dropdown **Tăng tốc** (tab Nguồn & nhận diện) được lưu cho các phiên sau. Tương đương CLI: `--accel` hoặc `MANGA_ACCEL`.

| Chế độ | Hành vi |
| --- | --- |
| `auto` | Tự nhận OS/thiết bị. macOS ARM64: CoreML cho `balloon`, `ctd`, `head`. Có `onnxruntime-gpu`: CUDA. Còn lại: CPU |
| `cpu` | Chạy hoàn toàn trên CPU. Ổn định, mát máy; nên dùng cho chương dài trên Mac ít RAM |
| `coreml` | Như `auto` trên Mac nhưng ép dùng CoreML cho các model đã kiểm chứng; model khác vẫn chạy CPU |
| `cuda` | Ép CUDA cho ONNX và PyTorch; fallback CPU khi lỗi |

Hướng dẫn chọn nhanh: Mac dùng `auto`; Mac nóng/chậm dần khi batch dùng `cpu`; PC NVIDIA dùng `auto` hoặc `cuda`. Không có số liệu nào bảo đảm từng node thật sự chạy trên GPU/ANE; xem `hardware` trong `trace.json` để biết provider đã đăng ký và fallback.

Batch nhiều trang: script tự gọi `app.purge(PurgeTarget.ALLCACHES)` sau mỗi trang và dọn `work/jobs/` khi RPC thành công (chỉ giữ log khi lỗi). Chi tiết: [hardware và dispatch](docs/runtime/hardware.md).

## 8. Xuất file và dung lượng

- **PSD**: giữ layer, nhúng profile màu.
- **Photoshop PDF**: giữ layer và dữ liệu chỉnh sửa; ảnh nén JPEG chất lượng cao, không nhúng thumbnail, để dung lượng gần với lưu tay. PDF giữ layer vẫn nặng hơn PDF đã flatten vì nhúng cả dữ liệu PSD.
- **JPEG**: flatten, chất lượng 10; **PNG**: RGB.

## 9. Engine 1107 làm gì

Các stage: general recovery, border validation, text ownership, flat-background finish và role guard. Polygon là một tín hiệu hình học; ownership hạn chế việc lấy chữ của bubble kế bên. Nền phẳng được dựng theo màu giấy cục bộ. Role guard giữ nguyên ảnh gốc cho chữ tự do và banner chữ nhật mang chữ display dày. Bong bóng nối liền nhiều phần được tách thành các thùng thoại riêng khi OCR tiếng Nhật xác nhận từng phần.

Kết quả đã thử trên mẫu truyện thật và Photoshop CMYK; chưa có ground truth độc lập toàn volume. 1107 vẫn cần duyệt, nhất là bubble trong suốt, chữ sát artwork hoặc ảnh nén mạnh. [Changelog](CHANGELOG.md) · [Kiểm chứng vệt chữ 0.4](docs/validation/1107_flat_field.md) · [Quy trình tiến hóa engine](docs/architecture/engine_evolution.md).

## 10. Xử lý sự cố

| Triệu chứng | Cách xử lý |
| --- | --- |
| "Thiếu Python trong .venv" | Tạo `.venv` ở gốc project theo mục 2 hoặc 3 |
| `doctor` báo thiếu ngôn ngữ OCR | Cài thêm gói Tesseract (đặc biệt `jpn_vert`, `vie`) |
| Không thấy `CUDAExecutionProvider` | `pip uninstall onnxruntime`, cài lại `onnxruntime-gpu`, kiểm tra CUDA 12/cuDNN 9 |
| Mac chậm dần khi batch | Đổi Tăng tốc sang `CPU`; đóng bớt ứng dụng nặng |
| Lần đầu chạy rất chậm trên Mac | Bình thường: CoreML đang biên dịch cache |
| "Python không phản hồi trong 180 giây" | Xem `worker.log` trong thư mục job; thử `cpu` |
| Báo dữ liệu version cũ | Scan lại từ ảnh gốc |

## 11. Phát triển, kiểm thử, đóng gói

```sh
python -m unittest discover -s tests -q
node tests/test_windows_launcher.js
node tests/test_engine_review_ui.js
node tests/test_ui_modes.js
node tests/chapter_dialog.js
node tests/test_native_smoke.js
python scripts/build_source_bundle.py --check
```

Unit test dùng fixture tổng hợp; CI không tải weights hoặc ảnh truyện. [Photoshop smoke test](docs/validation/photoshop-smoke.md) kiểm tra scan → hộp duyệt → engine → layer → mở lại PSD; chất lượng ảnh vẫn cần xem riêng. `work/`, `output/`, `.venv*`, credentials và weights không thuộc Git.

[Đóng góp](CONTRIBUTING.md) · [Cấu trúc project](docs/architecture/layout.md) · [Data contracts](docs/architecture/data_contracts.md) · [Thêm engine](manga_ai/engines/README.md).

## License

Source code chưa được cấp license chung. Model và thành phần upstream có điều khoản riêng trong [models/NOTICE.md](models/NOTICE.md); không gán license source thay cho license weights. Không phân phối weights trong Git.
