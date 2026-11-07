# Cấu trúc source phát hành

```text
Photoshop_Typeset.jsx       UI chính và batch Photoshop
Photoshop_CheckPython.jsx  Kiểm tra bridge Python
manga_typesetter.py        Entry point CLI / JSON RPC
manga_scan.py              CLI scan tương thích Baseline
manga_ai/                  Backend, geometry, OCR và tools tùy chọn
  engines/                 Registry, contracts, 1107 core, preview, flat finish
    stages/                General / border / ownership
  runtime/                 Đọc ảnh, hashing và quản lý tài nguyên
scripts/                   Bridge JSX, cài model, audit và đóng gói
models/                    Chỉ manifest + notices trong Git; weights ở local
tests/                     Unit, Node và native smoke portable
docs/                      Architecture / hardware / validation
demo_project/              Fixture tổng hợp nhỏ cho OCR/PSD test
```

`manga_ai/engine_1107.py` điều phối handler 1107 và giữ đường import công khai. Một số module có tên `experimental_*` là dependency của engine hiện tại hoặc công cụ tùy chọn; không xóa chỉ dựa trên tên. Registry kiểm soát engine nào được gọi; không nạp plugin bên ngoài tùy ý.

Bản phát hành không chứa runner benchmark gắn Chef/Mayonaka/page ID hoặc các phiên bản pipeline lịch sử. Workspace phát triển giữ chúng để tái tạo kết quả. Một adapter ownership được duy trì cho regression; thuật toán thật nằm ở `manga_ai/engines/stages/`, không có bản copy runtime trong script đó.

`work/` lưu snapshot, manifest, masks, cache, báo cáo và queue; `output/` lưu PSD/PDF/JPEG. Hai folder và `.venv*/` không nằm trong Git. Không tự xóa vì có dữ liệu người dùng và bằng chứng để tái tạo/rollback. Cleanup tool chỉ xóa cache code/Finder metadata ngoài các folder được bảo vệ.
