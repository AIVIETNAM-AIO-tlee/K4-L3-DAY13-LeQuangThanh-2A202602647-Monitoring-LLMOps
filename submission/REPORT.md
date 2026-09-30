# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Quang Thành
- **MSSV:** 2A202602647
- **Lớp:** K4-L3B
- **Repository URL:**https://github.com/AIVIETNAM-AIO-tlee/K4-L3-DAY13-LeQuangThanh-2A202602647-Monitoring-LLMOps
- **Commit SHA cuối:**f867b88 (HEAD -> main) feat: complete CP1 to CP4 with incident investigation and report
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602647`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt toàn bộ 4 tiêu chí: schema, correlation ID propagation, log enrichment và PII scrubbing |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ toàn bộ 6 panel theo hợp đồng config/dashboard.yaml |
| `pytest` | 21/22 passed | 24/24 passed | Vượt qua tất cả unit test ban đầu và các test PII mở rộng |
| Số traces hợp lệ | 0 | 10+ traces | Tự tạo trên project Langfuse cá nhân, đủ root/retrieval/generation |
| Số PII leak | 0 | 0 | Không có rò rỉ PII trong toàn bộ log ghi nhận |
| Latency P95 / TTFT P95 | ~500ms / 50ms | ~650ms / 50ms | Nằm trong ngưỡng an toàn của SLO (<= 3000ms) |
| Retrieval success rate | 100% | 100% | Đạt yêu cầu guardrail (>= 90%) |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Trong `CorrelationIdMiddleware` (`app/middleware.py`), khi mỗi request đến, gọi `clear_contextvars()` để dọn sạch context của request trước nhằm tránh rò rỉ dữ liệu giữa các request đồng thời.
  - Lấy `x-request-id` từ request header nếu client truyền lên (thông qua `request.headers.get("x-request-id")`). Nếu không có, tự động sinh mã mới theo định dạng `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`).
  - Gắn correlation ID vào ngữ cảnh structlog bằng `bind_contextvars(correlation_id=correlation_id)` và lưu vào `request.state.correlation_id`.
  - Khi xử lý xong request, middleware tính thời gian chạy (`latency_ms`) và gắn `x-request-id` cùng `x-response-time-ms` vào headers của response trả về cho client.

- **Các metadata được ghi vào structured log:**
  - **Trường hệ thống và định danh:** `ts` (ISO 8601 UTC timestamp), `level` (info/error/warning), `service` (`api`/`control`), `correlation_id` (định danh đồng bộ log và trace).
  - **Context enrichment (được bind tại endpoint `/chat` trong `app/main.py`):**
    - `user_id_hash`: Hash SHA-256 (12 ký tự đầu) từ `user_id` để ẩn danh thông tin người dùng (`hash_user_id(body.user_id)`).
    - `session_id`: Định danh phiên người dùng (`body.session_id`).
    - `feature`: Chức năng gọi API (`body.feature`, ví dụ `qa`, `summary`).
    - `model`: Tên mô hình LLM được sử dụng (`agent.model`, ví dụ `claude-sonnet-4-5`).
    - `env`: Môi trường ứng dụng (`APP_ENV`, mặc định `dev`).
  - **Performance & Observability (tại event `response_sent`):** `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success` và `payload.answer_preview`.

- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Xây dựng regex patterns trong `app/pii.py` cho 4 nhóm PII nhạy cảm: Email (`[\w\.-]+@[\w\.-]+\.\w+`), Số điện thoại Việt Nam (`(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)`), CCCD (`\b\d{12}\b`), và Thẻ tín dụng (`\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b`).
  - Thiết kế processor `scrub_event` đệ quy (`_scrub_value`) trong `app/logging_config.py` để quét và thay thế tất cả giá trị string trong `event_dict` (bao gồm payload, message preview, exception details) thành `[REDACTED_<TYPE>]`.
  - Đăng ký `scrub_event` vào pipeline của structlog trước `JsonlFileProcessor()` và `JSONRenderer()`. Điều này đảm bảo toàn bộ dữ liệu log được làm sạch trong bộ nhớ trước khi tuần tự hóa JSON và ghi ra file `data/logs.jsonl` hoặc terminal.

- **Cách kiểm chứng kết quả:**
  - Chạy `pytest tests/test_pii.py`: Kiểm chứng các hàm che PII hoạt động chính xác với các định dạng email, số điện thoại VN (+84, 09x, dấu chấm, dấu cách), CCCD 12 số và thẻ tín dụng.
  - Chạy `load_test.py` với các câu hỏi chứa PII từ `data/sample_queries.jsonl`.
  - Chạy `python scripts/validate_logs.py`: Đạt điểm tuyệt đối **100/100**, kiểm tra 20 bản ghi log đạt chuẩn JSON schema, đầy đủ context enrichment, có đủ correlation IDs hợp lệ và 0 lỗi rò rỉ PII.
  - Kiểm tra `curl.exe -i http://127.0.0.1:8000/health`: Xác nhận response header có trả về `x-request-id` và `x-response-time-ms`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Cấu hình API keys trong `.env` trỏ về đúng project riêng `day13-k4-l3b-2A202602647` trên Langfuse Cloud (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL=https://cloud.langfuse.com`).
  - Mỗi trace mang tag định danh môi trường `environment=dev`, `tags=["lab", feature, model]`, `user_id_hash` và `session_id`.
  - Màn hình Langfuse hiển thị rõ tên project `day13-k4-l3b-2A202602647` và danh sách trace do workload máy local gửi lên.
- **Cấu trúc root/retrieval/generation observations:**
  - **Trace root:** Tên `day13-agent-request` bao bọc toàn bộ chu kỳ xử lý request của agent.
  - **Agent span (root observation):** `lab-agent-run` (loại `agent`) lưu trữ các metadata chung (`doc_count`, `query_preview`, `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`).
  - **Child observation 1:** `retrieval` (loại `retriever`) đo lường thời gian tìm kiếm tài liệu từ corpus và trả về các document phù hợp.
  - **Child observation 2:** `generation` (loại `generation`) bọc lệnh gọi `self.llm.generate()`, ghi nhận chính xác `model` (`claude-sonnet-4-5`), `prompt`, `usage_details` (`input`, `output`, `total` tokens) và `cost_details` (`total` USD).
- **Cách nối trace với log:**
  - Nhờ `CorrelationIdMiddleware`, mỗi request có một `correlation_id` duy nhất (ví dụ: `req-6cf8f590`).
  - ID này vừa được bind vào structlog để in ra mọi dòng log trong request (`data/logs.jsonl`), vừa được truyền vào `propagate_attributes(metadata={"correlation_id": correlation_id})` của Langfuse trace.
  - Khi cần đối chiếu, chỉ cần lấy `correlation_id` từ log đem tìm kiếm trong ô filter metadata trên Langfuse để mở đúng trace tương ứng.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (`v1`) - gắn label `baseline` và `production` ban đầu.
- **Version/label candidate:** Version 2 (`v2`) - chỉnh sửa độ dài/format phản hồi, gắn label `candidate`.
- **Trace ID của mỗi version:**
  - Trace ID dùng Version 1 (`baseline`/`production`): `04bf5f718e81edd48e3d4ca9ad5cae95`
  - Trace ID dùng Version 2 (`candidate`): `59d779c418c1610c41d0799fad0d4db2`
- **Cách promote và rollback `production`:**
  - **Promote:** Trên Langfuse UI, tại prompt `day13-chat`, gán thêm label `production` cho Version 2 (để lưu lượng production trỏ sang v2).
  - **Rollback:** Khi phát hiện version 2 gây suy giảm hiệu năng/chi phí (regression), chuyển label `production` quay trở lại trỏ vào Version 1 ngay trên UI mà không cần sửa code ứng dụng.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - Xây dựng theo hợp đồng `config/dashboard.yaml` và kiểm chứng đạt 6/6 panel qua `validate_dashboard.py`.
  - Được hiển thị trực quan tại endpoint runtime `http://127.0.0.1:8000/dashboard` đọc trực tiếp từ `data/logs.jsonl` trong cửa sổ 60 phút, tự làm mới sau 30 giây:
    1. *Latency percentiles & TTFT:* P50, P95, P99 và TTFT P95 (threshold: P95 <= 3000ms).
    2. *Request traffic:* Tổng requests và tốc độ (req/phút) (threshold: rate >= 1 req/min).
    3. *Error rate & Retrieval:* Tỷ lệ lỗi (%) và tỷ lệ retrieval thành công (%) (threshold: error_rate <= 2%).
    4. *Cost over time:* Tổng chi phí USD và chi phí trung bình/request (threshold: total <= $2.50).
    5. *Input and output tokens:* Tổng số token in và token out (threshold: total <= 50,000 tokens).
    6. *Quality proxy:* Điểm đánh giá heuristic chất lượng câu trả lời (threshold: mean >= 0.75).
- **SLO và lý do chọn:**
  - SLO chính: `fast_successful_requests` với mục tiêu **99.5%** trong cửa sổ trượt 28 ngày.
  - SLI đạt yêu cầu khi: `event == "response_sent" and latency_ms <= 3000`.
  - Lý do: Phản hồi nhanh (dưới 3 giây) và không gặp lỗi là yếu tố then chốt cho trải nghiệm người dùng trong hệ thống đàm thoại AI/RAG.
- **Cách tính error budget:**
  - Với SLO là **99.5%**, error budget tương ứng là **0.5%** ($100\% - 99.5\%$).
  - Trong cửa sổ 28 ngày, nếu hệ thống tiếp nhận 10,000 request thì tối đa chỉ có 50 request được phép bị lỗi (HTTP 500) hoặc có độ trễ vượt quá 3,000ms. Nếu số request lỗi vượt quá 50, error budget sẽ bị cháy (exhausted) và cần phong tỏa phát hành tính năng mới để tập trung vá lỗi hệ thống.
- **Ba alert và runbook tương ứng:**
  - *Alert 1 (`HighLatencyP95`):* Cảnh báo `warning` khi P95 latency vượt 3,000ms duy trì trong 5 phút. Runbook tại `docs/alerts.md#alert-1`.
  - *Alert 2 (`HighErrorRate`):* Cảnh báo `critical` khi error rate vượt 2% duy trì trong 3 phút. Runbook tại `docs/alerts.md#alert-2`.
  - *Alert 3 (`LowRetrievalSuccessRate`):* Cảnh báo `warning` khi tỷ lệ retrieval thành công giảm dưới 90% duy trì trong 5 phút. Runbook tại `docs/alerts.md#alert-3`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** `2026-09-30 05:48:00Z – 05:50:00Z` (12:48 – 12:50 múi giờ Asia/Ho_Chi_Minh)
- **Triệu chứng từ metrics:**
  - Panel Latency trên Dashboard và kết quả đo workload tăng vọt bất thường: Latency P95 đạt hơn **2,654 ms** (vượt ngưỡng cho phép của challenge `latency_threshold_ms: 2000` và đe dọa trực tiếp SLO 99.5%), trong khi các chỉ số error rate (0%), quality score (0.80 - 0.90) và cost vẫn ở mức bình thường.
- **Log line và correlation ID liên quan:**
  - Correlation ID: `req-9f4e76cb` (đại diện cho query *"Describe how to prove a slow span is the root cause."*, session: `k4-l3b-challenge-s05`, user: `k4-l3b-u05`).
  - Dòng log `response_sent`:
    ```json
    {"service": "api", "latency_ms": 2653, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 125, "cost_usd": 0.00198, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "user_id_hash": "68e37dc7cb5e", "model": "claude-sonnet-4-5", "session_id": "k4-l3b-challenge-s05", "feature": "monitoring", "correlation_id": "req-9f4e76cb", "env": "dev", "level": "info", "ts": "2026-09-30T05:48:30.962728Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Trace ID: `6f038f4afcc9b3b54c11216ddc52e2c4` (tìm thấy trên Langfuse qua filter `correlation_id: req-9f4e76cb`).
  - Phân tích chi tiết waterfall trên Langfuse:
    - Root span `lab-agent-run`: tổng thời gian `2.654 s`.
    - Span con `generation`: thời gian chỉ mất `0.153 s` (hoàn toàn bình thường).
    - Span con `retrieval`: thời gian kéo dài tới **`2.501 s`** (chiếm tới 94.2% tổng thời gian của cả request).
  - Kết luận: Span `retrieval` chính là điểm nghẽn (bottleneck) trực tiếp gây chậm.
- **Root cause:**
  - Sự cố `rag_slow` được kích hoạt trên hệ thống, làm cho bước truy vấn dữ liệu từ vector database / retriever bị nghẽn (mô phỏng bởi độ trễ 2.5 giây trong hàm `retrieve()`). Do bước retrieval bị nghẽn nặng nên toàn bộ chu trình xử lý request bị kéo dài vượt ngưỡng 2000ms.
- **Fix action:**
  - Khôi phục hoạt động của retrieval bằng cách vô hiệu hóa sự cố (`disable incident rag_slow` qua lệnh `python scripts/inject_incident.py --disable` hoặc gọi API `POST /incidents/rag_slow/disable`).
  - Sau khi disable, độ trễ `retrieval` lập tức quay về mức dưới 5ms, đưa tổng latency của request về mức bình thường (~160ms).
- **Preventive measure:**
  - Thiết lập timeout nghiêm ngặt cho bước retrieval (ví dụ `timeout=1.0s`). Nếu quá thời gian này mà vector store chưa phản hồi thì tự động kích hoạt fallback context hoặc static knowledge để không làm chậm toàn bộ request.
  - Bật Alert `HighLatencyP95` (với threshold 3000ms trong 5m) và thiết lập circuit breaker cho retrieval service để tự động cách ly khi vector DB bị quá tải.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Quyết định phân tách child observations độc lập (`retrieval` và `generation`) dưới root span `lab-agent-run` bằng Observation API của Langfuse Python SDK v4 thay vì chỉ quan sát toàn bộ agent như một hộp đen. Quyết định này cho phép bóc tách chính xác thời gian của tầng tìm kiếm (retrieval) và tầng sinh ngôn ngữ (LLM generation). Nhờ đó, khi sự cố xảy ra, kỹ sư có thể cô lập ngay nguyên nhân nằm ở RAG retrieval hay do LLM/prompt chỉ trong vài giây.
- **Một lỗi/blocker đã gặp:**
  - Khi bắt đầu CP1, việc truy cập trực tiếp `request.headers["x-request-id"]` làm server ném ngoại lệ `KeyError: 'x-request-id'` với những request không gửi header này từ client, dẫn đến sập middleware.
- **Cách tìm nguyên nhân và xử lý:**
  - Kiểm tra log lỗi chi tiết qua `pytest tests/test_chat_observability.py`, phát hiện lỗi truy cập dict header không an toàn. Đã chuyển sang dùng `request.headers.get("x-request-id")`, đồng thời tự động sinh mã dự phòng `f"req-{uuid.uuid4().hex[:8]}"` nếu header rỗng.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics** là lớp radar cảnh báo đầu tiên: Cho biết *hệ thống có vấn đề gì và xảy ra từ lúc nào* (ví dụ: Latency P95 trên dashboard vượt ngưỡng 2000ms).
  - **Logs** là lớp thu hẹp phạm vi: Giúp trích xuất *request cụ thể nào bị ảnh hưởng* bằng cách lọc các log line bất thường trong khoảng thời gian xảy ra sự cố và lấy mã `correlation_id` (ví dụ `req-9f4e76cb`).
  - **Traces** là lớp chẩn đoán gốc rễ: Dùng `correlation_id` từ log để mở đúng cây waterfall trace trên Langfuse nhằm xác định chính xác *bước/span nào bên trong request đó chạy chậm hoặc lỗi* (ví dụ: phát hiện span `retrieval` mất 2.501s).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Prompt là một thành phần có tính biến động cao và ảnh hưởng trực tiếp đến chất lượng, độ trễ và chi phí token. Quản lý prompt theo version và label (`production`, `candidate`, `baseline`) cho phép theo dõi sát sao regression và thực hiện rollback tức thời trên UI/SDK mà không cần can thiệp redeploy code khi bản prompt mới gặp vấn đề về chi phí hoặc độ dài.
- **Điều quan trọng nhất đã học:**
  - Quy trình vận hành và điều tra có căn cứ dữ liệu (data-driven observability) thay vì suy đoán cảm tính. Việc gắn kết chặt chẽ giữa `correlation_id` trong structured log và distributed trace là chìa khóa để gỡ lỗi các hệ thống AI phức tạp.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Hệ thống hiện tại đang sử dụng FakeLLM và in-memory vector store cho môi trường lab, chưa tích hợp streaming TTFT thực tế qua WebSocket / SSE từ remote LLM providers.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
