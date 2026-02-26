from datetime import UTC, datetime

from nano_multiagent.core import ids

from .models import Session


class SessionService:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        session_id = ids.make_session_id()
        session = Session(
            session_id=session_id,
            status='active',
            created_at=datetime.now(UTC).isoformat(),
        )
        self._sessions[session_id] = session
        return session
