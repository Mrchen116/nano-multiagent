"""Application service for idempotent IM relay delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import Message, RelayTask


@dataclass(frozen=True, slots=True)
class _RelayAgentSnapshot:
    agent_id: str | None
    profile_version: int | None
    system_prompt: str | None


@dataclass(frozen=True, slots=True)
class RelayEnqueueResult:
    """Describe the outcome of enqueueing one relay task."""

    relay_task: RelayTask
    created: bool


class RelayService:
    """Create and update idempotent relay tasks for gateway delivery.

    Args:
        connection: SQLite connection shared with the IM app lifecycle.

    Notes:
        Relay task uniqueness is enforced by ``idempotency_key`` so retries do not
        create duplicate downstream deliveries.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def enqueue_message_relay(
        self,
        *,
        message: Message,
        target_node_id: str,
        idempotency_key: str,
        sender_user_id: str,
        conversation_type: str | None = None,
        extra_metadata: dict[str, object] | None = None,
        _override_agent_id: str | None = None,
    ) -> RelayEnqueueResult:
        """Create or return an existing relay task for one IM message.

        Args:
            message: Persisted message that should be relayed to a gateway node.
            target_node_id: Gateway node that should receive the relay.
            idempotency_key: Stable retry key for the logical relay request.
            sender_user_id: Human sender identifier copied into the relay payload.
            conversation_type: Conversation kind copied into relay metadata so gateway mention gating
                can distinguish group chats from direct chats.
            _override_agent_id: Internal-only override for group-chat fan-out; forces payload.agent_id
                to this value instead of the snapshot-resolved agent.  Callers should prefer
                ``enqueue_message_relay_all`` for group broadcasts.

        Returns:
            RelayEnqueueResult with the canonical task and whether it was newly created.

        Raises:
            ValueError: When target_node_id or idempotency_key is blank.
        """
        if not target_node_id.strip():
            raise ValueError("target_node_id must be non-empty")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty")

        existing = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
        if existing is not None:
            return RelayEnqueueResult(relay_task=existing, created=False)

        created_at = _utc_now()
        relay_task_id = uuid4().hex
        mentioned_agent_ids = self._resolve_mention_to_agent_ids(
            self._extract_mentioned_agent_ids(message.content)
        )
        agent_snapshot = self._resolve_agent_snapshot(
            conversation_id=message.conversation_id,
            mentioned_agent_ids=mentioned_agent_ids,
        )
        metadata = {
            "conversation_type": conversation_type,
            "mentioned_agent_ids": mentioned_agent_ids,
        }
        if conversation_type == "group":
            metadata["participant_agent_ids"] = self._resolve_participant_agent_ids(
                conversation_id=message.conversation_id,
            )
        if extra_metadata:
            metadata.update(extra_metadata)
        if agent_snapshot.profile_version is not None:
            metadata["config_profile_version"] = agent_snapshot.profile_version
        payload = {
            "idempotency_key": idempotency_key,
            "conversation_id": message.conversation_id,
            "metadata": metadata,
            "message": {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_user_id": sender_user_id,
                "sender_type": message.sender_type,
                "content": message.content,
                "attachments": [
                    {
                        "url": att.url,
                        "content_type": att.content_type,
                        "file_name": att.file_name,
                    }
                    for att in message.attachments
                ],
                "created_at": message.created_at,
            },
        }
        # M247: group relays carry structured sender and participants so gateway
        # can show display names instead of raw UUIDs.  Direct chats omit these
        # fields to keep the payload backward-compatible.
        if conversation_type == "group":
            payload["sender"] = self._resolve_sender_info(sender_user_id=sender_user_id)
            payload["participants"] = self._resolve_all_participants(
                conversation_id=message.conversation_id,
            )
        # _override_agent_id is used by enqueue_message_relay_all for group fan-out:
        # each per-agent relay identifies its own target agent explicitly.
        effective_agent_id = _override_agent_id if _override_agent_id is not None else agent_snapshot.agent_id
        if effective_agent_id:
            payload["agent_id"] = effective_agent_id
        payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self._connection:
            try:
                self._connection.execute(
                    """
                    INSERT INTO relay_tasks(
                        relay_task_id,
                        message_id,
                        conversation_id,
                        target_node_id,
                        payload_json,
                        idempotency_key,
                        status,
                        receipt_status,
                        receipt_detail,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relay_task_id,
                        message.id,
                        message.conversation_id,
                        target_node_id,
                        payload_json,
                        idempotency_key,
                        "pending",
                        None,
                        None,
                        created_at,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
                if existing is None:  # pragma: no cover - defensive consistency guard
                    raise
                return RelayEnqueueResult(relay_task=existing, created=False)
        created = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
        assert created is not None
        return RelayEnqueueResult(relay_task=created, created=True)

    def enqueue_message_relay_all(
        self,
        *,
        message: Message,
        target_node_id: str,
        idempotency_key_base: str,
        sender_user_id: str,
        conversation_type: str | None = None,
    ) -> list[RelayEnqueueResult]:
        """Create relay tasks for all participant agents in the conversation.

        For group chats: creates one independent relay task per participant agent, each
        carrying the full ``mentioned_agent_ids`` list so gateway can decide execute vs
        buffer based on whether this agent was addressed.

        For direct chats: creates a single relay task (same semantics as
        ``enqueue_message_relay``).

        Args:
            message: Persisted message to relay.
            target_node_id: Gateway node that should receive every relay.
            idempotency_key_base: Base retry key; per-agent key is ``{base}:{agent_id}``.
            sender_user_id: Human sender identifier copied into relay payload.
            conversation_type: Conversation kind; ``"group"`` triggers fan-out.

        Returns:
            List of RelayEnqueueResult, one per agent.  Never empty for known conversations.

        Raises:
            ValueError: When target_node_id or idempotency_key_base is blank.
        """
        if not target_node_id.strip():
            raise ValueError("target_node_id must be non-empty")
        if not idempotency_key_base.strip():
            raise ValueError("idempotency_key_base must be non-empty")

        if conversation_type != "group":
            # Direct/unknown chats: single relay, backward-compatible path.
            result = self.enqueue_message_relay(
                message=message,
                target_node_id=target_node_id,
                idempotency_key=idempotency_key_base,
                sender_user_id=sender_user_id,
                conversation_type=conversation_type,
            )
            return [result]

        # Group chat: one relay per participant agent so each gateway node receives its own task.
        participant_agent_ids = self._resolve_participant_agent_ids(
            conversation_id=message.conversation_id,
        )
        if not participant_agent_ids:
            # No known agents in conversation; fall back to single relay.
            result = self.enqueue_message_relay(
                message=message,
                target_node_id=target_node_id,
                idempotency_key=idempotency_key_base,
                sender_user_id=sender_user_id,
                conversation_type=conversation_type,
            )
            return [result]

        results: list[RelayEnqueueResult] = []
        for agent_id in participant_agent_ids:
            per_agent_key = f"{idempotency_key_base}:{agent_id}"
            # Each agent gets its own relay; payload.agent_id identifies the target agent.
            result = self.enqueue_message_relay(
                message=message,
                target_node_id=target_node_id,
                idempotency_key=per_agent_key,
                sender_user_id=sender_user_id,
                conversation_type=conversation_type,
                _override_agent_id=agent_id,
            )
            results.append(result)
        return results

    def resolve_target_node_id(
        self,
        *,
        conversation_id: str,
        content: str,
    ) -> str | None:
        """Resolve the bound node for the concrete target agent of a message."""
        mentioned_agent_ids = self._resolve_mention_to_agent_ids(
            self._extract_mentioned_agent_ids(content)
        )
        agent_snapshot = self._resolve_agent_snapshot(
            conversation_id=conversation_id,
            mentioned_agent_ids=mentioned_agent_ids,
        )
        if not agent_snapshot.agent_id:
            return None
        row = self._connection.execute(
            "SELECT node_id FROM agent_profiles WHERE agent_id = ?",
            (agent_snapshot.agent_id,),
        ).fetchone()
        if row is None or row["node_id"] in (None, ""):
            return None
        return str(row["node_id"])

    @classmethod
    def _extract_mentioned_agent_ids(cls, content: str) -> list[str]:
        mentioned: set[str] = set()
        for token in content.split():
            if not token.startswith("@") or len(token) <= 1:
                continue
            candidate = cls._normalize_mentioned_agent_id(token[1:])
            if candidate:
                mentioned.add(candidate)
        return sorted(mentioned)

    @staticmethod
    def _normalize_mentioned_agent_id(token: str) -> str | None:
        candidate = token.strip().strip(".,!?:;)]}\"'”’")
        if not candidate:
            return None
        if candidate.startswith("agent:"):
            candidate = candidate[len("agent:") :].strip()
        return candidate or None

    def _resolve_mention_to_agent_ids(self, raw_mentions: list[str]) -> list[str]:
        """把原始 @mention token 解析成真实 agent_id。

        用户在 picker 里选择 display_name（如"架构"），发出的文本是 @架构，
        但 Gateway 的 mentioned_agent_ids 需要存真实 agent_id（如"Arch"）。
        先按 agent_id 精确匹配，找不到再按 display_name 查表。
        """
        if not raw_mentions:
            return []
        resolved: list[str] = []
        for raw in raw_mentions:
            # 先检查是否直接就是合法的 agent_id
            exact = self._connection.execute(
                "SELECT agent_id FROM agent_profiles WHERE agent_id = ?", (raw,)
            ).fetchone()
            if exact is not None:
                resolved.append(raw)
                continue
            # 按 display_name 模糊查（大小写不敏感）
            by_name = self._connection.execute(
                "SELECT agent_id FROM agent_profiles WHERE lower(display_name) = lower(?)", (raw,)
            ).fetchone()
            if by_name is not None:
                resolved.append(str(by_name["agent_id"]))
                continue
            # 保留原始值作为兜底（上游可能已经是 agent_id）
            resolved.append(raw)
        return resolved

    def _resolve_agent_snapshot(self, *, conversation_id: str, mentioned_agent_ids: list[str]) -> _RelayAgentSnapshot:
        conversation_row = self._connection.execute(
            """
            SELECT type, config_agent_id, config_profile_version, config_system_prompt
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,),
        ).fetchone()
        conversation_type = str(conversation_row["type"]) if conversation_row is not None else None
        frozen_agent_id = None
        frozen_profile_version = None
        frozen_system_prompt = None
        if conversation_row is not None:
            if conversation_row["config_agent_id"] is not None:
                frozen_agent_id = str(conversation_row["config_agent_id"])
            if conversation_row["config_profile_version"] is not None:
                frozen_profile_version = int(conversation_row["config_profile_version"])
            if conversation_row["config_system_prompt"] is not None:
                frozen_system_prompt = str(conversation_row["config_system_prompt"])

        def _profile_snapshot(agent_id: str) -> _RelayAgentSnapshot | None:
            profile = self._profile_row(agent_id=agent_id)
            if profile is None:
                return None
            return _RelayAgentSnapshot(
                agent_id=agent_id,
                profile_version=int(profile["profile_version"]),
                system_prompt=str(profile["system_prompt"]),
            )

        participant_rows = self._connection.execute(
            """
            SELECT cp.user_id, u.username
            FROM conversation_participants cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.conversation_id = ?
            ORDER BY cp.rowid
            """,
            (conversation_id,),
        ).fetchall()
        participant_agent_ids: list[str] = []
        for row in participant_rows:
            direct_agent_id = str(row["user_id"])
            if self._profile_row(agent_id=direct_agent_id) is not None:
                participant_agent_ids.append(direct_agent_id)
                continue
            username = str(row["username"])
            if not username.startswith("agent:"):
                continue
            alias_agent_id = username[len("agent:") :].strip()
            if not alias_agent_id:
                continue
            if self._profile_row(agent_id=alias_agent_id) is None:
                continue
            participant_agent_ids.append(alias_agent_id)

        selected_agent_id: str | None = None
        for mentioned_agent_id in mentioned_agent_ids:
            if mentioned_agent_id in participant_agent_ids:
                selected_agent_id = mentioned_agent_id
                break
        if selected_agent_id is None and participant_agent_ids:
            selected_agent_id = participant_agent_ids[0]

        if conversation_type == "direct" and frozen_agent_id and (
            selected_agent_id is None or selected_agent_id == frozen_agent_id
        ):
            frozen_snapshot = _profile_snapshot(frozen_agent_id)
            return _RelayAgentSnapshot(
                agent_id=frozen_agent_id,
                profile_version=frozen_profile_version,
                system_prompt=frozen_system_prompt,
            )

        if selected_agent_id is None:
            return _RelayAgentSnapshot(agent_id=None, profile_version=frozen_profile_version, system_prompt=None)

        selected_snapshot = _profile_snapshot(selected_agent_id)
        if selected_snapshot is not None:
            if (
                conversation_type == "group"
                and frozen_agent_id == selected_snapshot.agent_id
                and frozen_system_prompt == selected_snapshot.system_prompt
                and frozen_profile_version is not None
                and selected_snapshot.profile_version > frozen_profile_version
            ):
                return _RelayAgentSnapshot(
                    agent_id=selected_snapshot.agent_id,
                    profile_version=selected_snapshot.profile_version,
                    system_prompt=frozen_system_prompt,
                )
            return selected_snapshot

        if conversation_type == "group" and frozen_agent_id and (
            selected_agent_id is None or selected_agent_id == frozen_agent_id
        ):
            frozen_snapshot = _profile_snapshot(frozen_agent_id)
            return _RelayAgentSnapshot(
                agent_id=frozen_agent_id,
                profile_version=frozen_profile_version,
                system_prompt=frozen_system_prompt,
            )

        return _RelayAgentSnapshot(agent_id=None, profile_version=frozen_profile_version, system_prompt=None)

    def _resolve_participant_agent_ids(self, *, conversation_id: str) -> list[str]:
        """Return all participant agent IDs for a conversation, in insertion order.

        Resolves both direct agent_id matches (where user_id is a known agent_id) and
        ``agent:`` username aliases.  Only IDs with a known agent_profiles row are returned.

        Args:
            conversation_id: Conversation to inspect.

        Returns:
            Ordered list of resolved agent IDs; empty if no agents are participants.
        """
        participant_rows = self._connection.execute(
            """
            SELECT cp.user_id, u.username
            FROM conversation_participants cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.conversation_id = ?
            ORDER BY cp.rowid
            """,
            (conversation_id,),
        ).fetchall()
        agent_ids: list[str] = []
        for row in participant_rows:
            direct_agent_id = str(row["user_id"])
            if self._profile_row(agent_id=direct_agent_id) is not None:
                agent_ids.append(direct_agent_id)
                continue
            username = str(row["username"])
            if not username.startswith("agent:"):
                continue
            alias_agent_id = username[len("agent:"):].strip()
            if not alias_agent_id:
                continue
            if self._profile_row(agent_id=alias_agent_id) is None:
                continue
            agent_ids.append(alias_agent_id)
        return agent_ids

    def _resolve_sender_info(self, *, sender_user_id: str) -> dict[str, str]:
        """Return ``{id, display_name, type}`` for one sender.

        Args:
            sender_user_id: Raw user UUID from the relay request.

        Returns:
            Dict with ``id``, ``display_name`` (fallback to id when unknown), and
            ``type`` (``"user"`` or ``"agent"``).

        Notes:
            Resolves against the users table first; if the user's username begins with
            ``agent:`` the sender is typed as an agent.  Fallback to ``id`` when the
            user row cannot be found.
        """
        row = self._connection.execute(
            "SELECT id, username, display_name FROM users WHERE id = ?",
            (sender_user_id,),
        ).fetchone()
        if row is None:
            return {"id": sender_user_id, "display_name": sender_user_id, "type": "user"}
        username = str(row["username"])
        sender_type = "agent" if username.startswith("agent:") else "user"
        display_name = str(row["display_name"]) or sender_user_id
        return {"id": sender_user_id, "display_name": display_name, "type": sender_type}

    def _resolve_all_participants(self, *, conversation_id: str) -> list[dict[str, str]]:
        """Return ``[{id, display_name, type}]`` for all conversation participants.

        Args:
            conversation_id: Conversation to inspect.

        Returns:
            Ordered list of participant dicts in insertion order.  Each dict has
            ``id`` (user UUID), ``display_name`` (from users or agent_profiles),
            and ``type`` (``"user"`` or ``"agent"``).

        Notes:
            For agent participants (``agent:`` username prefix), ``display_name`` is
            resolved from ``agent_profiles.display_name`` when available, otherwise
            from ``users.display_name``.  Human user display names come from
            ``users.display_name``.
        """
        rows = self._connection.execute(
            """
            SELECT cp.user_id, u.username, u.display_name
            FROM conversation_participants cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.conversation_id = ?
            ORDER BY cp.rowid
            """,
            (conversation_id,),
        ).fetchall()
        result: list[dict[str, str]] = []
        for row in rows:
            user_id = str(row["user_id"])
            username = str(row["username"])
            user_display_name = str(row["display_name"]) or user_id
            if username.startswith("agent:"):
                # Resolve agent display_name from agent_profiles (canonical title).
                agent_id = username[len("agent:"):].strip()
                profile = self._agent_display_name_row(agent_id=agent_id) if agent_id else None
                display_name = profile if profile else user_display_name
                result.append({"id": user_id, "display_name": display_name, "type": "agent"})
            else:
                result.append({"id": user_id, "display_name": user_display_name, "type": "user"})
        return result

    def _agent_display_name_row(self, *, agent_id: str) -> str | None:
        """Return the display_name from agent_profiles for one agent, or None when missing."""
        row = self._connection.execute(
            "SELECT display_name FROM agent_profiles WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        value = row["display_name"]
        return str(value) if value else None

    def _profile_row(self, *, agent_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT agent_id, profile_version, system_prompt FROM agent_profiles WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()

    def get_task_by_idempotency_key(self, *, idempotency_key: str) -> RelayTask | None:
        """Return the canonical relay task for one idempotency key if present."""
        row = self._connection.execute(
            """
            SELECT relay_task_id, message_id, conversation_id, target_node_id, payload_json,
                   idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at
            FROM relay_tasks
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_relay_task(row)

    def mark_dispatched(self, *, relay_task_id: str) -> RelayTask:
        """Move one relay task from pending to dispatched after websocket push."""
        updated_at = _utc_now()
        with self._connection:
            self._connection.execute(
                "UPDATE relay_tasks SET status = ?, updated_at = ? WHERE relay_task_id = ?",
                ("dispatched", updated_at, relay_task_id),
            )
        task = self.get_task(relay_task_id=relay_task_id)
        assert task is not None
        return task

    def apply_delivery_receipt(
        self,
        *,
        relay_task_id: str,
        delivery_status: str,
        detail: str | None,
    ) -> RelayTask:
        """Apply a gateway delivery receipt to an existing relay task."""
        normalized = delivery_status.strip().lower()
        if normalized not in {"sent", "completed", "failed"}:
            raise ValueError("delivery_status must be one of sent/completed/failed")
        status = "failed" if normalized == "failed" else normalized
        updated_at = _utc_now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE relay_tasks
                SET status = ?, receipt_status = ?, receipt_detail = ?, updated_at = ?
                WHERE relay_task_id = ?
                """,
                (status, normalized, detail, updated_at, relay_task_id),
            )
        task = self.get_task(relay_task_id=relay_task_id)
        if task is None:
            raise ValueError("relay_task_id not found")
        return task

    def get_task(self, *, relay_task_id: str) -> RelayTask | None:
        """Return one relay task by primary key if present."""
        row = self._connection.execute(
            """
            SELECT relay_task_id, message_id, conversation_id, target_node_id, payload_json,
                   idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at
            FROM relay_tasks
            WHERE relay_task_id = ?
            """,
            (relay_task_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_relay_task(row)


def _row_to_relay_task(row: sqlite3.Row) -> RelayTask:
    payload = json.loads(row["payload_json"])
    return RelayTask(
        relay_task_id=row["relay_task_id"],
        message_id=row["message_id"],
        conversation_id=row["conversation_id"],
        target_node_id=row["target_node_id"],
        payload=payload,
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        receipt_status=row["receipt_status"],
        receipt_detail=row["receipt_detail"],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
