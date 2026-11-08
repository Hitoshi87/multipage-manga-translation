# Font mẫu cho Photoshop

Ba font được lấy từ kho Google Fonts, phát hành theo SIL Open Font License 1.1. Các file gốc và OFL của từng family nằm cạnh nhau. Đây là lựa chọn mẫu có đủ ký tự tiếng Việt để thử vai trò; không khẳng định là font chính xác trong ảnh tham khảo hoặc được mọi team manga Việt sử dụng.

- **Itim Regular** (`Itim-Regular`): thử lời thoại thường.
- **Patrick Hand Regular** (`PatrickHand-Regular`): thử lời dẫn hoặc giọng nhẹ.
- **Bangers Regular** (`Bangers-Regular`): thử thoại nhấn/hét; không dùng mặc định cho toàn bộ lời thoại.

Nguồn: [Itim](https://github.com/google/fonts/tree/main/ofl/itim), [Patrick Hand](https://github.com/google/fonts/tree/main/ofl/patrickhand), [Bangers](https://github.com/google/fonts/tree/main/ofl/bangers). Tên font, glyph và hiển thị cần được kiểm tra trong Photoshop trên máy đích. Cài các file `.ttf` bằng trình quản lý font của hệ điều hành và mở lại Photoshop. Sau đó bấm **Font comic mẫu** trong tab Typeset để chọn các PostScript name tương ứng; nếu thiếu bất kỳ font nào thì không tự thay font hiện có. Checkbox in hoa chỉ thay text layer xuất ra, không thay bản dịch đã lưu. Có thể chọn font khác hoặc chỉnh từng vùng.

## Font bổ sung (OFL 1.1, đủ glyph tiếng Việt)

Đã kiểm tra bằng `fontTools` rằng các font dưới đây có đủ chữ cái tiếng Việt có dấu và `“ ” ‘ ’ — … ! ?`. Chưa kiểm tra hiển thị trong Photoshop.

- **Mali** (Regular, Bold): [google/fonts/ofl/mali](https://github.com/google/fonts/tree/main/ofl/mali)
- **Pangolin Regular**: [google/fonts/ofl/pangolin](https://github.com/google/fonts/tree/main/ofl/pangolin)
- **Sriracha Regular**: [google/fonts/ofl/sriracha](https://github.com/google/fonts/tree/main/ofl/sriracha)

Comic Neue đã thử nhưng thiếu nhiều glyph tiếng Việt (Ơ, Ư, các chữ có dấu hỏi/nặng...), nên không đưa vào.
