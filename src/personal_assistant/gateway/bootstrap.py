"""Bootstrap helpers for starting and stopping configured channels."""

from __future__ import annotations

from typing import Callable

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry


def start_channels(registry: ChannelRegistry, on_inbound: Callable[[InboundMessage], None]) -> tuple[str, ...]:
    """Start all registered channel adapters.

    Args:
        registry: Registry containing configured channel adapters.
        on_inbound: Shared gateway callback invoked by every adapter.

    Returns:
        Names of adapters started in registry order.

    Side Effects:
        Calls ``start()`` on each registered channel adapter.
    """

    started: list[str] = []
    for channel in registry.list():
        channel.start(on_inbound)
        started.append(channel.name)
    return tuple(started)


def stop_channels(registry: ChannelRegistry) -> tuple[str, ...]:
    """Stop all registered channel adapters in reverse startup order."""

    stopped: list[str] = []
    for channel in reversed(registry.list()):
        channel.stop()
        stopped.append(channel.name)
    return tuple(stopped)
