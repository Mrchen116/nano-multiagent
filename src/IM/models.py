"""Legacy compatibility facade for IM domain models."""

from IM.domain.models import (
    AgentProfile,
    Conversation,
    ConversationEvent,
    DeviceBindRequest,
    Message,
    NodeStatus,
    RelayTask,
    User,
)

__all__ = [
    "AgentProfile",
    "Conversation",
    "ConversationEvent",
    "DeviceBindRequest",
    "Message",
    "NodeStatus",
    "RelayTask",
    "User",
]
