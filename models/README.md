# Weights ngoài Git

Git chỉ lưu manifest/checksum và notices. Weights được tải từ upstream về thư mục local `models/`, không có trong clone GitHub.

```sh
python scripts/download_models.py --profile 1107          # kiểm tra offline
python scripts/download_models.py --profile 1107 --download
```

Profile 1107 tải bốn ONNX model (bubble, text detector, CTD, head) và Magi (7 file, ~2 GB, dùng cho thứ tự panel). Lệnh downloader không cài thư viện, không thực thi code từ model và không đổi weights đúng checksum. Phiên bản upstream được pin trong URL; file tải tạm chỉ thay thế sau khi đúng kích thước và SHA-256. Không tự tải khi đang inference.

Các profile `preview`, `assist`, `aot` là tùy chọn; Magi/Qwen và weights nghiên cứu không nằm trong profile 1107. Xem NOTICE.md và điều khoản upstream trước khi sử dụng/phân phối. Không coi source code license là license của weights. `--model-dir` chỉ đổi nơi downloader ghi file; runtime hiện vẫn đọc project/models, chưa hỗ trợ model directory tùy ý.
