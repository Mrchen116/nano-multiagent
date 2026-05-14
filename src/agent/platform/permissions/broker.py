"""PermissionBroker: coordinates auto_mode_gate ask flow.

Holds:
- pending asyncio.Future per request_id (keyed per run_id)
- per-run deny-count per tool_name (for deny-limit escalation)
- per-session allowlist (for allow_session decisions)

Thread-safety: all mutable state is protected by threading.Lock.
asyncio.Future creation and resolution happen on the same event loop.

Design mirrors CC's handleDenialLimitExceeded pattern — the broker is the
sole authoritative stateful coordinator; auto_mode_gate hook stays stateless.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Literal

from agent.platform.config.auto_mode import AutoModeConfig


@dataclass(frozen=True)
class PermissionOption:
    """One selectable option in a permission request dialog."""

    id: str
    label: str
    description: str


@dataclass(frozen=True)
class PermissionRequest:
    """Payload sent to the client when the gate needs user confirmation."""

    id: str
    tool_name: str
    tool_input: dict
    question: str
    options: tuple[PermissionOption, ...]


@dataclass(frozen=True)
class PermissionResponse:
    """Decision returned by the user for a permission request."""

    decision: Literal["allow_once", "deny", "allow_session", "allow_always"]
    request_id: str = ""
    reason: str = ""
    rule_update: dict | None = None


@dataclass(frozen=True)
class PermissionDecision:
    """Internal gate decision output."""

    behavior: Literal["allow", "deny", "ask"]
    reason: str = ""
    rule_source: str = ""


# Default options per tool category
def _default_options_for_tool(tool_name: str) -> tuple[PermissionOption, ...]:
    """Return default ask options for a tool type.

    Mirrors CC's per-tool differentiation (bash has 4 options including always-allow;
    file-write tools have 3; others get the standard 4).
    """
    allow_once = PermissionOption("allow_once", "Allow once", "Allow this single action")
    deny = PermissionOption("deny", "Deny", "Block this action")
    allow_session = PermissionOption("allow_session", "Allow for session", "Allow all calls to this tool this session")
    allow_always = PermissionOption("allow_always", "Always allow", "Remember and always allow this tool")

    if tool_name in ("write", "edit"):
        return (allow_once, deny, allow_session)
    return (allow_once, deny, allow_session, allow_always)


class PermissionBroker:
    """Coordinate permission request lifecycle across hook coroutines.

    Provides:
    - register_request / resolve: future-based park-and-resume for ask flows
    - cancel_all_pending: resolve all pending futures to deny (on run interrupt)
    - deny-count per (run_id, tool_name)
    - session-allowlist per session_id
    """

    def __init__(self, *, config: AutoModeConfig) -> None:
        self._config = config
        self._lock = threading.Lock()

        # request_id -> (Future, run_id)
        self._pending: dict[str, tuple[asyncio.Future[PermissionResponse], str | None]] = {}

        # (run_id, tool_name) -> deny count
        self._deny_counts: dict[tuple[str, str], int] = {}

        # session_id -> set[tool_name]
        self._session_allowlist: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Future-based request lifecycle
    # ------------------------------------------------------------------

    def register_request(
        self,
        request_id: str,
        run_id: str | None = None,
    ) -> asyncio.Future[PermissionResponse]:
        """Register a pending permission request and return its Future.

        The future will be resolved by resolve() when a decision arrives,
        or by cancel_all_pending() when the run is interrupted.

        Args:
            request_id: Unique identifier for this permission request.
            run_id: Optional run scope for cancel_all_pending targeting.

        Returns:
            asyncio.Future that resolves to PermissionResponse.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[PermissionResponse] = loop.create_future()
        with self._lock:
            self._pending[request_id] = (future, run_id)
        return future

    def resolve(self, request_id: str, response: PermissionResponse) -> None:
        """Resolve a pending permission request with the given response.

        No-op if request_id is not registered (idempotent by design).

        Args:
            request_id: The request to resolve.
            response: The user or timeout decision.
        """
        with self._lock:
            entry = self._pending.pop(request_id, None)
        if entry is None:
            return
        future, _ = entry
        if not future.done():
            future.get_loop().call_soon_threadsafe(future.set_result, response)

    def cancel_all_pending(self, *, run_id: str | None) -> None:
        """Resolve all pending futures in scope to deny.

        When run_id is None, cancels ALL pending requests.
        When run_id is provided, cancels only requests for that run.

        Used by run interrupt and timeout cleanup to prevent hook coroutine leaks.

        Args:
            run_id: Scope filter, or None to cancel everything.
        """
        with self._lock:
            to_cancel = {
                rid: (fut, rid_scope)
                for rid, (fut, rid_scope) in self._pending.items()
                if run_id is None or rid_scope == run_id
            }
            for rid in to_cancel:
                self._pending.pop(rid, None)

        deny_response = PermissionResponse(
            decision="deny",
            reason="cancelled: run interrupted or timed out",
        )
        for rid, (future, _) in to_cancel.items():
            if not future.done():
                try:
                    future.get_loop().call_soon_threadsafe(future.set_result, deny_response)
                except Exception:
                    # Loop may be closing; best-effort cancellation
                    pass

    # ------------------------------------------------------------------
    # Deny-count state (deny-limit escalation)
    # ------------------------------------------------------------------

    def increment_deny_count(self, run_id: str, tool_name: str) -> int:
        """Increment and return the deny count for (run_id, tool_name).

        Args:
            run_id: The current run identifier.
            tool_name: The tool that was denied.

        Returns:
            New deny count after increment.
        """
        key = (run_id, tool_name)
        with self._lock:
            self._deny_counts[key] = self._deny_counts.get(key, 0) + 1
            return self._deny_counts[key]

    def get_deny_count(self, run_id: str, tool_name: str) -> int:
        """Return current deny count for (run_id, tool_name)."""
        key = (run_id, tool_name)
        with self._lock:
            return self._deny_counts.get(key, 0)

    def reset_deny_count(self, run_id: str, tool_name: str) -> None:
        """Reset deny count to 0 (on allow or ask resolution)."""
        key = (run_id, tool_name)
        with self._lock:
            self._deny_counts.pop(key, None)

    def is_deny_limit_exceeded(self, run_id: str, tool_name: str) -> bool:
        """Check if deny count has reached the configured limit.

        Args:
            run_id: The current run identifier.
            tool_name: The tool to check.

        Returns:
            True if deny count >= deny_limit threshold.
        """
        return self.get_deny_count(run_id, tool_name) >= self._config.deny_limit

    # ------------------------------------------------------------------
    # Session allowlist state (allow_session decisions)
    # ------------------------------------------------------------------

    def add_session_allowlist(self, session_id: str, tool_name: str) -> None:
        """Add tool_name to session-scoped allowlist.

        Subsequent calls to is_session_allowed return True for this pair.

        Args:
            session_id: The session to scope the allowlist entry to.
            tool_name: The tool to always allow for this session.
        """
        with self._lock:
            if session_id not in self._session_allowlist:
                self._session_allowlist[session_id] = set()
            self._session_allowlist[session_id].add(tool_name)

    def is_session_allowed(self, session_id: str, tool_name: str) -> bool:
        """Check if tool_name is in the session allowlist.

        Args:
            session_id: The session to check.
            tool_name: The tool to look up.

        Returns:
            True if the tool was previously granted allow_session.
        """
        with self._lock:
            session_tools = self._session_allowlist.get(session_id, set())
            return tool_name in session_tools
