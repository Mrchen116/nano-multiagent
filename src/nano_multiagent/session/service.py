from datetime import UTC, datetime
from secrets import token_hex

from .models import Session


class SessionService:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        session_id = f'sess_{token_hex(8)}'
        session = Session(
            session_id=session_id,
            status='active',
            created_at=datetime.now(UTC).isoformat(),
        )
        self._sessions[session_id] = session
        return session
