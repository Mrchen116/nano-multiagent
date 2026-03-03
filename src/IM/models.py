"""Domain models for the independent IM service."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    """Represent a human chat user persisted in IM storage."""

    id: str
    username: str
    display_name: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Conversation:
    """Represent a human-to-human conversation with participants."""

    id: str
    title: str
    participant_ids: list[str]
    created_at: str


@dataclass(frozen=True, slots=True)
class Message:
    """Represent a single message in a conversation."""

    id: str
    conversation_id: str
    sender_user_id: str
    content: str
    created_at: str
