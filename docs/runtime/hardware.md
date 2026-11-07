# Hardware dispatch cho Photoshop / 1107

Chạy `python manga_typesetter.py doctor` để xem `hardware`: OS, architecture, ONNX Runtime execution providers có trong package và cấu hình được chọn. Registry provider không bảo đảm từng node thực sự chạy GPU/ANE. Scan manifest và trace clean ghi providers đã đăng ký và fallback của process đó.

- macOS ARM64: nếu ORT có CoreML, 1107 dùng CoreML cho balloon, CTD và head; comic text detector tiếp tục CPU vì CoreML không khởi tạo được trong phép thử. Không dò tên chip M4; máy Apple ARM khác vẫn phải benchmark.
- Ngoài macOS ARM64: nếu ORT có CUDAExecutionProvider, thử CUDA; nếu không có, dùng CPU. Lỗi khởi tạo/suy luận GPU sẽ thử lại CPU, ghi log. Các ONNX model khác chỉ chọn CUDA khi được gọi, không tự bật thêm model.
- Chính sách phần cứng (Hardware Policy): `coreml` chỉ áp dụng cho các model đã kiểm chứng (balloon, ctd, head); model khác chạy CPU vì ép CoreML làm chậm. Hỗ trợ `auto`, `cpu`, `coreml`, `cuda`. Có thể chọn trực tiếp từ dropdown **Tăng tốc** trong giao diện Photoshop, truyền tham số `--accel` qua CLI hoặc gán biến môi trường `MANGA_ACCEL`. CoreML compile cache phân theo SHA-256 model, ORT, phiên bản kernel và kiến trúc.
- Bộ nhớ & Batch Processing: Photoshop tự động gọi `app.purge(PurgeTarget.ALLCACHES)` sau mỗi trang trong batch loop để tránh phình RAM/Scratch Disk; thư mục tạm `work/jobs/` được dọn dẹp tự động khi RPC thành công.

Windows/NVIDIA: cần môi trường `.venv/Scripts/python.exe`, Tesseract trong PATH, gói `onnxruntime-gpu` (thay vì `onnxruntime` CPU) phù hợp driver/CUDA/cuDNN. Xem bảng chính thức https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html. Khi có CUDA, PyTorch (Comic Text Mask, AOT) tự động nhận diện thiết bị `cuda`.

Lưu ý hiệu năng Apple Silicon: mặc định `auto` (CoreML cho các model đã kiểm chứng) là cấu hình được thử trên M4. Chế độ `cpu` là dự phòng khi CoreML lỗi hoặc máy nóng; việc CPU ổn định hơn khi chạy chương dài chưa được đo, nên so sánh `seconds` trong `trace.json` giữa hai chế độ trước khi kết luận.
