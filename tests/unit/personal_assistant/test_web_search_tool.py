"""Tests for web_search tool — provider unavailable must fail loud, not return [].

Covers:
- ImportError / missing provider package → tool raises, not returns []
- Real zero results → returns [] (provider worked, query had no hits)
- Brave fallback chain exhausted → raises
- Valid search via ddgs returns non-empty results (integration, importorskip)
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
