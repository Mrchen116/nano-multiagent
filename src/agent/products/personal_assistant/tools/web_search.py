"""Product-owned web_search tool for personal_assistant — web search with provider fallback."""

from __future__ import annotations

import os
from typing import Any, Mapping

from agent.core.tools.base import ToolContext


def _search_duckduckgo(query: str, count: int) -> list[dict[str, str]]:
    """Search via DuckDuckGo (free, no API key).

    Returns:
        List of dicts with title/url/snippet keys. Empty list on failure.
    """
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=count))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]
    except Exception:
        return []


def _search_brave(query: str, count: int) -> list[dict[str, str]]:
    """Search via Brave Search API. Falls back to DuckDuckGo when key is absent.

    Requires BRAVE_API_KEY env var.

    Returns:
        List of dicts with title/url/snippet keys.
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return _search_duckduckgo(query, count)
    try:
        import httpx  # type: ignore[import-untyped]

        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return [
            {
                "title": x.get("title", ""),
                "url": x.get("url", ""),
                "snippet": x.get("description", ""),
            }
            for x in resp.json().get("web", {}).get("results", [])
        ]
    except Exception:
        return _search_duckduckgo(query, count)


_PROVIDERS: dict[str, Any] = {
    "duckduckgo": _search_duckduckgo,
    "brave": _search_brave,
}


class WebSearchTool:
    """Search the web using DuckDuckGo (free) or Brave (API key).

    Args:
        default_provider: Provider name used when caller omits ``provider``.
    """

    name = "web_search"
    description = (
        "Search the web and return a list of results with title, URL, and snippet. "
        "Supports providers: duckduckgo (free, default), brave (needs BRAVE_API_KEY)."
    )
    input_schema: Mapping[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "count": {
                "type": "integer",
                "description": "Number of results (1-10, default 5).",
                "minimum": 1,
                "maximum": 10,
            },
            "provider": {
                "type": "string",
                "description": "Search provider: duckduckgo (default) or brave.",
                "enum": ["duckduckgo", "brave"],
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, *, default_provider: str = "duckduckgo") -> None:
        self._default_provider = default_provider

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Execute a web search and return structured results.

        Args:
            args: Must contain ``query``; optionally ``count`` and ``provider``.
            ctx: Tool execution context (unused beyond protocol compliance).

        Returns:
            Dict with ``ok``, ``query``, ``provider``, ``results`` keys.

        Raises:
            ValueError: If ``query`` is missing or empty.
        """
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        query = query.strip()
        count = min(max(int(args.get("count", 5)), 1), 10)
        provider = str(args.get("provider", self._default_provider)).strip().lower()

        search_fn = _PROVIDERS.get(provider)
        if search_fn is None:
            return {
                "ok": False,
                "error": f"Unknown provider: {provider}",
                "query": query,
            }

        raw = search_fn(query, count)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in raw[:count]
        ]
        return {"ok": True, "query": query, "provider": provider, "results": results}


TOOL = WebSearchTool()
