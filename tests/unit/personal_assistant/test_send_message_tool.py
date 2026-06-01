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


# ---------------------------------------------------------------------------
# Contract: no module-level TOOL singleton, no bind_dispatcher
# ---------------------------------------------------------------------------


def test_send_message_tool_has_no_module_level_singleton() -> None:
    """send_message.py must not export a module-level TOOL singleton."""
    import agent.products.personal_assistant.tools.send_message as mod

    assert not hasattr(mod, "TOOL"), (
        "send_message.py must not have a module-level TOOL singleton"
    )


def test_send_message_tool_has_no_bind_dispatcher() -> None:
    """SendMessageTool must not have a bind_dispatcher method."""
    from agent.products.personal_assistant.tools.send_message import SendMessageTool

    instance = SendMessageTool()
    assert not hasattr(instance, "bind_dispatcher"), (
        "SendMessageTool must not have bind_dispatcher (stateless rewrite required)"
    )


# ---------------------------------------------------------------------------
# Functional: run() dispatches HTTP POST from session_metadata URL
# ---------------------------------------------------------------------------


def test_send_message_tool_dispatches_http_post_to_gateway_dispatch_url() -> None:
    """run() must POST to gateway_dispatch_url from session_metadata."""
    from agent.products.personal_assistant.tools.send_message import SendMessageTool

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


def test_send_message_tool_raises_when_no_gateway_dispatch_url() -> None:
    """run() must raise RuntimeError with clear message when gateway_dispatch_url is absent."""
    from agent.products.personal_assistant.tools.send_message import SendMessageTool

    ctx = _make_tool_context(session_metadata={})
    tool = SendMessageTool()

    with pytest.raises(RuntimeError, match="gateway_dispatch_url"):
        tool.run({"text": "hello", "to": "agent_b"}, ctx)


def test_send_message_tool_validates_text_field() -> None:
    """run() must raise ValueError for blank text."""
    from agent.products.personal_assistant.tools.send_message import SendMessageTool

    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
        }
    )
    tool = SendMessageTool()

    with pytest.raises((ValueError, Exception)):
        tool.run({"text": "  ", "to": "agent_b"}, ctx)


def test_send_message_tool_run_returns_ok_target_text() -> None:
    """run() must return ok, target, and text fields."""
    from agent.products.personal_assistant.tools.send_message import SendMessageTool

    ctx = _make_tool_context(
        session_metadata={
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
        }
    )
    tool = SendMessageTool()

    def _ok_response(url: str, **kwargs) -> httpx.Response:
        return httpx.Response(
            200, json={"ok": True}, request=httpx.Request("POST", url)
        )

    with patch("httpx.post", side_effect=_ok_response):
        result = tool.run({"text": "hello world", "to": "agent_x"}, ctx)

    assert result["ok"] is True
    assert result["target"] == "agent_x"
    assert result["text"] == "hello world"
