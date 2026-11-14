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

Cỡ `px` trong bộ style là pixel chuẩn ở trang 1008×1440, tăng theo cùng hệ số kích thước trang của công cụ hiện tại. Cỡ `pt` đổi sang pixel theo DPI tài liệu. Ví dụ 18 pt tại 300 DPI là 75 px. **Cố định tuyệt đối** giữ cỡ style; **Đồng đều ±10%** cho style giảm tối đa 10%; **Tự do** cho giảm tối đa 25%. Cỡ style là trần, không tự phóng lớn hơn. Viền là pixel chuẩn và tăng theo kích thước trang.

Chưa nhập bố cục giao diện TypeR, Markdown/rich text nhiều run, căn lề khác căn giữa, chữ dọc, scale ký tự, baseline shift, underline/strikethrough, kerning/ligature tùy chỉnh, tự đổi cỡ theo chiều rộng trang, phóng dấu câu và hiệu ứng viền nâng cao. Cửa sổ nhập hiển thị thông báo phạm vi hỗ trợ. Đây là bộ chuyển đổi định dạng JSON, không cần cài hay chạy TypeR.

## Gợi ý xuống dòng khi rà soát

1. Mở **Rà soát nhanh**, chọn vùng cần sửa.
2. Chọn **Style vùng này** nếu muốn đổi style cho riêng vùng đó.
3. Bấm **Gợi ý xuống dòng**. Công cụ dùng font, tracking, dấu tiếng Việt và hình dạng vùng để tìm tối đa năm phương án khác nhau; có thể chỉ có một phương án vừa.
4. Chọn phương án trong danh sách để xem xuống dòng trong ô lời sửa. Bước này không thay layer có sẵn.
5. Bấm **Áp dụng lời sửa** để đo và kiểm tra lại trong Photoshop, giữ cách xuống dòng đã chọn, thay layer và lưu file. Phương án không vừa ở phép đo cuối sẽ bị từ chối, layer cũ vẫn còn.

Sửa nội dung hoặc đổi style sau khi chọn phương án sẽ hủy ràng buộc của phương án cũ. Các dòng tự gợi ý không thêm gạch nối tiếng Anh/Pháp vào tiếng Việt. Phép đo dùng đúng cách in hoa khi hiển thị, còn ô lời sửa giữ cách viết hoa/thường của bản dịch.

Mỗi PSD/PDF mới có file cạnh nó, ví dụ `001.pdf.lettering.json`, lưu cấu hình của trang và lựa chọn từng vùng. Giữ file này khi chuyển kết quả sang máy khác để rà soát bằng đúng bộ style lúc xuất, kể cả khi thư viện hiện tại đã thay đổi. Lượt chạy có giám sát cũng giữ bản chụp bộ style qua các lần khởi động lại Photoshop. File cũ không có metadata vẫn dùng được; công cụ giữ font, màu và đậm/nghiêng/tracking trên layer khi không chọn bộ style.

Thay bộ style không tự dàn lại file đã xuất hoặc trang được checkpoint đánh dấu hoàn tất. QA/rút gọn phía Python hiện chưa mô phỏng đầy đủ mọi style nhập; phép đo và kiểm tra cuối trong Photoshop quyết định chữ có vừa hay không.

## Kiểm chứng

Các test Node kiểm tra chuyển đổi JSON TypeR/native, đơn vị, font thiếu, vai trò, cách ly bộ truyện, thao tác lưu/hủy, bản chụp style khi rà soát, giữ nội dung và cách xuống dòng. Phép đo Photoshop trong test được mô phỏng; chưa xác nhận giao diện và kết quả native trên nhiều phiên bản Photoshop.
