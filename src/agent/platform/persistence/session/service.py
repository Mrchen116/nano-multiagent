"""Facade for session manager wiring and default store selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from agent.core import ids
from agent.core.session.entries import SessionEntry, SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.session.models import Session

if TYPE_CHECKING:
    from agent.products.base import ProductProfile


@dataclass(frozen=True, slots=True)
class AppendMessageResult:
    """Describe the outcome of one append-only session message request."""

    entry: SessionEntry
    created: bool


class SessionService:
    """Expose session APIs while hiding store/manager construction details.

    Args:
        store: Explicit JSONL session store; takes priority over both ``profile``
            and the default path when provided.
        manager: Explicit session manager; bypasses all store construction when
            provided.
        profile: Optional product profile; when given and ``store`` is not
            explicitly provided, the session data directory is placed at
            ``ConfigResolver(profile).session_data_dir()`` only when the profile
            declares ``global_config_home``. Otherwise, or when profile is
            absent, falls back to legacy ``_default_data_dir()`` behavior.
    """

    def __init__(
        self,
        *,
        store: JsonlSessionStore | None = None,
        manager: SessionManager | None = None,
        profile: ProductProfile | None = None,
    ) -> None:
        if manager is not None:
            self._manager = manager
        else:
            active_store = store or _resolve_store(profile)
            self._manager = SessionManager(store=active_store)

    @property
    def manager(self) -> SessionManager:
        """Return underlying manager for advanced flows needing raw access."""

        return self._manager

    def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        """Create a session via manager using typed domain fields."""

        return self._manager.create_session(
            workspace_root=workspace_root,
            title=title,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=metadata,
        )

    def get_session(self, session_id: str) -> Session | None:
        """Return session by id or `None` when no persisted state exists."""

        return self._manager.get_session(session_id)

    def list_sessions(self, *, limit: int, offset: int) -> tuple[tuple[Session, ...], bool]:
        """List sessions with pagination and `has_more` result."""

        return self._manager.list_sessions(limit=limit, offset=offset)

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        message_id: str | None = None,
        turn_id: str | None = None,
        parts: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> AppendMessageResult:
        """Append one persisted user/assistant message without triggering a model run."""

        normalized_role = role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        if self._manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")

        normalized_metadata = dict(metadata or {})
        normalized_idempotency_key = idempotency_key.strip() if isinstance(idempotency_key, str) else ""
        if normalized_idempotency_key:
            normalized_metadata.setdefault("idempotency_key", normalized_idempotency_key)
            existing = self._find_message_by_idempotency_key(
                session_id=session_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing is not None:
                return AppendMessageResult(entry=existing, created=False)

        entry = self._manager.append_turn_message(
            session_id,
            turn_id=turn_id or ids.make_turn_id(),
            role=normalized_role,
            content=content,
            message_id=message_id or ids.make_message_id(),
            parts=parts,
            metadata=normalized_metadata,
        )
        return AppendMessageResult(entry=entry, created=True)

    def _find_message_by_idempotency_key(self, *, session_id: str, idempotency_key: str) -> SessionEntry | None:
        for entry in self._manager.list_entries(session_id):
            if not isinstance(entry, SessionEntry) or entry.kind is not SessionEntryKind.TURN_APPENDED:
                continue
            metadata = entry.data.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            if metadata.get("idempotency_key") == idempotency_key:
                return entry
        return None


def _resolve_store(profile: ProductProfile | None = None) -> JsonlSessionStore:
    """Construct a JsonlSessionStore at the resolved data directory."""

    data_dir = _resolve_data_dir(profile)
    return JsonlSessionStore(data_dir=data_dir)


def _resolve_data_dir(profile: ProductProfile | None = None) -> Path:
    """Resolve the session data directory.

    The returned path is the *base* directory; ``JsonlSessionStore`` appends
    ``sessions/`` internally via ``_resolve_path``.

    Priority:
    1. ``NANO_MULTIAGENT_DATA_DIR`` env var
    2. Profile's ``global_config_home``
    3. ``.nano`` relative to CWD
    """

    env_dir = os.getenv("NANO_MULTIAGENT_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    return Path(".nano")
