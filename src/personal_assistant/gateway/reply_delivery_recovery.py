"""Replay unresolved image publications from saved destinations and provider receipts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from personal_assistant.channels.base import (
    OutboundMessage,
    ProviderImagePreparation,
)


def external_recovery_payload(
    outbound: OutboundMessage, preparation: ProviderImagePreparation
) -> dict[str, Any]:
    """Freeze provider publication inputs without retaining original source paths."""
    return {
        "kind": "external_prepared",
        "outbound": {
            "channel_name": outbound.channel_name,
            "text": outbound.text,
            "target_chat_id": outbound.target_chat_id,
            "thread_id": outbound.thread_id,
            "metadata": dict(outbound.metadata),
        },
        "preparation": asdict(preparation),
    }
