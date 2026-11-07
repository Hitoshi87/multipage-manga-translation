# Dữ liệu scan, engine và Photoshop

Manifest scan giữ `schema: 1`, `regions` có ID duy nhất trong từng trang, box/safe theo pixel ảnh gốc và analysis geometry ghi riêng. Không nâng schema làm hỏng các job cũ. Với region retain_unread, field confidence cũ vẫn là placeholder của quyết định; `ocr_evidence` giữ từ, confidence Tesseract 0–100, tọa độ analysis_pixels và trung bình số học, null khi không có OCR. Evidence không cấp quyền clean.

Kết quả registry engine có `result_schema: 1` bổ sung:

- `region_results`: một bản ghi mỗi region được chọn và có nội dung mapping: region_id, decision (`applied`, `review`, `skip`), reason_code, reason.
- `review_ids`: các vùng có output thử hoặc cần kiểm tra; không đồng nghĩa không xử lý hay clean lỗi.
- `counts`: số region độc lập theo decision. Không cộng raw legacy skipped vào review để đếm lỗi.
- `overlay`, `mask`, `trace`: đường dẫn artifact; không nhúng mảng ảnh vào JSON/RPC.
- `applied`, `skipped`, `blocked`, `skip_reason_codes`: field tương thích cũ. Với 1107, review_ids vẫn nằm trong skipped vì JSX cũ cần biết vùng chưa xác nhận an toàn.

Registry kiểm tra ID được chọn, duplicate, ID không tồn tại trong mapping, applied/skip/review mâu thuẫn, decision thiếu và kiểu reason maps. Sai hợp đồng bị từ chối; không tự bỏ qua bản ghi sai.

Batch Photoshop lưu clean_region_results, clean_review_ids, clean_counts cùng engine ID/version và trace. API cũ gọi clean/model_batch_clean vẫn giữ định dạng cũ; schema mới áp dụng qua run_engine. Region ID như B001 phải được hiểu trong manifest/trang tương ứng, không là ID toàn volume. Không đổi source text hoặc thuật toán mask trong lần chuẩn hóa này.

UI `1107-ui.1` lưu `ui_version` riêng với engine version trong request, manifest và batch log. Checkbox biểu thị yêu cầu của người dùng; với engine khác baseline, `auto_clean` và mask baseline không có quyền bỏ chọn hoặc khóa yêu cầu đó. Backend vẫn quyết định mask và an toàn. Mapping sang engine khác baseline luôn xóa cờ `force` cũ. Khi tiếp tục hàng chờ, ưu tiên engine trong batch entry, rồi queue, rồi `engine_selection` của manifest; chỉ mặc định baseline nếu tất cả đều không có metadata engine. Version không khớp vẫn bị backend từ chối.

Từ UI `1107-ui.2`, `list_engines.ui_features` cung cấp trạng thái file/dependency của công cụ tùy chọn; đây là kiểm tra nhẹ, không nạp model hoặc xác minh hash. `run_engine(preview=true)` bổ sung `images.original`, `images.mask`, `images.clean` là thumbnail 540×600 tạo từ đúng overlay do handler trả về; không chạy model/clean lần thứ hai, không thay mask hoặc ảnh clean. Ảnh giao diện nằm trong thư mục manifest, còn engine/version trong kết quả không đổi. Backend cũ thiếu `images` bị UI báo lỗi rõ thay vì dùng preview model khác.

Preview toàn trang dùng mapping đã duyệt nếu có và giữ `clean:false`; vùng chưa có mapping được đưa thành candidate, backend quyết định clean/review/skip. Cờ force chỉ được giữ cho baseline. Manifest import có engine khác baseline phải tìm được đúng registry ID/version và ảnh gốc/masks trước khi mở để chạy tiếp; không tự hạ về baseline/offline.
