# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Primary SLO `fast_successful_requests` (latency P95 của `response_sent.latency_ms`)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` kéo dài liên tục trong `5m`
- Ảnh hưởng tới người dùng: Người dùng phải chờ đợi phản hồi quá lâu (> 3 giây), trải nghiệm chat bị suy giảm, nguy cơ tiêu hao nhanh error budget của SLO 99.5%.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency trên Dashboard để kiểm tra P50/P95/P99 và TTFT nhằm xác định khoảng thời gian latency bắt đầu tăng vọt.
  2. Lọc `data/logs.jsonl` trong khung giờ đó, tìm các log event `response_sent` có `latency_ms > 3000` và trích xuất một `correlation_id` đại diện.
  3. Mở trace trên Langfuse có cùng `correlation_id`, so sánh thời gian thực thi của span `retrieval` và span `generation` để xác định bước nào là thủ phạm gây nghẽn.
- Mitigation tạm thời:
  - Nếu span `retrieval` bị chậm: Kiểm tra tải và tình trạng vector database/cache, kích hoạt timeout hoặc bật fallback context.
  - Nếu span `generation` bị chậm hoặc prompt mới sinh quá nhiều token: Rollback label prompt `production` về version ổn định trước đó. Tắt practice scenario nếu đang bật giả lập sự cố.
- Owner: `student-2A202602647` (Lê Quang Thành)

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail `error_rate_pct_max: 2` (tỷ lệ request lỗi so với tổng request nhận vào)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` kéo dài liên tục trong `3m`
- Ảnh hưởng tới người dùng: Người dùng nhận phản hồi lỗi HTTP 500 hoặc thông báo hệ thống không khả dụng, làm gián đoạn hoàn toàn luồng nghiệp vụ.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors trên Dashboard để kiểm tra biểu đồ lỗi và bảng phân loại `error_type`.
  2. Lọc file `data/logs.jsonl` tìm các log event `request_failed` gần nhất, đọc trường `error_type`, `payload.detail` và lấy một `correlation_id` của request gặp lỗi.
  3. Tra cứu trace có cùng `correlation_id` trên Langfuse để xem chi tiết exception stack trace và quan sát span nào ném ra exception.
- Mitigation tạm thời:
  - Nếu lỗi do dependency bên thứ 3 hoặc vector database: Kích hoạt mạch ngắt (circuit breaker), chuyển sang câu trả lời dự phòng (fallback answer).
  - Khởi động lại service hoặc rollback commit/deploy gần nhất nếu phát sinh lỗi code logic mới.
- Owner: `student-2A202602647` (Lê Quang Thành)

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail `retrieval_success_rate_pct_min: 90` (tỷ lệ retrieval thành công)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` kéo dài liên tục trong `5m`
- Ảnh hưởng tới người dùng: RAG không tìm được context phù hợp hoặc gặp lỗi kết nối vector store, dẫn đến LLM bị ảo giác (hallucination) hoặc trả về câu trả lời chung chung không chính xác.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors trên Dashboard, đối chiếu tỷ lệ `retrieval success rate` với ngưỡng 90%.
  2. Lọc `data/logs.jsonl` tìm các bản ghi có `tool_name == "retrieval"` và `tool_success == false`, lấy `correlation_id` liên quan.
  3. Kiểm tra trace trên Langfuse để xem input query của bước retrieval và thông báo lỗi/thời gian timeout của span `retrieval`.
- Mitigation tạm thời:
  - Khôi phục kết nối vector store, kiểm tra index hoặc tạm thời sử dụng static documents/fallback context để đảm bảo chất lượng phản hồi tối thiểu.
- Owner: `student-2A202602647` (Lê Quang Thành)
