"""Unit tests: Gateway /internal/dispatch endpoint (M250 R4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_dispatch_handler(im_manager=None):
    """Build a minimal InternalDispatchHandler for testing."""
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
    return InternalDispatchHandler(im_connection_manager=im_manager)


def test_dispatch_handler_returns_ok_when_im_manager_available() -> None:
    """handle() must return ok=True when IM manager is connected and send succeeds."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    manager = MagicMock()
    manager.connected = True
    manager.send_json = AsyncMock(return_value=None)

    handler = InternalDispatchHandler(im_connection_manager=manager)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is True
    manager.send_json.assert_called_once()


def test_dispatch_handler_returns_error_when_no_im_manager() -> None:
    """handle() must return ok=False with error when IM manager is absent."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_returns_error_when_im_manager_disconnected() -> None:
    """handle() must return ok=False when IM manager is not connected."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    manager = MagicMock()
    manager.connected = False

    handler = InternalDispatchHandler(im_connection_manager=manager)
    result = asyncio.run(handler.handle({"text": "hi", "to": "agent_b", "from_session_id": "sess_1"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_validates_required_fields() -> None:
    """handle() must return ok=False when required fields are missing."""
    import asyncio
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    manager = MagicMock()
    manager.connected = True
    manager.send_json = AsyncMock(return_value=None)

    handler = InternalDispatchHandler(im_connection_manager=manager)
    # Missing 'to' field
    result = asyncio.run(handler.handle({"text": "hi"}))
    assert result["ok"] is False
    assert "error" in result


def test_dispatch_handler_build_aiohttp_handler_returns_callable() -> None:
    """InternalDispatchHandler.build_aiohttp_handler must return a callable."""
    from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler

    handler = InternalDispatchHandler(im_connection_manager=None)
    aiohttp_handler = handler.build_aiohttp_handler()
    assert callable(aiohttp_handler)
