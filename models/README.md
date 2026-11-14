# Weights ngoài Git

Git chỉ lưu manifest/checksum và notices. ZIP/clone từ GitHub không có weights. Chạy bộ cài hệ điều hành với `--install` để cài thư viện **và** đủ model profile `auto`.

```sh
# Chạy bằng Python trong .venv của máy hiện tại
python scripts/download_models.py --profile auto
python scripts/download_models.py --profile auto --download
```

Downloader là công cụ chỉ dùng thư viện chuẩn, không cài dependency. Mặc định kiểm tra offline; `--download` cho phép tải. URL được pin revision; xác minh cả kích thước và SHA-256 trước khi thay file. Tải thất bại có thể chạy lại, file hợp lệ được giữ nguyên. Không tải trong lúc inference.

`auto` gồm balloon, text detector, CTD, head, LaMa, 4 file Baberu và 7 ngôn ngữ Tesseract. Các profile cũ `1107`, `assist`, `preview`, `aot` giữ nguyên nội dung; **1107 và assist có Magi (~2 GB)**. `all` bao gồm mọi file manifest; Qwen/MLX vẫn cài riêng. Magi có điều khoản phi thương mại; xem NOTICE.md trước khi sử dụng/phân phối.

`--model-dir` chỉ đổi đích của downloader; worker vẫn đọc `project/models`. Xem [hướng dẫn cài đặt](../docs/runtime/installation.md) để biết lệnh cụ thể từng OS và cách kiểm tra thư viện/DLL thực tế.
