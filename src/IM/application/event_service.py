"""Application service for IM conversation event streaming."""

from __future__ import annotations

from dataclasses import replace
import json

from IM.domain.models import ConversationEvent
from IM.infra._helpers import _optional_text
from IM.infra.repositories import EventRepository


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

    def global_max_event_id(self) -> int:
        """Return the latest persisted event id across all conversations."""
        return self._events.global_max_event_id()

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
        return self._enrich_relay_identity(
            conversation_id=conversation_id, events=events
        )

    def _enrich_relay_identity(
        self,
        *,
        conversation_id: str,
        events: list[ConversationEvent],
    ) -> list[ConversationEvent]:
        if not events:
            return events
        up_to_event_id = max(event.event_id for event in events)
        run_identity_by_run_id = self._events.relay_run_identities(
            conversation_id=conversation_id,
            up_to_event_id=up_to_event_id,
        )
        agent_display_names = self._events.agent_display_names(
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
                run_id = _optional_text(payload.get("run_id"))
                identity = (
                    run_identity_by_run_id.get(run_id) if run_id is not None else None
                )
                if identity is not None:
                    if identity.agent_id is not None and "agent_id" not in payload:
                        payload["agent_id"] = identity.agent_id
                        changed = True
                    if (
                        identity.relay_task_id is not None
                        and "relay_task_id" not in payload
                    ):
                        payload["relay_task_id"] = identity.relay_task_id
                        changed = True
            agent_id = _optional_text(payload.get("agent_id"))
            if agent_id is not None and "sender_display_name" not in payload:
                sender_display_name = agent_display_names.get(agent_id)
                if sender_display_name is not None:
                    payload["sender_display_name"] = sender_display_name
                    changed = True
            if changed:
                event = replace(
                    event,
                    payload_json=json.dumps(
                        payload, ensure_ascii=True, separators=(",", ":")
                    ),
                )
            enriched_events.append(event)
        return enriched_events

    @staticmethod
    def _decode_payload(event: ConversationEvent) -> dict[str, object] | None:
        try:
            payload = json.loads(event.payload_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload


__all__ = ["EventService"]
