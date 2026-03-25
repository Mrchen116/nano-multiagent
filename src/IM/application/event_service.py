"""Application service for IM conversation event streaming."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json

from IM.domain.models import ConversationEvent
from IM.infra.repositories import EventRepository


@dataclass(frozen=True, slots=True)
class _RelayRunIdentity:
    relay_task_id: str | None
    agent_id: str | None


class EventService:
    """Coordinate read access to persisted conversation events."""

    def __init__(self, *, events: EventRepository) -> None:
        """Bind service to the event repository.

        Args:
            events: Repository used for SSE replay and polling.
        """
        self._events = events

    def get_latest_event_id(self, *, conversation_id: str) -> int:
        """Return the latest persisted event id for one conversation."""
        return self._events.get_latest_event_id(conversation_id=conversation_id)

    def list_events(
        self,
        *,
        conversation_id: str,
        after_event_id: int = 0,
        limit: int = 200,
    ) -> list[ConversationEvent]:
        """List conversation events newer than the provided cursor."""
        events = self._events.list_events(
            conversation_id=conversation_id,
            after_event_id=after_event_id,
            limit=limit,
        )
        return self._enrich_relay_identity(conversation_id=conversation_id, events=events)

    def _enrich_relay_identity(
        self,
        *,
        conversation_id: str,
        events: list[ConversationEvent],
    ) -> list[ConversationEvent]:
        if not events:
            return events
        up_to_event_id = max(event.event_id for event in events)
        run_identity_by_run_id = self._load_relay_run_identity(
            conversation_id=conversation_id,
            up_to_event_id=up_to_event_id,
        )
        agent_display_names = self._load_agent_display_names(
            agent_ids={
                identity.agent_id
                for identity in run_identity_by_run_id.values()
                if identity.agent_id is not None and identity.agent_id.strip()
            }
        )
        enriched_events: list[ConversationEvent] = []
        for event in events:
            payload = self._decode_payload(event)
            if payload is None:
                enriched_events.append(event)
                continue

            changed = False
            if event.event_type in {"relay.processing", "relay.report"}:
                run_id = self._optional_text(payload.get("run_id"))
                identity = run_identity_by_run_id.get(run_id) if run_id is not None else None
                if identity is not None:
                    if identity.agent_id is not None and "agent_id" not in payload:
                        payload["agent_id"] = identity.agent_id
                        changed = True
                    if identity.relay_task_id is not None and "relay_task_id" not in payload:
                        payload["relay_task_id"] = identity.relay_task_id
                        changed = True
            agent_id = self._optional_text(payload.get("agent_id"))
            if agent_id is not None and "sender_display_name" not in payload:
                sender_display_name = agent_display_names.get(agent_id)
                if sender_display_name is not None:
                    payload["sender_display_name"] = sender_display_name
                    changed = True
            if changed:
                event = replace(event, payload_json=json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
            enriched_events.append(event)
        return enriched_events

    def _load_relay_run_identity(
        self,
        *,
        conversation_id: str,
        up_to_event_id: int,
    ) -> dict[str, _RelayRunIdentity]:
        rows = self._events._connection.execute(  # noqa: SLF001
            """
            SELECT payload_json
            FROM conversation_events
            WHERE conversation_id = ? AND event_type = ? AND event_id <= ?
            ORDER BY event_id
            """,
            (conversation_id, "relay.accepted", up_to_event_id),
        ).fetchall()
        run_identity_by_run_id: dict[str, _RelayRunIdentity] = {}
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            run_id = self._parse_run_id(payload)
            if run_id is None:
                continue
            run_identity_by_run_id[run_id] = _RelayRunIdentity(
                relay_task_id=self._optional_text(payload.get("relay_task_id")),
                agent_id=self._optional_text(payload.get("agent_id")),
            )
        return run_identity_by_run_id

    def _load_agent_display_names(self, *, agent_ids: set[str]) -> dict[str, str]:
        if not agent_ids:
            return {}
        placeholders = ",".join("?" for _ in agent_ids)
        rows = self._events._connection.execute(  # noqa: SLF001
            f"SELECT agent_id, display_name FROM agent_profiles WHERE agent_id IN ({placeholders})",  # noqa: S608, SLF001
            tuple(agent_ids),
        ).fetchall()
        return {
            str(row["agent_id"]): str(row["display_name"])
            for row in rows
            if row["agent_id"] is not None and row["display_name"] is not None and str(row["display_name"]).strip()
        }

    @staticmethod
    def _decode_payload(event: ConversationEvent) -> dict[str, object] | None:
        try:
            payload = json.loads(event.payload_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @classmethod
    def _parse_run_id(cls, payload: dict[str, object]) -> str | None:
        direct_run_id = cls._optional_text(payload.get("run_id"))
        if direct_run_id is not None:
            return direct_run_id
        detail = cls._optional_text(payload.get("detail"))
        if detail is None or not detail.startswith("run_id="):
            return None
        return cls._optional_text(detail[len("run_id=") :])

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None


__all__ = ["EventService"]
