# Changelog

## 1107-ui.6 — 2026-11-14

- Thêm style theo bộ truyện, nhập JSON TypeR và lựa chọn xuống dòng trong Rà soát nhanh; tự xếp hạng phương án khi typeset.
- Lưu văn phong/quy tắc xưng hô theo bộ truyện, bộ nhớ thoại trước có giới hạn và lượt kiểm tra ngữ cảnh tùy chọn sau mỗi nhóm (thêm lượt API). Giữ cấu hình lượt cũ khi tiếp tục.
- Auto leading đo chiều cao chữ trong câu thực tế. Chế độ Đồng đều được thu nhỏ có kiểm soát đến 65% cỡ chuẩn cho bóng hẹp; Cố định tuyệt đối vẫn từ chối câu không vừa.
- Chữ vẫn không vừa được giữ ẩn thay vì kéo rộng đè tranh. Sửa hàng loạt dùng cùng bộ dàn chữ, giữ trạng thái ẩn của vùng chưa clean và cập nhật metadata bên cạnh PDF/PSD.
- Báo cáo ghi nhận các vùng phải dùng cỡ nhỏ. Đã kiểm tra dàn lại 12 vùng của ba trang thử bằng Photoshop 2025 trên macOS, xuất lại PDF giữ layer và kiểm tra hình render. Chưa xác thực native Windows hoặc toàn bộ font.

## 1107-ui.5 — 2026-11-14

- Chạy dài tiếp tục đúng checkpoint, thử kết nối lại Photoshop an toàn, chờ cập nhật API key hoặc phục hồi upstream thay vì bỏ nhóm dịch.
- Thoại mặc định là Horizontal Paragraph Text, giãn dòng theo dấu tiếng Việt; cache số đo font và giảm thao tác lặp khi ước lượng cỡ chữ.
- Thêm sửa hàng loạt PDF/PSD cũ, đổi tối đa ba tên, rút phần tên và bỏ kính ngữ cho mọi tên. Giữ layer và checkpoint theo thiết lập; lỗi lưu không âm thầm flatten PDF giữ layer.
- Lượt dịch mới nhận ngữ cảnh Nhật–Việt trước đó, mặc định sáu câu; bổ sung quy tắc giữ xưng hô và hậu xử lý kính ngữ có gạch nối.
- Snapshot PNG nén lossless; xóa snapshot kiểm tra sau khi đối chiếu thành công. Thêm công cụ nén cache PNG cũ, kiểm tra nguyên vẹn dữ liệu ảnh và metadata trước khi thay file.
- Kiểm thử native trên Photoshop 26.11.7/macOS; chất lượng dịch toàn volume mới và vận hành native Windows vẫn cần đối chiếu thực tế.

- Đưa Magi vào profile `1107` (manifest có pin SHA-256) và dependency PyTorch/transformers vào `requirements-ai.txt`, để checkbox Magi sẵn sàng sau cài đặt chuẩn. Tải thêm khoảng 2 GB.
- Sửa PDF xuất từ script quá nặng: nén JPEG, không thumbnail; PDF mặc định flatten, PDF giữ layer (nhúng cả PSD) thành tùy chọn riêng.
- Chế độ `coreml` chỉ áp dụng cho model đã kiểm chứng; trước đó ép mọi model qua CoreML làm batch chậm.
- Cache model Comic Text Mask và chuyển AOT sang device một lần để giảm lag preview.
- Tách bong bóng nối nhiều phần (từ 3 phần) bằng cắt lồng nhau; chạy cả khi OCR tin cậy cao nhưng bubble chứa nhiều nhóm chữ. Chưa kiểm chứng trên mẫu thật.
- README viết lại: hướng dẫn cài lần đầu cho Apple Silicon và NVIDIA CUDA, luồng sử dụng, xử lý sự cố.
- **1107-shadow-0.5**: thêm `engines/role_guard.py` — rào sau clean, giữ nguyên ảnh gốc cho vùng không phải thoại bubble. Chữ tự do (`comic_text_ai` không nằm trong bubble) không được xử lý; ô chữ nhật hoàn hảo mang chữ display dày (banner/logo kiểu "新連載") được hoàn nguyên. Bóng thoại thường và bóng vẽ tay không bị ảnh hưởng. Ngưỡng hiệu chỉnh trên 1 mẫu dương tính duy nhất: cần thêm dữ liệu gán nhãn.
- Kích hoạt tăng tốc phần cứng NVIDIA CUDA (`CUDAExecutionProvider`, PyTorch CUDA) với fallback CPU; thêm `--accel`/`MANGA_ACCEL=cuda`.
- `doctor` nhận `models/tessdata` cục bộ và yêu cầu thêm ngôn ngữ `vie`.

## 1107-ui.4 / 1107-shadow-0.4 — 2026-11-07

- Đưa engine 1107 vào registry có version; preview và clean từ Photoshop dùng cùng handler. Baseline giữ mặc định.
- Giữ checkbox clean theo lựa chọn người dùng, xử lý opt-out và loại cờ force Baseline khi chuyển engine; không dùng flag scan cũ để âm thầm bỏ chọn region.
- Giao diện bốn tab, khóa input không tương thích với engine, kiểm tra readiness model/dependency và giữ engine khi tiếp tục hàng chờ.
- Tích hợp general/border/ownership recovery và flat-paper background field. Sửa hình chữ mờ do fill stencil và polygon thiếu phủ vùng đã clean.
- Trace theo region lưu mask, reason, crop transform, config và bằng chứng phục vụ so sánh/rollback. Output 1107 cần duyệt.
- Xuất PSD/PDF/JPEG CMYK theo Color Settings của Photoshop, giữ layer; PNG preview RGB.
- Detect macOS ARM/CoreML, CUDA và CPU fallback; cache/hashing tài nguyên. Đã thử native Apple M4; Windows/NVIDIA chưa được xác thực native.
- Đóng gói source không weights/dữ liệu truyện, downloader pin revision/checksum, CI và smoke test cấu hình local. Loại runner benchmark lịch sử khỏi bản phát hành.

Bản 0.4 được người dùng duyệt trên mẫu Chef047 sau kiểm chứng composite CMYK. Điều này không chứng minh toàn volume hoặc mọi artwork khó đã clean an toàn. Chi tiết: [báo cáo kiểm chứng](docs/validation/1107_flat_field.md).

## Cài đặt đa nền tảng và model auto

- Bộ cài chung Python 3.12, wrapper Windows/macOS/Linux, profile auto đủ Baberu, CTD/LaMa, head và Tesseract languages (~653 MB).
- Manifest dùng chung cho downloader/preflight; tải có retry, kiểm tra size/SHA-256, không ghi đè file bằng download lỗi.
- Doctor theo profile kiểm tra import thư viện thực tế và model; phát hiện Tesseract trên Windows, hỗ trợ đường dẫn Unicode.
- Thêm CI kiểm tra bộ cài trên ba OS; bổ sung hướng dẫn cài từ GitHub và phân biệt model tùy chọn/Magi.
