"""SSE HTTP handlers for global event stream polling."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from nano_multiagent.server.sse import EventStreamHub, StreamEvent, encode_sse_event

from ..auth import require_bearer_auth
from ..deps import get_event_stream_hub

router = APIRouter(
    prefix="/v1",
    tags=["events"],
    dependencies=[Depends(require_bearer_auth)],
)


@router.get("/events")
def stream_global_events(
    max_events: int = Query(default=20, ge=1, le=200),
    timeout_seconds: float = Query(default=0.25, ge=0.0, le=5.0),
    event_hub: EventStreamHub = Depends(get_event_stream_hub),
) -> StreamingResponse:
    """Stream cross-session SSE events within one bounded poll window."""
    return StreamingResponse(
        _iter_sse(
            event_hub.stream(
                session_id=None,
                max_events=max_events,
                timeout_seconds=timeout_seconds,
            )
        ),
        media_type="text/event-stream",
    )


def _iter_sse(events: Iterator[StreamEvent]) -> Iterator[str]:
    """Encode hub events into wire-level SSE text chunks."""
    for item in events:
        yield encode_sse_event(event_id=item.event_id, event=item.event, data=item.data)
