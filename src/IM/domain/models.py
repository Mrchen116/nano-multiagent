"""Domain models for the independent IM service."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_MANAGED_WORKSPACE_ROOT = Path("~/nano-assistant/workspace").expanduser()


def managed_workspace_root(agent_id: str) -> str:
    """Return the canonical managed workspace path for one agent.

    Args:
        agent_id: Stable agent identifier used to derive the managed workspace directory.

    Returns:
        Absolute workspace path under the shared managed workspace root.
    """
    return str((_MANAGED_WORKSPACE_ROOT / agent_id).resolve())


def is_managed_workspace_root(*, agent_id: str, workspace_root: str | None) -> bool:
    """Return whether one stored workspace path matches the managed default.

    Args:
        agent_id: Stable agent identifier whose managed default should be checked.
        workspace_root: Stored workspace path from persistence.

    Returns:
        ``True`` when the stored path is empty or resolves to the managed default path.
    """
    if workspace_root is None:
        return True
    normalized = workspace_root.strip()
    if not normalized:
        return True
    candidate = Path(normalized).expanduser()
    if not candidate.is_absolute():
        return False
    return str(candidate.resolve()) == managed_workspace_root(agent_id)


@dataclass(frozen=True, slots=True)
class Attachment:
    """Represent one attachment reference stored with a message."""

    url: str
    content_type: str | None = None
    file_name: str | None = None


@dataclass(frozen=True, slots=True)
class Actor:
    """Represent one stable actor identity used by IM APIs."""

    type: str
    id: str
    display_name: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        if self.type not in {"user", "agent", "system"}:
            raise ValueError("actor.type must be one of: user, agent, system")
        if not self.id.strip():
            raise ValueError("actor.id must be non-empty")
        if self.user_id is not None and not self.user_id.strip():
            raise ValueError("actor.user_id must be non-empty when provided")

    @property
    def agent_id(self) -> str | None:
        """Return the stable agent id when this actor is an agent."""
        return self.id if self.type == "agent" else None


@dataclass(frozen=True, slots=True)
class User:
    """Represent a human chat user persisted in IM storage."""

    id: str
    username: str
    display_name: str
    owner_id: str
    owned_node_ids: list[str] = field(default_factory=list)
    default_entry_node_id: str | None = None
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class SettingsPolicy:
    """Represent the singleton settings-policy document for the IM control center."""

    default_model: str
    max_turn_per_run: int
    max_attachment_size_mb: int
    retention_days: int
    audit_level: str
    rate_limit_per_min: int


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Represent an agent configuration owned by one IM user."""

    agent_id: str
    owner_id: str
    node_id: str | None = None
    display_name: str = ""
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = field(default_factory=list)
    tool_allowlist: list[str] = field(default_factory=list)
    group_reply_policy: str = "manual"
    default_model: str | None = None
    workspace_root: str | None = None
    profile_version: int = 1


@dataclass(frozen=True, slots=True)
class Conversation:
    """Represent a chat conversation with owner-scoped metadata."""

    id: str
    title: str
    participant_ids: list[str]
    type: str
    owner_id: str
    # creator_id: user who created the conversation; used for dissolve-permission checks (M234).
    creator_id: str
    is_pinned: bool
    is_muted: bool
    unread_count: int
    last_message_preview: str | None
    last_message_at: str | None
    config_profile_version: int | None
    created_at: str
    participants: list[Actor] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.participants:
            return
        object.__setattr__(
            self,
            "participants",
            [
                Actor(type="user", id=participant_id, user_id=participant_id)
                for participant_id in self.participant_ids
            ],
        )

    @property
    def direct_kind(self) -> str | None:
        """Return direct conversation subtype when ``type`` is direct."""
        if self.type != "direct" or len(self.participants) != 2:
            return None
        participant_types = {item.type for item in self.participants}
        if participant_types == {"agent"}:
            return "agent-agent"
        if participant_types == {"agent", "user"}:
            return "user-agent"
        if participant_types == {"user"}:
            return "user-user"
        return None


_TOOL_CALL_STATUSES = frozenset({"running", "completed", "failed"})


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Represent one tool invocation embedded inside an agent message.

    Stored as JSON in ``messages.tool_calls_json`` rather than a separate table:
    tool calls are strongly subordinate to one message, never queried across messages,
    and share its lifecycle (decision 4 of feat-340 design).
    """

    id: str
    name: str
    status: str
    duration_ms: int | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _TOOL_CALL_STATUSES:
            raise ValueError(
                f"tool_call.status must be one of: {sorted(_TOOL_CALL_STATUSES)}; got {self.status!r}"
            )
        if not self.id.strip():
            raise ValueError("tool_call.id must be non-empty")
        if not self.name.strip():
            raise ValueError("tool_call.name must be non-empty")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Per-message token usage snapshot rendered in the chat Token Chip.

    ``context_used`` / ``context_window`` are the model's request-side context
    accounting; ``output`` is the completion tokens for this single message.
    """

    output: int
    context_used: int
    context_window: int


@dataclass(frozen=True, slots=True)
class Message:
    """Represent a single message in a conversation."""

    id: str
    conversation_id: str
    sender_user_id: str
    sender_type: str
    content: str
    sender: Actor | None = None
    attachments: list[Attachment] = field(default_factory=list)
    delivery_status: str = "completed"
    created_at: str = ""
    tool_calls: list[ToolCall] | None = None
    token_usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        if self.sender is None:
            object.__setattr__(
                self,
                "sender",
                Actor(
                    type=self.sender_type,
                    id=self.sender_user_id,
                    user_id=self.sender_user_id,
                ),
            )


@dataclass(frozen=True, slots=True)
class NodeStatus:
    """Represent the runtime status snapshot and center config of one gateway node."""

    node_id: str
    owner_id: str
    node_name: str
    status: str
    last_heartbeat_at: str
    agent_count: int
    version: str
    relay_enabled: bool = True
    reporting_enabled: bool = True
    alias: str | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class UsageMetric:
    """Represent one aggregated token/turn usage snapshot."""

    scope: str
    scope_id: str | None
    owner_id: str | None
    conversation_id: str | None
    agent_id: str | None
    turns: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    last_used_at: str | None


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
class DeviceBindRequest:
    """Represent one device bind request across start and confirm steps."""

    bind_id: str
    node_id: str
    user_id: str | None
    status: str
    bind_token: str
    bind_url: str
    created_at: str
    confirmed_at: str | None = None


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
