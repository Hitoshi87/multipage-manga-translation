# Style theo bộ truyện và gợi ý xuống dòng

## Tạo bộ style

Trong tab **Tự động** hoặc **3. Typeset & xuất**, dùng mục **Style bộ truyện**:

1. Chọn **Theo font & cỡ hiện tại**, bấm **Tạo / sửa / nhập TypeR** để tạo bộ mới. Nếu đã chọn một bộ, nút này sửa bộ đó.
2. Đặt tên bộ truyện. Ba style khởi tạo lấy font thoại, dẫn chuyện và hét hiện tại.
3. Chọn style ở danh sách bên trái để sửa font, cỡ, màu RGB, giãn dòng, tracking, đậm/nghiêng giả và viền ngoài. Có thể thêm hoặc xóa style.
4. Gán style cho **Thoại / Dẫn chuyện / Hét** ở cuối cửa sổ. **Theo cấu hình** giữ font và cỡ từ giao diện chính cho vai trò đó.
5. Bấm **Lưu bộ style**. Đóng bằng **Hủy** bỏ thay đổi chưa lưu. **Xuất JSON** tạo bản sao để chia sẻ; bản xuất này nhập lại được bằng cùng nút nhập JSON.

Style áp dụng cho cả typeset một trang và chạy tự động. Chọn **Theo font & cỡ hiện tại** để dùng cấu hình trước đây. Khi chọn thư mục ảnh hoặc sửa tên bộ truyện, giao diện tìm bộ style trùng tên (không phân biệt hoa thường); nếu không có thì trở về cấu hình hiện tại. Nếu tên thư mục là tên chương, hãy chọn bộ truyện từ danh sách.

Thư viện được lưu tại `Folder.userData/MangaTypesetterLite/series_styles.json`, có bản sao `.bak` khi cập nhật. Font chưa cài được báo khi nhập và chặn chạy khi bộ style đó đang được chọn; chọn font thay thế trong trình sửa hoặc cài font rồi mở lại Photoshop.

## Nhập từ TypeR

Trong trình sửa, bấm **Nhập JSON TypeR / bộ style**, chọn JSON do TypeR xuất thư viện (`styles`) hoặc một thư mục (`exportedStyles`). JSON tối đa 2 MiB, mỗi bộ tối đa 500 style. Các style nhập được thêm vào bản đang sửa; cần gán vai trò và bấm **Lưu bộ style** để lưu.

Các trường được chuyển đổi:

| Thuộc tính TypeR | Cách dùng trong Manga Typesetter |
| --- | --- |
| `fontPostScriptName` | Font Photoshop; không tự tải/cài font |
| `size`, `typeUnit` | Nhận `pixelsUnit` hoặc `pointsUnit` |
| `color` | RGB |
| `leading`, `autoLeadingPercentage` | Tỷ lệ giãn dòng; vẫn giữ khoảng hở tối thiểu cho dấu tiếng Việt |
| `tracking` | Khoảng cách ký tự; được tính trong phép đo font |
| `syntheticBold`, `syntheticItalic` | Đậm/nghiêng giả |
| `prefixes` | Chọn style theo tiền tố đầu câu và bỏ tiền tố khỏi chữ hiển thị |
| `stroke` | Viền ngoài màu đặc, 100% opacity |

Tiền tố nên gồm dấu phân cách, ví dụ `REG:` hoặc `SFX:`. Nếu nhiều tiền tố cùng khớp, tiền tố dài nhất thắng. Chọn style thủ công khi rà soát ưu tiên hơn tiền tố; tiền tố nhận diện được vẫn được bỏ khỏi chữ hiển thị. Tiền tố không bị xóa khỏi bản dịch gốc chỉ vì typeset.

Cỡ `px` trong bộ style là pixel chuẩn ở trang 1008×1440, tăng theo cùng hệ số kích thước trang của công cụ hiện tại. Cỡ `pt` đổi sang pixel theo DPI tài liệu. Ví dụ 18 pt tại 300 DPI là 75 px. **Cố định tuyệt đối** giữ cỡ style; **Đồng đều, co khi bóng hẹp** ưu tiên khoảng cỡ đồng đều, nhưng được giảm đến 65% cỡ chuẩn khi không có phương án vừa trong khoảng thông thường; **Tự do** cho style giảm tối đa 25%. Cỡ style là trần, không tự phóng lớn hơn. Viền là pixel chuẩn và tăng theo kích thước trang.

Từ `1107-ui.6`, Auto leading dùng chiều cao mực của câu thực tế để tính khoảng dòng thay vì áp mẫu dấu cao nhất cho mọi câu. Trường hợp thu nhỏ ngoài khoảng đồng đều được lưu trong `sizeException` của metadata và đánh dấu cần kiểm tra độ dễ đọc. Cỡ cố định tuyệt đối không có ngoại lệ này. Nếu vẫn không vừa, layer dự phòng được giữ ẩn để không đè tranh; báo cáo chỉ ra vùng cần rút gọn/chỉnh khung.

Chưa nhập bố cục giao diện TypeR, Markdown/rich text nhiều run, căn lề khác căn giữa, chữ dọc, scale ký tự, baseline shift, underline/strikethrough, kerning/ligature tùy chỉnh, tự đổi cỡ theo chiều rộng trang, phóng dấu câu và hiệu ứng viền nâng cao. Cửa sổ nhập hiển thị thông báo phạm vi hỗ trợ. Đây là bộ chuyển đổi định dạng JSON, không cần cài hay chạy TypeR.

## Tự động chọn cách xuống dòng

Khi typeset hoặc chạy **Tự động**, công cụ tự so sánh tối đa bảy phương án về số dòng và cỡ chữ, rồi chọn phương án có điểm bố cục tốt nhất trong số đó. Cách chấm điểm xét ngắt dòng dễ đọc, độ đầy và vị trí cân trong bong bóng, đồng thời phạt việc thu nhỏ quá nhiều. Cỡ cố định và các ngắt đoạn bạn đã nhập vẫn được giữ; chế độ Đồng đều có ngoại lệ thu nhỏ được ghi rõ ở trên.

Phương án ưu tiên được đo lại bằng chữ thực trong Photoshop, kể cả khoảng trống cho viền ngoài. Nếu phép đo dòng không đạt, công cụ thử phương án kế tiếp trước khi giảm cỡ trong giới hạn cho phép. Khi không có phương án qua kiểm tra, cơ chế đặt tạm/đánh dấu cần rà soát hiện tại được dùng. Không cần mở Gợi ý hoặc chọn từng bubble để chạy tính năng này.

Việc xếp hạng dùng quy tắc bố cục, không phải đánh giá thẩm mỹ đã được xác nhận. Phương án được chọn, điểm và số lần kiểm tra được ghi trong `.lettering.json`; nội dung bản dịch gốc không bị viết lại. Tính toán các phương án dùng chung số đo font để hạn chế thao tác với Photoshop.

## Gợi ý xuống dòng khi rà soát

1. Mở **Rà soát nhanh**, chọn vùng cần sửa.
2. Chọn **Style vùng này** nếu muốn đổi style cho riêng vùng đó.
3. Bấm **Gợi ý xuống dòng**. Công cụ hiển thị tối đa năm phương án theo cùng cách xếp hạng của luồng tự động, tốt nhất trước, và tự chọn phương án đầu; có thể chỉ có một phương án vừa.
4. Xem xuống dòng trong ô lời sửa; có thể chọn phương án khác nếu muốn. Bước này không thay layer có sẵn.
5. Bấm **Áp dụng lời sửa** để đo và kiểm tra lại trong Photoshop, giữ cách xuống dòng đã chọn, thay layer và lưu file. Phương án không vừa ở phép đo cuối sẽ bị từ chối, layer cũ vẫn còn.

Sửa nội dung hoặc đổi style sau khi chọn phương án sẽ hủy ràng buộc của phương án cũ. Các dòng tự gợi ý không thêm gạch nối tiếng Anh/Pháp vào tiếng Việt. Phép đo dùng đúng cách in hoa khi hiển thị, còn ô lời sửa giữ cách viết hoa/thường của bản dịch.

Mỗi PSD/PDF mới có file cạnh nó, ví dụ `001.pdf.lettering.json`, lưu cấu hình của trang và lựa chọn từng vùng. Giữ file này khi chuyển kết quả sang máy khác để rà soát bằng đúng bộ style lúc xuất, kể cả khi thư viện hiện tại đã thay đổi. Lượt chạy có giám sát cũng giữ bản chụp bộ style qua các lần khởi động lại Photoshop. File cũ không có metadata vẫn dùng được; công cụ giữ font, màu và đậm/nghiêng/tracking trên layer khi không chọn bộ style.

Thay bộ style không tự dàn lại file đã xuất hoặc trang được checkpoint đánh dấu hoàn tất. QA/rút gọn phía Python hiện chưa mô phỏng đầy đủ mọi style nhập; phép đo và kiểm tra cuối trong Photoshop quyết định chữ có vừa hay không.

## Kiểm chứng

Các test Node kiểm tra chuyển đổi JSON TypeR/native, đơn vị, font thiếu, vai trò, cách ly bộ truyện, thao tác lưu/hủy, bản chụp style khi rà soát, tự chọn phương án, thử phương án khác khi phép đo loại, giữ nội dung và cách xuống dòng. Python và JavaScript có kiểm tra tương đương kết quả xếp hạng. Đã kiểm tra native trên Photoshop 2025/macOS với ba trang thử, 12 vùng chữ: đặt gọn hai câu bị tràn ở bóng hẹp, sửa giãn dòng, giữ layer chưa clean ở trạng thái ẩn và lưu lại PDF giữ layer. Chưa xác nhận trên toàn bộ font/phiên bản Photoshop hoặc Windows.
