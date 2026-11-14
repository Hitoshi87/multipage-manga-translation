# Giữ văn phong và xưng hô theo bộ truyện

## Dùng trong tab Tự động

Bấm **Văn phong / xưng hô** cạnh phần style bộ truyện để lưu bối cảnh, văn phong, tên nhân vật và quy tắc xưng hô. Nếu đang chọn bộ style, tên bộ style được dùng làm tên bộ truyện; nếu không, dùng ô **Tên bộ truyện**. Dùng cùng tên cho các vol của cùng một bộ để dùng lại quy tắc. Bộ khác có cấu hình riêng.

Ghi rõ chiều người nói → người nghe, gồm cả người nói tự xưng và gọi người nghe là gì. Ví dụ về cách nhập, không phải quy tắc mặc định:

```text
A nói với B: A xưng “tớ”, gọi B là “cậu”.
B nói với A: B xưng “tôi”, gọi A là “cậu”.
A nói với giáo viên C: A xưng “em”, gọi C là “thầy”.
```

Chỉ ghi cặp và quan hệ đã xác nhận. Có thể để trống khi chưa rõ; công cụ không tự áp “tớ/cậu” hoặc “anh/em” cho toàn bộ nhân vật. Quy tắc chỉ áp dụng khi ngữ cảnh nhận diện được người nói và người nghe; tên xuất hiện trong câu không tự xác định ai đang nói.

Thư viện nằm tại `Folder.userData/MangaTypesetterLite/dialogue_profiles.json`, có bản sao `.bak` khi ghi lại. File chỉ lưu các trường quy tắc/văn phong, không lưu API key. Quy tắc được dùng cho vol/project mới hoặc project chưa có lượt dịch. Lượt đang dịch tiếp giữ profile đã đóng băng; muốn đổi quy tắc giữa lượt thì tạo project/kết quả mới hoặc chỉnh profile và tạo lượt mới qua **Dịch AI / project**. Không tự sửa các trang đã xuất.

Trong **Dịch AI / project** cũng có ô **Quy tắc xưng hô theo cặp nhân vật** và tùy chọn kiểm tra ngữ cảnh để cấu hình trực tiếp cho một project.

## Bộ nhớ ngữ cảnh

Lượt dịch mới (`translation_quality_version: 3`) có thêm tối đa 12 ví dụ Nhật/Việt đã dịch ở các trang trước, trong khoảng hai trang gần nhất và trong giới hạn đầu vào API. Các bản sửa đã duyệt tay được ưu tiên. Thoại còn flag mơ hồ về người nói/người nghe hoặc OCR không được nâng thành quy tắc xưng hô; bản chưa duyệt luôn được ghi rõ trạng thái.

Chỉ dùng nguồn có revision còn khớp và đứng trước nhóm hiện tại theo thứ tự trang thực tế. Không lấy thoại tương lai, kể cả khi một trang được xử lý bù sau các trang khác. Nếu bản tham chiếu bị sửa trong lúc đang gọi API, kết quả nhóm bị từ chối để thử lại với ngữ cảnh mới. Ngữ cảnh này không tự xác nhận danh tính người nói, không suy ra giới tính hoặc độ thân mật từ kính ngữ Nhật và không đưa bảng cast chưa giới hạn thời gian vào prompt toàn bộ lượt dịch.

## Lượt kiểm tra xưng hô sau dịch

Project mới bắt đầu từ tab **Tự động** mặc định bật **Kiểm tra lại ngữ cảnh/xưng hô sau mỗi nhóm**. Có thể tắt trong **Văn phong / xưng hô** trước khi bắt đầu vol/project mới. API/CLI giữ mặc định `dialogue_review: false`; bật rõ trong profile nếu muốn dùng lượt kiểm tra này.

Khi bật, mỗi nhóm có tối đa một lần gọi provider bổ sung để đối chiếu bản nháp với tiếng Nhật, quy tắc bộ truyện và thoại trước đó. Lượt kiểm tra dùng cùng provider/model, cùng ảnh nếu chế độ dịch đã bật vision; không gửi thêm trang truyện mới. Timeout tối đa 90 giây và không tự retry riêng lượt này. Vì thế thời gian và chi phí API tăng.

Lượt kiểm tra giữ câu đã đúng, chỉ đề xuất sửa lỗi có căn cứ về người nói, người thực hiện, tên, xưng hô, giọng điệu hoặc câu nhắc lại. Nó không thay đại từ hàng loạt. Câu còn mơ hồ phải giữ flag hoặc dùng cách diễn đạt trung tính; không tự bịa quan hệ để lấp chỗ chưa rõ.

Khi bản kiểm tra thay từ xưng hô, công cụ giữ bản trước sửa trong `dialogue_original_translation` và đưa vùng vào báo cáo với lý do **Lượt kiểm tra ngữ cảnh đã sửa cách xưng hô**. Đây là đề xuất của model, không phải bản đã được người dùng xác nhận.

Nếu API kiểm tra lỗi, trả JSON sai ID/placeholder hoặc nhóm vượt giới hạn đầu vào, bản nháp ban đầu được giữ và đánh dấu chưa kiểm tra. Hủy giữa hai lượt không ghi một nhóm dở. Nhóm đã lưu xong không bị gọi lại chỉ vì lượt kiểm tra trước đó lỗi; người dùng vẫn cần duyệt vùng đó trong báo cáo.

Số token của hai lượt được cộng khi provider cung cấp usage. Khi thiếu usage của một lượt, metadata có `usage_complete: false` và không trình bày chi phí một phần như chi phí đầy đủ. Các lượt cũ giữ prompt và hành vi cũ; không tự phát sinh lượt API kiểm tra mới khi tiếp tục một run cũ.

## Giới hạn và kiểm chứng

Không có đảm bảo tự động hết lỗi xưng hô khi ảnh/OCR hoặc người nói chưa rõ. Chế độ **Chất lượng** có ảnh vùng thoại giúp model có thêm bằng chứng; vẫn cần rà soát những vùng được đánh dấu.

Unit tests dùng provider giả lập để kiểm tra revision, thứ tự trang, dùng lại bản sửa tay, cách ly từng bộ truyện, giữ lượt cũ, giới hạn đầu vào, lỗi API/JSON, hủy và thống kê token. Chúng không đo độ hay của bản dịch hay chứng minh model luôn xác định đúng người nói. Chưa chạy thử tính năng này qua API thật hoặc giao diện Photoshop native.
