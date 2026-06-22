"""Product-owned web_search tool for personal_assistant — web search with provider fallback."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import httpx  # type: ignore[import-untyped]

_log = logging.getLogger("personal_assistant.tools.web_search")

from agent.sdk import ToolContext


def _search_duckduckgo(query: str, count: int) -> list[dict[str, str]]:
    """Search via DuckDuckGo (free, no API key).

    Raises ImportError if ddgs package is not installed — caller must not
    treat a missing provider as zero results.

    Returns:
        List of dicts with title/url/snippet keys. Empty list only when the
        provider works normally but the query returns no hits.
    """
    # ImportError propagates intentionally: missing provider ≠ zero results.
    from ddgs import DDGS  # type: ignore[import-untyped]

    raw = DDGS().text(query, max_results=count)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in raw
    ]


def _search_brave(query: str, count: int) -> list[dict[str, str]]:
    """Search via Brave Search API. Falls back to DuckDuckGo when key is absent.

    Requires BRAVE_API_KEY env var.

    When Brave API itself fails (network error, bad status) the call falls
    through to DuckDuckGo.  If the fallback also fails, the exception
    propagates — search is genuinely unavailable and must not be silenced.

    Returns:
        List of dicts with title/url/snippet keys.
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return _search_duckduckgo(query, count)
    try:
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
    except Exception as exc:
        # Brave API failed — log so the error is visible, then fall through to ddg;
        # if ddg also raises, propagate (genuine unavailability must not be silenced).
        _log.warning(
            "Brave Search API request failed, falling back to DuckDuckGo: %s", exc
        )
        return _search_duckduckgo(query, count)


def _search_searxng(query: str, count: int) -> list[dict[str, str]]:
    """Search via a user-hosted SearXNG instance (free, self-hosted metasearch).

    Reads the instance base URL from the ``SEARXNG_URL`` env var. Search-only:
    SearXNG aggregates upstream engines but does not fetch/extract URLs.

    Unlike ``_search_brave``, this provider does NOT fall back to another
    provider on failure — SearXNG is a source the operator deliberately chose,
    and silently reverting to the engine they meant to avoid would hide the
    problem. Failures propagate (fail-loud): an unset URL, an unreachable
    instance, a non-2xx status, or a non-JSON response all raise.

    Provenance: hermes-agent plugins/web/searxng/provider.py (score-sorted
    normalization), adapted to this repo's fail-loud provider contract.

    Returns:
        List of dicts with title/url/snippet keys, sorted by SearXNG ``score``
        descending and capped to ``count``. Empty list only when the instance
        works normally but the query returns no hits.

    Raises:
        RuntimeError: If ``SEARXNG_URL`` is not set.
        httpx.HTTPError: If the instance is unreachable or returns a bad status.
    """
    base_url = os.environ.get("SEARXNG_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "SEARXNG_URL is not set — cannot use the searxng provider. "
            "Set SEARXNG_URL to your SearXNG instance (e.g. http://localhost:8888)."
        )

    resp = httpx.get(
        f"{base_url}/search",
        params={"q": query, "format": "json", "pageno": 1},
        headers={"Accept": "application/json"},
        timeout=15.0,
    )
    resp.raise_for_status()

    raw = resp.json().get("results", [])
    ranked = sorted(raw, key=lambda r: float(r.get("score", 0)), reverse=True)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in ranked[:count]
    ]


_PROVIDERS: dict[str, Any] = {
    "duckduckgo": _search_duckduckgo,
    "brave": _search_brave,
    "searxng": _search_searxng,
}


class WebSearchTool:
    """Search the web using DuckDuckGo (free) or Brave (API key).

    Args:
        default_provider: Provider name used when caller omits ``provider``.
    """

    name = "web_search"
    description = (
        "Search the web and return a list of results with title, URL, and snippet. "
        "Supports providers: duckduckgo (free, default), brave (needs BRAVE_API_KEY), "
        "searxng (free, self-hosted; needs SEARXNG_URL — when set, becomes the default)."
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
                "description": (
                    "Search provider: duckduckgo (default), brave, or searxng "
                    "(needs SEARXNG_URL). When SEARXNG_URL is set and provider is "
                    "omitted, searxng is used automatically."
                ),
                "enum": ["duckduckgo", "brave", "searxng"],
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, *, default_provider: str = "duckduckgo") -> None:
        self._default_provider = default_provider

    def _effective_default(self) -> str:
        """Resolve the default provider at call time from the environment.

        ``SEARXNG_URL`` is runtime state, so it is read here on every call (not
        at construction) — that way pointing the env var at a SearXNG instance
        takes effect without re-instantiating the tool. When set, searxng wins;
        otherwise the static ``default_provider`` (duckduckgo) applies.
        """
        if os.environ.get("SEARXNG_URL", "").strip():
            return "searxng"
        return self._default_provider

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
        provider = str(args.get("provider", self._effective_default())).strip().lower()

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
