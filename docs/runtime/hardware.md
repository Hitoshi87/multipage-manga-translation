# Hardware dispatch cho Photoshop / 1107

Chạy `python manga_typesetter.py doctor` để xem `hardware`: OS, architecture, ONNX Runtime execution providers có trong package và cấu hình được chọn. Registry provider không bảo đảm từng node thực sự chạy GPU/ANE. Scan manifest và trace clean ghi providers đã đăng ký và fallback của process đó.

- macOS ARM64: nếu ORT có CoreML, 1107 dùng CoreML cho balloon, CTD và head; comic text detector tiếp tục CPU vì CoreML không khởi tạo được trong phép thử. Không dò tên chip M4; máy Apple ARM khác vẫn phải benchmark.
- Ngoài macOS ARM64: nếu ORT có CUDAExecutionProvider, thử CUDA; nếu không có, dùng CPU. Lỗi khởi tạo/suy luận GPU sẽ thử lại CPU, ghi log. Các ONNX model khác chỉ chọn CUDA khi được gọi, không tự bật thêm model.
- CPU: đặt `MANGA_ACCEL=cpu` trong môi trường của tiến trình Photoshop/worker để rollback. CoreML compile cache phân theo SHA-256 model, ORT, phiên bản kernel và kiến trúc.

Windows/NVIDIA: cần môi trường `.venv/Scripts/python.exe`, Tesseract trong PATH, ONNX Runtime GPU build phù hợp driver/CUDA/cuDNN, không cài chồng hai gói runtime tùy tiện. Xem bảng chính thức https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html. Launcher Windows và chọn/fallback CUDA mới được unit test giả lập, chưa chạy native Windows/NVIDIA. Không tuyên bố tốc độ/độ chính xác trên NVIDIA cho đến khi đo end-to-end.

MPS và CUDA PyTorch của các model tùy chọn (Comic Text Mask, AOT, Magi) chưa được tối ưu trong thay đổi này. Không dùng thêm weights, không chạy lại model tự động. Worker vẫn khởi tạo process theo mỗi RPC; CoreML cache không làm session sống qua nhiều trang.
