"""Application service for IM conversation event streaming."""

from IM.domain.models import ConversationEvent
from IM.infra.repositories import EventRepository


class EventService:
    """Coordinate read access to persisted conversation events."""

    def __init__(self, *, events: EventRepository) -> None:
        """Bind service to the event repository.

        Args:
            events: Repository used for SSE replay and polling.
        """
        self._events = events

    def list_events(
        self,
        *,
        conversation_id: str,
        after_event_id: int = 0,
        limit: int = 200,
    ) -> list[ConversationEvent]:
        """List conversation events newer than the provided cursor."""
        return self._events.list_events(
            conversation_id=conversation_id,
            after_event_id=after_event_id,
            limit=limit,
        )
