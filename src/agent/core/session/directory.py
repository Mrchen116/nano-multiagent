"""Stable identity directory for per-conversation session objects."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, Protocol

from agent.core import ids
from agent.core.types import Message

from .jsonl_files import JsonlSessionFiles
from .jsonl_writer import JsonlWriter
from .models import Session
from .transcript import JsonlTranscript
from .types import (
    NewSession,
    SessionAddressMismatch,
    SessionConfig,
    SessionNotFoundError,
    SessionRef,
    strip_internal_metadata,
)


class ConversationLike(Protocol):
    """Describe the lifecycle surface owned by the directory."""

    ref: SessionRef

    async def close(self) -> None: ...

    async def discard_turn(self, turn_id: str) -> bool: ...

    def try_evict_payload(self) -> bool: ...


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
        max_loaded_conversations: int = 32,
    ) -> None:
        self._files = files
        self._writer = writer
        self._conversation_factory = conversation_factory
        self._default_metadata = dict(default_metadata or {})
        self._guard = threading.Lock()
        self._conversations: dict[str, ConversationLike] = {}
        self._refs: dict[str, SessionRef] = {}
        self._max_loaded_conversations = max(1, max_loaded_conversations)
        self._loaded_lru: OrderedDict[str, None] = OrderedDict()

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
        _bind_directory(conversation, self)
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
            _bind_directory(conversation, self)
            self._refs[ref.session_id] = ref
            self._conversations[ref.session_id] = conversation
            return conversation

    def get(self, ref: SessionRef) -> Session | None:
        """Read one immutable session snapshot without creating live state."""

        try:
            config = JsonlTranscript(
                ref=ref,
                files=self._files,
                writer=self._writer,
            ).load_config()
        except SessionNotFoundError:
            return None
        return _session_from_config(config)

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
                metadata = JsonlTranscript(
                    ref=ref,
                    files=self._files,
                    writer=self._writer,
                ).initial_metadata()
            except SessionNotFoundError:
                continue
            if all(metadata.get(key) == value for key, value in query.items()):
                return ref
        return None

    def note_quiescent(self, conversation: ConversationLike) -> None:
        """Keep only a bounded LRU set of loaded conversation payloads."""

        session_id = conversation.ref.session_id
        evictions: list[ConversationLike] = []
        with self._guard:
            self._loaded_lru.pop(session_id, None)
            self._loaded_lru[session_id] = None
            while len(self._loaded_lru) > self._max_loaded_conversations:
                evicted_id, _ = self._loaded_lru.popitem(last=False)
                candidate = self._conversations.get(evicted_id)
                if candidate is not None:
                    evictions.append(candidate)
        for candidate in evictions:
            if candidate.try_evict_payload():
                continue
            candidate_id = candidate.ref.session_id
            with self._guard:
                self._loaded_lru[candidate_id] = None

    async def close_all(self) -> None:
        """Close every interned conversation after taking a stable snapshot."""

        with self._guard:
            conversations = tuple(self._conversations.values())
        for conversation in conversations:
            await conversation.close()

    async def fork_from(
        self, source, *, up_to: str | None
    ) -> tuple[Session, dict[str, str]]:
        """Capture, re-stamp, persist, and intern one independent fork target."""

        snapshot = await source.capture_fork(up_to=up_to)
        metadata = strip_internal_metadata(snapshot.config.metadata)
        metadata["forked_from"] = source.ref.session_id
        target = self.create(
            NewSession(
                workspace_root=snapshot.config.workspace_root,
                system_prompt=snapshot.config.system_prompt,
                skills=snapshot.config.skills,
                tool_allowlist=snapshot.config.tool_allowlist,
                metadata=metadata,
                prompt_seed=snapshot.prompt_seed,
            )
        )
        mapping: dict[str, str] = {}
        restamped: list[Message] = []
        for message in snapshot.messages:
            new_id = ids.make_message_id()
            mapping[message.message_id] = new_id
            restamped.append(
                replace(
                    message,
                    message_id=new_id,
                    parent_message_id=mapping.get(message.parent_message_id)
                    if message.parent_message_id
                    else None,
                    group_id=mapping.get(message.group_id)
                    if message.group_id
                    else None,
                    metadata=dict(message.metadata),
                )
            )
        target._install_fork_snapshot(tuple(restamped))
        target_snapshot = self.get(target.ref)
        if target_snapshot is None:  # pragma: no cover - durable create invariant.
            raise RuntimeError("fork target disappeared after durable creation")
        return target_snapshot, mapping

    def active_session_ids(self) -> tuple[str, ...]:
        """Return ids whose stable objects are interned in this process."""

        with self._guard:
            return tuple(self._refs)

    def ref_for(self, session_id: str) -> SessionRef | None:
        """Return an interned canonical reference without probing storage."""

        with self._guard:
            return self._refs.get(session_id)


def _session_from_config(config: SessionConfig) -> Session:
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


def _bind_directory(
    conversation: ConversationLike, directory: SessionDirectory
) -> None:
    binder = getattr(conversation, "_bind_fork_directory", None)
    if callable(binder):
        binder(directory)
