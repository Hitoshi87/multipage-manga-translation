# Cài worker và model trên Windows, macOS, Linux

Source GitHub không chứa weights và không chứa `.venv`. Giải nén đầy đủ source vào một thư mục có quyền ghi, giữ cấu trúc `scripts/`, `models/manifest.json`, `manga_ai/`. Mỗi máy/hệ điều hành cần tạo `.venv` mới. Dùng Python **3.12 64-bit**, có kết nối HTTPS tới PyPI, GitHub và Hugging Face khi cài.

Bộ cài mặc định dùng ONNX Runtime CPU, chạy được không cần NVIDIA. Trên macOS wheel ONNX Runtime cung cấp CoreML khi phần cứng/model hỗ trợ. Model được tải theo manifest ghim revision, kích thước và SHA-256. File lỗi không thay thế file đang có; chạy lại để tiếp tục các file còn thiếu.

## Windows

1. Cài [Python 3.12](https://www.python.org/downloads/windows/) bản 64-bit, bật Python Launcher (`py`). Kiểm tra `py -3.12 --version`.
2. Cài Tesseract theo [hướng dẫn của dự án Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html). Tesseract là chương trình riêng, `pip install pytesseract` không cài chương trình này.
3. Mở CMD tại thư mục project và chạy:

```bat
setup_windows.cmd --install
.venv\Scripts\python.exe manga_typesetter.py doctor --profile auto --verify-models
```

Tool tìm Tesseract qua `PATH`, `ProgramFiles`, `ProgramFiles(x86)` và `LOCALAPPDATA`. Nếu cài nơi khác, đặt biến môi trường người dùng `TESSERACT_CMD` bằng đường dẫn đầy đủ tới `tesseract.exe` rồi mở lại Photoshop. Trong CMD hiện tại có thể kiểm tra bằng:

```bat
set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
.venv\Scripts\python.exe manga_typesetter.py doctor --profile auto
```

Bộ cài tải đủ 7 ngôn ngữ về `models/tessdata`. Khi đủ các file và không có cấu hình ghi đè, worker dùng thư mục này. Nếu bạn đã đặt `TESSDATA_PREFIX` đến thư mục khác thiếu ngôn ngữ, bỏ biến đó hoặc bổ sung ngôn ngữ ở vị trí đã chọn. Cài Microsoft Visual C++ Runtime nếu import ONNX báo thiếu DLL, theo [hướng dẫn ONNX Runtime](https://onnxruntime.ai/docs/install/).

## macOS

Cài [Homebrew](https://brew.sh), sau đó:

```sh
bash setup_macos.command --install
.venv/bin/python manga_typesetter.py doctor --profile auto --verify-models
```

Wrapper cài `python@3.12`, Tesseract qua Homebrew rồi gọi bộ cài chung. Không cần cài PyTorch cho profile `auto`.

## Linux

Trên Ubuntu 24.04 có thể chuẩn bị bằng:

```sh
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv tesseract-ocr
bash setup_linux.sh --install
.venv/bin/python manga_typesetter.py doctor --profile auto --verify-models
```

Distro khác: cài Python 3.12 + venv và Tesseract bằng trình quản lý gói tương ứng. Bộ cài Python không tự chạy `sudo`. Linux hỗ trợ worker/CLI, không có bản Photoshop desktop Linux.

## Profile và kiểm tra

| Profile | Nội dung |
| --- | --- |
| `auto` (mặc định) | Balloon + text detector, CTD, LaMa, bảo vệ đầu/mặt, Baberu và 7 ngôn ngữ Tesseract |
| `1107` | 4 model nhận diện/bảo vệ và Magi; không thay thế gói auto |
| `assist` | Head, Baberu, E5 và Magi |
| `preview` | CTD, Comic Text Mask, LaMa, Koharu |
| `aot` | AOT inpainting |
| `tessdata` | eng, jpn, jpn_vert, chi_sim, chi_tra, kor, vie |
| `all` | Tất cả model trong manifest (không bao gồm Qwen/MLX) |

Chạy wrapper với `--install --profile preview` để cài gói auto cùng profile tùy chọn. Các lệnh `scripts/setup_*.py` cũ chuyển tiếp tới bộ cài chung. Qwen/MLX vẫn là tùy chọn riêng cho Apple, không thuộc gói đa nền tảng.

Không có `--install`: chỉ kiểm tra, không cài hay tải. `--plan`: in cấu hình dự kiến, không sửa máy. Nếu thư viện hoặc model thiếu, setup/doctor trả mã lỗi; không báo hoàn thành giả. `download-models --check-only` xác minh checksum offline. GUI kiểm tra nhanh kích thước để phát hiện ZIP lỗi/Git LFS pointer; dùng doctor với `--verify-models` để xác minh toàn bộ hash.

## CUDA tùy chọn

Hoàn thành bản CPU trước. Bộ cài chuẩn không tự chọn CUDA theo tên card, không cài đồng thời `onnxruntime` và `onnxruntime-gpu`. Nếu chủ động chuyển môi trường sang GPU, gỡ bản CPU và cài bản GPU theo [ma trận CUDA/cuDNN chính thức](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html). Sau đó kiểm tra:

```sh
python -c "import onnxruntime as o; print(o.get_available_providers())"
```

Cần có `CUDAExecutionProvider`; provider xuất hiện chưa chứng minh mọi model chạy GPU. Xem báo cáo hardware của doctor và log fallback lúc chạy. Bộ cài chuẩn từ chối ghi đè môi trường đã có `onnxruntime-gpu`; giữ môi trường tùy chỉnh riêng hoặc đổi tên `.venv` trước khi cài lại CPU.

## Lỗi thường gặp

- **Tải model thất bại:** xem tên file lỗi; kiểm tra proxy/firewall, dung lượng trống rồi chạy lại cùng lệnh. Tối đa 3 lần thử mỗi file; file đã xác minh không tải lại.
- **`.venv` sai hệ điều hành/Python:** đổi tên thư mục đó, chạy lại bộ cài; không chép `.venv` giữa máy.
- **`No matching distribution`:** kiểm tra Python 3.12 64-bit và wheel hỗ trợ kiến trúc máy. Không dùng Python 32-bit; Windows ARM cần môi trường x64 tương thích hoặc tự xác minh wheel riêng.
- **Model đủ nhưng không dịch:** kiểm tra API key/host/model dịch trong tool. API dịch không phải model local.
- **Thông báo checksum sai:** chạy lại downloader, không bỏ qua checksum và không tải file HTML rồi đổi đuôi thành ONNX.
