"""Behavior tests for the CLI release-observability helpers documented in README."""

from coding_cli.release_observability import build_guardrail_hints
from coding_cli.release_observability import summarize_perf_metrics


def test_release_observability_summarizes_metrics_for_operators() -> None:
    lines = summarize_perf_metrics(
        {
            "batches": 3,
            "polled_events": 120,
            "consumed_events": 96,
            "preview_emitted": 12,
            "run_filtered": 18,
            "dedupe_dropped": 6,
            "throughput_ratio": 0.8,
            "redraw_ratio": 0.125,
            "sample_ready": True,
            "stable": True,
            "guardrail_reason": "ok",
        }
    )

    assert lines == [
        "perf: stable=True reason=ok batches=3",
        "perf: polled=120 consumed=96 preview=12 filtered=18 dedupe=6",
        "perf: throughput=0.8 redraw_ratio=0.125 sample_ready=True",
    ]


def test_release_observability_explains_failed_guardrails() -> None:
    hints = build_guardrail_hints(
        {
            "stable": False,
            "guardrail_reason": "throughput, redraw_ratio, sample_size",
            "throughput_ok": False,
            "redraw_ratio_ok": False,
            "sample_ready": False,
        }
    )

    assert hints == [
        "throughput: 检查 run_id 过滤或去重策略是否过严。",
        "redraw_ratio: 检查 preview 发射是否超过关键节点集合。",
        "sample_size: 当前样本不足，继续采样后再判定稳定性。",
    ]
