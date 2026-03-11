"""Legacy compatibility facade for IM domain models."""

from IM.domain.models import (
    AgentProfile,
    Conversation,
    ConversationEvent,
    Message,
    NodeStatus,
    RelayTask,
    User,
)

__all__ = [
    "AgentProfile",
    "Conversation",
    "ConversationEvent",
    "Message",
    "NodeStatus",
    "RelayTask",
    "User",
]
