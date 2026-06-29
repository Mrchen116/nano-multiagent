"""Tests for the web_search presenter (feat-425 决策 5).

The product-owned web_search tool carries its own presenter (presentation travels
with the tool object, 决策 12; module boundary: written in the product package,
importing only ``agent.sdk``). Mirrors web_fetch:
- collapsed row → ``🔍 <query>`` (human-facing primary arg + globe-search emoji);
- detail → structured ``{query, provider, results, count}``;
- empty / both failure channels handled (unknown provider {ok:False,error};
  searxng raise surfaced via result.error).
"""

from __future__ import annotations

from typing import Any


class _FakeResult:
    def __init__(self, output: Any = None, error: str | None = None) -> None:
        self.output = output
        self.error = error


def _presenter():
    from personal_assistant.tools.web_search import WebSearchTool

    presenter = WebSearchTool.presenter
    assert presenter is not None
    return presenter


def test_presenter_attached_to_tool() -> None:
    # 决策 12: presentation travels with the tool object.
    from personal_assistant.tools.web_search import WebSearchTool

    assert getattr(WebSearchTool, "presenter", None) is not None


def test_start_shows_query_with_search_emoji() -> None:
    evt = _presenter().format_start({"query": "nano multiagent 架构"})
    assert evt.visible is True
    assert evt.summary == "nano multiagent 架构"
    assert evt.emoji == "🔍"
    assert evt.detail == {"query": "nano multiagent 架构"}


def test_end_success_detail_has_results() -> None:
    results = [
        {"title": "T1", "url": "https://a.example", "snippet": "s1"},
        {"title": "T2", "url": "https://b.example", "snippet": "s2"},
    ]
    evt = _presenter().format_end(
        {"query": "kw"},
        _FakeResult(
            output={
                "ok": True,
                "query": "kw",
                "provider": "duckduckgo",
                "results": results,
            }
        ),
        duration_ms=120,
    )
    assert evt.summary == "kw"
    assert evt.emoji == "🔍"
    assert evt.detail is not None
    assert evt.detail["query"] == "kw"
    assert evt.detail["provider"] == "duckduckgo"
    assert evt.detail["results"] == results
    assert evt.detail["count"] == 2


def test_end_empty_results() -> None:
    # 空态:results=[],count=0 — 前端渲染"无结果"空态。
    evt = _presenter().format_end(
        {"query": "无命中查询"},
        _FakeResult(
            output={
                "ok": True,
                "query": "无命中查询",
                "provider": "searxng",
                "results": [],
            }
        ),
        duration_ms=50,
    )
    assert evt.summary == "无命中查询"
    assert evt.detail is not None
    assert evt.detail["results"] == []
    assert evt.detail["count"] == 0


def test_end_failed_unknown_provider() -> None:
    # 失败通道 1: unknown provider → run() 返回 {ok:False,error},result.error 为空。
    # presenter 必须判 output["ok"] is False,折叠仍显 query,展开看到 error。
    evt = _presenter().format_end(
        {"query": "kw"},
        _FakeResult(
            output={"ok": False, "query": "kw", "error": "Unknown provider: bogus"}
        ),
        duration_ms=5,
    )
    assert evt.summary == "kw"
    assert evt.emoji == "🔍"
    assert "Unknown provider" not in evt.summary
    assert evt.detail is not None
    assert "error" in evt.detail


def test_end_failed_searxng_raise() -> None:
    # 失败通道 2: searxng provider raise → 内核 result.error 非空。
    evt = _presenter().format_end(
        {"query": "kw"},
        _FakeResult(error="SEARXNG_URL is not set"),
        duration_ms=5,
    )
    assert evt.summary == "kw"
    assert evt.emoji == "🔍"
    assert "SEARXNG_URL" not in evt.summary
    assert evt.detail is not None
    assert "error" in evt.detail
