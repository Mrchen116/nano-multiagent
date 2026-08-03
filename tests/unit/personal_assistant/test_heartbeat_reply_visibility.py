"""Heartbeat protocol-silence behavior at the reply-visibility seam."""

from __future__ import annotations

import pytest

from personal_assistant.gateway.reply_visibility import is_protocol_silence_token


@pytest.mark.parametrize("text", ["HEARTBEAT_OK", "  HEARTBEAT_OK  "])
def test_heartbeat_ok_is_protocol_silence(text: str) -> None:
    """Suppress the current heartbeat acknowledgement token, including whitespace."""

    assert is_protocol_silence_token(text) is True


@pytest.mark.parametrize("text", ["", "Daily update", "HEARTBEAT_OK: investigate"])
def test_non_protocol_content_remains_visible(text: str) -> None:
    """Do not mistake empty or ordinary assistant content for the exact token."""

    assert is_protocol_silence_token(text) is False
