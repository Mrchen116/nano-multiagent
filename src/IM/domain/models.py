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
    is_stale: bool | None = None

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
    password_hash: str | None = None
    locale: str = "en"


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
    is_stale: bool = False
    # feat-379-M2: per-agent feature-flag overrides (keyed by FEATURE_REGISTRY key)
    # and optional custom prompt supplement.  Absent keys inherit gateway defaults.
    features: dict[str, bool] = field(default_factory=dict)
    custom_prompt: str | None = None
    # feat-394: heartbeat cadence persisted as JSON string.
    # Shape: {"every": str, "active_hours": {...} | null}
    # Stored as raw JSON so the gateway can forward cadence config without re-serialization;
    # enable state lives in features["heartbeat"] (feat-394 M9-E decision D).
    # None means not yet configured (no cadence set by user).
    heartbeat_json: str | None = None


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
    config_agent_id: str | None
    config_profile_version: int | None
    created_at: str
    external_source: str | None = None
    external_chat_id: str | None = None
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
class ThinkingSegment:
    """feat-439-M2: 助手回复一轮里的一段思考（过程时间线的「过程项」之一）。

    一个气泡 = 一个 turn = 多次模型调用，每次各自可能产出一段思考；思考与工具调用按
    真实时序混排成一条「过程」时间线。``seq`` 是与 ``ToolCall.seq`` **共享的同一个
    per-message 单调递增序号**——由 IM 在持久化边界按真实到达序赋值、全局唯一（跨思考
    与工具一个计数器）：渲染端按 seq 升序把思考与工具 merge 成时间线，唯一性也让 live
    WS 事件可按 seq 幂等去重。与 ``ToolCall`` 一样作为 JSON 存在 ``messages.thinking_json``，
    强从属于一条消息。
    """

    seq: int
    text: str


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
    # bugfix-410-M2 (#97): sidecar classification of a non-success terminal state,
    # kept SEPARATE from status (which stays running/completed/failed). The badge
    # renders denied→已拒绝 / timed_out→执行超时 / interrupted→已中断. None otherwise.
    reason: str | None = None
    # feat-409: presenter-produced structured detail forwarded from the Gateway.
    # None for historical rows / tools without a presenter — the front-end falls
    # back to ``output`` then.
    detail: dict[str, Any] | None = None
    # feat-425: tool-carried emoji forwarded from the Gateway (决策 1/2). None for
    # historical rows / tools that declare none — the front-end then falls back to
    # its name→emoji table (built-ins keep their icon; DIY/MCP get the generic 🔧).
    emoji: str | None = None
    # feat-434-M1: user-decision verdict forwarded from the Gateway. "user_allow" /
    # "user_deny" only for calls that passed through a user permission card; None for
    # auto-allowed / historical rows — the front-end gate region then stays hidden.
    approval: str | None = None
    # feat-439-M2: per-message 单调递增「过程项」序号，与 ThinkingSegment.seq 同一计数器，
    # 由 IM 在持久化边界按真实到达序赋予（首次 upsert 分配、后续完成保留）。渲染端按 seq
    # 把工具与思考 merge 成一条过程时间线。None = 旧持久化行（无思考时按列表序渲染）。
    seq: int | None = None

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
    ``total`` (M17/R8-3) is the per-turn prompt+completion sum surfaced by the
    chip so users see actual token consumption, not just the completion size.
    """

    output: int
    context_used: int
    context_window: int
    total: int = 0
    # feat-439-M1: 整轮缓存命中率(spec Q1=B)。cache_read_tokens=命中缓存读取的 input 累计
    # (分子)，cache_total_input_tokens=本轮总 input 累计(分母)。命中率 = 前/后。默认 0 →
    # 旧持久化行 / 不带缓存的 provider 天然兼容，渲染端按「缓存命中 0 (0%)」空态显示。
    cache_read_tokens: int = 0
    cache_total_input_tokens: int = 0


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
    # feat-439-M2: 整轮多段思考（过程时间线）。None = 本轮无思考 / 旧持久化行（不留
    # 空壳）。每段带 seq（与 tool_calls 共享的 per-message 单调递增唯一序号）+ text，
    # 与 tool_calls 并存、由渲染端按 seq 升序 merge 成时间线。
    thinking: list[ThinkingSegment] | None = None
    token_usage: TokenUsage | None = None
    # feat-414: 本轮 agent 处理墙钟耗时（毫秒）。turn_start 建行时为 None，
    # on_message_completed 写入（见 event_bridge.py）。用户消息始终为 None。
    elapsed_ms: int | None = None
    # bugfix-367: 同一 message 上的所有 permission ask 按时间顺序保留(list 而非 single
    # dict)。同泡内 ask 不再覆盖前一次的 resolved 记录,UI 可以渲染历史"已允许 / 已拒绝"
    # 小条 + 当前 pending 卡。每个元素 shape:
    # {request_id, tool_name, tool_input, question, options, status, decision?}
    permission_requests: list[dict[str, Any]] = field(default_factory=list)
    # feat-445-M1: 产出该气泡的 kernel assistant 消息的 id（= gateway session JSONL 的 turn
    # uuid）。relay 收尾时落库，fork 据此把被点的气泡对齐回源 session 日志那条消息。None =
    # 用户/系统消息或本特性上线前的旧 agent 气泡（fork 入口对其禁用）。
    kernel_message_id: str | None = None

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
