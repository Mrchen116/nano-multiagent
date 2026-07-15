"""Registry for configured channel adapters."""

from __future__ import annotations

import threading
from typing import Iterable

from personal_assistant.channels.base import ChannelAdapter


class ChannelRegistry:
    """Store channel adapters by name and expose lifecycle-friendly lookups.

    Args:
        channels: Optional initial adapters registered in iteration order.
    """

    def __init__(self, channels: Iterable[ChannelAdapter] = ()) -> None:
        self._lock = threading.RLock()
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
        with self._lock:
            if name in self._channels and not replace:
                raise ValueError(f"channel already registered: {name}")
            self._channels[name] = channel

    def remove(
        self, name: str, *, expected: ChannelAdapter | None = None
    ) -> ChannelAdapter | None:
        """Atomically remove one adapter, optionally only when identity matches."""
        with self._lock:
            current = self._channels.get(name)
            if current is None or (expected is not None and current is not expected):
                return None
            return self._channels.pop(name)

    def replace(self, channel: ChannelAdapter) -> ChannelAdapter | None:
        """Atomically route a stable adapter name to a new runtime."""
        name = str(getattr(channel, "name", "")).strip()
        if not name:
            raise ValueError("channel name is required")
        with self._lock:
            previous = self._channels.get(name)
            self._channels[name] = channel
            return previous

    def get(self, name: str) -> ChannelAdapter | None:
        """Return one registered channel adapter by name."""

        with self._lock:
            return self._channels.get(name)

    def list(self) -> tuple[ChannelAdapter, ...]:
        """Return registered channel adapters in bootstrap order."""

        with self._lock:
            return tuple(self._channels.values())
