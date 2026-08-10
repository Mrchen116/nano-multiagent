"""Exact process-local provenance for PA's readable chat-history copy."""

from __future__ import annotations

import threading


class ReadableInputProjectionStore:
    """Hand one normal admission's readable text to the matching input hook."""

    def __init__(self) -> None:
        """Create an empty process-local exact-provenance store."""
        self._lock = threading.Lock()
        self._pending: dict[str, tuple[str, str]] = {}

    def stage_or_replace(
        self, session_id: str, model_fallback: str, readable_fallback: str
    ) -> None:
        """Stage the latest normal projection for a session.

        Args:
            session_id: Kernel session that will run the normal admission.
            model_fallback: Exact text expected by the Kernel input hook.
            readable_fallback: Raw user-facing text to persist in PA chat history.
        """

        with self._lock:
            self._pending[session_id] = (model_fallback, readable_fallback)

    def resolve_exact(self, session_id: str, model_fallback: str) -> str | None:
        """Consume and return readable text only for an exact model-text match.

        Args:
            session_id: Kernel session invoking the input hook.
            model_fallback: Complete text observed by that hook.

        Returns:
            The readable projection on an exact match, otherwise ``None``.
        """

        with self._lock:
            staged = self._pending.get(session_id)
            if staged is None or staged[0] != model_fallback:
                return None
            self._pending.pop(session_id, None)
            return staged[1]

    def rollback(self, session_id: str, model_fallback: str) -> None:
        """Remove a still-pending projection after synchronous submit failure.

        Args:
            session_id: Kernel session whose admission failed.
            model_fallback: Exact staged text for the failed admission.
        """

        with self._lock:
            staged = self._pending.get(session_id)
            if staged is not None and staged[0] == model_fallback:
                self._pending.pop(session_id, None)


__all__ = ["ReadableInputProjectionStore"]
