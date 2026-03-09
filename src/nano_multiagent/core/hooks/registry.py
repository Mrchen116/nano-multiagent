"""Canonical hook registration primitives and source-aware setup API."""

from pathlib import Path
from threading import Lock
from typing import Any, Mapping

from .types import (
    DEFAULT_HOOK_PRIORITY,
    DEFAULT_HOOK_TIMEOUT_MS,
    HookEventType,
    HookHandler,
    HookRegistration,
    HookSource,
    ensure_known_hook_event,
    normalize_hook_event,
)


class HookRegistry:
    """Store hook handlers by event with stable priority/order semantics."""

    def __init__(self) -> None:
        self._registrations: dict[str, list[HookRegistration]] = {}
        self._next_order = 0
        self._extension_state: dict[str, Any] = {}
        self._extension_state_lock = Lock()

    def on(
        self,
        event: str | HookEventType,
        handler: HookHandler,
        *,
        priority: int = DEFAULT_HOOK_PRIORITY,
        timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
        source: HookSource = "runtime",
        module_name: str | None = None,
        file_path: Path | None = None,
    ) -> HookRegistration:
        """Register a handler for one known event."""

        normalized_event = ensure_known_hook_event(event)
        if not callable(handler):
            raise TypeError("hook handler must be callable")
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        order = self._next_order
        self._next_order += 1
        hook_id = f"{source}:{normalized_event}:{order}"
        registration = HookRegistration(
            event=normalized_event,
            handler=handler,
            priority=int(priority),
            timeout_ms=int(timeout_ms),
            order=order,
            source=source,
            module_name=module_name,
            file_path=file_path,
            hook_id=hook_id,
        )
        self._registrations.setdefault(normalized_event, []).append(registration)
        return registration

    def handlers_for(self, event: str | HookEventType) -> tuple[HookRegistration, ...]:
        """Return handlers for an event sorted by priority then registration order."""

        normalized_event = normalize_hook_event(event)
        registrations = list(self._registrations.get(normalized_event, ()))
        registrations.sort(key=lambda item: (item.priority, item.order))
        return tuple(registrations)

    def by_event(self) -> Mapping[str, tuple[HookRegistration, ...]]:
        """Return all handlers grouped by normalized event name."""

        return {event: self.handlers_for(event) for event in sorted(self._registrations.keys())}

    def all_handlers(self) -> tuple[HookRegistration, ...]:
        """Return all handlers flattened and deterministically sorted."""

        all_items: list[HookRegistration] = []
        for registrations in self._registrations.values():
            all_items.extend(registrations)
        all_items.sort(key=lambda item: (item.event, item.priority, item.order))
        return tuple(all_items)

    def set_extension_state(self, key: str, value: object | None) -> None:
        """Store extension state scoped to this registry instance."""

        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("extension state key must be non-empty")
        with self._extension_state_lock:
            if value is None:
                self._extension_state.pop(normalized_key, None)
            else:
                self._extension_state[normalized_key] = value

    def get_extension_state(self, key: str) -> object | None:
        """Read extension state scoped to this registry instance."""

        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("extension state key must be non-empty")
        with self._extension_state_lock:
            return self._extension_state.get(normalized_key)


class HookAPI:
    """Module-facing registration facade that injects source metadata."""

    def __init__(
        self,
        registry: HookRegistry,
        *,
        source: HookSource,
        module_name: str | None,
        file_path: Path | None,
    ) -> None:
        self._registry = registry
        self._source = source
        self._module_name = module_name
        self._file_path = file_path

    def on(
        self,
        event: str | HookEventType,
        handler: HookHandler,
        *,
        priority: int = DEFAULT_HOOK_PRIORITY,
        timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS,
    ) -> HookRegistration:
        """Register a hook while preserving module/source provenance."""

        return self._registry.on(
            event,
            handler,
            priority=priority,
            timeout_ms=timeout_ms,
            source=self._source,
            module_name=self._module_name,
            file_path=self._file_path,
        )

    def set_state(self, key: str, value: object | None) -> None:
        """Store extension state on the backing registry."""

        self._registry.set_extension_state(key, value)

    def get_state(self, key: str) -> object | None:
        """Read extension state from the backing registry."""

        return self._registry.get_extension_state(key)
