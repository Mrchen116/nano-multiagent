"""Compatibility shim for the canonical apps-level CLI release observability helpers."""

from nano_multiagent.apps.coding_cli.release_observability import build_guardrail_hints, summarize_perf_metrics

__all__ = ["build_guardrail_hints", "summarize_perf_metrics"]
