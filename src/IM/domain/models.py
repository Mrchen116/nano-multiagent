"""Domain models for the independent IM service."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class User:
    """Represent a human chat user persisted in IM storage."""

    id: str
    username: str
    display_name: str
    owner_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Represent an agent configuration owned by one IM user."""

    agent_id: str
    owner_id: str
    display_name: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)
    tool_allowlist: list[str] = field(default_factory=list)
    group_reply_policy: str = "manual"
    default_model: str | None = None
    profile_version: int = 1


@dataclass(frozen=True, slots=True)
class Conversation:
    """Represent a chat conversation with owner-scoped metadata."""

    id: str
    title: str
    participant_ids: list[str]
    type: str
    owner_id: str
    is_pinned: bool
    is_muted: bool
    unread_count: int
    last_message_at: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class Message:
    """Represent a single message in a conversation."""

    id: str
    conversation_id: str
    sender_user_id: str
    sender_type: str
    content: str
    attachments: list[str] = field(default_factory=list)
    delivery_status: str = "completed"
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class NodeStatus:
    """Represent the runtime status snapshot of one gateway node."""

    node_id: str
    owner_id: str
    node_name: str
    status: str
    last_heartbeat_at: str
    agent_count: int
    version: str
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class RelayTask:
    """Represent one idempotent relay task enqueued for gateway delivery."""

    relay_task_id: str
    message_id: str
    conversation_id: str
    target_node_id: str
    payload: dict[str, object]
    idempotency_key: str
    status: str
    created_at: str
    updated_at: str
    receipt_status: str | None = None
    receipt_detail: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationEvent:
    """Represent a persisted conversation event for SSE replay/reconnect."""

    event_id: int
    conversation_id: str
    message_id: str | None
    event_type: str
    delivery_status: str
    payload_json: str
    created_at: str
