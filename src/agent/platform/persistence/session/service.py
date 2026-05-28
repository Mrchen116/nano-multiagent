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
        store: Explicit JSONL session store; takes priority over ``profile`` and
            the fallback when provided. In production ``create_app`` always
            passes the workspace-aware store built by ``bootstrap_product``.
        manager: Explicit session manager; bypasses all store construction when
            provided.
        profile: Optional product profile. Currently unused for store
            construction — when neither ``store`` nor ``manager`` is given the
            service falls back to ``_resolve_store`` (a stateless store, or a
            ``NANO_MULTIAGENT_DATA_DIR``-rooted one if that env var is set).
    """

    def __init__(
        self,
        *,
        store: JsonlSessionStore | None = None,
        manager: SessionManager | None = None,
        profile: ProductProfile | None = None,
        default_session_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if manager is not None:
            self._manager = manager
        else:
            active_store = store or _resolve_store(profile)
            self._manager = SessionManager(store=active_store)
        # default_session_metadata is the bootstrap-resolved per-product baseline
        # (e.g. self_evolution config from workspace config.yaml). It is merged
        # under the caller-supplied metadata in create_session so callers can
        # override individual top-level keys but unspecified keys still inherit
        # the product default. Without this wire, the bootstrap output was a
        # dead field — feat-349 self-evolution hook silently fell back to
        # interval=10 defaults regardless of user config.
        self._default_session_metadata: dict[str, Any] = dict(default_session_metadata or {})

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

        # Shallow merge at top level: default first, caller-supplied wins per key.
        # Deep merge would require knowing each subsection's semantics; we don't —
        # callers wanting per-subkey override should resolve it themselves.
        merged_metadata: dict[str, Any] = dict(self._default_session_metadata)
        if metadata:
            merged_metadata.update(metadata)
        return self._manager.create_session(
            workspace_root=workspace_root,
            title=title,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=merged_metadata or None,
        )

    def get_session(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> Session | None:
        """Return session by id or `None` when no persisted state exists.

        ``workspace_root`` locates the session JSONL; the stateless store cannot
        guess it (omit only when the store has a ``data_dir`` default base).
        """

        return self._manager.get_session(session_id, workspace_root=workspace_root)

    def list_sessions(
        self, *, limit: int, offset: int, workspace_root: Path | None = None
    ) -> tuple[tuple[Session, ...], bool]:
        """List sessions with pagination and `has_more` result.

        Scoped to one ``workspace_root`` — there is no cross-workspace listing.
        """

        return self._manager.list_sessions(
            limit=limit, offset=offset, workspace_root=workspace_root
        )

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
        workspace_root: Path | None = None,
    ) -> AppendMessageResult:
        """Append one persisted user/assistant message without triggering a model run.

        ``workspace_root`` locates the session JSONL.
        """

        normalized_role = role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        if self._manager.get_session(session_id, workspace_root=workspace_root) is None:
            raise ValueError(f"session does not exist: {session_id}")

        normalized_metadata = dict(metadata or {})
        normalized_idempotency_key = idempotency_key.strip() if isinstance(idempotency_key, str) else ""
        if normalized_idempotency_key:
            normalized_metadata.setdefault("idempotency_key", normalized_idempotency_key)
            existing = self._find_message_by_idempotency_key(
                session_id=session_id,
                idempotency_key=normalized_idempotency_key,
                workspace_root=workspace_root,
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
            workspace_root=workspace_root,
        )
        return AppendMessageResult(entry=entry, created=True)

    def _find_message_by_idempotency_key(
        self, *, session_id: str, idempotency_key: str, workspace_root: Path | None = None
    ) -> SessionEntry | None:
        for entry in self._manager.list_entries(session_id, workspace_root=workspace_root):
            if not isinstance(entry, SessionEntry) or entry.kind is not SessionEntryKind.TURN_APPENDED:
                continue
            metadata = entry.data.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            if metadata.get("idempotency_key") == idempotency_key:
                return entry
        return None


def _resolve_store(profile: ProductProfile | None = None) -> JsonlSessionStore:
    """Construct a fallback JsonlSessionStore when no explicit store is supplied.

    This path is only reached by ``SessionService`` callers that pass neither a
    ``store`` nor a ``manager`` (e.g. ``create_app()`` invoked without a product
    profile in tests/SDK glue). In production both products call ``create_app``
    *with* a profile, so ``bootstrap_product`` always injects a concrete
    workspace-aware store and this fallback is never used.

    The fallback honours one explicit opt-in — the ``NANO_MULTIAGENT_DATA_DIR``
    env var — for tests/dev that want a fixed flat directory. Otherwise it
    returns a **stateless** store (``data_dir=None``): callers must pass
    ``workspace_root`` on every path-resolving call, exactly like the production
    store. There is deliberately no silent ``.nano``-relative-to-cwd fallback —
    that silent cwd fallback was the bugfix-348 root cause and must not survive
    here either.

    Args:
        profile: Unused. Kept in the signature because the legacy docstring
            advertised a profile-derived path that was never implemented; a
            future change may wire ``ConfigResolver`` here, but until then the
            production store comes from ``bootstrap_product``, not this function.
    """

    del profile  # see docstring — profile-derived path is not implemented here
    env_dir = os.getenv("NANO_MULTIAGENT_DATA_DIR")
    if env_dir:
        return JsonlSessionStore(data_dir=Path(env_dir))
    return JsonlSessionStore(data_dir=None)
