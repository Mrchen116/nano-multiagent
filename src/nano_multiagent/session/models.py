from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    session_id: str
    status: str
    created_at: str
