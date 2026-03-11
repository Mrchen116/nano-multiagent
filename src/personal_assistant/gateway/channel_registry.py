"""Registry for configured channel adapters."""

from __future__ import annotations

from typing import Iterable

from personal_assistant.channels.base import ChannelAdapter


class ChannelRegistry:
    """Store channel adapters by name and expose lifecycle-friendly lookups.

    Args:
        channels: Optional initial adapters registered in iteration order.
    """

    def __init__(self, channels: Iterable[ChannelAdapter] = ()) -> None:
        self._channels: dict[str, ChannelAdapter] = {}
        for channel in channels:
            self.register(channel)

    def register(self, channel: ChannelAdapter, *, replace: bool = False) -> None:
        """Register one channel adapter.

        Args:
            channel: Adapter instance exposing the canonical channel contract.
            replace: When ``True``, replace an existing adapter with the same name.

        Raises:
            ValueError: When the adapter name is empty or already registered.
        """

        name = str(getattr(channel, "name", "")).strip()
        if not name:
            raise ValueError("channel name is required")
        if name in self._channels and not replace:
            raise ValueError(f"channel already registered: {name}")
        self._channels[name] = channel

    def get(self, name: str) -> ChannelAdapter | None:
        """Return one registered channel adapter by name."""

        return self._channels.get(name)

    def list(self) -> tuple[ChannelAdapter, ...]:
        """Return registered channel adapters in bootstrap order."""

        return tuple(self._channels.values())
