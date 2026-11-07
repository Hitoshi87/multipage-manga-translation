# Photoshop smoke test với ảnh của bạn

Test này chạy giao diện thật: scan mới → duyệt region → engine 1107 đang đăng ký → layer clean → lưu và mở lại PSD → snapshot composite. Không dùng output clean từ cache benchmark để giả lập thành công. Không cần đường dẫn của tác giả repo.

1. Tạo `work/smoke/input/` và đặt 1–10 trang **ảnh gốc** PNG/JPEG/PSD vào đó. Chọn các trang khó bạn có quyền dùng; không commit ảnh truyện.
2. Copy `docs/validation/photoshop-smoke.example.json` thành `work/smoke/config.json`. Input/output là đường dẫn tương đối với project. Chọn `language` theo chữ gốc, mặc định `jpn_vert`.
3. Cài môi trường và profile weights 1107 theo README. Trong Photoshop, File → Scripts → Browse → `tests/photoshop_engine_smoke.jsx`.
4. Bấm **Chạy smoke engine 1107**. Mỗi hộp duyệt có nút **Kiểm tra mọi vùng rồi xác nhận**: test lần lượt chọn region, kiểm tra checkbox, commit và thử bỏ chọn/bật lại một vùng. Bấm nút đó để tiếp tục từng trang.
5. Đọc `work/smoke/latest.json` để lấy đường dẫn report mới nhất. Mỗi lần chạy có folder output riêng. Mở PSD và xem crop ở 100%, đặc biệt chữ nhỏ, dấu câu, rìa mask và artwork.

Report ghi UI/engine version thực, mapping, trạng thái checkbox, manifest/trace, PSD, mode/profile và snapshot composite RGB. Ảnh gốc/tài liệu đang mở giữ nguyên. PSD dùng CMYK theo Color Settings hiện tại nếu `cmyk:true`; profile in cuối cùng do nhà in quyết định.

`ok:true` chứng minh test vận hành/assertion đã qua; không chứng minh ảnh sạch. Region `review` cần xem output, không đồng nghĩa bị skip. Không dùng số proposal hoặc mask pixels làm tỷ lệ chính xác. Chưa có nhãn độc lập thì giữ trường `quality_ground_truth:false`.

Các runner riêng cho Chef/Mayonaka và pilot P0.x chỉ nằm ở workspace phát triển, không có trong bản source phát hành. Báo cáo lịch sử: [kiểm chứng 0.4](1107_flat_field.md).
