# Changelog

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
