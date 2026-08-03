"""User-visible presentation states for the PA web search tool."""

from __future__ import annotations

from typing import Any

import pytest

from personal_assistant.tools.web_search import WebSearchTool


class _Result:
    def __init__(self, *, output: Any = None, error: str | None = None) -> None:
        self.output = output
        self.error = error


def test_search_start_exposes_query_as_visible_summary() -> None:
    event = WebSearchTool.presenter.format_start({"query": "nano multiagent"})

    assert event.visible is True
    assert event.summary == "nano multiagent"
    assert event.emoji == "🔍"
    assert event.detail == {"query": "nano multiagent"}


@pytest.mark.parametrize(
    "results",
    [
        [],
        [{"title": "Result", "url": "https://example.test", "snippet": "body"}],
    ],
)
def test_search_success_preserves_results_and_count(
    results: list[dict[str, str]],
) -> None:
    event = WebSearchTool.presenter.format_end(
        {"query": "query"},
        _Result(
            output={
                "ok": True,
                "query": "query",
                "provider": "searxng",
                "results": results,
            }
        ),
        duration_ms=10,
    )

    assert event.summary == "query"
    assert event.detail == {
        "query": "query",
        "provider": "searxng",
        "results": results,
        "count": len(results),
    }


@pytest.mark.parametrize(
    "result",
    [
        _Result(output={"ok": False, "error": "Unknown provider"}),
        _Result(error="SEARXNG_URL is not set"),
    ],
)
def test_search_failure_keeps_query_summary_and_exposes_error_detail(
    result: _Result,
) -> None:
    event = WebSearchTool.presenter.format_end(
        {"query": "query"},
        result,
        duration_ms=10,
    )

    assert event.summary == "query"
    assert event.emoji == "🔍"
    assert event.detail is not None
    assert "error" in event.detail
    error = event.detail["error"]
    assert isinstance(error, dict)
    assert error["message"] not in event.summary
