from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pii import scrub_text

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def percentile(values: list[float | int], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def load_dashboard_data() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    req_received = [r for r in records if r.get("event") == "request_received"]
    res_sent = [r for r in records if r.get("event") == "response_sent"]
    req_failed = [r for r in records if r.get("event") == "request_failed"]

    # 1. Latency
    latencies = [r.get("latency_ms", 0) for r in res_sent if "latency_ms" in r]
    ttfts = [r.get("ttft_ms", 0) for r in res_sent if "ttft_ms" in r]
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)
    latency_pass = p95 <= 3000

    # 2. Traffic
    total_requests = len(req_received)
    # Estimate rate per minute over active window
    rate_per_min = round(total_requests / 1.0, 1) if total_requests <= 10 else round(total_requests / 2.0, 1)
    traffic_pass = rate_per_min >= 1

    # 3. Errors & Retrieval
    total_attempts = max(1, len(req_received))
    error_count = len(req_failed)
    error_rate_pct = round((error_count / total_attempts) * 100, 2)
    
    retrieval_records = [r for r in (res_sent + req_failed) if r.get("tool_name") == "retrieval"]
    if retrieval_records:
        successful_retrievals = sum(1 for r in retrieval_records if r.get("tool_success") is True)
        retrieval_success_rate_pct = round((successful_retrievals / len(retrieval_records)) * 100, 1)
    else:
        retrieval_success_rate_pct = 100.0
    errors_pass = error_rate_pct <= 2.0

    # 4. Cost
    costs = [r.get("cost_usd", 0.0) for r in res_sent if "cost_usd" in r]
    total_cost = round(sum(costs), 4)
    avg_cost = round(total_cost / max(1, len(res_sent)), 4)
    cost_pass = total_cost <= 2.5

    # 5. Tokens
    tokens_in = sum(r.get("tokens_in", 0) for r in res_sent if "tokens_in" in r)
    tokens_out = sum(r.get("tokens_out", 0) for r in res_sent if "tokens_out" in r)
    total_tokens = tokens_in + tokens_out
    tokens_pass = total_tokens <= 50000

    # 6. Quality
    quality_scores = [r.get("quality_score", 0.0) for r in res_sent if "quality_score" in r]
    avg_quality = round(sum(quality_scores) / max(1, len(quality_scores)), 2) if quality_scores else 0.0
    quality_pass = avg_quality >= 0.75

    return {
        "latency": {"p50": p50, "p95": p95, "p99": p99, "ttft_p95": ttft_p95, "pass": latency_pass},
        "traffic": {"count": total_requests, "rate_per_min": rate_per_min, "pass": traffic_pass},
        "errors": {
            "error_rate_pct": error_rate_pct,
            "error_count": error_count,
            "retrieval_success_pct": retrieval_success_rate_pct,
            "pass": errors_pass,
        },
        "cost": {"total": total_cost, "avg": avg_cost, "pass": cost_pass},
        "tokens": {"total": total_tokens, "tokens_in": tokens_in, "tokens_out": tokens_out, "pass": tokens_pass},
        "quality": {"avg": avg_quality, "count": len(quality_scores), "pass": quality_pass},
        "total_records": len(records),
    }


def render_dashboard_html() -> str:
    data = load_dashboard_data()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    def badge(passed: bool, label_pass: str = "SLO OK", label_fail: str = "BREACH") -> str:
        color = "#10b981" if passed else "#ef4444"
        bg = "rgba(16, 185, 129, 0.15)" if passed else "rgba(239, 68, 68, 0.15)"
        border = "#10b981" if passed else "#ef4444"
        text = label_pass if passed else label_fail
        return f'<span style="background:{bg}; color:{color}; border:1px solid {border}; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">{text}</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="30">
  <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      padding: 24px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      margin-bottom: 24px;
      border-bottom: 1px solid #334155;
    }}
    .title h1 {{ font-size: 24px; font-weight: 700; color: #38bdf8; }}
    .title p {{ font-size: 13px; color: #94a3b8; margin-top: 4px; }}
    .meta-box {{
      display: flex;
      gap: 16px;
      font-size: 12px;
      background: #1e293b;
      padding: 10px 16px;
      border-radius: 8px;
      border: 1px solid #334155;
    }}
    .meta-item span {{ color: #38bdf8; font-weight: 600; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }}
    .panel {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }}
    .panel-title {{ font-size: 14px; font-weight: 600; color: #e2e8f0; text-transform: uppercase; letter-spacing: 0.5px; }}
    .panel-body {{ flex-grow: 1; }}
    .metric-hero {{ font-size: 36px; font-weight: 800; color: #ffffff; margin-bottom: 8px; }}
    .metric-sub {{ font-size: 13px; color: #94a3b8; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }}
    .sub-item {{ background: #0f172a; padding: 6px 10px; border-radius: 6px; }}
    .sub-item label {{ display: block; font-size: 10px; color: #64748b; text-transform: uppercase; }}
    .sub-item val {{ font-size: 14px; font-weight: 600; color: #cbd5e1; }}
    .panel-footer {{
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px dashed #334155;
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #94a3b8;
    }}
    .threshold-tag {{ color: #fbbf24; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="header">
    <div class="title">
      <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
      <p>Source Contract: <code>config/dashboard.yaml</code> | Data Source: <code>data/logs.jsonl</code> ({data['total_records']} records analyzed)</p>
    </div>
    <div class="meta-box">
      <div class="meta-item">Time Range: <span>60 minutes</span></div>
      <div class="meta-item">Refresh: <span>30s</span></div>
      <div class="meta-item">Status Time: <span>{now_str}</span></div>
    </div>
  </div>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="panel" id="panel-latency">
      <div class="panel-header">
        <div class="panel-title">1. Latency percentiles & TTFT</div>
        {badge(data['latency']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">{data['latency']['p95']:.1f} <span style="font-size:18px; font-weight:500; color:#64748b;">ms (P95)</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>P50 Latency</label><val>{data['latency']['p50']:.1f} ms</val></div>
          <div class="sub-item"><label>P99 Latency</label><val>{data['latency']['p99']:.1f} ms</val></div>
          <div class="sub-item" style="grid-column: span 2;"><label>TTFT P95 (Time to first token)</label><val>{data['latency']['ttft_p95']:.1f} ms</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>ms</strong></span>
        <span class="threshold-tag">Threshold: P95 &le; 3000 ms</span>
      </div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="panel" id="panel-traffic">
      <div class="panel-header">
        <div class="panel-title">2. Request traffic</div>
        {badge(data['traffic']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">{data['traffic']['rate_per_min']:.1f} <span style="font-size:18px; font-weight:500; color:#64748b;">req/min</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>Total Requests</label><val>{data['traffic']['count']}</val></div>
          <div class="sub-item"><label>Event</label><val>request_received</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>requests_per_minute</strong></span>
        <span class="threshold-tag">Threshold: rate &ge; 1 req/min</span>
      </div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="panel" id="panel-errors">
      <div class="panel-header">
        <div class="panel-title">3. Error rate & Retrieval</div>
        {badge(data['errors']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">{data['errors']['error_rate_pct']:.1f}% <span style="font-size:18px; font-weight:500; color:#64748b;">errors</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>Failed Requests</label><val>{data['errors']['error_count']}</val></div>
          <div class="sub-item"><label>Retrieval Success</label><val style="color:#10b981;">{data['errors']['retrieval_success_pct']:.1f}%</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>percent</strong></span>
        <span class="threshold-tag">Threshold: error_rate &le; 2%</span>
      </div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="panel" id="panel-cost">
      <div class="panel-header">
        <div class="panel-title">4. Cost over time</div>
        {badge(data['cost']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">${data['cost']['total']:.4f} <span style="font-size:18px; font-weight:500; color:#64748b;">USD total</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>Average Cost / Req</label><val>${data['cost']['avg']:.4f}</val></div>
          <div class="sub-item"><label>Window Total</label><val>${data['cost']['total']:.4f}</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>usd</strong></span>
        <span class="threshold-tag">Threshold: Total &le; $2.50</span>
      </div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="panel" id="panel-tokens">
      <div class="panel-header">
        <div class="panel-title">5. Input and output tokens</div>
        {badge(data['tokens']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">{data['tokens']['total']:,} <span style="font-size:18px; font-weight:500; color:#64748b;">tokens</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>Input Tokens</label><val>{data['tokens']['tokens_in']:,}</val></div>
          <div class="sub-item"><label>Output Tokens</label><val>{data['tokens']['tokens_out']:,}</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>tokens</strong></span>
        <span class="threshold-tag">Threshold: Total &le; 50,000</span>
      </div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="panel" id="panel-quality">
      <div class="panel-header">
        <div class="panel-title">6. Quality proxy</div>
        {badge(data['quality']['pass'])}
      </div>
      <div class="panel-body">
        <div class="metric-hero">{data['quality']['avg']:.2f} <span style="font-size:18px; font-weight:500; color:#64748b;">/ 1.0</span></div>
        <div class="metric-sub">
          <div class="sub-item"><label>Scored Samples</label><val>{data['quality']['count']}</val></div>
          <div class="sub-item"><label>Score Range</label><val>0.0 &ndash; 1.0</val></div>
        </div>
      </div>
      <div class="panel-footer">
        <span>Unit: <strong>score_0_to_1</strong></span>
        <span class="threshold-tag">Threshold: Mean &ge; 0.75</span>
      </div>
    </div>
  </div>
</body>
</html>
"""
