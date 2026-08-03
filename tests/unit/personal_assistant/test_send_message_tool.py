"""Unit tests: SendMessageTool stateless HTTP dispatch (M250 R2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest

import httpx


def _make_tool_context(session_metadata: dict | None = None):
    """Build a minimal ToolContext with optional session_metadata."""
    from agent.core.tools.base import (
        ToolContext,
        set_tool_safety_factory,
        set_tool_safety_config_factory,
    )

    class _FakeSafety:
        def __init__(self, **kwargs):
            pass

        def check_path(self, *a, **kw):
            pass

    class _FakeSafetyConfig:
        pass

    set_tool_safety_factory(lambda **kwargs: _FakeSafety())
    set_tool_safety_config_factory(lambda: _FakeSafetyConfig())

    ctx = ToolContext.create(repo_root=Path("/tmp"))
    ctx = ctx.with_session("sess_test", session_metadata=session_metadata or {})
    return ctx


class _FakeResult:
    def __init__(self, output: Any = None, error: str | None = None) -> None:
        self.output = output
        self.error = error


def test_send_message_presenter_splits_start_params_and_end_status() -> None:
    from personal_assistant.tools.send_message import SendMessageTool

    presenter = SendMessageTool.presenter
    start = presenter.format_start({"to": "agent_b", "text": "hello"})
    assert start.summary == "→ agent_b"
    assert start.detail == {"target": "agent_b", "text": "hello"}

    end = presenter.format_end(
        {"to": "agent_b", "text": "hello"},
        _FakeResult(output={"ok": True, "target": "agent_b", "text": "hello"}),
        duration_ms=12,
    )
    assert end.summary == "→ agent_b"
    assert end.detail == {
        "target": "agent_b",
        "text": "hello",
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# Functional: run() dispatches HTTP POST from session_metadata URL
# ---------------------------------------------------------------------------


def test_send_message_tool_dispatches_http_post_to_gateway_dispatch_url() -> None:
    """run() must POST to gateway_dispatch_url from session_metadata."""
    from personal_assistant.tools.send_message import SendMessageTool

    captured_urls: list[str] = []
    captured_payloads: list[dict] = []

    def mock_post(url: str, **kwargs) -> httpx.Response:
        captured_urls.append(url)
        captured_payloads.append(kwargs.get("json", {}))
        req = httpx.Request("POST", url)
        return httpx.Response(200, json={"ok": True}, request=req)

    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_id": "agent_a",
        }
    ).with_session(
        "sess_test",
        tool_call_id="toolu_test_dispatch",
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_id": "agent_a",
        },
    )
    tool = SendMessageTool()

    with patch("httpx.post", side_effect=mock_post):
        result = tool.run({"text": "hello", "to": "agent_b"}, ctx)

    assert result["ok"] is True
    assert result["target"] == "agent_b"
    assert result["text"] == "hello"
    assert len(captured_urls) == 1
    assert "127.0.0.1:8089" in captured_urls[0]
    assert captured_payloads[0]["text"] == "hello"
    assert captured_payloads[0]["to"] == "agent_b"
    assert captured_payloads[0]["origin_kernel_session_id"] == "sess_test"
    assert captured_payloads[0]["source_agent_id"] == "agent_a"
    assert captured_payloads[0]["dispatch_request_id"] == "toolu_test_dispatch"
    assert (
        captured_payloads[0]["from_session_id"]
        == "agent_a|tool_call:toolu_test_dispatch"
    )


def test_send_message_tool_resolves_live_provider_on_every_call() -> None:
    """One tool instance follows endpoint publication instead of snapshotting it."""

    from personal_assistant.gateway.internal_dispatch import InternalDispatchEndpoint
    from personal_assistant.tools.send_message import SendMessageTool

    endpoint = InternalDispatchEndpoint()
    endpoint.publish(host="127.0.0.1", port=41001)
    tool = SendMessageTool(gateway_dispatch_url_provider=endpoint.current_url)
    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:39999/internal/dispatch"
        }
    )
    captured_urls: list[str] = []

    def _ok_response(url: str, **_kwargs: Any) -> httpx.Response:
        captured_urls.append(url)
        return httpx.Response(
            200, json={"ok": True}, request=httpx.Request("POST", url)
        )

    with patch("httpx.post", side_effect=_ok_response):
        tool.run({"text": "first", "to": "agent_b"}, ctx)
        endpoint.publish(host="127.0.0.1", port=42002)
        tool.run({"text": "second", "to": "agent_b"}, ctx)

    assert captured_urls == [
        "http://127.0.0.1:41001/internal/dispatch",
        "http://127.0.0.1:42002/internal/dispatch",
    ]


def test_send_message_tool_live_provider_clear_never_falls_back_to_metadata() -> None:
    """A production provider without a listener fails before using stale metadata."""

    from personal_assistant.gateway.internal_dispatch import InternalDispatchEndpoint
    from personal_assistant.tools.send_message import SendMessageTool

    endpoint = InternalDispatchEndpoint()
    endpoint.publish(host="127.0.0.1", port=41001)
    endpoint.clear()
    tool = SendMessageTool(gateway_dispatch_url_provider=endpoint.current_url)
    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:41001/internal/dispatch"
        }
    )

    with (
        patch("httpx.post") as post,
        pytest.raises(RuntimeError, match="live gateway_dispatch_url.*not available"),
    ):
        tool.run({"text": "hello", "to": "agent_b"}, ctx)

    post.assert_not_called()


def test_send_message_tool_raises_when_no_gateway_dispatch_url() -> None:
    """run() must raise RuntimeError with clear message when gateway_dispatch_url is absent."""
    from personal_assistant.tools.send_message import SendMessageTool

    ctx = _make_tool_context(session_metadata={})
    tool = SendMessageTool()

    with pytest.raises(RuntimeError, match="gateway_dispatch_url"):
        tool.run({"text": "hello", "to": "agent_b"}, ctx)


def test_send_message_tool_validates_text_field() -> None:
    """run() must raise ValueError for blank text."""
    from personal_assistant.tools.send_message import SendMessageTool

    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
        }
    )
    tool = SendMessageTool()

    with pytest.raises(ValueError, match="text must be a non-empty string"):
        tool.run({"text": "  ", "to": "agent_b"}, ctx)
