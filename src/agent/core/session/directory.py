"""Stable identity directory for per-conversation session objects."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from agent.core import ids

from .jsonl_files import JsonlSessionFiles
from .jsonl_writer import JsonlWriter
from .models import Session
from .transcript import JsonlTranscript, TranscriptLoad
from .types import (
    NewSession,
    SessionAddressMismatch,
    SessionNotFoundError,
    SessionRef,
    strip_internal_metadata,
)


class ConversationLike(Protocol):
    """Describe the lifecycle surface owned by the directory."""

    async def close(self) -> None: ...


ConversationFactory = Callable[[SessionRef, JsonlTranscript], ConversationLike]


class SessionDirectory:
    """Intern stable conversation identities and perform scoped session queries."""

    def __init__(
        self,
        *,
        files: JsonlSessionFiles,
        writer: JsonlWriter,
        conversation_factory: ConversationFactory,
        default_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._files = files
        self._writer = writer
        self._conversation_factory = conversation_factory
        self._default_metadata = dict(default_metadata or {})
        self._guard = threading.Lock()
        self._conversations: dict[str, ConversationLike] = {}
        self._refs: dict[str, SessionRef] = {}

    def create(self, spec: NewSession) -> ConversationLike:
        """Create, persist, and intern one new conversation."""

        metadata = dict(self._default_metadata)
        metadata.update(spec.metadata)
        session_id = ids.make_session_id()
        ref = SessionRef(
            session_id=session_id,
            workspace_root=spec.workspace_root,
            parent_session_id=spec.parent_session_id,
        )
        effective_spec = NewSession(
            workspace_root=ref.workspace_root,
            title=spec.title,
            system_prompt=spec.system_prompt,
            skills=spec.skills,
            tool_allowlist=spec.tool_allowlist,
            metadata=metadata,
            parent_session_id=ref.parent_session_id,
            prompt_seed=spec.prompt_seed,
        )
        transcript = JsonlTranscript.create(
            ref=ref,
            spec=effective_spec,
            files=self._files,
            writer=self._writer,
        )
        conversation = self._conversation_factory(ref, transcript)
        with self._guard:
            self._refs[session_id] = ref
            self._conversations[session_id] = conversation
        return conversation

    def open(self, ref: SessionRef) -> ConversationLike:
        """Return the stable object for ``ref`` or intern a lazy cold object."""

        with self._guard:
            existing_ref = self._refs.get(ref.session_id)
            if existing_ref is not None:
                if existing_ref != ref:
                    raise SessionAddressMismatch(
                        f"session {ref.session_id} is already bound to {existing_ref}"
                    )
                return self._conversations[ref.session_id]
            transcript = JsonlTranscript(
                ref=ref,
                files=self._files,
                writer=self._writer,
            )
            conversation = self._conversation_factory(ref, transcript)
            self._refs[ref.session_id] = ref
            self._conversations[ref.session_id] = conversation
            return conversation

    def get(self, ref: SessionRef) -> Session | None:
        """Read one immutable session snapshot without creating live state."""

        try:
            loaded = JsonlTranscript(
                ref=ref,
                files=self._files,
                writer=self._writer,
            ).load()
        except SessionNotFoundError:
            return None
        return _session_from_load(loaded)

    def list(
        self,
        *,
        workspace_root,
        limit: int,
        offset: int,
    ) -> tuple[tuple[Session, ...], bool]:
        """List immutable snapshots in descending transcript mtime order."""

        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")
        refs = self._files.enumerate_addresses(workspace_root=workspace_root)
        page = refs[offset : offset + limit + 1]
        snapshots = tuple(
            snapshot for ref in page[:limit] if (snapshot := self.get(ref)) is not None
        )
        return snapshots, len(page) > limit

    def find_by_metadata(
        self,
        *,
        workspace_root,
        parent_session_id: str | None,
        query: Mapping[str, object],
    ) -> SessionRef | None:
        """Find a session whose metadata matches within the exact parent scope."""

        for ref in self._files.enumerate_addresses(workspace_root=workspace_root):
            if ref.parent_session_id != parent_session_id:
                continue
            try:
                loaded = JsonlTranscript(
                    ref=ref,
                    files=self._files,
                    writer=self._writer,
                ).load()
            except SessionNotFoundError:
                continue
            if all(
                loaded.config.metadata.get(key) == value for key, value in query.items()
            ):
                return ref
        return None

    async def close_all(self) -> None:
        """Close every interned conversation after taking a stable snapshot."""

        with self._guard:
            conversations = tuple(self._conversations.values())
        for conversation in conversations:
            await conversation.close()

    def active_session_ids(self) -> tuple[str, ...]:
        """Return ids whose stable objects are interned in this process."""

        with self._guard:
            return tuple(self._refs)

    def ref_for(self, session_id: str) -> SessionRef | None:
        """Return an interned canonical reference without probing storage."""

        with self._guard:
            return self._refs.get(session_id)


def _session_from_load(loaded: TranscriptLoad) -> Session:
    config = loaded.config
    return Session(
        session_id=config.session_id,
        status="active",
        created_at=config.created_at,
        workspace_root=config.workspace_root,
        system_prompt=config.system_prompt,
        skills=config.skills,
        tool_allowlist=config.tool_allowlist,
        metadata=strip_internal_metadata(config.metadata),
    )
