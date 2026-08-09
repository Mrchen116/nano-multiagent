"""Private, session-bound JSONL transcript semantics."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core import ids
from agent.core.types import Message
from agent.core.utils.time import utc_now_iso

from .entries import (
    CompactionEntry,
    SessionEntry,
    new_compaction_entry,
    new_session_created_entry,
    new_turn_appended_entry,
    parse_parts,
)
from .jsonl_files import JsonlSessionFiles
from .jsonl_writer import JsonlWriter
from .types import (
    INTERNAL_PROMPT_SLOTS_KEY,
    INTERNAL_RUNTIME_KEY,
    AppendMessageResult,
    ExternalMessage,
    NewSession,
    PromptSlotSeed,
    SessionConfig,
    SessionNotFoundError,
    SessionRef,
    internal_metadata,
)

USER_INTERRUPT_RECOVERY_CONTENT = "[Request interrupted by user for tool use]"


@dataclass(frozen=True, slots=True)
class TranscriptLoad:
    """Return one materialized transcript plus its internal prompt seed."""

    config: SessionConfig
    messages: list[Message]
    prompt_seed: PromptSlotSeed
    external_epoch: int = 0


class JsonlTranscript:
    """Own schema, chain, repair, tail, and durability for one session file."""

    def __init__(
        self,
        *,
        ref: SessionRef,
        files: JsonlSessionFiles,
        writer: JsonlWriter,
        known_empty: bool = False,
    ) -> None:
        self._ref = ref
        self._files = files
        self._writer = writer
        self._path = files.resolve_path(ref)
        self._mutex = threading.RLock()
        self._tail_known = known_empty
        self._tail_uuid: str | None = None
        self._external_epoch = 0

    @classmethod
    def create(
        cls,
        *,
        ref: SessionRef,
        spec: NewSession,
        files: JsonlSessionFiles,
        writer: JsonlWriter,
    ) -> "JsonlTranscript":
        """Create a new transcript through the single raw writer path."""

        transcript = cls(ref=ref, files=files, writer=writer, known_empty=True)
        metadata = internal_metadata(spec.metadata, prompt_seed=spec.prompt_seed)
        if spec.runtime_model is not None:
            runtime_metadata = dict(metadata.get(INTERNAL_RUNTIME_KEY) or {})
            runtime_metadata.update(
                {
                    "model": spec.runtime_model,
                    "features": spec.runtime_features,
                    "reasoning_effort": spec.runtime_reasoning_effort,
                }
            )
            metadata[INTERNAL_RUNTIME_KEY] = runtime_metadata
        if spec.title is not None:
            metadata["title"] = spec.title
        entry: dict[str, Any] = {
            "type": "session_created",
            "session_id": ref.session_id,
            "created_at": utc_now_iso(),
            "workspace_root": str(ref.workspace_root),
            "metadata": metadata,
        }
        if spec.system_prompt is not None:
            entry["system_prompt"] = spec.system_prompt
        if spec.skills is not None:
            entry["skills"] = list(spec.skills)
        if spec.tool_allowlist is not None:
            entry["tool_allowlist"] = list(spec.tool_allowlist)
        writer.enqueue_raw(transcript._path, entry)
        writer.durable_barrier(transcript._path)
        return transcript

    @property
    def ref(self) -> SessionRef:
        """Return the immutable address bound to this transcript."""

        return self._ref

    @property
    def external_epoch(self) -> int:
        """Return the monotonic count of committed external appends."""

        with self._mutex:
            return self._external_epoch

    @property
    def path(self) -> Path:
        """Return the bound path for internal hook diagnostics."""

        return self._path

    def load(self, *, up_to: str | None = None) -> TranscriptLoad:
        """Materialize config and reachable conversation messages."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            raw = list(self._files.read_raw_entries(self._ref))
            loaded = _materialize(self._ref, raw, up_to=up_to)
            return TranscriptLoad(
                config=loaded.config,
                messages=loaded.messages,
                prompt_seed=loaded.prompt_seed,
                external_epoch=self._external_epoch,
            )

    def load_config(self) -> SessionConfig:
        """Project config entries without constructing conversation messages."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            config: dict[str, Any] = {}
            for entry in self._files.read_raw_entries(self._ref):
                entry_type = entry.get("type")
                if entry_type == "session_created":
                    config = _extract_config(entry)
                elif entry_type == "config_update":
                    config = _merge_config(config, entry)
            return _to_config(self._ref, config)

    def initial_metadata(self) -> dict[str, Any]:
        """Read immutable creation metadata without scanning turn history."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            for entry in self._files.read_raw_entries(self._ref, limit=1):
                if entry.get("type") == "session_created":
                    return dict(_extract_config(entry).get("metadata") or {})
            raise SessionNotFoundError(f"session not found: {self._ref.session_id}")

    def list_event_entries(self) -> tuple[SessionEntry | CompactionEntry, ...]:
        """Project raw JSONL into the existing compaction planner event vocabulary."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            raw_lines = list(self._files.read_raw_entries(self._ref))
        raw_turns = {
            raw["uuid"]: raw
            for raw in raw_lines
            if raw.get("type") == "turn" and isinstance(raw.get("uuid"), str)
        }
        entries: list[SessionEntry | CompactionEntry] = []
        for raw in raw_lines:
            entry_type = raw.get("type")
            created_at = str(
                raw.get("created_at") or raw.get("timestamp") or utc_now_iso()
            )
            if entry_type in {"session_created", "config_update"}:
                entries.append(
                    new_session_created_entry(
                        session_id=self._ref.session_id,
                        created_at=created_at,
                        data=raw,
                    )
                )
            elif entry_type == "compact_boundary":
                summary_uuid = raw.get("summary_uuid")
                summary = raw_turns.get(summary_uuid, {}).get("content", "")
                entries.append(
                    new_compaction_entry(
                        session_id=self._ref.session_id,
                        first_kept_event_id="",
                        summary=str(summary),
                        data=raw.get("data")
                        if isinstance(raw.get("data"), Mapping)
                        else {},
                        created_at=created_at,
                    )
                )
        for message in _project_recoverable_messages(raw_lines):
            raw = raw_turns.get(message.message_id, {})
            entries.append(
                new_turn_appended_entry(
                    session_id=self._ref.session_id,
                    turn_id=str(raw.get("turn_id") or ""),
                    role=message.role,
                    content=message.content,
                    message_id=message.message_id,
                    parent_message_id=message.parent_message_id,
                    tool_call_id=message.tool_call_id,
                    group_id=message.group_id,
                    reasoning_content=message.reasoning_content,
                    reasoning_signature=message.reasoning_signature,
                    parts=message.parts,
                    metadata=message.metadata,
                    created_at=str(raw.get("timestamp") or utc_now_iso()),
                )
            )
        return tuple(entries)

    def append_messages(
        self,
        messages: Sequence[Message],
        *,
        durable: bool = False,
        turn_id: str | None = None,
    ) -> None:
        """Serialize and append messages onto the current reachable tail."""

        with self._mutex:
            self._append_turn_entries_locked(
                [
                    _message_to_raw(
                        message,
                        self._ref.session_id,
                        turn_id=turn_id,
                    )
                    for message in messages
                ],
                durable=durable,
            )

    def append_messages_snapshot(self, messages: Sequence[Message]) -> None:
        """Append a re-stamped fork snapshot while preserving its internal graph."""

        entries = [
            _message_to_raw(message, self._ref.session_id) for message in messages
        ]
        batch_ids = {entry["uuid"] for entry in entries}
        with self._mutex:
            self._ensure_tail_locked()
            for entry in entries:
                if entry.get("parent_uuid") not in batch_ids:
                    entry["parent_uuid"] = self._tail_uuid
                self._writer.enqueue_raw(self._path, entry)
            if entries:
                self._tail_uuid = str(entries[-1]["uuid"])
                self._tail_known = True
            self._writer.durable_barrier(self._path)

    def append_external(self, request: ExternalMessage) -> AppendMessageResult:
        """Append one idempotent external turn and return only after durability."""

        role = request.role.strip().lower()
        if role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        with self._mutex:
            self._ensure_tail_locked()
            idempotency_key = (
                request.idempotency_key.strip()
                if isinstance(request.idempotency_key, str)
                else ""
            )
            if idempotency_key:
                existing = self._find_idempotency_locked(idempotency_key)
                if existing is not None:
                    return AppendMessageResult(entry=existing, created=False)
            message_id = request.message_id or ids.make_message_id()
            turn_id = request.turn_id or ids.make_turn_id()
            metadata = dict(request.metadata)
            if idempotency_key:
                metadata["idempotency_key"] = idempotency_key
            entry: dict[str, Any] = {
                "type": "turn",
                "uuid": message_id,
                "parent_uuid": self._tail_uuid,
                "session_id": self._ref.session_id,
                "turn_id": turn_id,
                "role": role,
                "content": request.content,
                "timestamp": utc_now_iso(),
            }
            if idempotency_key:
                entry["idempotency_key"] = idempotency_key
            if request.parts:
                entry["parts"] = [dict(part) for part in request.parts]
            _copy_turn_metadata(entry, metadata)
            self._writer.enqueue_raw(self._path, entry)
            self._writer.durable_barrier(self._path)
            self._tail_uuid = message_id
            self._tail_known = True
            self._external_epoch += 1
            return AppendMessageResult(
                entry=new_turn_appended_entry(
                    session_id=self._ref.session_id,
                    turn_id=turn_id,
                    role=role,
                    content=request.content,
                    message_id=message_id,
                    parent_message_id=entry.get("parent_uuid"),
                    parts=request.parts,
                    metadata=metadata,
                ),
                created=True,
            )

    def replace_runtime(
        self,
        *,
        runtime_model: str,
        skills: Sequence[str] | None,
        tool_allowlist: Sequence[str],
        metadata: Mapping[str, Any],
        prompt_seed: PromptSlotSeed,
    ) -> None:
        """Durably replace the complete next-run configuration in one entry."""

        entry: dict[str, Any] = {
            "type": "config_update",
            "session_id": self._ref.session_id,
            "timestamp": utc_now_iso(),
            "skills": list(skills) if skills is not None else None,
            "tool_allowlist": list(tool_allowlist),
            "metadata": internal_metadata(metadata, prompt_seed=prompt_seed),
        }
        runtime_metadata = dict(metadata.get(INTERNAL_RUNTIME_KEY) or {})
        runtime_metadata["model"] = runtime_model
        entry["metadata"][INTERNAL_RUNTIME_KEY] = runtime_metadata
        with self._mutex:
            self._writer.enqueue_raw(self._path, entry)
            self._writer.durable_barrier(self._path)

    def append_tool_call_recovery(
        self,
        *,
        tool_call_id: str,
        reason: str,
        tool_name: str | None = None,
        content: str | None = None,
        durable: bool = False,
    ) -> None:
        """Append one control entry without advancing the conversation tail."""

        entry: dict[str, Any] = {
            "type": "tool_call_recovery",
            "session_id": self._ref.session_id,
            "tool_call_id": tool_call_id,
            "reason": reason,
            "timestamp": utc_now_iso(),
            "idempotency_key": f"tool-call-recovery:{tool_call_id}",
        }
        if tool_name:
            entry["tool_name"] = tool_name
        if content is not None:
            entry["content"] = content
        with self._mutex:
            self._writer.enqueue_raw(self._path, entry)
            if durable:
                self._writer.durable_barrier(self._path)

    def append_compaction(
        self,
        *,
        summary: Message,
        reinjections: Sequence[Message] = (),
        reason: str,
        restored_files: Sequence[str] = (),
        expected_external_epoch: int | None = None,
        manual_idempotency_key: str | None = None,
        result_data: Mapping[str, Any] | None = None,
    ) -> bool:
        """Atomically append a boundary and replacement messages when capture is fresh."""

        with self._mutex:
            if (
                expected_external_epoch is not None
                and expected_external_epoch != self._external_epoch
            ):
                return False
            summary_uuid = summary.message_id
            if not summary_uuid:
                raise ValueError("compaction summary requires uuid")
            boundary = {
                "type": "compact_boundary",
                "session_id": self._ref.session_id,
                "timestamp": utc_now_iso(),
                "summary_uuid": summary_uuid,
                "data": {
                    "reason": reason,
                    "restored_files": list(restored_files),
                    **(
                        {"manual_idempotency_key": manual_idempotency_key}
                        if manual_idempotency_key is not None
                        else {}
                    ),
                    **dict(result_data or {}),
                },
            }
            replacement_entries = []
            for message in (summary, *reinjections):
                entry = _message_to_raw(message, self._ref.session_id)
                message_id = entry.get("uuid")
                if not isinstance(message_id, str) or not message_id:
                    raise ValueError("turn entry requires uuid")
                entry["type"] = "turn"
                entry["session_id"] = self._ref.session_id
                entry["timestamp"] = entry.get("timestamp") or utc_now_iso()
                replacement_entries.append(entry)
            self._ensure_tail_locked()
            self._writer.enqueue_atomic_batch(
                self._path, [boundary, *replacement_entries]
            )
            self._writer.durable_barrier(self._path)
            self._tail_uuid = replacement_entries[-1]["uuid"]
            self._tail_known = True
            return True

    def find_manual_compaction(self, idempotency_key: str) -> Mapping[str, Any] | None:
        """Return the persisted manual-compaction result for one replay key."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            raw = list(self._files.read_raw_entries(self._ref))
        turns = {
            entry.get("uuid"): entry
            for entry in raw
            if entry.get("type") == "turn" and isinstance(entry.get("uuid"), str)
        }
        for entry in reversed(raw):
            if entry.get("type") != "compact_boundary":
                continue
            data = entry.get("data")
            if (
                not isinstance(data, Mapping)
                or data.get("manual_idempotency_key") != idempotency_key
            ):
                continue
            summary_uuid = entry.get("summary_uuid")
            if not isinstance(summary_uuid, str) or not summary_uuid:
                continue
            summary_entry = turns.get(summary_uuid)
            if summary_entry is None:
                continue
            return {
                "entry_id": summary_uuid,
                "summary": str(summary_entry.get("content") or ""),
                "first_kept_event_id": str(data.get("first_kept_event_id") or ""),
                "dropped_event_ids": tuple(data.get("dropped_event_ids") or ()),
                "kept_event_ids": tuple(data.get("kept_event_ids") or ()),
            }
        return None

    def _append_turn_entries_locked(
        self,
        entries: Sequence[Mapping[str, Any]],
        *,
        durable: bool,
    ) -> None:
        """Append already-serialized turns while the transcript mutex is held."""

        self._ensure_tail_locked()
        for raw in entries:
            entry = dict(raw)
            message_id = entry.get("uuid")
            if not isinstance(message_id, str) or not message_id:
                raise ValueError("turn entry requires uuid")
            entry["type"] = "turn"
            entry["session_id"] = self._ref.session_id
            entry["timestamp"] = entry.get("timestamp") or utc_now_iso()
            entry["parent_uuid"] = self._tail_uuid
            self._writer.enqueue_raw(self._path, entry)
            self._tail_uuid = message_id
            self._tail_known = True
        if durable:
            self._writer.durable_barrier(self._path)

    def prepare_for_run(self, *, reason: str = "orphaned") -> None:
        """Repair every persisted orphaned tool call exactly once."""

        with self._mutex:
            self._writer.durable_barrier(self._path)
            raw = list(self._files.read_raw_entries(self._ref))
            pending: dict[str, dict[str, Any]] = {}
            closed: set[str] = set()
            for entry in raw:
                if entry.get("type") == "turn":
                    if entry.get("role") == "assistant":
                        for tool_call in entry.get("tool_calls") or ():
                            call_id = tool_call.get("call_id") or tool_call.get("id")
                            if call_id:
                                pending[call_id] = entry
                    elif entry.get("role") == "tool":
                        call_id = entry.get("tool_call_id")
                        if call_id:
                            closed.add(call_id)
                elif entry.get("type") == "tool_call_recovery":
                    call_id = entry.get("tool_call_id")
                    if call_id:
                        closed.add(call_id)
            for call_id, assistant in pending.items():
                if call_id in closed:
                    continue
                self.append_tool_call_recovery(
                    tool_call_id=call_id,
                    tool_name=_tool_name(assistant, call_id),
                    reason=reason,
                )
            self._writer.durable_barrier(self._path)

    def flush(self) -> None:
        """Wait until every prior raw mutation is durable."""

        self._writer.durable_barrier(self._path)

    async def flush_async(self) -> None:
        """Await durability without blocking the active event loop."""

        await self._writer.durable_barrier_async(self._path)

    def discard_turn(self, turn_id: str) -> bool:
        """Remove one persisted turn while preserving every later branch.

        This is the transcript owner's selective rewrite path. It shares the
        append mutex and writer barrier, reparents retained descendants around
        removed messages, and rebuilds the cached tail before another append can
        proceed. Product code must never truncate the JSONL file directly.

        Args:
            turn_id: Stable identity written on every message in one model turn.

        Returns:
            True when at least one matching message was removed, otherwise False.
        """

        normalized_turn_id = turn_id.strip()
        if not normalized_turn_id:
            return False
        with self._mutex:
            self._writer.durable_barrier(self._path)
            raw = list(self._files.read_raw_entries(self._ref))
            removed_parents = {
                str(entry["uuid"]): entry.get("parent_uuid")
                for entry in raw
                if entry.get("type") == "turn"
                and entry.get("turn_id") == normalized_turn_id
                and isinstance(entry.get("uuid"), str)
            }
            if not removed_parents:
                return False

            retained: list[dict[str, Any]] = []
            for raw_entry in raw:
                if (
                    raw_entry.get("type") == "turn"
                    and raw_entry.get("turn_id") == normalized_turn_id
                ):
                    continue
                entry = dict(raw_entry)
                if entry.get("type") == "turn":
                    entry["parent_uuid"] = _nearest_retained_parent(
                        entry.get("parent_uuid"),
                        removed_parents,
                    )
                retained.append(entry)

            tmp_path = self._path.with_suffix(".jsonl.rewrite_tmp")
            try:
                tmp_path.write_text(
                    "".join(
                        json.dumps(entry, ensure_ascii=False) + "\n"
                        for entry in retained
                    ),
                    encoding="utf-8",
                )
                os.replace(tmp_path, self._path)
            finally:
                tmp_path.unlink(missing_ok=True)

            self._tail_known = False
            self._tail_uuid = None
            self._ensure_tail_locked()
            return True

    def _ensure_tail_locked(self) -> None:
        if self._tail_known:
            return
        self._writer.durable_barrier(self._path)
        raw = self._files.read_raw_entries(self._ref)
        boundary = max(
            (
                index
                for index, entry in enumerate(raw)
                if entry.get("type") == "compact_boundary"
            ),
            default=-1,
        )
        turns = [entry for entry in raw[boundary + 1 :] if entry.get("type") == "turn"]
        reachable = _reachable_turn_entries(turns)
        self._tail_uuid = (
            str(reachable[-1]["uuid"])
            if reachable and isinstance(reachable[-1].get("uuid"), str)
            else None
        )
        self._tail_known = True

    def _find_idempotency_locked(self, key: str):
        self._writer.durable_barrier(self._path)
        for entry in self._files.read_raw_entries(self._ref):
            if entry.get("type") != "turn" or entry.get("idempotency_key") != key:
                continue
            metadata = _turn_metadata(entry)
            metadata["idempotency_key"] = key
            return new_turn_appended_entry(
                session_id=self._ref.session_id,
                turn_id=str(entry.get("turn_id") or ""),
                role=str(entry.get("role") or "user"),
                content=str(entry.get("content") or ""),
                message_id=str(entry.get("uuid") or ""),
                parent_message_id=entry.get("parent_uuid"),
                tool_call_id=entry.get("tool_call_id"),
                group_id=entry.get("group_id"),
                reasoning_content=entry.get("reasoning_content"),
                reasoning_signature=entry.get("reasoning_signature"),
                parts=entry.get("parts"),
                metadata=metadata,
                created_at=str(entry.get("timestamp") or utc_now_iso()),
            )
        return None


def _materialize(
    ref: SessionRef,
    raw: list[dict[str, Any]],
    *,
    up_to: str | None = None,
) -> TranscriptLoad:
    if up_to is not None:
        cut = next(
            (
                index
                for index, entry in enumerate(raw)
                if entry.get("type") == "turn" and entry.get("uuid") == up_to
            ),
            None,
        )
        if cut is None or raw[cut].get("role") != "assistant":
            raise SessionNotFoundError(
                f"fork point {up_to!r} is not an assistant turn in {ref.session_id}"
            )
        raw = raw[: cut + 1]

    config: dict[str, Any] = {}
    for entry in raw:
        entry_type = entry.get("type")
        if entry_type == "session_created":
            config = _extract_config(entry)
        elif entry_type == "config_update":
            config = _merge_config(config, entry)
    resolved = _to_config(ref, config)
    prompt_seed = PromptSlotSeed.from_metadata(
        resolved.metadata.get(INTERNAL_PROMPT_SLOTS_KEY)
    )

    messages = _project_recoverable_messages(raw)
    return TranscriptLoad(config=resolved, messages=messages, prompt_seed=prompt_seed)


def _project_recoverable_messages(raw: list[dict[str, Any]]) -> list[Message]:
    """Materialize the latest active branch with persisted tool recoveries."""

    boundary = max(
        (
            index
            for index, entry in enumerate(raw)
            if entry.get("type") == "compact_boundary"
        ),
        default=-1,
    )
    recoveries: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if entry.get("type") != "tool_call_recovery":
            continue
        call_id = entry.get("tool_call_id")
        if isinstance(call_id, str) and call_id:
            recoveries.setdefault(call_id, entry)
    source = raw[boundary + 1 :] if boundary >= 0 else raw
    turns = [entry for entry in source if entry.get("type") == "turn"]
    return _inject_recovery_messages(_materialize_turns(turns), recoveries)


def _materialize_turns(turns: list[dict[str, Any]]) -> list[Message]:
    return [_to_message(entry) for entry in _reachable_turn_entries(turns)]


def _reachable_turn_entries(
    turns: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve the active branch without allocating domain Messages."""

    if not turns:
        return []
    by_uuid = {entry["uuid"]: entry for entry in turns if "uuid" in entry}
    parents = {entry.get("parent_uuid") for entry in turns if entry.get("parent_uuid")}
    terminals = [entry for entry in turns if entry.get("uuid") not in parents]
    leaf = max(terminals or turns, key=lambda entry: entry.get("timestamp", ""))
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current: dict[str, Any] | None = leaf
    while current is not None:
        chain.append(current)
        current_id = current.get("uuid")
        if isinstance(current_id, str):
            seen.add(current_id)
        parent = current.get("parent_uuid")
        current = by_uuid.get(parent) if parent else None
    if not any(entry.get("parent_uuid") in by_uuid for entry in turns):
        return sorted(turns, key=lambda entry: entry.get("timestamp", ""))
    chain.reverse()
    active_groups = {entry["group_id"] for entry in chain if entry.get("group_id")}
    while True:
        found = False
        for entry in turns:
            entry_id = entry.get("uuid")
            if entry_id in seen:
                continue
            if (
                entry.get("parent_uuid") in seen
                and entry.get("group_id") in active_groups
            ):
                seen.add(entry_id)
                found = True
        if not found:
            break
    chain_ids = {entry.get("uuid") for entry in chain}
    ordered = chain + [
        entry
        for entry in turns
        if entry.get("uuid") in seen and entry.get("uuid") not in chain_ids
    ]
    ordered.sort(key=lambda entry: entry.get("timestamp", ""))
    return ordered


def _inject_recovery_messages(
    messages: list[Message], recoveries: Mapping[str, Mapping[str, Any]]
) -> list[Message]:
    closed = {
        message.tool_call_id
        for message in messages
        if message.role == "tool" and message.tool_call_id
    }
    pending = {key: value for key, value in recoveries.items() if key not in closed}
    if not pending:
        return messages
    result: list[Message] = []
    for message in messages:
        result.append(message)
        if message.role != "assistant":
            continue
        for tool_call in message.metadata.get("tool_calls") or ():
            call_id = tool_call.get("call_id") or tool_call.get("id")
            recovery = pending.get(call_id)
            if recovery is None:
                continue
            reason = str(recovery.get("reason") or "interrupted")
            result.append(
                Message(
                    message_id=ids.make_message_id(),
                    role="tool",
                    content=str(recovery.get("content") or f"[{reason}]"),
                    tool_call_id=call_id,
                    metadata={
                        "recovery_reason": reason,
                        "tool_name": recovery.get("tool_name") or call_id,
                        "is_recovery": True,
                    },
                )
            )
    return result


def _extract_config(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "workspace_root",
            "system_prompt",
            "skills",
            "tool_allowlist",
            "metadata",
            "created_at",
        )
        if key in entry
    }


def _merge_config(base: Mapping[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in ("system_prompt", "skills", "tool_allowlist", "metadata"):
        if key in update:
            merged[key] = update[key]
    return merged


def _to_config(ref: SessionRef, config: Mapping[str, Any]) -> SessionConfig:
    raw_root = config.get("workspace_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise SessionNotFoundError(
            f"session {ref.session_id} is missing workspace_root in session_created"
        )
    persisted_root = Path(raw_root).expanduser().resolve()
    if persisted_root != ref.workspace_root:
        raise SessionNotFoundError(
            f"session {ref.session_id} workspace binding does not match its address"
        )
    skills = config.get("skills")
    allowlist = config.get("tool_allowlist")
    metadata = config.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    runtime_payload = metadata.get(INTERNAL_RUNTIME_KEY)
    runtime_model = (
        runtime_payload.get("model")
        if isinstance(runtime_payload, Mapping)
        and isinstance(runtime_payload.get("model"), str)
        else None
    )
    return SessionConfig(
        session_id=ref.session_id,
        created_at=str(config.get("created_at") or utc_now_iso()),
        workspace_root=persisted_root,
        runtime_model=runtime_model,
        system_prompt=config.get("system_prompt")
        if isinstance(config.get("system_prompt"), str)
        else None,
        skills=tuple(item for item in skills if isinstance(item, str))
        if isinstance(skills, list)
        else None,
        tool_allowlist=tuple(item for item in allowlist if isinstance(item, str))
        if isinstance(allowlist, list)
        else None,
        metadata=metadata,
    )


def _to_message(entry: Mapping[str, Any]) -> Message:
    return Message(
        message_id=str(entry["uuid"]),
        role=str(entry["role"]),
        content=entry.get("content", ""),
        parent_message_id=entry.get("parent_uuid"),
        group_id=entry.get("group_id"),
        tool_call_id=entry.get("tool_call_id"),
        metadata=_turn_metadata(entry),
        reasoning_content=entry.get("reasoning_content") or None,
        reasoning_signature=entry.get("reasoning_signature") or None,
        parts=parse_parts(entry.get("parts")),
    )


def _turn_metadata(entry: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "is_meta",
        "is_compact_summary",
        "is_skill_reinjection",
        "skill_reinjection_refs",
        "is_provider_error",
        "entrypoint",
        "tool_calls",
        "tool_name",
        "tool_error",
        "tool_output",
    )
    metadata = {key: entry[key] for key in keys if key in entry}
    if "idempotency_key" in entry:
        metadata["idempotency_key"] = entry["idempotency_key"]
    return metadata


def _copy_turn_metadata(entry: dict[str, Any], metadata: Mapping[str, Any]) -> None:
    for key in (
        "is_meta",
        "is_compact_summary",
        "is_skill_reinjection",
        "skill_reinjection_refs",
        "is_provider_error",
        "entrypoint",
        "tool_calls",
        "tool_name",
        "tool_error",
        "tool_output",
        "tool_call_id",
        "group_id",
        "reasoning_content",
        "reasoning_signature",
    ):
        if key in metadata:
            entry[key] = metadata[key]


def _tool_name(entry: Mapping[str, Any], call_id: str) -> str | None:
    for tool_call in entry.get("tool_calls") or ():
        if (tool_call.get("call_id") or tool_call.get("id")) == call_id:
            name = tool_call.get("name")
            return name if isinstance(name, str) else None
    return None


def _message_to_raw(
    message: Message,
    session_id: str,
    *,
    turn_id: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "turn",
        "uuid": message.message_id,
        "parent_uuid": message.parent_message_id,
        "session_id": session_id,
        "role": message.role,
        "content": message.content,
        "timestamp": utc_now_iso(),
    }
    if turn_id:
        entry["turn_id"] = turn_id
    if message.parts:
        entry["parts"] = [dict(part) for part in message.parts]
    metadata = dict(message.metadata)
    if message.tool_call_id is not None:
        metadata["tool_call_id"] = message.tool_call_id
    if message.group_id is not None:
        metadata["group_id"] = message.group_id
    if message.reasoning_content is not None:
        metadata["reasoning_content"] = message.reasoning_content
    if message.reasoning_signature is not None:
        metadata["reasoning_signature"] = message.reasoning_signature
    _copy_turn_metadata(entry, metadata)
    return entry


def _nearest_retained_parent(
    parent_uuid: object,
    removed_parents: Mapping[str, object],
) -> str | None:
    """Resolve a retained ancestor when selective deletion removes a parent."""

    current = parent_uuid if isinstance(parent_uuid, str) else None
    seen: set[str] = set()
    while current in removed_parents:
        if current in seen:
            return None
        seen.add(current)
        parent = removed_parents[current]
        current = parent if isinstance(parent, str) else None
    return current
