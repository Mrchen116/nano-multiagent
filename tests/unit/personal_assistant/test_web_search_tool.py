"""Operational behavior for the PA web search provider seam."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.core.tools.base import ToolContext
from personal_assistant.tools import web_search as web_search_module
from personal_assistant.tools.web_search import WebSearchTool


def _context() -> ToolContext:
    return MagicMock(spec=ToolContext)


def test_missing_default_provider_dependency_fails_loud() -> None:
    with patch.dict(sys.modules, {"ddgs": None}):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            WebSearchTool().run({"query": "query"}, _context())


def test_provider_failure_is_not_reported_as_zero_results() -> None:
    def fail(_query: str, _count: int) -> list[dict[str, str]]:
        raise RuntimeError("provider unavailable")

    with patch.dict(web_search_module._PROVIDERS, {"duckduckgo": fail}):
        with pytest.raises(RuntimeError, match="provider unavailable"):
            WebSearchTool().run({"query": "query"}, _context())


def test_true_zero_results_remain_a_success() -> None:
    with patch.dict(
        web_search_module._PROVIDERS,
        {"duckduckgo": lambda _query, _count: []},
    ):
        result = WebSearchTool().run({"query": "no hits"}, _context())

    assert result["ok"] is True
    assert result["provider"] == "duckduckgo"
    assert result["results"] == []


def _searxng_response(results: list[dict[str, Any]]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": results}
    return response


def test_searxng_results_are_normalized_ranked_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    raw = [
        {"title": "low", "url": "http://a", "content": "a body", "score": 0.1},
        {"title": "high", "url": "http://b", "content": "b body", "score": 9.0},
        {"title": "mid", "url": "http://c", "content": "c body", "score": 1.0},
    ]
    with patch.object(
        web_search_module.httpx,
        "get",
        return_value=_searxng_response(raw),
    ):
        result = WebSearchTool().run(
            {"query": "query", "provider": "searxng", "count": 2},
            _context(),
        )

    assert result["provider"] == "searxng"
    assert result["results"] == [
        {"title": "high", "url": "http://b", "snippet": "b body"},
        {"title": "mid", "url": "http://c", "snippet": "c body"},
    ]


def test_explicit_searxng_requires_configured_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    with pytest.raises(RuntimeError, match="SEARXNG_URL"):
        WebSearchTool().run(
            {"query": "query", "provider": "searxng"},
            _context(),
        )


@pytest.mark.parametrize(
    ("searxng_url", "explicit_provider", "expected_provider"),
    [
        (None, None, "duckduckgo"),
        ("http://localhost:8888", None, "searxng"),
        ("http://localhost:8888", "duckduckgo", "duckduckgo"),
    ],
)
def test_runtime_default_and_explicit_provider_selection(
    monkeypatch: pytest.MonkeyPatch,
    searxng_url: str | None,
    explicit_provider: str | None,
    expected_provider: str,
) -> None:
    if searxng_url is None:
        monkeypatch.delenv("SEARXNG_URL", raising=False)
    else:
        monkeypatch.setenv("SEARXNG_URL", searxng_url)
    arguments = {"query": "query"}
    if explicit_provider is not None:
        arguments["provider"] = explicit_provider
    providers = {
        "duckduckgo": lambda _query, _count: [],
        "searxng": lambda _query, _count: [],
    }

    with patch.dict(web_search_module._PROVIDERS, providers):
        result = WebSearchTool().run(arguments, _context())

    assert result["provider"] == expected_provider
