"""Regression tests for web_relay_adapter attachment extraction and forwarding.

Covers the bug where image messages sent from the Web IM frontend resulted in a
500 error because:
  1. relay_service serialized Attachment dataclass objects directly (not JSON-safe)
  2. _parse_relay_payload did not extract attachments from the relay message
  3. _build_inbound did not include attachments in InboundMessage.metadata
"""

from __future__ import annotations

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter, _parse_relay_payload


def _minimal_payload(*, content: str = "hello", attachments: list | None = None) -> dict:
    """Build a minimal valid relay payload with optional attachments."""
    message: dict = {
        "id": "msg-1",
        "conversation_id": "conv-1",
        "sender_user_id": "user-1",
        "sender_type": "user",
        "content": content,
        "created_at": "2026-01-01T00:00:00Z",
    }
    if attachments is not None:
        message["attachments"] = attachments
    return {
        "relay_task_id": "rt-1",
        "idempotency_key": "idem-1",
        "message": message,
        "metadata": {"conversation_type": "direct"},
    }


def test_parse_relay_payload_extracts_single_image_attachment() -> None:
    """Attachments list from relay message must be extracted into RelayEnvelope.attachments."""
    payload = _minimal_payload(
        content="look at this",
        attachments=[
            {"url": "http://im.local/im/uploads/abc.png", "content_type": "image/png", "file_name": "screen.png"}
        ],
    )

    envelope = _parse_relay_payload(payload)

    assert len(envelope.attachments) == 1
    att = envelope.attachments[0]
    assert att["url"] == "http://im.local/im/uploads/abc.png"
    assert att["content_type"] == "image/png"
    assert att["file_name"] == "screen.png"


def test_parse_relay_payload_empty_attachments_list_produces_empty_list() -> None:
    """Empty attachments list must yield empty list, not None."""
    payload = _minimal_payload(attachments=[])
    envelope = _parse_relay_payload(payload)
    assert envelope.attachments == []


def test_parse_relay_payload_missing_attachments_key_produces_empty_list() -> None:
    """Relay payload without attachments key must still produce empty list."""
    payload = _minimal_payload()  # no attachments key
    envelope = _parse_relay_payload(payload)
    assert envelope.attachments == []


def test_parse_relay_payload_skips_attachment_without_url() -> None:
    """Attachments missing a url field must be silently skipped."""
    payload = _minimal_payload(
        attachments=[
            {"content_type": "image/png"},  # no url
            {"url": "http://im.local/im/uploads/valid.jpg", "content_type": "image/jpeg"},
        ]
    )
    envelope = _parse_relay_payload(payload)
    assert len(envelope.attachments) == 1
    assert envelope.attachments[0]["url"] == "http://im.local/im/uploads/valid.jpg"


def test_accept_relay_puts_attachments_in_inbound_metadata() -> None:
    """accept_relay must forward attachments into InboundMessage.metadata['attachments']."""
    received = []
    adapter = WebRelayAdapter()
    adapter.start(lambda msg: received.append(msg))

    payload = _minimal_payload(
        content="check image",
        attachments=[
            {"url": "http://im.local/im/uploads/photo.png", "content_type": "image/png", "file_name": "photo.png"}
        ],
    )

    inbound = adapter.accept_relay(payload)

    assert len(received) == 1
    assert inbound is received[0]
    attachments = inbound.metadata.get("attachments")
    assert isinstance(attachments, list)
    assert len(attachments) == 1
    assert attachments[0]["url"] == "http://im.local/im/uploads/photo.png"


def test_accept_relay_without_attachments_does_not_set_metadata_key() -> None:
    """InboundMessage.metadata must not contain 'attachments' key when message has none."""
    received = []
    adapter = WebRelayAdapter()
    adapter.start(lambda msg: received.append(msg))

    payload = _minimal_payload(content="plain text")
    inbound = adapter.accept_relay(payload)

    assert "attachments" not in inbound.metadata


def test_accept_relay_multiple_attachments_all_forwarded() -> None:
    """All valid attachments must be forwarded to InboundMessage.metadata."""
    received = []
    adapter = WebRelayAdapter()
    adapter.start(lambda msg: received.append(msg))

    payload = _minimal_payload(
        content="two images",
        attachments=[
            {"url": "http://im.local/im/uploads/a.png", "content_type": "image/png"},
            {"url": "http://im.local/im/uploads/b.jpg", "content_type": "image/jpeg", "file_name": "b.jpg"},
        ],
    )

    inbound = adapter.accept_relay(payload)

    attachments = inbound.metadata.get("attachments", [])
    assert len(attachments) == 2
    urls = [a["url"] for a in attachments]
    assert "http://im.local/im/uploads/a.png" in urls
    assert "http://im.local/im/uploads/b.jpg" in urls
