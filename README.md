# Multipage Manga Translation

**MangaTypesetter Lite · Engine 1107** — công cụ local chạy trong Photoshop: nhận diện bong bóng/chữ, OCR, clean, ghép bản dịch và xuất PSD giữ layer.

```
ảnh gốc → nhận diện & OCR → duyệt vùng → clean → typeset → PSD / PDF / JPEG
```

Bạn có thể cung cấp bản dịch hoặc thử tính năng dịch AI tùy chọn; OCR và context sẽ được gửi tới API khi dùng tính năng này. Ảnh chỉ được gửi khi bạn bật vision; crop có thể chứa nội dung lân cận và gửi cả trang có thể lộ diễn biến. Vùng khó có thể giữ lại để clean tay. Xem [hướng dẫn Translation V1](docs/architecture/translation_v1.md).

| Thành phần | Bản hiện tại |
| --- | --- |
| Giao diện Photoshop | `1107-ui.4` |
| Engine tùy chọn | `1107-shadow-0.5` — output cần duyệt |
| Engine mặc định | `baseline-1` |
| Đã kiểm thử thực tế | Apple M4 (macOS ARM64, CoreML), NVIDIA RTX 3050 (Linux, CUDA). Windows/NVIDIA chưa xác thực native |

## Mục lục

1. [Yêu cầu chung](#1-yêu-cầu-chung)
2. [Cài đặt lần đầu — macOS (Apple Silicon / Intel)](#2-cài-đặt-lần-đầu--macos-apple-silicon--intel)
3. [Cài đặt lần đầu — NVIDIA CUDA (Windows / Linux)](#3-cài-đặt-lần-đầu--nvidia-cuda-windows--linux)
4. [Tải model weights](#4-tải-model-weights)
5. [Kiểm tra môi trường](#5-kiểm-tra-môi-trường)
6. [Luồng sử dụng trong Photoshop](#6-luồng-sử-dụng-trong-photoshop)
7. [Chọn phần cứng và tối ưu hiệu năng](#7-chọn-phần-cứng-và-tối-ưu-hiệu-năng)
8. [Xuất file và dung lượng](#8-xuất-file-và-dung-lượng)
9. [Engine 1107 làm gì](#9-engine-1107-làm-gì)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Phát triển, kiểm thử, đóng gói](#11-phát-triển-kiểm-thử-đóng-gói)

## 1. Yêu cầu chung

- Photoshop desktop có ExtendScript (File → Scripts → Browse).
- Python **3.12** trong thư mục `.venv` ngay tại gốc project (Photoshop chỉ gọi `.venv/bin/python` hoặc `.venv\Scripts\python.exe`).
- Tesseract OCR kèm ngôn ngữ `eng`, `jpn`, `jpn_vert`, `chi_sim`, `chi_tra`, `kor`, `vie`.
- Khoảng vài GB trống cho weights và môi trường Python.

Repo **không chứa weights hoặc ảnh truyện**.

```sh
git clone https://github.com/Hitoshi87/multipage-manga-translation.git
cd multipage-manga-translation
```

## 2. Cài đặt lần đầu — macOS (Apple Silicon / Intel)

Cần [Homebrew](https://brew.sh). Script cài `python@3.12`, `tesseract`, `tesseract-lang`, tạo `.venv` và cài dependency cơ bản.

```sh
# 1. Môi trường, Tesseract và dependency cơ bản
bash setup_macos.command --install

# 2. ONNX Runtime (có CoreML provider trên macOS ARM64)
.venv/bin/python -m pip install -r requirements-ai.txt

# 3. Weights profile 1107
.venv/bin/python manga_typesetter.py download-models --profile 1107

# 4. Kiểm tra
.venv/bin/python manga_typesetter.py doctor
```

Ghi chú Apple Silicon:

- CoreML được dùng cho `balloon`, `ctd`, `head`; các model còn lại chạy CPU. Không cần cấu hình thêm.
- **Lần chạy đầu chậm hơn**: CoreML biên dịch model và lưu cache tại `~/Library/Caches/MangaTypesetterLite/CoreML`. Các lần sau dùng lại cache.
- Dùng **Tăng tốc → Tự động** (mặc định). `CPU` chỉ là phương án dự phòng nếu CoreML lỗi hoặc máy nóng/chậm dần khi chạy chương dài; đây là giả thuyết chưa được đo.
- Muốn dùng công cụ preview thử nghiệm (Comic Text Mask, AOT): `.venv/bin/python scripts/setup_preview_models.py`.
- Lần đầu Photoshop có thể hỏi quyền cho script chạy Python; hãy cho phép.

## 3. Cài đặt lần đầu — NVIDIA CUDA (Windows / Linux)

Yêu cầu: card NVIDIA, driver mới, **CUDA 12.x + cuDNN 9** (cài hệ thống hoặc qua pip như bên dưới), Tesseract trong `PATH` kèm đủ ngôn ngữ ở mục 1.

- Linux (Debian/Ubuntu): `sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-jpn tesseract-ocr-jpn-vert tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-kor tesseract-ocr-vie`
- Windows: cài [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki), chọn đủ gói ngôn ngữ, thêm vào `PATH`.

```sh
# 1. Tạo môi trường ảo
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Dependency cơ bản
pip install -r requirements.txt

# 3. ONNX Runtime GPU — GỠ bản CPU trước, hai gói xung đột nhau
pip uninstall -y onnxruntime
pip install "onnxruntime-gpu>=1.23.2,<2"

# 4. Thư viện CUDA qua pip (bỏ qua nếu đã cài CUDA 12 + cuDNN 9 ở hệ thống)
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12 \
            nvidia-cufft-cu12 nvidia-curand-cu12

# 5. (Tùy chọn) PyTorch CUDA cho Comic Text Mask / AOT inpainting
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 6. Weights profile 1107 và kiểm tra
python manga_typesetter.py download-models --profile 1107
python manga_typesetter.py doctor
```

Ghi chú CUDA:

- Trong `doctor`, mục `hardware.available_onnx_providers` phải có `CUDAExecutionProvider`. Nếu không, bạn đang dùng `onnxruntime` CPU hoặc thiếu thư viện CUDA/cuDNN.
- Runtime tự nạp thư viện `nvidia/*/lib` cài bằng pip. Khi lỗi khởi tạo hoặc hết VRAM, nó tự fallback CPU và ghi log.
- Bảng tương thích phiên bản chính thức: [ORT CUDA Execution Provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
- Windows/NVIDIA chưa được xác thực native; hãy báo lại nếu gặp lỗi.

## 4. Tải model weights

```sh
python manga_typesetter.py download-models --profile 1107 --check-only   # kiểm tra offline
python manga_typesetter.py download-models --profile 1107                # tải về models/
```

Luồng **Tự động** còn cần **Baberu OCR** (đọc chữ Nhật, profile `assist`):

```sh
python manga_typesetter.py download-models --profile assist
```

Bấm **Kiểm tra môi trường** trong tab Tự động để biết còn thiếu gì. Máy cũng tự kiểm tra tất cả điều kiện (thư viện, Tesseract `jpn_vert`, model nhận diện, Baberu OCR, API key) **trước khi làm bất cứ việc gì**, và liệt kê đủ mọi mục thiếu kèm lệnh sửa, thay vì báo lỗi giữa chừng.

Tab **Tự động** cần thêm model **LaMa** (206 MB, nằm trong profile `preview`; cả profile này tải khoảng 490 MB vì còn có CTD, mask chữ và Koharu layout) để vẽ lại nền ở các bong bóng trong suốt hoặc có tranh phía sau. Thiếu model này, máy chỉ dùng engine thường và nhiều bong bóng sẽ không được xoá chữ gốc:

```sh
python manga_typesetter.py download-models --profile preview
```

Profile 1107 tải bốn ONNX model (bubble, text detector, CTD, head) và model Magi (sắp xếp panel, khoảng **2 GB**, giấy phép phi thương mại), kiểm tra kích thước và SHA-256 theo revision được pin. Magi cần PyTorch và `transformers` đã nằm trong `requirements-ai.txt`; trên NVIDIA hãy cài `torch` bản CUDA trước (bước 5 ở mục 3) rồi mới cài `requirements-ai.txt`. Inference không bao giờ tự tải weights. Các profile `preview`, `assist`, `aot` là tùy chọn. Qwen (nhận diện font) vẫn cài riêng bằng `scripts/setup_heavy_assist.py`. Xem [model manifest](models/manifest.json), [hướng dẫn weights](models/README.md), [notices upstream](models/NOTICE.md).

`requirements*.lock.txt` ghi môi trường đã đo trên Mac; môi trường khác dùng file requirements thường để pip chọn wheel tương thích.

## 5. Kiểm tra môi trường

```sh
.venv/bin/python manga_typesetter.py doctor        # Windows: .venv\Scripts\python.exe
```

Báo cáo `ready: true` nghĩa là đủ package, Tesseract và ngôn ngữ OCR. Bạn cũng có thể chạy `Photoshop_CheckPython.jsx` trong Photoshop để kiểm tra đường Photoshop → Python; kết quả lưu ở `work/environment.json`.

## 6. Luồng sử dụng trong Photoshop

### Thử nhanh bằng tab "Tự động" (người mới)

1. Mở Photoshop, chạy `Photoshop_Typeset.jsx`. Tab đầu tiên là **Tự động (khuyên dùng)**. Dòng **Sẽ chạy** cho biết đúng engine và model nào được dùng (nhận diện, Baberu OCR, engine xoá chữ, model dịch); có thể chọn engine khác ở ô **Engine xoá chữ**.
2. Cài font trong `assets/fonts/` vào máy (Pangolin là font mặc định của tab này) rồi mở lại Photoshop. Điền **Host**, **Tên model** và **API key** (key chỉ cần dán một lần, được lưu trên máy này và xoá khỏi ô sau khi lưu).
3. Bấm **Chọn thư mục truyện** (JPG, PNG hoặc PSD, mỗi trang một file), kiểm tra tên bộ truyện. Kết quả mặc định lưu vào `_MangaTypesetter/` cạnh thư mục truyện; bấm **Đổi thư mục lưu kết quả** để chọn nơi khác.
4. Bấm **Chỉ thử 3 trang** trước. Máy làm thử 3 trang rải trong tập, rồi báo có nên chạy cả tập không. Nếu ổn, bấm **Bắt đầu** để chạy cả tập; có thể làm việc khác, Photoshop sẽ báo khi xong.
5. Kết quả nằm trong `_MangaTypesetter/` cạnh thư mục truyện: mỗi trang một Adobe Photoshop PDF giữ layer (nhóm `CLEAN — từng bubble` và `TYPESET — Tiếng Việt`), cùng báo cáo `BAO_CAO.html` liệt kê chỗ cần xem. Bấm **Rà soát nhanh** để sửa từng bong bóng ngay trong Photoshop.

Nếu Photoshop dừng giữa chừng, mở lại Photoshop và script, chọn đúng thư mục ảnh gốc, cùng thư mục kết quả và cấu hình dịch trước đó, rồi bấm **Chạy cả chương ngay** để tiếp tục không chạy lại ba trang thử. Giữ nguyên ảnh gốc, project JSON, log `draft_*.json`, thư mục `work/` và các file đã xuất. Trang đã ghi log và có PDF/PSD hợp lệ được bỏ qua; trang lỗi, chưa đủ mapping hoặc có file xuất bị hỏng sẽ được thử lại. File xuất dở có thể còn lại dưới tên cũ, kết quả thử lại có thể mang hậu tố `_1`. Log có bản sao `.bak` để phục hồi nếu lần ghi log bị gián đoạn. Việc kiểm tra PDF chỉ xác nhận dấu đầu/cuối file, không đảm bảo mọi nội dung bên trong đều hợp lệ.

Trên macOS có nút **Chạy dài tự phục hồi (macOS)** để chạy trực tiếp cả chương bằng bộ giám sát độc lập. Đóng tất cả tài liệu Photoshop trước khi bấm. Để tiếp tục một lượt cũ, chọn đúng thư mục ảnh và thư mục kết quả trước đó; script tự dùng lại cấu hình dịch và engine clean đã lưu trong project, thông báo cấu hình trước khi chạy. Script lưu cấu hình không chứa API key, xuất và ghi checkpoint theo nhóm tối đa bốn trang, sau đó đóng và mở lại Photoshop để giải phóng bộ nhớ tích tụ. Bộ giám sát lấy mẫu RAM thường trú của Photoshop; nếu vượt ngưỡng bằng 35% RAM vật lý (giới hạn trong khoảng 1–6 GiB), script hoàn tất và ghi checkpoint trang hiện tại, khởi động lại Photoshop rồi giảm nhóm tiếp theo còn một trang; nhóm tăng dần lại khi tải thấp. Sau crash cũng thử lại từng trang, tối đa ba lần thoát liên tiếp tại cùng nhóm. Các trị số RAM và ngưỡng được ghi trong `supervisor_status.json`. Thư mục trạng thái được hiển thị khi bắt đầu: xem thêm `progress.json`, `supervisor.log`; mở `Dung.command` để yêu cầu dừng an toàn. Nếu trạng thái là `needs_attention`, danh sách `pending_pages` cho biết trang lỗi, thiếu mapping hoặc file xuất không hợp lệ; kiểm tra và chạy lại để thử tiếp. Không tắt máy hoặc xóa thư mục project, `work/` trong lúc chạy.

Trước khi chạy có giám sát, script đọc kích thước từ header ảnh và tách riêng các trang có dữ liệu pixel thô ước tính từ 64 MiB trở lên, file PSD/PSB và file không đọc được header. Photoshop được khởi động lại giữa các nhóm, nên trang lớn được xử lý riêng sau checkpoint. Ước tính này chỉ dùng để xếp lịch; layer và bản sao làm việc có thể cần thêm nhiều RAM.

Khi xong, dừng hoặc cần xử lý, bộ giám sát gửi thông báo macOS nếu hệ thống cho phép; `supervisor_status.json` vẫn là nguồn trạng thái chính nếu thông báo bị tắt. Khi macOS báo bộ nhớ khả dụng toàn hệ thống dưới 20%, script yêu cầu checkpoint sớm; trước trang tiếp theo, bộ giám sát chờ đến ít nhất 25% trong tối đa 5 phút, sau đó dừng an toàn nếu vẫn thiếu. Nếu macOS không cung cấp số liệu này, chỉ cơ chế theo dõi RAM Photoshop được dùng. Photoshop có thể chờ hộp thoại khởi động, quyền Apple Events hoặc có tài liệu khác được mở trong lúc chạy. Khi không thể khởi động hoặc đóng an toàn, bộ giám sát dừng và ghi lỗi; hãy xử lý hộp thoại, kiểm tra trạng thái rồi chạy lại thủ công. Chế độ này hiện cần kiểm thử thêm trên nhiều máy. Các ngưỡng là tín hiệu yêu cầu dừng ở checkpoint trang gần nhất; lấy mẫu có thể bỏ sót đỉnh ngắn. Việc dọn cache và khởi động lại giảm bộ nhớ tích tụ nhưng không đặt giới hạn RAM cứng cho một trang lớn. Trong luồng dịch cả tập, cả worker scan, clean và dịch của cùng project được chạy tuần tự, kể cả khi đổi giữa chạy thường và chạy có giám sát: worker mới chờ worker cũ hoàn tất sau crash. Giữ file `.lock` cạnh project và các file khóa trong thư mục tác vụ; file khóa không có nghĩa là worker vẫn đang chạy. Bảo đảm ổ đĩa kết quả và scratch disk hoạt động ổn định và còn chỗ trống.

Chế độ **Chất lượng** gửi ảnh vùng thoại tới API đã chọn. Với vùng chưa xác nhận chứa số, cụm chữ Hán dài có thể chứa tên, hoặc chữ hiệu ứng nghi bị nhập vào thoại, hệ thống gửi thêm ảnh cận theo nhóm tối đa 8 vùng/trang để đề xuất cách đọc và furigana độc lập; các đề xuất không tự xác nhận OCR và số vẫn được đưa vào báo cáo cần kiểm tra. Chế độ này tốn thêm thời gian và chi phí API. Nếu MAGI đã cài, script ưu tiên MAGI để sắp thứ tự đọc; kiểm tra điều khoản sử dụng của model trong [models/NOTICE.md](models/NOTICE.md).

Khi báo lỗi, gửi kèm `BAO_CAO.html`, thư mục `_MangaTypesetter/chay_thu_*` và file `work/jobs/*/worker.log` mới nhất. Đây là bản thử: giao diện Photoshop mới được kiểm bằng mô phỏng, chưa chạy thật trên nhiều máy.

1. **Mở ảnh gốc** (hoặc chọn folder cả chương), rồi File → Scripts → Browse → `Photoshop_Typeset.jsx`.
2. **Tab Nguồn & nhận diện**: chọn tài liệu/folder, ngôn ngữ OCR đúng với chữ gốc (ví dụ `jpn_vert` cho tiếng Nhật dọc), mức quét, và **Tăng tốc** (xem [mục 7](#7-chọn-phần-cứng-và-tối-ưu-hiệu-năng)). Bấm quét.
3. **Tab Engine clean**: chọn `1107-shadow-0.5` hoặc Baseline (mặc định). **Xem thử clean theo engine đang chọn** hiển thị đúng output của engine đó, cùng backend với clean thật.
4. **Duyệt vùng**: kiểm tra mapping và bỏ chọn vùng muốn giữ nguyên. Vùng bị bỏ chọn không bị đụng tới. Mapping Baseline không mang cờ `force` sang engine khác.
5. **Clean**: có thể chỉ clean cả chương, hoặc clean rồi nhập bản dịch để typeset. Chế độ "đã clean thủ công" chỉ tạo chữ. Mỗi lần clean tạo bản sao và layer riêng.
6. **Tab Typeset & xuất**: chọn font, nhập bản dịch, chọn PSD/PDF/PNG/JPEG. Tùy chọn CMYK dùng Color Settings hiện tại của Photoshop; chọn ICC theo nhà in. PNG preview luôn RGB.

Lưu ý:

- `review` nghĩa là cần duyệt **output đã tạo**, không phải chưa chạy.
- Job/manifest/trace ghi riêng UI và engine version. Dữ liệu ghim version cũ sẽ báo không khớp; scan lại từ ảnh gốc để dùng engine mới.
- Tab **Thử nghiệm nâng cao** chứa công cụ tùy chọn. Công cụ mask/inpainting của Baseline bị khóa khi chọn 1107.

### Chạy bằng CLI (không cần Photoshop)

```sh
python manga_typesetter.py --accel cpu scan /duong/dan/anh --out /duong/dan/xuat
```

`--accel` đặt trước tên lệnh con. Có thể dùng biến môi trường `MANGA_ACCEL` thay thế.

Font comic mẫu và giấy phép: [assets/fonts](assets/fonts/README.md).

## 7. Chọn phần cứng và tối ưu hiệu năng

Dropdown **Tăng tốc** (tab Nguồn & nhận diện) được lưu cho các phiên sau. Tương đương CLI: `--accel` hoặc `MANGA_ACCEL`.

| Chế độ | Hành vi |
| --- | --- |
| `auto` | Tự nhận OS/thiết bị. macOS ARM64: CoreML cho `balloon`, `ctd`, `head`. Có `onnxruntime-gpu`: CUDA. Còn lại: CPU |
| `cpu` | Chạy hoàn toàn trên CPU. Phương án dự phòng khi CoreML/CUDA lỗi hoặc máy nóng; thường chậm hơn |
| `coreml` | Như `auto` trên Mac nhưng ép dùng CoreML cho các model đã kiểm chứng; model khác vẫn chạy CPU |
| `cuda` | Ép CUDA cho ONNX và PyTorch; fallback CPU khi lỗi |

Hướng dẫn chọn nhanh: Mac và PC NVIDIA dùng `auto`. Chỉ chuyển `cpu` khi gặp lỗi thiết bị hoặc máy bị throttling; chưa có số đo chính thức so sánh `auto` với `cpu` trên M4. Không có số liệu nào bảo đảm từng node thật sự chạy trên GPU/ANE; xem `hardware` trong `trace.json` để biết provider đã đăng ký và fallback.

Batch nhiều trang: script tự gọi `app.purge(PurgeTarget.ALLCACHES)` sau mỗi trang và dọn `work/jobs/` khi RPC thành công (chỉ giữ log khi lỗi). Chi tiết: [hardware và dispatch](docs/runtime/hardware.md).

## 8. Xuất file và dung lượng

- **PSD**: giữ layer, nhúng profile màu.
- **PDF (gọn, flatten)**: mặc định, nén JPEG chất lượng cao, không nhúng thumbnail, không giữ layer; dung lượng gần với lưu tay. Cần chỉnh sửa thì dùng PSD.
- **PDF giữ layer**: tùy chọn riêng, nhúng toàn bộ PSD nên rất nặng (có thể hàng chục MB mỗi trang).
- **JPEG**: flatten, chất lượng 10; **PNG**: RGB.

## 9. Engine 1107 làm gì

Các stage: general recovery, border validation, text ownership, flat-background finish và role guard. Polygon là một tín hiệu hình học; ownership hạn chế việc lấy chữ của bubble kế bên. Nền phẳng được dựng theo màu giấy cục bộ. Role guard giữ nguyên ảnh gốc cho chữ tự do và banner chữ nhật mang chữ display dày. Bong bóng nối liền nhiều phần được tách thành các thùng thoại riêng khi OCR tiếng Nhật xác nhận từng phần.

Kết quả đã thử trên mẫu truyện thật và Photoshop CMYK; chưa có ground truth độc lập toàn volume. 1107 vẫn cần duyệt, nhất là bubble trong suốt, chữ sát artwork hoặc ảnh nén mạnh. [Changelog](CHANGELOG.md) · [Kiểm chứng vệt chữ 0.4](docs/validation/1107_flat_field.md) · [Quy trình tiến hóa engine](docs/architecture/engine_evolution.md).

## 10. Xử lý sự cố

| Triệu chứng | Cách xử lý |
| --- | --- |
| "Thiếu Python trong .venv" | Tạo `.venv` ở gốc project theo mục 2 hoặc 3 |
| `doctor` báo thiếu ngôn ngữ OCR | Cài thêm gói Tesseract (đặc biệt `jpn_vert`, `vie`) |
| Không thấy `CUDAExecutionProvider` | `pip uninstall onnxruntime`, cài lại `onnxruntime-gpu`, kiểm tra CUDA 12/cuDNN 9 |
| Mac chậm dần khi batch | Đóng bớt ứng dụng nặng; nếu vẫn chậm, thử `CPU` và gửi `trace.json` (mục `hardware`, `seconds`) để so sánh |
| Lần đầu chạy rất chậm trên Mac | Bình thường: CoreML đang biên dịch cache |
| "Python không phản hồi trong 180 giây" | Xem `worker.log` trong thư mục job; thử `cpu` |
| Báo dữ liệu version cũ | Scan lại từ ảnh gốc |

## 11. Phát triển, kiểm thử, đóng gói

```sh
python -m unittest discover -s tests -q
node tests/test_windows_launcher.js
node tests/test_engine_review_ui.js
node tests/test_ui_modes.js
node tests/chapter_dialog.js
node tests/test_native_smoke.js
python scripts/build_source_bundle.py --check
```

Unit test dùng fixture tổng hợp; CI không tải weights hoặc ảnh truyện. [Photoshop smoke test](docs/validation/photoshop-smoke.md) kiểm tra scan → hộp duyệt → engine → layer → mở lại PSD; chất lượng ảnh vẫn cần xem riêng. `work/`, `output/`, `.venv*`, credentials và weights không thuộc Git.

[Đóng góp](CONTRIBUTING.md) · [Cấu trúc project](docs/architecture/layout.md) · [Data contracts](docs/architecture/data_contracts.md) · [Thêm engine](manga_ai/engines/README.md).

## License

Source code chưa được cấp license chung. Model và thành phần upstream có điều khoản riêng trong [models/NOTICE.md](models/NOTICE.md); không gán license source thay cho license weights. Không phân phối weights trong Git.
