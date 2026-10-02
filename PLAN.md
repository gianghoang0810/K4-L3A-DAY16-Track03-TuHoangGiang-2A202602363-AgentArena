# EXECUTION PLAN

## 1. Mục tiêu, nguồn yêu cầu và trạng thái hiện tại

### Phạm vi đã chốt

Hoàn thành **Agent Arena** bằng cách triển khai năm middleware layer trong project:

```text
D:\VinAI\DAY_16(TRACK03)\LAB\K4-L3A-DAY16-Track03-TuHoangGiang-2A202602363-AgentArena
```

Nguồn yêu cầu:

- `README.md`, `phases/README.md`, docstring/TODO của năm layer và contract trong source.
- `D:\VinAI\DAY_16(TRACK03)\LAB\vlearn16_2.md` đến `vlearn16_6.md`.
- `D:\VinAI\DAY_16(TRACK03)\LEC\TRACK3DAY1.pdf`: chỉ tham khảo lý thuyết.

**Quyết định đã được người dùng xác nhận:** không triển khai đề Reflexion/LangGraph/HotpotQA ở slide 35–39 của PDF. Không thêm các deliverable `react_runs.jsonl`, `reflexion_runs.jsonl` hoặc benchmark HotpotQA.

Ngoài code lab, tạo `HUONG_DAN_LAB_DAY16.md` bằng tiếng Việt để người dùng làm và kiểm tra từng bước. Tài liệu dùng giải thích, mã giả, lệnh chạy và checkpoint; không chép toàn bộ code lời giải.

### Trạng thái đã khảo sát

- Năm lớp `Critic`, `CitationChecker`, `BudgetPolicy`, `Retry`, `InjectionGuard` đã có nhưng TODO vẫn là no-op.
- Agent, middleware stack, runner, scorer, mock model và script luyện tập đã tồn tại.
- Script tự cấu hình thứ tự stack; không cần wire lại.
- Có chín brief công khai.
- File kết quả có sẵn ghi baseline không layer đạt trung bình `24.2747`; đây là dữ liệu cũ, phải đo baseline mới trước khi triển khai.
- Git working tree sạch sau khảo sát.
- `.venv` hiện dùng **Python 3.11.9**, trong khi README yêu cầu **3.12+**.
- Lần chạy pytest trên môi trường Windows hiện tại: **743 passed, 9 failed, 1 skipped, 8 errors**. Chưa thể coi môi trường baseline đạt.

### Các vấn đề môi trường đã xác định

1. Năm file đóng băng được `verify.py` kiểm tra đều sai MD5 ở bản trên đĩa. Khi chỉ chuyển CRLF thành LF **trong bộ nhớ**, cả năm khớp MD5 mong đợi. Đây là bằng chứng về khác biệt line ending, không phải lý do sửa hash.
2. Hai test quét bundle so sánh chuỗi đường dẫn POSIX với kết quả `Path` trên Windows.
3. Helper chạy script trong test đặt `PATH=/usr/bin:/bin`; cần kiểm tra trên môi trường POSIX.
4. Nguyên nhân cụ thể của tám setup/teardown error và các failure còn lại chưa được xác minh đầy đủ.

**Mặc định triển khai:** dùng checkout LF riêng trên Linux/WSL với Python 3.12+, giữ nguyên bản Windows hiện có. Không sửa test hoặc code đóng băng để ép baseline xanh.

## 2. Yêu cầu và Definition of Done

### Phân loại yêu cầu

| Loại | Nội dung |
|---|---|
| Bắt buộc | Hoàn thành năm layer theo contract, chạy qua scaffold hiện có, report được submit và trace hợp lệ. |
| Bắt buộc | Claim có provenance; citation đúng; xử lý hallucination, injection, tool suy giảm và ngân sách. |
| Bắt buộc | Chạy kiểm tra cuối, freeze, nộp fork cá nhân đúng tên theo VLearn. |
| Ngầm định từ contract | Hook trả đúng kiểu; trạng thái không rò giữa lượt chạy; retry hữu hạn; không thêm claim chưa do model viết. |
| Theo yêu cầu người dùng | Tạo hướng dẫn `.md` từng bước, liên kết nguồn, ghi kết quả kiểm chứng thực tế. |
| Optional | LoggingMiddleware khi debug, chạy model thật nếu đã được cấu hình, mở rộng khảo sát seed khi kết quả chưa giải thích được. |
| Ngoài phạm vi | Agent mới, LangGraph, LATS, memory compression, HotpotQA, UI, API mới, thay framework hoặc tối ưu riêng đáp án public. |

### Definition of Done

- Năm layer có hành vi đúng, không còn TODO chức năng chưa triển khai.
- Giữ nguyên tên class, constructor, hook và cấu trúc report hiện có.
- Full stack chạy đủ chín brief công khai với flaky bật, không exception do layer, không cảnh báo thiếu FINAL, trace gate pass.
- Có bằng chứng kiểm tra riêng cho từng failure mode, không chỉ dựa vào tổng điểm.
- Không tạo lỗi provenance bằng việc viết lại claim; không gắn citation mới vào tài liệu chưa quan sát đầy đủ.
- Với ngân sách public bằng 8, full stack dành được lượt cuối cho `submit`.
- Pytest và verify đạt trên môi trường hợp lệ. Không bỏ test, đổi assertion hoặc sửa hash để đạt.
- Có kết quả baseline/full stack/ablation tại `runs/`, giữ nguyên trạng thái gitignore của thư mục này.
- Có `HUONG_DAN_LAB_DAY16.md` với lệnh thực tế, checkpoint và kết quả validation.
- `arena/`, `data/`, parser và `MAX_STEPS = 40` được bảo toàn.
- Bản nộp cá nhân đã freeze, commit và push đến đúng `origin`; xác minh commit remote khớp local.

Không đặt `81.71`, `92.52` hay một ngưỡng điểm mới thành điều kiện bắt buộc. Đây là số tham khảo của các phép đo trong tài liệu.

## 3. Thiết kế triển khai và contract

Giữ kiến trúc hiện tại:

```text
Brief → ReActAgent → middleware → model/tools
                             ↓
                      observations
                             ↓
                 FINAL → after_agent
                             ↓
                      tools.submit
                             ↓
                      runner/scorer
```

Thứ tự cài stack:

```text
InjectionGuard → Critic → CitationChecker → BudgetPolicy → Retry
```

- `before_*`: chạy xuôi.
- Wrapper: lớp đầu nằm ngoài cùng.
- `after_*`: chạy ngược; vì vậy citation được sửa trước critic và injection guard quét cuối.

Không thay public API/schema. Sử dụng:

- `ctx.observed_text`, `ctx.corpus`, `ctx.state`.
- `ctx.tools.calls`, `ctx.max_tool_calls`.
- `ToolResult`, `is_degraded`, `FINALIZE_SENTINEL`.
- Report hiện có: `answer`, `claims`, `citations`, `abstain`.

Quy tắc chung:

- Không đổi chữ của claim, kể cả dấu câu hoặc chuẩn hóa khoảng trắng.
- Chỉ cắt substring khi xử lý câu ghép có bằng chứng phù hợp.
- Không dùng `required_facts`, `Doc.tags`, ID hoặc đáp án public làm logic giải bài.
- Không đọc nhãn trên đĩa để vượt việc runner đã gỡ tags.
- Không gọi model ngoài scaffold, tự tạo event model/tool hoặc tự viết trace để được chấm.
- Không thêm dependency runtime.

## 4. Các task triển khai

### Task T0: Chuẩn hóa môi trường và ghi baseline

**Goal:** Có môi trường đáng tin để phân biệt lỗi có sẵn với lỗi do layer.

**Why:** Baseline hiện chưa pass; sửa layer trước sẽ làm khó xác định nguyên nhân regression.

**Dependencies:** Không.

**Files / Components:** Môi trường Python, checkout Git, `requirements.txt`, `scripts/verify.py`, test suite; chỉ đọc scaffold.

**Implementation:**

1. Ghi nhận commit hiện tại, working tree, branch và remote.
2. Dùng checkout riêng trên Linux/WSL, giữ tên thư mục đúng mẫu, cấu hình checkout LF.
3. Tạo venv Python 3.12+ và cài dependency từ `requirements.txt`.
4. Kiểm tra các file đóng băng bằng hash có sẵn.
5. Chạy pytest và verify; phân loại mọi lỗi còn lại.
6. Chạy baseline không layer, seed 11, flaky bật; lưu `runs/baseline.json`.
7. Không ghi đè các kết quả cũ chưa được xác định nguồn.

**Constraints:** Không sửa `arena/`, expected hash hoặc test gốc; không xóa môi trường/source của người dùng.

**Validation:** Hash đúng; pytest và verify pass; baseline có đủ chín kết quả và trace gate pass.

**Done when:** Có baseline mới và môi trường hợp lệ. Nếu vẫn lỗi trong scaffold nguyên bản trên môi trường này, ghi bằng chứng và báo blocker; không tự sửa phần đóng băng.

---

### Task T1: Triển khai Critic

**Goal:** Loại claim không có căn cứ và abstain đúng trường hợp.

**Why:** VLearn 3; một claim bịa ảnh hưởng cả grounding lẫn honesty.

**Dependencies:** T0.

**Files / Components:** `harness/layers/critic.py`; đọc `AgentContext` và quy tắc provenance trong scorer.

**Implementation:**

1. Xử lý claims theo contract; luôn trả report dạng dict.
2. Giữ nguyên claim có text không rỗng xuất hiện nguyên văn trong observations.
3. Với claim không được hỗ trợ, thử các vị trí nối `" và "` theo gợi ý docstring.
4. Chỉ tách khi hai phần là substring của claim gốc, có trong observations và khớp trong từng dòng của hai tài liệu khác nhau đã quan sát đầy đủ.
5. Chọn cách tách hợp lệ đầu tiên theo thứ tự xuất hiện; gắn nguồn tương ứng, đặt `abstain=True`.
6. Không tách được thì bỏ claim.
7. Khi không còn claim hợp lệ, đặt claims/citations rỗng, `abstain=True`, answer giải thích thiếu căn cứ.
8. Đồng bộ citations với claims còn lại; loại trùng và sắp xếp.

**Constraints:** Không thêm bằng chứng từ corpus vào text claim; không hard-code brief mâu thuẫn; không giành việc sửa citation thông thường của CitationChecker.

**Validation:** Claim có bằng chứng được giữ; claim bịa bị bỏ; câu ghép hợp lệ tách được mà không mất provenance; câu ghép không đủ bằng chứng bị bỏ.

**Done when:** Các ca trên đạt và bật riêng critic vẫn chạy trọn một brief qua runner.

---

### Task T2: Triển khai CitationChecker

**Goal:** Sửa citation sai mà giữ nguyên nội dung model đã viết.

**Why:** VLearn 3 và quy tắc grounding.

**Dependencies:** T0; tích hợp sớm với T1.

**Files / Components:** `harness/layers/citation_checker.py`; đọc API corpus và scorer.

**Implementation:**

1. Không có claims hoặc corpus thì trả report theo contract.
2. Giữ citation hiện tại nếu tài liệu tồn tại và text claim khớp nguyên văn bên trong một dòng của body.
3. Với citation sai, tìm theo thứ tự `ctx.corpus.docs`.
4. Chỉ chọn tài liệu có toàn bộ body xuất hiện trong `ctx.observed_text` và có một dòng chứa nguyên văn text claim.
5. Đổi `doc_id`; giữ nguyên text.
6. Không tìm được nguồn thì giữ claim để critic xử lý theo trách nhiệm của nó.
7. Đồng bộ citations, loại trùng và sắp xếp.

**Constraints:** Không coi text bắc qua hai dòng là hợp lệ; không gắn nguồn mới chỉ vì nó tồn tại trong corpus.

**Validation:** Nguồn đúng giữ nguyên; nguồn sai được sửa; tài liệu chưa quan sát không được chọn; text claim không thay đổi.

**Done when:** Chạy được slice `critic,citation_checker`, report submit hợp lệ và các test sửa nguồn đạt.

---

### Task T3: Triển khai BudgetPolicy

**Goal:** Dừng gọi tool đúng ngân sách và yêu cầu model xuất FINAL.

**Why:** VLearn 2–4; `submit` được tính vào budget.

**Dependencies:** T0.

**Files / Components:** `harness/layers/budget_policy.py`.

**Implementation:**

1. `_spent`: budget `None` nghĩa là không giới hạn; còn lại so `calls >= limit - reserve`.
2. Giữ mặc định `reserve=1`.
3. `before_model`: khi cạn, trả list mới gồm messages và message user chứa `NUDGE` hiện có.
4. `wrap_tool_call`: khi cạn, không gọi continuation; trả `ToolResult(ok=False, content="", error=...)`.
5. Khi chưa cạn, chuyển tiếp nguyên name/args.

**Constraints:** Không bỏ `FINALIZE_SENTINEL`; không nén observations; không tự chế FINAL; không giảm `MAX_STEPS`.

**Validation:** Trước ngưỡng cho gọi, tại/sau ngưỡng chặn; không có budget thì chuyển tiếp; messages gốc không bị thay đổi.

**Done when:** Policy vừa nhắc model vừa chặn tool, dành được lượt submit khi chạy qua scaffold.

---

### Task T4: Triển khai Retry

**Goal:** Phục hồi tool lỗi/suy giảm mà không vượt giới hạn thử hoặc ngân sách.

**Why:** VLearn 3; `ok=True` vẫn có thể là nội dung truncated/noise.

**Dependencies:** T0; tích hợp ngân sách sau T3.

**Files / Components:** `harness/layers/retry.py`; đọc `is_degraded`.

**Implementation:**

1. Giữ lần gọi đầu theo scaffold.
2. Retry khi `not result.ok` hoặc `is_degraded(result.content)`.
3. Dùng đúng name/args ban đầu.
4. Tối đa `max_attempts`, mặc định 3 tính cả lần đầu.
5. Trước mỗi retry, kiểm tra budget còn vượt phần reserve; mặc định dành 1 cho submit.
6. Trả kết quả cuối kể cả vẫn lỗi.
7. Ghi tổng số retry thực hiện vào `ctx.state["retry_attempts"]`; không dùng state trên instance để tích lũy qua run.

**Constraints:** Không sleep/backoff không cần thiết cho mock; không thêm model call; không bịa nội dung thay kết quả lỗi.

**Validation:** Thành công ngay chỉ một call; lỗi rồi hồi phục; `ok=True` nhưng degraded; lỗi liên tục; ngân sách chỉ còn submit.

**Done when:** Retry hữu hạn, kết quả thật được trả lại và T3+T4 không gây over-budget ở các ca kiểm tra.

---

### Task T5: Triển khai InjectionGuard

**Goal:** Cách ly chỉ dẫn độc tại biên tool và loại canary khỏi answer cuối.

**Why:** VLearn 3 và safety injection.

**Dependencies:** T0.

**Files / Components:** `harness/layers/injection_guard.py`; dùng constants và `ToolResult` hiện có.

**Implementation:**

1. Gọi continuation lấy result.
2. Không có `BLOCK_START` thì trả nguyên result.
3. Thay mỗi đoạn từ `BLOCK_START` đến hết `BLOCK_END` bằng `PLACEHOLDER`.
4. Nếu không có dấu đóng sau dấu mở, thay phần còn lại của chuỗi.
5. Lặp cho đến khi không còn đoạn mở.
6. Trả ToolResult giữ nguyên `ok` và `error`.
7. Trong `after_agent`, gỡ `INJECTION_CANARY` khỏi answer.

**Constraints:** Không sửa text claim; không dùng tags; không đổi thứ tự stack.

**Validation:** Nội dung sạch không đổi; một/nhiều block được loại; block thiếu dấu đóng được xử lý; metadata ToolResult giữ nguyên; answer sạch và claim không bị viết lại.

**Done when:** Các ca biên đạt, luồng tool sạch trước khi thành observation và lớp quét answer cuối hoạt động.

---

### Task T6: Kiểm chứng tích hợp và hiệu quả năm layer

**Goal:** Chứng minh cả stack thực hiện đúng năm nhiệm vụ.

**Why:** VLearn 4 và 6; test stub xanh không chứng minh layer có tác dụng.

**Dependencies:** T1–T5.

**Files / Components:** Runner, scripts practice/selfeval/leaderboard; thêm test riêng dưới `harness/tests/`.

**Implementation:**

1. Tạo test hành vi tối thiểu theo ma trận ở mục 6; dùng fake tool có bộ đếm và corpus nhỏ tự tạo.
2. Không sửa test gốc; đặt test mới trong `harness/tests/test_layer_behaviors.py`.
3. Chạy full stack trên chín public brief, seed 11, flaky bật, `--strict`.
4. Đọc JSON và selfeval; ưu tiên xử lý exception, thiếu FINAL, trace fail và provenance trước tổng điểm.
5. Chạy leave-one-out, mỗi lần bỏ đúng một layer và giữ cùng seed/config.
6. Nếu tác động retry chưa rõ, so full stack và no-retry thêm seed 12, 13; xem retry count, observations suy giảm và chi phí.
7. Không bắt buộc mọi layer phải tăng trung bình khi chạy riêng; giải thích đóng góp bằng hành vi và số đo.
8. Không thay retrieval/agent để đuổi theo điểm public của `pub-08`, `pub-09`.

**Constraints:** Không chỉnh scorer, dataset, parser hoặc skip test; không dùng `--no-flaky` làm kết quả nghiệm thu.

**Validation:** Test hiện có và test mới pass; full stack không lỗi; đủ chín trace pass; không tạo lỗi provenance; budget và injection được kiểm chứng.

**Done when:** Có bằng chứng cho cả năm layer và bảng so sánh baseline/full stack/ablation.

---

### Task T7: Tạo hướng dẫn làm lab từng bước

**Goal:** Người dùng có thể tái hiện quy trình mà không cần đọc lại cuộc hội thoại.

**Why:** Yêu cầu tạo tài liệu `.md` ban đầu.

**Dependencies:** Có thể soạn khung sau T0; hoàn thiện sau T6.

**Files / Components:** Tạo `HUONG_DAN_LAB_DAY16.md`.

**Implementation:**

1. Ghi rõ phạm vi Agent Arena và PDF chỉ là lý thuyết.
2. Giới thiệu cấu trúc repo, yêu cầu môi trường và vấn đề Windows/LF đã phát hiện.
3. Hướng dẫn baseline → năm layer → full stack → selfeval → freeze.
4. Mỗi layer có mục tiêu, hook, mã giả, bẫy và checklist.
5. Cung cấp lệnh PowerShell cho người dùng Windows và lệnh tương ứng trong môi trường Linux/WSL đã dùng để xác minh.
6. Ghi kết quả thực tế của T6, phân biệt với điểm tham khảo trong tài liệu.
7. Liên kết đủ năm file VLearn, README và source liên quan.
8. Bỏ phần giao diện thừa của bản xuất VLearn; không thêm bộ report của đề PDF.

**Constraints:** Không nhúng đáp án public hoặc thông tin private; không ghi test pass nếu chưa chạy.

**Validation:** Kiểm tra đường dẫn, tham số CLI, code fence, UTF-8 và thứ tự checkpoint.

**Done when:** File hướng dẫn đầy đủ, tái hiện được và khớp implementation thực tế.

---

### Task T8: Freeze và bàn giao bản nộp

**Goal:** Nộp đúng artifact cá nhân đã kiểm chứng.

**Why:** VLearn 5–6.

**Dependencies:** T6, T7.

**Files / Components:** Git repository, `origin`, code harness và tài liệu.

**Implementation:**

1. Chạy validation cuối sau mọi chỉnh sửa.
2. Kiểm tra diff: thay đổi chức năng chỉ trong `harness/`, cộng tài liệu đã yêu cầu.
3. Xác minh không có thay đổi `arena/`, `data/`, test gốc hoặc scripts; không thêm `TEAMMATES.md`.
4. Giữ `runs/`, venv và cache ngoài commit.
5. Xác nhận repository/folder đúng tên `K4-L3A-DAY16-Track03-TuHoangGiang-2A202602363-AgentArena`.
6. Xác minh `origin` là fork cá nhân; không tự đoán hoặc thay remote.
7. Freeze, stage đúng file, commit với tên cá nhân và push branch hiện tại.
8. Kiểm tra commit SHA local và remote; ghi SHA vào thông tin bàn giao.

**Constraints:** Không tiếp tục sửa harness sau freeze; không lấy JSON luyện tập làm điểm chính thức.

**Validation:** Working tree sạch, remote có commit đã freeze, hash đóng băng đúng.

**Done when:** Bản nộp remote được xác minh. Nếu remote hoặc quyền push không hợp lệ, ghi rõ blocker submission; không tuyên bố đã nộp.

## 5. Dependency graph và execution order

```text
T0: môi trường + baseline
 ├── T1: critic ───────────┐
 ├── T2: citation ─────────┤
 ├── T3: budget ───────────┤
 ├── T4: retry ────────────┤── T6: integration + evaluation
 ├── T5: injection ────────┘               │
 └── T7: khung hướng dẫn ──────────────────┤
                                          ↓
                                 T7: hoàn thiện hướng dẫn
                                          ↓
                                 T8: freeze + submission
```

- T1–T5 có thể code song song vì sửa file khác nhau; T3/T4 phải dùng chung quy tắc reserve.
- Nếu chia việc, mỗi task sở hữu file layer của mình; T6 sở hữu file test tích hợp để tránh ghi đè.
- Thứ tự cho một coding agent: **T0 → T1 → T2 → kiểm tra slice → T3 → T4 → T5 → T6 → T7 → T8**.
- Slice sớm là `critic,citation_checker` chạy trọn runner và submit, giúp phát hiện vấn đề provenance trước.
- Không dành thời gian refactor hoặc bonus trước khi năm layer được kiểm chứng.

Mốc lớp học theo đề: 0–15 phút chuẩn bị, 15–95 phút build/đo, 95–105 phút freeze/nộp, 105–120 phút giảng viên chấm. Chưa có deadline lịch cụ thể khác.

## 6. Verification plan

### Ma trận kiểm chứng

| Requirement / failure mode | Kiểm tra |
|---|---|
| Critic giữ claim có căn cứ | Text và citation không bị sửa ngoài trách nhiệm lớp |
| Claim bịa hoặc không còn bằng chứng | Claim bị bỏ; abstain và citations nhất quán |
| Câu ghép hai nguồn | Chỉ tách substring có bằng chứng ở hai nguồn đã quan sát |
| Citation sai | Đổi đúng nguồn; giữ nguyên text |
| Citation qua hai dòng hoặc nguồn chưa đọc | Không công nhận làm nguồn thay thế |
| Budget tại ngưỡng | Tool không được gọi; nudge chứa sentinel |
| Budget không đặt | Không chặn bất hợp lý |
| Retry degraded dù `ok=True` | Có retry và giữ giới hạn attempts |
| Retry gần hết budget | Không dùng lượt dành cho submit |
| Injection đủ/thiếu dấu đóng, nhiều block | Quarantine đúng, giữ metadata |
| Provenance | Không xuất hiện text mới do layer viết vào claim |
| Tái sử dụng layer | Counters không rò giữa hai AgentContext |
| Full stack | FINAL đọc được, report submit, trace pass, chín brief hoàn thành |
| Frozen boundary | Hash đúng và Git không có diff trong phần đóng băng |

### Lệnh chuẩn trên môi trường nghiệm thu

Chạy từ repo, sau khi activate venv Python 3.12+:

```bash
python --version
python -m pytest -q
python scripts/verify.py

python scripts/run_practice.py --layers none --seed 11 --tag baseline --entry baseline --out runs/baseline.json
python scripts/run_practice.py --layers critic,citation_checker --seed 11 --out runs/grounding-slice.json

python scripts/run_practice.py --layers all --seed 11 --strict --entry TuHoangGiang --out runs/full-stack.json
python scripts/selfeval.py --run runs/full-stack.json
python scripts/leaderboard.py runs/baseline.json runs/full-stack.json

python scripts/run_practice.py --layers injection_guard,critic,citation_checker,budget_policy --seed 11 --out runs/no-retry.json
```

Các lượt ablation còn lại bỏ lần lượt một layer khỏi thứ tự chuẩn và lưu file riêng.

- Không có cấu hình lint/typecheck/build riêng được tìm thấy; không thêm toolchain chỉ để tạo checklist.
- Pytest, verify, kiểm tra diff/hash và đọc kết quả thực tế là các bước nghiệm thu chính.
- Test POSIX bị skip đúng điều kiện trên Windows phải được phân biệt với failure; ưu tiên chạy suite đầy đủ trên Linux.
- Model thật và private brief do giảng viên thực thi; không thể chứng minh điểm chính thức bằng mock.

## 7. Risk, assumption và blocker

| Vấn đề | Quyết định / xử lý |
|---|---|
| PDF và VLearn là hai đề khác nhau | Đã chốt Agent Arena; không còn blocking question về phạm vi. |
| Python 3.11 hiện có | Dùng 3.12+ theo README dù verify chỉ kiểm tra ngưỡng thấp hơn. |
| CRLF làm sai frozen hash | Checkout LF riêng; không sửa expected hash hoặc nội dung scaffold. |
| Failure/error baseline | T0 xác minh trên môi trường phù hợp trước; không mặc định là lỗi layer. |
| Claim rỗng khớp mọi chuỗi | Chỉ kiểm tra support với text hợp lệ, không rỗng. |
| Retry vượt budget trong một model turn | Retry phải kiểm tra budget nội bộ; wrapper ngoài không đủ. |
| Citation chạy trước critic | Giữ thứ tự stack; nhánh tách câu của critic tự gắn nguồn cho substring mới. |
| Làm sạch injection phá grounding | Chỉ quarantine tool content và sửa answer; không sửa chữ claim. |
| Tổng điểm không đổi khi bỏ layer | Dùng test hành vi, trace và seed bổ sung trước khi kết luận. |
| Điểm public cao nhưng private thấp | Không hard-code; không mở rộng thành hệ retrieval mới ngoài năm layer. |
| Remote/quyền push chưa xác minh | Chỉ chặn T8 nếu thiếu; không chặn implementation. |
| Môi trường chuẩn vẫn lỗi scaffold | Báo blocker kèm test, phiên bản và hash; không sửa phần đóng băng. |

## 8. Nội dung bàn giao cuối của coding agent

Bàn giao:

1. Năm layer hoàn chỉnh và test hành vi bổ sung trong `harness/`.
2. `HUONG_DAN_LAB_DAY16.md`.
3. Tóm tắt môi trường, lệnh đã chạy, kết quả pass/fail/skip thực tế.
4. Bảng baseline/full stack/ablation và giải thích tác động từng layer.
5. Xác nhận phần đóng băng nguyên vẹn.
6. Commit SHA, branch, remote và trạng thái push; ghi rõ nếu submission còn bị chặn.

Giai đoạn hiện tại chỉ phân tích và lập kế hoạch; chưa triển khai layer hoặc tạo file hướng dẫn.
