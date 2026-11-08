# Đối chiếu thiết kế Translation Engine Nhật → Việt với codebase

Ngày khảo sát: 2026-11-08. Source local: branch `main`, commit `0cfe95c`. Đây là báo cáo thiết kế và điểm tích hợp, chưa triển khai engine dịch.

## 1. Kết luận

Thiết kế phù hợp để mở rộng repo, nhưng chưa thể cắm trực tiếp bằng cách đổi prompt và thêm request API. Repo hiện là **Photoshop ExtendScript/ScriptUI + Python worker**, xử lý nhận diện, OCR, clean, ghép bản dịch có sẵn và typeset. Không phải ứng dụng React; đuôi `.jsx` ở đây là ExtendScript.

Nên thêm một tầng `translation` độc lập, có adapter xuất về mapping hiện tại. Giữ engine clean và các safety gate của nó. Không đưa translator vào registry clean `manga_ai/engines/`, vì registry đó nhận manifest/mapping để tạo overlay ảnh, không quản lý dịch thuật.

Ba yêu cầu bổ sung của người dùng đều khả thi:

- Prompt chung thay đổi theo từng bộ: lưu thành profile của series.
- Văn phong là ô riêng: không trộn với bối cảnh, glossary hoặc quy tắc kỹ thuật.
- Nhiều ô trong `.jsx`, ghép thành prompt: ScriptUI dùng được nhiều `edittext` multiline; JSX gửi các phần có tên cho Python, Python ghép prompt thực sự để CLI và UI dùng cùng một logic.

## 2. Những gì repo thực sự có

| Hạng mục | Hiện trạng và điểm đọc source | Hệ quả khi tích hợp |
| --- | --- | --- |
| Pipeline | README: người dùng cung cấp bản dịch; `manga_ai/cli.py:50` dispatch scan/import/alignment/font/clean | Chưa có client LLM, prompt dịch, semantic QA hoặc memory |
| OCR chính | `manga_ai/engine.py:241`, `:452`, `:632`: Tesseract, kể cả crop OCR tiếng Nhật | OCR hiện có là dự đoán, không phải tiếng Nhật đã được user xác nhận |
| OCR bổ trợ | `manga_ai/alignment_assist.py:44`: Baberu đọc crop rồi E5 gợi ý ghép với câu Việt có sẵn | Tái sử dụng Baberu như nguồn OCR thay thế được; E5 không phải dịch giả hoặc bộ chứng minh bản dịch đúng |
| MAGI | `manga_ai/magi_layout.py:74`: tắt OCR/crop embeddings, chỉ nạp nhóm trọng số detection; `:98` chỉ trả box panel | Chưa có speaker association, character identity hoặc speaker confidence |
| Thứ tự đọc | `manga_ai/engine.py:210`, `:681`: xếp region bằng panel và geometry | Có cơ sở gom panel; chưa lưu quan hệ region → panel thành ID rõ ràng, chưa có scene |
| Manifest | `manga_ai/engine.py:703`; `manga_ai/io.py:137`; `docs/architecture/data_contracts.md` | `schema: 1`, box/safe theo pixel ảnh gốc; ID `B001` chỉ duy nhất trong từng trang |
| Mapping | `manga_ai/io.py:117` | Kiểm tra ID lạ/trùng và chuỗi; cho phép thiếu vùng, bỏ chuỗi rỗng, chỉ giữ một số field cố định |
| Giao diện | `Photoshop_Typeset.jsx:18`, `:281` | Có tab và hộp duyệt mapping; chưa có chỉnh/xác nhận OCR, nhân vật, context hoặc prompt |
| Cả chương | `Photoshop_Typeset.jsx:874` | Scan rồi xử lý ngay từng trang; chưa có bước gom dữ liệu nhiều trang trước khi dịch |
| Bridge | `scripts/core.jsxinc:88` | Mỗi RPC tạo process Python riêng; timeout tổng 180 giây; không phải server giữ state trong RAM |
| Lettering | `scripts/core.jsxinc:155` | Đo font/wrap bằng Photoshop; không tự sửa nghĩa câu. Đây là điểm dùng lại tốt |

Các chi tiết dễ gây lỗi:

1. `B001` được gán sau khi sắp thứ tự (`engine.py:688`), nên scan lại có thể đổi liên kết ID ↔ nội dung. Không dùng ID này độc lập làm khóa memory toàn series.
2. `source` có thể là `[OCR chưa đọc được]`, `[AI tìm thấy chữ — cần kiểm tra]` hoặc `Vùng thủ công`. Adapter phải phân biệt nhãn UI với tiếng Nhật thật, không đưa chúng cho model như nguyên tác.
3. `confidence=0` có lúc là placeholder quyết định; confidence Tesseract là thang 0–100; detector có thang riêng. Không đồng nhất chúng với xác suất đúng của OCR/speaker.
4. `checked_mapping()` loại bỏ field như `flags`, `semantic_translation`, `lettering_translation`. Lưu toàn bộ kết quả dịch vào mapping hiện tại sẽ mất metadata.
5. Đếm đủ số dòng không chứng minh đúng bubble; kiểm tra đủ target ID cũng không chứng minh OCR/detector đã tìm đủ chữ trên trang.

## 3. Kiến trúc đề xuất

```text
Photoshop snapshot / ảnh nguồn
    → scan & OCR hiện tại
    → chuẩn hóa evidence + sửa OCR khi cần
    → lưu thứ tự trang / panel / segment
    → gom nhóm dịch + resolver lọc context theo thời điểm
    → OpenAI-compatible provider → DeepSeek hoặc model đã cấu hình
    → kiểm tra hợp đồng 100% + semantic QA có chọn lọc
    → lưu bản dịch / vấn đề cần duyệt
    → adapter segment → region mapping
    → clean / Photoshop lettering hiện tại

Nguồn Nhật + memory được duyệt
    → trích xuất đề xuất fact
    → kiểm tra nguồn / xung đột / mốc tiết lộ
    → xác nhận theo chính sách
    → cập nhật memory có version
```

Không cần speaker detection hoàn chỉnh mới phát hành bản dịch đầu tiên. Khi chưa có detector hoặc user chưa gán, để `speaker.status = unknown`. Không giả lập confidence hoặc lấy head box của công cụ bảo vệ artwork làm danh tính nhân vật.

### 3.1. Contract riêng cho dịch, adapter cho manifest cũ

Giữ scan manifest `schema: 1` và ID region cũ. Tạo project/series store bền vững, ví dụ thư mục project do người dùng chọn, gồm project index, source revisions, prompt profile, translation runs và memory. Không đặt dữ liệu chính chỉ trong `work/jobs/`: bridge xóa file job khi RPC thành công.

Với quy mô ứng dụng local hiện tại, JSON có version và atomic write là đủ cho bản đầu nếu chỉ một writer; dùng khóa khi cần. Có thể chuyển SQLite khi truy vấn và số writer tăng. Không cần vector database để bắt đầu.

Một normalized segment nên có:

```json
{
  "segment_id": "seg_01_example",
  "page_id": "page_012",
  "source_revision": "sha256:...",
  "region_refs": [{"manifest_id": "scan_012_r1", "region_id": "B001"}],
  "position": {"volume": 1, "chapter": 2, "page": 12, "order": 1},
  "panel_id": "panel_012_01",
  "group_id": "group_004",
  "kind": "dialogue",
  "source": {
    "text": "先輩、ちょっといいですか？",
    "origin": "tesseract",
    "status": "unreviewed",
    "confidence": {"value": 87.0, "scale": "word_mean_0_100"}
  },
  "speaker": {"candidate": null, "status": "unknown", "confidence": null},
  "addressee": {"candidate": null, "status": "unknown"}
}
```

`segment_id` là khóa được project store giữ ổn định qua chỉnh thứ tự. Scan lại phải reconcile có kiểm tra; không tự nhận `B001` mới là `B001` cũ. Đổi nội dung nguồn phải đổi revision và đánh dấu bản dịch, QA, memory dẫn xuất có thể đã lỗi thời. Model chỉ cần nhận ID, tiếng Nhật và thông tin ngữ nghĩa cần thiết; geometry/hash đầy đủ có thể ở backend.

Lưu `raw_ocr`, bản sửa `corrected_source` và người/lần xác nhận. OCR confidence cao không tự chuyển thành verified. Baberu có thể là OCR dự phòng nhưng hàm hiện tại chỉ trả chuỗi, không được tự bịa điểm tin cậy.

Một segment và một bubble không luôn tương ứng 1:1: bubble nối, một câu chia nhiều vùng, nhiều câu trong một vùng đều đã có nhu cầu trong UI. Thiết kế `region_refs`/placement mapping riêng; nếu tách bản dịch qua nhiều vị trí, giữ nguyên bản đầy đủ và xác nhận cách tách.

### 3.2. Gom cảnh là một bước mới

Panel order không cung cấp scene boundary. Bản đầu nên dùng **nhóm panel liên tục theo thứ tự đã duyệt**, có giới hạn token và cho user tách/gộp. Gọi đây là translation group cho đến khi có bằng chứng đó là một scene.

Chương cần hai lượt: scan/index các trang trước; sau đó dịch theo nhóm và trả kết quả về từng trang để clean/typeset. Nhóm có thể xuyên trang. Context lân cận chỉ nằm trong phạm vi cho phép; source tương lai ngoài group hiện tại không tự trở thành context.

Khi vượt budget, chia target thành nhiều request, giữ một ít source lân cận dưới dạng context-only và không cho xuất các ID đó. Không âm thầm bỏ target hoặc cắt mất glossary bắt buộc. `max_tokens=4096` chỉ là giá trị thử, không đủ cho mọi nhóm.

### 3.3. Xưng hô cần người nghe và quan hệ có hướng

Speaker riêng lẻ không đủ để chọn xưng hô Việt. Cần `addressee`, quan hệ A → B và B → A, bối cảnh giao tiếp, mốc có hiệu lực. Nhân vật có thể đổi xưng hô theo cảnh, hoặc che giấu quan hệ.

Khi không đủ bằng chứng, cho phép bỏ đại từ bằng cách diễn đạt tự nhiên hoặc đưa vào review. Không bắt user nhập hết quan hệ trước khi dịch. Speaker/quan hệ suy đoán không được khóa glossary hay canonical memory.

### 3.4. Memory cần cả thời điểm sự kiện lẫn thời điểm tiết lộ

Giữ ba tầng canonical / rolling / volume như đề xuất ban đầu, nhưng bổ sung:

- `status`, `source_ids`, source revisions, `approved_by`, `approved_at`, lịch sử supersede/conflict.
- `revealed_at` hoặc `available_from`: thời điểm độc giả được phép biết fact.
- `valid_from` / `valid_to`: thời gian fact có hiệu lực trong truyện, có thể khác thời điểm tiết lộ.
- Với fact về tri thức nhân vật: ai biết điều gì và biết từ lúc nào.
- Với summary: danh sách fact nền, trạng thái kiểm tra và `source_horizon` tối đa của mọi nguồn phụ thuộc.

Resolver phải lọc **tất cả** context: summary, tên/alias nhân vật, quan hệ, mô tả giọng nói và fact; không chỉ lọc summary. Một quan hệ xảy ra từ quá khứ nhưng chương 5 mới tiết lộ không được cấp cho bản dịch chương 1 chỉ vì `valid_from` rất sớm.

Canonical nghĩa là đáng tin, không có nghĩa được phép dùng từ đầu truyện. `approved_at` là thời gian thao tác ngoài đời, không thay cho mốc tiết lộ. Dùng tuple số/thứ tự project để so vị trí, không so chuỗi tên trang/chapter.

Fact chỉ có source ID chưa đủ để verified. Builder chỉ tạo proposal; backend kiểm tra source tồn tại, revision và phạm vi, sau đó nội dung phải được xác nhận theo chính sách. Sửa/xóa nguồn hoặc bác bỏ fact phải làm summary phụ thuộc bị đánh dấu stale. Hợp nhất từ fact gốc, hạn chế chuỗi summary-của-summary.

## 4. Chia prompt trong giao diện `.jsx`

Thêm tab **Dịch AI** giữa nhận diện và clean/typeset. Cấu hình kết nối có thể dùng hộp riêng để không chiếm hết chỗ biên tập prompt. Các trường dưới đây là đề xuất, chưa có trong UI hiện tại.

| Ô/nhóm | Phạm vi lưu | Nội dung |
| --- | --- | --- |
| API | Theo provider, dùng lại giữa series | Base URL mặc định `https://api.vilao.ai/v1`, model, khóa API tham chiếu, max output tokens, timeout, tùy chọn capability |
| Bộ truyện | Theo series/project | Tên bộ, ngôn ngữ nguồn/đích, volume/chapter và thứ tự trang |
| Prompt chung | Theo series | Bối cảnh và chỉ dẫn dịch riêng, user chỉnh tự do |
| Văn phong | Theo series, ô multiline riêng | Nhịp thoại, độ trang trọng, đặc trưng diễn đạt; mặc định tự nhiên, sát nghĩa, giữ cường độ nguyên tác |
| Chính sách localize | Theo series | Kính ngữ, tên riêng, SFX, chửi thề; có thể dùng dropdown kèm ghi chú |
| Glossary / nhân vật | Dữ liệu có cấu trúc | Đề xuất, sửa, khóa, xác nhận; không gộp vào ô prompt tự do |
| Core / output contract | Xem nâng cao, chỉ đọc mặc định | Quy tắc trung thành với nguồn, uncertainty, target IDs và JSON schema |
| Xem prompt đã ghép | Chỉ đọc | Chính xác system/user payload chuẩn bị gửi; không hiện secret |

Gợi ý bố cục prompt: system gồm core rules → series general → style → localization → nhắc lại output contract. User message là JSON source + target IDs + context đã được resolver lọc. Những phần cùng là system vẫn có thể mâu thuẫn, nên backend phải kiểm tra output độc lập; ghép thứ tự không bảo đảm model luôn tuân thủ.

JSX gửi `{general_prompt, style_prompt, localization_policy, profile_version}` thay vì tự ghép một chuỗi duy nhất không còn cấu trúc. Python tạo prompt cuối từ đúng các ô đó; preview gọi cùng compiler. Có thể tách code UI thành `.jsxinc` rồi include, tránh làm file chính hiện đã dài gần 1.000 dòng lớn thêm quá nhiều. Script đóng gói đang whitelist `.jsxinc` trong `scripts/`, nên cần cập nhật `scripts/build_source_bundle.py` nếu thêm include mới.

Nếu user đổi style/general/glossary, tạo profile revision mới; bản dịch cũ giữ provenance để tái tạo hoặc chọn dịch lại. Không tự thay bản user đã sửa/duyệt. User không phải nhập lại config cho mỗi trang.

## 5. API Vilao: tương thích ở lớp giao thức, capability cần xác minh

Mẫu `POST /v1/chat/completions` người dùng đưa phù hợp để xây OpenAI-compatible adapter. Client nhận base URL có `/v1`; không nối thêm `/v1` lần nữa. Model là chuỗi cấu hình, không hardcode alias DeepSeek chính thức cho gateway.

Tài liệu chính thức DeepSeek tại ngày khảo sát ghi `deepseek-flash` phục vụ V4.1-Flash-1017, hỗ trợ vision và JSON output; thinking mặc định bật. Trong thinking mode, temperature không có tác dụng. Thiết lập `thinking=disabled`, temperature 0.2 là baseline thử nghiệm hợp lý khi endpoint/model thực sự hỗ trợ, chưa phải cấu hình đã chứng minh dịch tốt nhất. Nguồn: [Models](https://api-docs.deepseek.com/quick_start/pricing/), [Thinking](https://api-docs.deepseek.com/guides/thinking_mode/), [Vision](https://api-docs.deepseek.com/guides/vision/).

Trang chính thức [Vilao](https://vilao.ai/) mô tả OpenAI-compatible Chat Completions và vision trên model phù hợp. Chưa có kết quả request có xác thực trong lần khảo sát này để xác nhận model khả dụng, passthrough `thinking`, JSON mode, giới hạn token, cache hay danh tính model upstream qua gateway. Không suy từ tài liệu DeepSeek sang Vilao.

Adapter nên có capability theo cặp endpoint/model: `json_output`, `vision`, `thinking_control`, token limit và các tham số được chấp nhận. `/models` giúp khám phá tên nhưng chưa chứng minh từng capability. Khi triển khai, kiểm tra bằng request nhỏ, ghi nhận kết quả; tham số chưa hỗ trợ phải có trạng thái rõ, không âm thầm bỏ `thinking` rồi khẳng định đang tắt thinking.

Các yêu cầu vận hành cần thêm:

- HTTP timeout, retry hữu hạn/backoff cho lỗi tạm thời và 429; không lặp retry lỗi auth/config như lỗi mạng.
- Tính tổng retry của SDK và orchestration, không để nhân số lần gọi ngoài dự kiến.
- Phản hồi rỗng/toàn khoảng trắng, JSON sai, thiếu ID, `finish_reason` chưa hoàn tất: không commit như thành công. [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/) còn ghi nhận trường hợp content chỉ có khoảng trắng dù finish reason là stop.
- Lưu job/checkpoint/progress trên đĩa; nếu một RPC ôm nhiều request và QA, có thể vượt 180 giây hiện tại. Dùng start/status/cancel hoặc chia từng group có checkpoint; đổi timeout phải đi cùng progress và giới hạn rõ ràng.
- Hủy không được commit kết quả trễ. Retry/resume cùng request không tạo bản dịch hoặc memory trùng; timeout sau khi provider đã xử lý vẫn có thể tốn phí.
- Lưu prompt hash/version, source revision, context snapshot/memory version, endpoint, model yêu cầu/model phản hồi, settings, usage và thời gian. Gateway có thể route/failover; chỉ ghi nhận thông tin nó thực sự trả, không hứa pin được upstream khi chưa có capability đó.
- Key do Python đọc từ môi trường hoặc credential store hệ điều hành; JSX chỉ gửi reference/profile, tránh ghi key vào `work/jobs/request.json`, manifest hoặc log. Cần tính cả trường hợp Photoshop mở từ GUI không thừa hưởng biến môi trường shell.
- Hiển thị rõ hành vi mới: gửi OCR/context ra API; gửi ảnh là lựa chọn riêng. README hiện nói mọi xử lý local nên phải cập nhật đúng khi tính năng này được thêm.

## 6. Output, QA và lettering: các chỉnh sửa nên làm ngay

### 6.1. Chốt output contract thống nhất

Thiết kế ban đầu dùng field `vi`, nhưng phần lettering lại gọi `semantic_translation`/`lettering_translation`. Nên chọn một contract nội bộ rõ ràng, ví dụ:

```json
{
  "translations": [
    {
      "id": "seg_01_example",
      "semantic_translation": "Tiền bối, hỏi chút được không?",
      "status": "draft",
      "flags": []
    }
  ]
}
```

Câu Việt trên chỉ minh họa schema, không phải bản dịch đã được xác nhận cho câu mẫu. Không dùng nó làm đáp án benchmark.

Cho phép `semantic_translation: null` và trạng thái `blocked_source` khi chưa có nguồn đọc được; backend cũng có thể chặn trước API và tự tạo bản ghi trạng thái này. Mỗi target vẫn có bản ghi truy vết, nhưng không ép model bịa câu cho đủ ID. Không để `null`/chuỗi trống bị adapter mapping âm thầm bỏ qua rồi báo hoàn tất.

Lưu kết quả dịch đầy đủ ở store riêng. Adapter chỉ đưa bản được chọn sang `{id: region_id, translation: text, clean: ...}`; không cho confidence/approval của dịch cấp quyền clean. Câu dịch có thể dùng được nhưng vùng ảnh vẫn phải clean tay, và ngược lại.

### 6.2. Đẩy deterministic QA vào V1

Không đợi đến V4 mới làm vì JSON/ID là điều kiện nhận kết quả an toàn ngay từ lần gọi đầu:

- Đúng schema/kiểu, đúng đủ tập target, đúng thứ tự, không duplicate/context-only/extra ID.
- Unicode và multiset placeholder/markup theo từng target; nhiều placeholder giống nhau vẫn phải giữ số lần xuất hiện.
- Không nhận sentinel OCR như nguyên tác; ghi lý do blocked và phạm vi chưa dịch.
- Kiểm tra source revision/context snapshot hiện hành trước commit; không ghi đè sửa tay hoặc revision mới.
- QA issue phải trỏ tới target thật, category/severity hợp lệ; review output cũng cần validation.

Deterministic QA không kiểm chứng được phủ định, hallucination hay độ tự nhiên. Semantic QA dùng source Nhật và context cần thiết đã phân tầng độ tin cậy, chạy ưu tiên đoạn rủi ro và lấy mẫu có seed phần còn lại. Không tự nâng một issue của reviewer thành bản sửa đã duyệt. Giữ trước/sau và nguồn căn cứ khi chấp nhận sửa.

Review dịch, review OCR, review clean và xác nhận memory là các trạng thái riêng. QA pass không có nghĩa fact truyện được verified. Flag `needs_review` phải xuất hiện trong hàng chờ và ảnh hưởng việc chấp nhận bản dịch, không chỉ nằm trong JSON.

### 6.3. Giữ bản dịch đủ nghĩa, chỉ tạo bản lettering khi cần

`MTA.addText()` đã đo chữ/font bằng Photoshop; khi không vừa cỡ tối thiểu thì báo lỗi, không tự lược câu. Giữ cơ chế này. Vision model hoặc số ký tự không thay thế được phép đo font thực tế.

Sau fit failure mới đề xuất lettering variant, lưu liên kết tới semantic revision, QA lại nghĩa và cho duyệt. Nếu không rút mà vẫn đủ nghĩa được, sửa font/layout hoặc đặt manual layer. Dù dùng variant nào để typeset, semantic translation gốc vẫn được giữ. Bỏ áp lực vừa balloon khỏi ưu tiên dịch nghĩa; chỉ yêu cầu diễn đạt gọn khi không mất thông tin.

## 7. Điểm tích hợp và thứ tự triển khai

Đề xuất module, chưa phải file đã tồn tại:

```text
manga_ai/translation/
  contracts.py       # normalized segment, translation, QA và memory proposal
  evidence.py        # adapter manifest/OCR, source revisions
  grouping.py        # panel groups, target/context-only, token budgets
  prompts.py         # compiler dùng chung UI/CLI, prompt version
  providers.py       # OpenAI-compatible transport và capabilities
  context.py         # glossary/relations/memory theo temporal boundary
  qa.py              # deterministic checks + semantic review selection
  store.py           # profiles, revisions, jobs, translations, memory
  service.py         # orchestration/checkpoints, không xử lý ảnh clean
```

RPC mới đi qua `manga_ai/cli.py:50`, ví dụ prepare/start/status/cancel translation, load/save series profile, review result và propose/approve memory. Không dùng `run_engine` clean để chạy translation. CLI và Photoshop gọi cùng service.

| Ưu tiên | Phạm vi | Điều kiện nghiệm thu |
| --- | --- | --- |
| V1 | Stable project/segment IDs, evidence normalization, sửa OCR, API config, các ô prompt, direct JP→VI theo group, deterministic QA, adapter/review | Thiếu nguồn/ID/schema bị chặn; không mất câu hoặc metadata; không ghi đè sửa tay; clean cũ vẫn dùng được |
| V2 | Hai lượt scan cả chương → dịch theo nhóm xuyên trang, token split, retry/resume/cancel/progress; glossary và quan hệ user xác nhận | Resume không trùng; hủy không commit trễ; group không xuất context-only; profile dùng lại đúng series |
| V3 | Semantic QA có chọn lọc, fact proposals, canonical + rolling memory, revision invalidation và spoiler tests | Speaker không rõ vẫn dịch trung tính/review; hypothesis không thành fact; nguồn đổi làm phụ thuộc stale |
| V4 | Volume summary từ fact có nguồn và vision escalation theo capability | Không rò tri thức tương lai qua summary/alias/relationship; không gửi ảnh khi chưa bật |
| Sau baseline | Speaker association thực sự và scene detector nếu benchmark chứng minh lợi ích | So với unknown/manual speaker, đo cải thiện đủ bù chi phí và lỗi gán nhầm |

Benchmark nên bắt đầu ngay từ V1 rồi mở rộng theo tính năng, không để cuối cùng. Giữ cùng source đã kiểm tra, target IDs, thiết lập, model route quan sát được và bộ người chấm; so baseline/context/memory/vision theo lỗi nghĩa, xưng hô, thêm/bớt thông tin, độ khuếch đại cảm xúc, thời gian sửa tay, latency và usage/cost nếu provider trả đủ. Thêm case riêng: OCR sai, đổi thứ tự/scan lại, duplicate/missing ID, response toàn khoảng trắng, JSON bị cắt, speaker sai, tên tiết lộ muộn, hủy lúc request đang chạy và lettering không vừa.

## 8. Kiểm chứng trong lần khảo sát

- `test_backend.py`: 24 tests pass, gồm OCR fixture tiếng Anh, import/mapping/clean. Không chứng minh chất lượng OCR Nhật hoặc dịch manga thật.
- `test_assist_models.py`: 5 tests pass; alignment dùng mock, không phải lần chạy weights MAGI/Baberu thật.
- `test_engine_review_ui.js`, `test_ui_modes.js`, `chapter_dialog.js`: cả ba pass. Đây là Node/harness checks, không phải kiểm thử Photoshop native.
- Probe trực tiếp `checked_mapping()`: thiếu một target vẫn được nhận; extra metadata bị loại; hai trang có thể cùng dùng `B001`. Hành vi hợp lý cho mapping clean hiện tại, cần contract dịch khác.
- Không gọi API có xác thực, không tiêu token dịch, không chạy MAGI speaker hoặc benchmark dịch (các tính năng đó chưa tồn tại).
- Chỉ thêm báo cáo này; không sửa runtime, chưa commit/push.

## 9. Quyết định đề xuất

Giữ các nguyên tắc source-first, uncertainty, không tự củng cố memory, temporal boundary và không khuếch đại văn phong. Điều chỉnh thiết kế thành **translation layer độc lập, provider cấu hình được, project store có version và adapter giữ tương thích Photoshop**.

Ưu tiên cao nhất là contract nguồn/ID/QA và prompt profile theo series. MAGI speaker, memory tự động và volume summary là phần mở rộng có kiểm chứng sau đó; bản dịch đầu tiên phải chạy đúng ngay cả khi chưa có các thành phần này.
