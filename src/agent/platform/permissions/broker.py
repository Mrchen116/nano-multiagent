"""PermissionBroker: coordinates auto_mode_gate ask flow.

Holds:
- pending asyncio.Future per request_id (keyed per run_id)
- per-session consecutive and total classifier denials
- per-session allowlist (for allow_session decisions)

Thread-safety: all mutable state is protected by threading.Lock.
asyncio.Future creation and resolution happen on the same event loop.

Design mirrors CC's handleDenialLimitExceeded pattern — the broker is the
sole authoritative stateful coordinator; auto_mode_gate hook stays stateless.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
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
    """Internal gate decision output.

    Extended in bugfix-355 to support tool-level check_permissions results.
    - behavior: now includes 'passthrough' (tool defers to hook layer)
    - decision_reason: structured reason dict (type='safety_check'|'preapproved'|'rule'|...)
      supersedes rule_source for new code; rule_source retained for backward compat
    - updated_input: optional tool input override (reserved for future use)
    """

    behavior: Literal["allow", "deny", "ask", "passthrough"]
    reason: str = ""
    rule_source: str = ""  # Deprecated: use decision_reason instead; retained for callers using rule_source
    decision_reason: dict | None = (
        None  # Structured reason: {"type": "safety_check"|"preapproved"|..., ...}
    )
    updated_input: dict | None = (
        None  # Reserved: tool may rewrite its own input (not used in M1)
    )


# Default options per tool category
def _default_options_for_tool(tool_name: str) -> tuple[PermissionOption, ...]:
    """Return default ask options for a tool type.

    Mirrors CC's per-tool differentiation (bash has 4 options including always-allow;
    file-write tools have 3; others get the standard 4).
    """
    allow_once = PermissionOption(
        "allow_once", "Allow once", "Allow this single action"
    )
    deny = PermissionOption("deny", "Deny", "Block this action")
    allow_session = PermissionOption(
        "allow_session",
        "Allow for session",
        "Allow all calls to this tool this session",
    )
    allow_always = PermissionOption(
        "allow_always", "Always allow", "Remember and always allow this tool"
    )

    if tool_name in ("write", "edit"):
        return (allow_once, deny, allow_session)
    if tool_name == "Workflow":
        return (allow_once, allow_always, deny)
    return (allow_once, deny, allow_session, allow_always)


class PermissionBroker:
    """Coordinate permission request lifecycle across hook coroutines.

    Provides:
    - register_request / resolve: future-based park-and-resume for ask flows
    - cancel_all_pending: resolve all pending futures to deny (on run interrupt)
    - classifier denial counts per session_id
    - session-allowlist per session_id
    """

    def __init__(self, *, config: AutoModeConfig) -> None:
        self._config = config
        self._lock = threading.Lock()

        # request_id -> (Future, run_id)
        self._pending: dict[
            str, tuple[asyncio.Future[PermissionResponse], str | None]
        ] = {}

        self._auto_denials: dict[str, tuple[int, int]] = {}

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

    def is_pending(self, request_id: str) -> bool:
        """Return True if request_id is currently waiting for a decision.

        Used by the inbound HTTP endpoint to distinguish "unknown/already-resolved"
        (404) from "valid pending request" (200) before calling resolve().

        Args:
            request_id: The request id to check.

        Returns:
            True if the request is registered and not yet resolved.
        """
        with self._lock:
            return request_id in self._pending

    def resolve(self, request_id: str, response: PermissionResponse) -> bool:
        """Resolve a pending permission request with the given response.

        The pop-then-schedule is atomic under the lock, so two concurrent
        callers for the same request_id cannot both return True — exactly one
        wins the pop and returns True; the other gets None and returns False.
        This eliminates the TOCTOU window of a separate is_pending pre-check.

        Args:
            request_id: The request to resolve.
            response: The user or timeout decision.

        Returns:
            True when the request was found and scheduled for resolution;
            False when request_id was not pending (unknown or already resolved).
        """
        with self._lock:
            entry = self._pending.pop(request_id, None)
        if entry is None:
            return False
        future, _ = entry
        if not future.done():
            future.get_loop().call_soon_threadsafe(future.set_result, response)
        return True

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
                    future.get_loop().call_soon_threadsafe(
                        future.set_result, deny_response
                    )
                except Exception:
                    # Loop may be closing; best-effort cancellation
                    pass

    # ------------------------------------------------------------------
    # Deny-count state (deny-limit escalation)
    # ------------------------------------------------------------------

    def record_auto_decision(
        self, session_id: str, allowed: bool, *, total_deny_limit: int | None = None
    ) -> tuple[int, int]:
        """Update session counters atomically and return this decision's counts.

        An allow resets only consecutive denials. On reaching the total limit,
        return the reached counts and reset both stored counters for the next
        proposal, matching CC's one-action threshold handling.

        Args:
            session_id: Kernel session identity, shared across ordinary runs.
            allowed: Whether the action was permitted (including fast paths).
            total_deny_limit: Effective session limit; defaults to broker config.

        Returns:
            Consecutive and total counts at the decision, before a total reset.
        """
        limit = (
            total_deny_limit
            if total_deny_limit is not None
            else self._config.total_deny_limit
        )
        with self._lock:
            consecutive, total = self._auto_denials.get(session_id, (0, 0))
            counts = (0, total) if allowed else (consecutive + 1, total + 1)
            self._auto_denials[session_id] = (
                (0, 0) if not allowed and counts[1] >= limit else counts
            )
            return counts

    def get_auto_denial_counts(self, session_id: str) -> tuple[int, int]:
        """Return this session's current consecutive and total denial counts."""
        with self._lock:
            return self._auto_denials.get(session_id, (0, 0))

    def clear_session_state(self) -> None:
        """Release nonpersistent permission state when the kernel closes."""
        with self._lock:
            self._auto_denials.clear()
            self._session_allowlist.clear()

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
