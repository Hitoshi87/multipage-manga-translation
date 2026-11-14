# Multipage Manga Translation

**MangaTypesetter Lite · Engine 1107** — công cụ local chạy trong Photoshop: nhận diện bong bóng/chữ, OCR, clean, ghép bản dịch và xuất PSD giữ layer.

```
ảnh gốc → nhận diện & OCR → duyệt vùng → clean → typeset → PSD / PDF / JPEG
```

Bạn có thể cung cấp bản dịch hoặc thử tính năng dịch AI tùy chọn; OCR và context sẽ được gửi tới API khi dùng tính năng này. Ảnh chỉ được gửi khi bạn bật vision; crop có thể chứa nội dung lân cận và gửi cả trang có thể lộ diễn biến. Vùng khó có thể giữ lại để clean tay. Xem [hướng dẫn Translation V1](docs/architecture/translation_v1.md).

| Thành phần | Bản hiện tại |
| --- | --- |
| Giao diện Photoshop | `1107-ui.5` |
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

Nếu API trả lỗi xác thực 401/403 hoặc chưa có key, trạng thái là `waiting_auth`: bộ giám sát giữ checkpoint và chờ tối đa 12 giờ, không liên tục gọi lại API. Cập nhật key trong giao diện script và đóng giao diện để tự thử tiếp; nếu đã sửa quyền ở phía nhà cung cấp mà không đổi key, mở `Tiep_tuc.command` trong thư mục trạng thái. Nếu key đến từ biến môi trường, biến đó được ưu tiên hơn key nhập trong giao diện; cần cập nhật môi trường và chạy lại Photoshop. Có thể mở `Dung.command` để dừng chờ. Khi gateway trả HTTP 200 nhưng nội dung là `Upstream temporarily unavailable, please retry.`, bộ giám sát chuyển sang `waiting_api`, giữ nhóm chưa dịch và tự thử lại với thời gian chờ tăng từ 30 giây đến tối đa 5 phút; lỗi dịch vụ này không trừ số lần thử của nhóm. File `progress.json` hiển thị trạng thái chờ thay cho trang cuối cùng.

Nếu một trang lớn **chưa được index** chỉ đổi tên, chế độ giám sát có thể nhận lại project cũ khi tên cũ đã được ghi trong tác vụ trước, thứ tự trang không đổi và dấu vân tay metadata (tên, dung lượng, thời gian sửa) khớp. Khi điều này xảy ra trong lúc chạy, script cập nhật checkpoint cấu hình và tiếp tục; khi bắt đầu lại thủ công, hộp thoại cho biết tên cũ và tên mới. Cách kiểm tra này không xác minh nội dung file bằng hash. Trường hợp không xác định được an toàn, script báo lỗi thay vì tự chạy lại từ đầu trong thư mục cũ; hãy khôi phục tên và ảnh ban đầu hoặc chọn thư mục kết quả mới.

Trước khi chạy có giám sát, script đọc kích thước từ header ảnh và tách riêng các trang có dữ liệu pixel thô ước tính từ 64 MiB trở lên, file PSD/PSB và file không đọc được header. Photoshop được khởi động lại giữa các nhóm, nên trang lớn được xử lý riêng sau checkpoint. Ước tính này chỉ dùng để xếp lịch; layer và bản sao làm việc có thể cần thêm nhiều RAM.

Khi xong, dừng hoặc cần xử lý, bộ giám sát gửi thông báo macOS nếu hệ thống cho phép; `supervisor_status.json` vẫn là nguồn trạng thái chính nếu thông báo bị tắt. Khi macOS báo bộ nhớ khả dụng toàn hệ thống dưới 20%, script yêu cầu checkpoint sớm; trước trang tiếp theo, bộ giám sát chờ đến ít nhất 25% trong tối đa 5 phút, sau đó dừng an toàn nếu vẫn thiếu. Nếu macOS không cung cấp số liệu này, chỉ cơ chế theo dõi RAM Photoshop được dùng. Photoshop có thể chờ hộp thoại khởi động, quyền Apple Events hoặc có tài liệu khác được mở trong lúc chạy. Khi không thể khởi động hoặc đóng an toàn, bộ giám sát dừng và ghi lỗi; hãy xử lý hộp thoại, kiểm tra trạng thái rồi chạy lại thủ công. Chế độ này hiện cần kiểm thử thêm trên nhiều máy. Các ngưỡng là tín hiệu yêu cầu dừng ở checkpoint trang gần nhất; lấy mẫu có thể bỏ sót đỉnh ngắn. Việc dọn cache và khởi động lại giảm bộ nhớ tích tụ nhưng không đặt giới hạn RAM cứng cho một trang lớn. Trong luồng dịch cả tập, cả worker scan, clean và dịch của cùng project được chạy tuần tự, kể cả khi đổi giữa chạy thường và chạy có giám sát: worker mới chờ worker cũ hoàn tất sau crash. Giữ file `.lock` cạnh project và các file khóa trong thư mục tác vụ; file khóa không có nghĩa là worker vẫn đang chạy. Bảo đảm ổ đĩa kết quả và scratch disk hoạt động ổn định và còn chỗ trống.

Nếu Photoshop vừa mở lại nhưng macOS tạm trả lỗi AppleScript `-600`, bộ giám sát thử kết nối lại tối đa ba lần. Trước khi thử lại, nó vô hiệu hóa lượt cũ và kiểm tra rằng Photoshop đã xử lý hết lệnh trước; nếu không xác minh được, tác vụ dừng tại checkpoint để tránh chạy trùng.

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

Lượt dịch mới dùng mặc định 6 câu ngữ cảnh nguồn thay vì 2 câu. Trước mỗi nhóm, tool bổ sung các cặp Nhật–Việt đã dịch ở những câu ngữ cảnh đó, chỉ lấy nhóm hoàn tất trước nhóm hiện tại và có revision nguồn còn khớp. Bản nháp được đánh dấu là chưa xác nhận, không biến thành chứng cứ về danh tính người nói. Ngữ cảnh bổ sung nằm trong giới hạn ký tự đầu vào; không gọi thêm API để rà văn phong. Prompt yêu cầu giữ xưng hô cho cùng quan hệ người nói–người nghe, kiểm tra nhịp đối đáp và giữ mức trang trọng theo cảnh. Có thể ghi quy tắc xưng hô đã xác nhận của từng cặp nhân vật trong **Quy tắc Việt hóa / Glossary**; không có đủ bằng chứng thì câu vẫn cần duyệt. Bộ rút gọn từ chối đề xuất đưa thêm từ xưng hô mới.

Mặc định bản dịch mới tự bỏ kính ngữ có gạch nối `-san/-kun/-chan/-sama/-senpai/-sensei/-dono` ở mọi tên, kể cả tên không nhập trong 3 cặp sửa thủ công. Prompt yêu cầu Việt hóa mức lịch sự theo cảnh thay vì giữ hậu tố hoặc tự thêm quan hệ anh/em. Hậu xử lý xác định loại bỏ hậu tố còn sót và giữ nguyên bản trả lời gốc trong `provider_translation` cùng `text_adjustments` để đối chiếu. Placeholder/markup và các từ đứng riêng được giữ nguyên. Có thể tắt trong cấu hình profile nếu chủ ý giữ hậu tố. Cải tiến không tự sửa bản dịch/human approval hoặc prompt của lượt cũ đang tiếp tục; mở lại script và tạo lượt mới cho volume sau.

Thoại mặc định là chữ ngang **Paragraph Text**, có khung kéo chỉnh bằng **Horizontal Type Tool (T)** trong Photoshop. Chữ mới dùng scale ngang/dọc 100%, tracking và baseline shift bằng 0, không kế thừa faux bold/italic hoặc All Caps từ lần dùng Type Tool trước; tùy chọn in hoa của script vẫn áp dụng khi được bật. Giãn dòng tự động tối thiểu 130%, tăng theo chiều cao nét và dấu tiếng Việt thực của từng font; chế độ nhập tay cũng giữ khoảng hở tối thiểu để các dòng không chạm nhau. Thay đổi áp dụng khi dàn chữ/xuất lại. Để giữ khung thoại khi mở lại, dùng PSD hoặc PDF giữ layer.

Để sửa file đã xuất, vào tab **Typeset**, bấm **Sửa hàng loạt PDF/PSD cũ: khung thoại + giãn dòng**, chọn thư mục kết quả có `draft_*.json` (ví dụ `PDF 2`). Tool lấy bản dịch từ layer chữ và tọa độ từ manifest đã lưu, không OCR/clean/dịch lại. Bản sửa giữ layer và nằm trong thư mục con `SUA_THOAI`, cùng `repair_log.json`. Chạy lại cùng thư mục để bỏ qua bản đã sửa thành công và tiếp tục trang còn lại. File đang mở, PDF đã flatten, mất manifest hoặc style không thể khớp được ghi lỗi để duyệt; đóng file đang mở rồi chạy lại để sửa trang đó.

Nút **Đổi tên nhân vật hàng loạt (tối đa 3 tên)** trong tab **3. Typeset & xuất** cho nhập tối đa ba cặp tên cũ → tên mới, ví dụ `Ajisawa → Shinjuku`. Chỉ khớp trọn tên, không phân biệt hoa/thường; tên viết HOA/thường được thay theo kiểu tương ứng. Các cặp áp dụng một lượt, không thay dây chuyền; nếu trùng một phần tên thì ưu tiên tên dài hơn. Tool dàn lại những thoại đổi tên để vừa khung, giữ màu/hiệu ứng và layer chữ. Chọn `PDF 2`, `SUA_THOAI` hoặc thư mục `DOI_TEN` có log liên kết checkpoint gốc. Kết quả nằm trong thư mục con `DOI_TEN`, kèm `rename_log.json`; các trang không đổi tên được sao chép sang để có bộ trang đầy đủ. Chạy lại cùng thư mục và cùng cặp tên sẽ tiếp tục theo checkpoint. Đổi cặp tên sẽ tạo bản xuất mới, không ghi đè bản cũ. Chỉ đổi tên trong layer thoại của file xuất, không sửa dữ liệu bản dịch trong project và không gọi API.

Mỗi cặp có thêm ô **Bỏ phần sau**: nhập `Takumi` để rút `Shinjuku Takumi` thành `Shinjuku`. Bật **Bỏ kính ngữ có gạch nối: -san, -kun, -chan, -sama, -senpai, -sensei, -dono** để xóa kính ngữ đứng ngay sau tên cũ hoặc tên mới; nhận các kiểu gạch nối `-san`, `- kun`, `–SAN`. Không tự xóa từ đứng riêng không có gạch nối để tránh nhầm các từ tiếng Việt như “san lấp”, “chan canh”. Ví dụ một cặp `Ajisawa → Shinjuku`, phần bỏ `Takumi`, bật bỏ kính ngữ sẽ đổi `Ajisawa Takumi-san` và rút `Shinjuku Takumi-kun` về `Shinjuku`. Chỉ rút tên đã đúng thì nhập `Shinjuku → Shinjuku`. Phần `Takumi` và các từ như `san` đứng riêng ở chỗ khác được giữ nguyên. Bật thêm **Áp dụng bỏ kính ngữ cho MỌI tên** để dọn hậu tố ở các nhân vật không nằm trong 3 cặp; có thể để trống cả 3 cặp nếu chỉ dọn kính ngữ. Giới hạn 3 cặp chỉ áp dụng đổi tên/rút phần tên, không giới hạn số tên được dọn hậu tố. Thiết lập bỏ kính ngữ/phần tên được lưu trong log; thay thiết lập sẽ xuất bản mới thay vì bỏ qua theo checkpoint cũ.

Phần dàn chữ dùng cache số đo font/từ có giới hạn và bỏ bước kiểm tra layer lặp trong lượt ước lượng cỡ chữ; lượt cuối vẫn kiểm tra biên thực trong Photoshop. Đo trên Photoshop 26.11.7 với 6 thoại, 3 font, cùng giãn dòng/cỡ chữ và hai lượt ước lượng + đặt chữ: 19,161 giây trước sửa, 14,470 giây sau sửa (giảm khoảng 24%). Số này chỉ đo dàn chữ, không gồm OCR, dịch API, clean hoặc lưu file.

- **PSD**: giữ layer, nhúng profile màu.
- **PDF (gọn, flatten)**: mặc định, nén JPEG chất lượng cao, không nhúng thumbnail, không giữ layer; dung lượng gần với lưu tay. Cần chỉnh sửa thì dùng PSD.
- **PDF giữ layer**: tùy chọn riêng, nhúng toàn bộ PSD nên rất nặng (có thể hàng chục MB mỗi trang).
- Khi lưu lỗi, script thử lại qua thư mục tạm và ghi lỗi vào log. PDF giữ layer không tự chuyển sang PDF phẳng hoặc bỏ hiệu ứng chữ để che lỗi lưu; file lỗi cần xem lại, bản gốc được giữ.
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

### Dung lượng cache làm việc

`work/pages/` giữ `original.png`, manifest, mask và ảnh trung gian cho OCR, clean, kiểm tra lại nguồn và sửa PDF/PSD cũ. Không xóa cả `work/` khi còn project cần tiếp tục hoặc chỉnh sửa. Snapshot kiểm tra nguồn được dọn ngay sau khi xác minh thành công; snapshot scan mới dùng PNG nén lossless.

Để thu nhỏ snapshot cũ mà giữ nguyên dữ liệu ảnh và các chunk metadata:

```sh
python scripts/compact_png_cache.py --root work/pages --report work/png-cache-audit.json
python scripts/compact_png_cache.py --root work/pages --apply --workers 2 --report work/png-cache-compaction.json
```

Lệnh đầu chỉ kiểm tra. Lệnh có `--apply` chỉ thay file nếu nén nhỏ hơn và xác minh dữ liệu ảnh giải nén cùng metadata khớp byte-for-byte; file đổi trong lúc nén, file lỗi hoặc symlink được giữ. Không xóa project, PDF/PSD, models hoặc môi trường Python. `scripts/clean_generated.py --apply` chỉ dọn Python cache/Finder metadata, không dọn cache trang còn tham chiếu.
