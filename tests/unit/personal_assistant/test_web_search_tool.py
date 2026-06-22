"""Tests for web_search tool — provider unavailable must fail loud, not return [].

Covers:
- ImportError / missing provider package → tool raises, not returns []
- Real zero results → returns [] (provider worked, query had no hits)
- Brave fallback chain exhausted → raises
- Valid search via ddgs returns non-empty results (integration, importorskip)
- SearXNG provider: normal returns, unreachable raises, unset SEARXNG_URL raises,
  empty results, and SEARXNG_URL-driven auto-default selection
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.core.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ToolContext:
    """Minimal ToolContext for tool calls."""
    ctx = MagicMock(spec=ToolContext)
    return ctx


def _make_tool() -> Any:
    from personal_assistant.tools.web_search import WebSearchTool

    return WebSearchTool()


# ---------------------------------------------------------------------------
# P0: provider import failure → must raise, not return []
# ---------------------------------------------------------------------------


def test_web_search_raises_when_ddgs_not_installed() -> None:
    """When ddgs package is absent, _search_duckduckgo must raise ImportError.

    The previous `except Exception: return []` swallowed this silently — tool
    appeared to work but always returned empty results.
    """
    import sys

    tool = _make_tool()
    ctx = _make_ctx()

    # Block ddgs by poisoning sys.modules — raises ModuleNotFoundError on `from ddgs import`
    with patch.dict(sys.modules, {"ddgs": None}):  # type: ignore[dict-item]
        with pytest.raises((ImportError, ModuleNotFoundError)):
            tool.run({"query": "test query"}, ctx)


def test_web_search_raises_when_provider_call_fails() -> None:
    """When DDGS().text() raises (e.g. network/auth error), the error must propagate.

    Provider-level failures are not 'zero results' — they mean 'search unavailable'.
    Uses patch.dict on _PROVIDERS so the tool's dispatch path sees the replaced fn.
    """
    from personal_assistant.tools import web_search as ws_module

    def _failing_ddgs(query: str, count: int) -> list[Any]:
        raise RuntimeError("upstream search provider unreachable")

    with patch.dict(ws_module._PROVIDERS, {"duckduckgo": _failing_ddgs}):
        tool = _make_tool()
        ctx = _make_ctx()
        with pytest.raises(RuntimeError):
            tool.run({"query": "anything"}, ctx)


# ---------------------------------------------------------------------------
# P0: true zero results → [] (provider worked normally)
# ---------------------------------------------------------------------------


def test_web_search_returns_empty_list_on_true_zero_results() -> None:
    """When provider returns [] legitimately (no hits), tool must return ok=True, results=[]."""
    from personal_assistant.tools import web_search as ws_module

    def _zero_results(query: str, count: int) -> list[Any]:
        return []

    with patch.dict(ws_module._PROVIDERS, {"duckduckgo": _zero_results}):
        tool = _make_tool()
        ctx = _make_ctx()
        result = tool.run({"query": "xyzzy_this_query_has_no_results_12345"}, ctx)

    assert result["ok"] is True
    assert result["results"] == []


# ---------------------------------------------------------------------------
# P0: Brave fallback chain exhausted → raises
# ---------------------------------------------------------------------------


def test_brave_fallback_exhausted_raises() -> None:
    """When Brave API fails and ddgs also fails, the error must propagate — not return [].

    Previously: brave except → _search_duckduckgo() → except → [] (silent double-swallow).
    Now: brave except → _search_duckduckgo() → raises → caller sees error.
    Uses patch.dict on _PROVIDERS so the dispatch in tool.run picks up the replaced fn.
    """
    from personal_assistant.tools import web_search as ws_module

    def _failing_brave(query: str, count: int) -> list[Any]:
        raise RuntimeError("brave and ddg both down")

    with patch.dict(ws_module._PROVIDERS, {"brave": _failing_brave}):
        tool = _make_tool()
        ctx = _make_ctx()
        with pytest.raises(RuntimeError):
            tool.run({"query": "test", "provider": "brave"}, ctx)


# ---------------------------------------------------------------------------
# P0: integration — ddgs installed → returns real results (importorskip)
# ---------------------------------------------------------------------------


def test_web_search_returns_results_when_ddgs_available() -> None:
    """When ddgs is installed, a real search query must return at least one result.

    Skipped if ddgs is not installed (optional integration check).
    """
    pytest.importorskip(
        "ddgs", reason="ddgs not installed — skipping integration check"
    )

    tool = _make_tool()
    ctx = _make_ctx()
    result = tool.run({"query": "python programming language", "count": 3}, ctx)

    assert result["ok"] is True
    assert isinstance(result["results"], list)
    # Real search should return some results for a common query
    assert len(result["results"]) > 0
    first = result["results"][0]
    assert "title" in first
    assert "url" in first
    assert "snippet" in first


# ---------------------------------------------------------------------------
# SearXNG provider — normalization, fail-loud, auto-default
# ---------------------------------------------------------------------------


def _mock_searxng_response(results: list[dict[str, Any]]) -> MagicMock:
    """Build a fake httpx.Response whose .json() returns a SearXNG payload."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"results": results}
    return resp


def test_searxng_normalizes_and_sorts_by_score(monkeypatch: Any) -> None:
    """Explicit provider=searxng returns {title,url,snippet}, sorted by score desc, capped to count."""
    from personal_assistant.tools import web_search as ws_module

    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    raw = [
        {"title": "low", "url": "http://a", "content": "a body", "score": 0.1},
        {"title": "high", "url": "http://b", "content": "b body", "score": 9.0},
        {"title": "mid", "url": "http://c", "content": "c body", "score": 1.0},
    ]
    with patch.object(ws_module.httpx, "get", return_value=_mock_searxng_response(raw)):
        tool = _make_tool()
        result = tool.run(
            {"query": "q", "provider": "searxng", "count": 2}, _make_ctx()
        )

    assert result["ok"] is True
    assert result["provider"] == "searxng"
    # sorted by score desc, capped to count=2
    assert [r["title"] for r in result["results"]] == ["high", "mid"]
    # content → snippet normalization, three canonical keys
    assert result["results"][0] == {
        "title": "high",
        "url": "http://b",
        "snippet": "b body",
    }


def test_searxng_unreachable_raises(monkeypatch: Any) -> None:
    """SEARXNG_URL set but instance unreachable → tool raises, does NOT return [] or fall back."""
    import httpx

    from personal_assistant.tools import web_search as ws_module

    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise httpx.ConnectError("connection refused")

    with patch.object(ws_module.httpx, "get", side_effect=_boom):
        tool = _make_tool()
        with pytest.raises(httpx.HTTPError):
            tool.run({"query": "q", "provider": "searxng"}, _make_ctx())


def test_searxng_unset_url_raises(monkeypatch: Any) -> None:
    """Explicit provider=searxng but SEARXNG_URL unset → tool raises with a clear message."""
    from personal_assistant.tools.web_search import WebSearchTool

    monkeypatch.delenv("SEARXNG_URL", raising=False)
    tool = WebSearchTool()
    with pytest.raises(RuntimeError, match="SEARXNG_URL"):
        tool.run({"query": "q", "provider": "searxng"}, _make_ctx())


def test_searxng_empty_results_ok(monkeypatch: Any) -> None:
    """SearXNG instance works but query has no hits → ok=True, results=[] (not an error)."""
    from personal_assistant.tools import web_search as ws_module

    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    with patch.object(ws_module.httpx, "get", return_value=_mock_searxng_response([])):
        tool = _make_tool()
        result = tool.run({"query": "no-hits", "provider": "searxng"}, _make_ctx())

    assert result["ok"] is True
    assert result["results"] == []


def test_auto_default_searxng_when_url_set(monkeypatch: Any) -> None:
    """SEARXNG_URL set and no provider passed → search routes through searxng."""
    from personal_assistant.tools import web_search as ws_module

    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    with patch.object(ws_module.httpx, "get", return_value=_mock_searxng_response([])):
        tool = _make_tool()
        result = tool.run({"query": "q"}, _make_ctx())

    assert result["provider"] == "searxng"


def test_explicit_provider_overrides_auto_default(monkeypatch: Any) -> None:
    """SEARXNG_URL set but caller explicitly passes duckduckgo → respect the explicit choice."""
    from personal_assistant.tools import web_search as ws_module

    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")

    def _zero(query: str, count: int) -> list[Any]:
        return []

    with patch.dict(ws_module._PROVIDERS, {"duckduckgo": _zero}):
        tool = _make_tool()
        result = tool.run({"query": "q", "provider": "duckduckgo"}, _make_ctx())

    assert result["provider"] == "duckduckgo"


def test_default_stays_duckduckgo_when_url_unset(monkeypatch: Any) -> None:
    """SEARXNG_URL unset and no provider passed → default stays duckduckgo (unchanged behavior)."""
    from personal_assistant.tools import web_search as ws_module

    monkeypatch.delenv("SEARXNG_URL", raising=False)

    def _zero(query: str, count: int) -> list[Any]:
        return []

    with patch.dict(ws_module._PROVIDERS, {"duckduckgo": _zero}):
        tool = _make_tool()
        result = tool.run({"query": "q"}, _make_ctx())

    assert result["provider"] == "duckduckgo"
