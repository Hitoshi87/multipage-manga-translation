# Chẩn đoán vệt chữ Chef23/047 — engine 0.4

Ngày kiểm tra: 2026-11-07, Apple M4 16 GB, Photoshop 2025.

## Nguyên nhân đã xác nhận

Lượt người dùng chạy UI1107-ui.3 / engine1107-shadow-0.3 có source, backend clean và final mask giống từng pixel với sample CLI đã kiểm tra. Vì vậy không có bằng chứng JSX gọi nhầm engine hoặc dùng output cũ trong lần này. Việc trước đó coi bản test đã sạch là thiếu kiểm tra chất lượng hình ảnh.

Ảnh backend đã có hình chữ nhạt trước Photoshop. Mask dạng nét chữ được fill sáng hơn phần counter, halo nén và nền gốc xung quanh. Stage 0.3 chỉ bổ sung mép 3 px nên vẫn tạo stencil âm bản. B005 còn có chữ đã được xử lý ngoài polygon detector; bước finish theo polygon bỏ lại các pixel đó. Snapshot composite CMYK của tài liệu đang mở cũng thấy cùng lỗi. Chuyển màu có thay đổi RGB trong mask, nhưng không tạo sai lệch tọa độ hoặc thay pixel ngoài mask.

## Thay đổi

- `manga_ai/engines/flat_finish.py::_background_plane`: lấy mẫu ngoài toàn bộ text envelope và halo mask; fit trường RGB affine robust, lưu hệ số/residual. Chỉ hỗ trợ giấy sáng, phẳng; giữ output cũ nếu thiếu donor, nền biến thiên hoặc phép ngoại suy không an toàn.
- `finish_page`: context bao gồm owned text boxes; dựng envelope từ convex hull mask đã được xử lý trong **từng** proposal để không cắt qua chữ bởi polygon thiếu phủ. Giới hạn theo ownership, bảo vệ head/region khác và nét tối chưa có trong mask.
- `finish_crop`: tái dựng nền liên tục trong domain có mask làm anchor, blend ở mép; giữ toàn bộ mask cũ, cập nhật compositing mask và artifact từng region. Component không có mask làm anchor giữ nguyên.
- `manga_ai/engine_1107.py::render`: stage nằm trong luồng backend thật; registry/UI đồng bộ phiên bản 1107-shadow-0.4 / 1107-ui.4. Baseline và weights giữ nguyên.

Đây là mở rộng compositing domain cho nền giấy của chữ đã xử lý, không phải tăng detection recall. Các hằng số trong FinishConfig là heuristic thử nghiệm được ghi trong trace, không phải confidence hoặc ngưỡng đã hiệu chỉnh độc lập.

## Kiểm chứng

- 185 Python unit tests; 4 Node suites qua. Có fixture nền gradient độc lập, halo nén/counter chữ, unanchored text box, polygon thiếu phủ, line/head/region protection, không thay pixel ngoài mask.
- Chạy lại engine trên 10 manifest khó đã cache (64 region), 74,12 giây; peak Python RSS 1263,30 MiB. Đây là thời gian engine với scan cache và peak của worker, không phải RAM toàn Photoshop.
- Chạy thêm guard 014/018/036, 39,29 giây; pixel ngoài mask thay đổi bằng 0. Finish giữ nguyên cả hai region 014 vì gate chưa đạt. Crop 036/B005 được xem lại cùng ảnh gốc và 0.3, không thấy tái xuất hiện chữ/dấu chấm.
- Chạy **scan mới → hộp duyệt JSX → run_engine → layer → lưu/mở PSD → snapshot composite** trên Chef23/047 và Mayonaka44: 2 trang, 21 region, 159,974 giây gồm thời gian chờ UI. Lựa chọn clean không bị bỏ; PSD CMYK SWOP v2 có layer. Backend Chef047 khớp từng pixel với CLI cùng source.
- Ghép thêm overlay 0.4 lên bản sao đúng background CMYK của tài liệu người dùng đang mở: background snapshot khớp source, thay đổi ngoài mask bằng 0, lưu PSD riêng. Không sửa các tài liệu người dùng.
- So sánh crop B004/B005 từ **composite Photoshop**, mức thường và contrast ×8: hình glyph mờ rõ ở 0.3 đã không còn ở 0.4 trong các crop kiểm tra. Nền/feather vẫn có sai khác rất nhỏ khi khuếch đại; không coi nền sạch đồng nghĩa RGB phải bằng 255.

Chỉ các kiểm tra pixel/invariant và vận hành có assertion tự động. Nhận xét hình ảnh do agent xem crop, chưa phải nhãn tay độc lập hoặc tỷ lệ chính xác. Không kết luận toàn volume sạch hoặc không tăng xóa nhầm chỉ từ các kiểm tra này. Những vùng artwork/nền phức tạp chưa đạt gate vẫn giữ cần duyệt.

## Artifact local

`work/aa_finish_04/` có benchmark.json, guards.json, native_verification.json, ảnh so sánh, clean/mask/trace từng trang và PSD CMYK. `photoshop_ui_comparison.png` là crop từ lần chạy JSX đầy đủ; `native_exact/chef23_047_1107_04_cmyk.psd` dùng đúng background CMYK của người dùng.

Runner riêng dùng lúc kiểm chứng là `tests/photoshop_flat_field_native.jsx` trong workspace phát triển. Bản source phát hành dùng [smoke test cấu hình local](photoshop-smoke.md), không phụ thuộc đường dẫn máy tác giả. Không đưa manga, PSD, cache hoặc weights vào source bundle.
