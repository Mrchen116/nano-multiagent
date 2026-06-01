"""Observability helpers for CLI release diagnostics and troubleshooting."""

from __future__ import annotations


_GUARDRAIL_HINT_BY_REASON = {
    "throughput": "throughput: 检查 run_id 过滤或去重策略是否过严。",
    "redraw_ratio": "redraw_ratio: 检查 preview 发射是否超过关键节点集合。",
    "sample_size": "sample_size: 当前样本不足，继续采样后再判定稳定性。",
}


def summarize_perf_metrics(metrics: dict[str, object]) -> list[str]:
    """Build human-readable summary lines from one perf metrics snapshot."""
    batches = _read_int(metrics.get("batches"))
    polled = _read_int(metrics.get("polled_events"))
    consumed = _read_int(metrics.get("consumed_events"))
    preview = _read_int(metrics.get("preview_emitted"))
    filtered = _read_int(metrics.get("run_filtered"))
    dedupe = _read_int(metrics.get("dedupe_dropped"))
    stable = _read_bool(metrics.get("stable"))
    reason = _read_reason(metrics.get("guardrail_reason"))
    throughput = _read_float(metrics.get("throughput_ratio"))
    redraw_ratio = _read_float(metrics.get("redraw_ratio"))
    sample_ready = _read_bool(metrics.get("sample_ready"))
    return [
        f"perf: stable={stable} reason={reason} batches={batches}",
        f"perf: polled={polled} consumed={consumed} preview={preview} filtered={filtered} dedupe={dedupe}",
        f"perf: throughput={throughput} redraw_ratio={redraw_ratio} sample_ready={sample_ready}",
    ]


def build_guardrail_hints(metrics: dict[str, object]) -> list[str]:
    """Build actionable hints for non-stable perf guardrail snapshots."""
    if _read_bool(metrics.get("stable")):
        return []
    reasons = _parse_reason_tokens(metrics.get("guardrail_reason"))
    hints: list[str] = []
    for reason in reasons:
        hint = _GUARDRAIL_HINT_BY_REASON.get(reason)
        if hint is not None:
            hints.append(hint)
    if hints:
        return hints
    if _read_bool(metrics.get("throughput_ok")) is False:
        hints.append(_GUARDRAIL_HINT_BY_REASON["throughput"])
    if _read_bool(metrics.get("redraw_ratio_ok")) is False:
        hints.append(_GUARDRAIL_HINT_BY_REASON["redraw_ratio"])
    if _read_bool(metrics.get("sample_ready")) is False:
        hints.append(_GUARDRAIL_HINT_BY_REASON["sample_size"])
    return hints


def _parse_reason_tokens(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    parts = [part.strip() for part in value.split(",")]
    return tuple(part for part in parts if part and part != "ok")


def _read_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _read_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _read_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return False


def _read_reason(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unknown"
