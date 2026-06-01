"""Upstream reporter that emits gateway -> IM websocket protocol frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

# refactor-387-M4: import from agent.sdk (public surface) instead of agent.core internals
from agent.sdk import (
    get_default_model,
    get_default_provider,
    list_provider_models,
    list_supported_providers,
    default_skill_search_roots,
    SkillRegistry,
    ConfigResolver,
    PERSONAL_ASSISTANT_PROFILE,
)
from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig


SendFrame = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class ReporterCapabilities:
    """Describe upstream feature flags and selectable runtime items.

    Args:
        relay: Whether the node accepts Web IM relay traffic.
        send_message: Whether the node supports agent-to-agent send_message delivery.
        config_sync: Whether the node can react to config.sync notifications.
        models: Runtime model ids currently selectable on this node.
        skills: 可选技能列表，每项为 ``{"name", "description"}``（description 来自 SKILL.md 元数据）。
        tools: Runtime tool ids currently selectable on this node.
    """

    relay: bool = True
    send_message: bool = True
    config_sync: bool = True
    models: tuple[str, ...] = ()
    skills: tuple[dict[str, str], ...] = ()
    tools: tuple[str, ...] = ()
    platform_default_model: str | None = None
    default_system_prompt: str = ""

    def as_payload(self) -> dict[str, object]:
        """Return a JSON-serializable capability declaration."""

        return {
            "relay": self.relay,
            "send_message": self.send_message,
            "config_sync": self.config_sync,
            "models": list(self.models),
            "skills": list(self.skills),
            "tools": list(self.tools),
            "platform_default_model": self.platform_default_model,
            "default_system_prompt": self.default_system_prompt,
        }

    def register_flags_payload(self) -> dict[str, object]:
        """仅用于 node.register：不包含 models/skills/tools 等大字段。"""
        return {
            "relay": self.relay,
            "send_message": self.send_message,
            "config_sync": self.config_sync,
        }


def _dedupe_preserve_order(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _product_root() -> Path:
    return (
        _repo_root()
        / "src"
        / "agent"
        / "products"
        / PERSONAL_ASSISTANT_PROFILE.product_id
    )


def _build_skill_capability_entries() -> tuple[dict[str, str], ...]:
    """从 SKILL.md 解析 name/description，供 IM 设置页展示。"""
    config_resolver = ConfigResolver(
        profile=PERSONAL_ASSISTANT_PROFILE, workspace_root=None
    )
    registry = SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=_repo_root(),
            config_resolver=config_resolver,
            product_skill_root=_product_root() / "skills",
        )
    )
    return tuple(
        {"name": skill.name, "description": skill.description or ""}
        for skill in registry.list_skills()
    )


def _build_tool_names() -> tuple[str, ...]:
    # feat-379-M9 (決策 13): advertise-phase only needs the declared tool names;
    # build_tool_registry(runtime=None) omits memory/skill_manage because those tools
    # require bootstrap path injection before they appear in list_specs().  Taking names
    # directly from the profile guarantees the full declared surface is advertised,
    # regardless of whether a live runtime is present.
    allowed_ids = [
        *PERSONAL_ASSISTANT_PROFILE.default_tool_ids,
        *PERSONAL_ASSISTANT_PROFILE.optional_tool_ids,
    ]
    return _dedupe_preserve_order(allowed_ids)


def _build_model_names() -> tuple[str, ...]:
    return _dedupe_preserve_order(
        [
            metadata.model
            for provider in list_supported_providers()
            for metadata in list_provider_models(provider)
        ]
    )


def build_runtime_capabilities() -> ReporterCapabilities:
    """Build node-level selectable runtime items from the Gateway runtime surface."""

    return ReporterCapabilities(
        models=_build_model_names(),
        skills=_build_skill_capability_entries(),
        tools=_build_tool_names(),
        platform_default_model=get_default_model(get_default_provider()),
        # feat-379-M5 (ISSUE-4): do NOT expose the raw RUNTIME_FILL template; the
        # sections assembler owns prompt construction at runtime.  Consumers (IM
        # agent-create page) that relied on this field for a system_prompt prefill
        # are migrated to custom_prompt (R5) — empty string is the safe neutral value.
        default_system_prompt="",
    )


def build_node_capabilities_payload() -> dict[str, object]:
    """Build node-level capability payload including FEATURE_REGISTRY projection.

    feat-379-M7 (ISSUE-1): node.capabilities.resolve was returning
    build_runtime_capabilities().as_payload() which has no 'features' key.
    The agent-create page queries GET /im/v1/nodes/{id}/capabilities (no per-agent
    context yet), so we inject a node-level features projection where all features
    are available=True (no tool_allowlist exists at this point to constrain them).

    Returns:
        Capability dict suitable for node.capabilities response frames.
    """
    from agent.sdk import FEATURE_REGISTRY  # noqa: PLC0415  # refactor-387-M4

    base = build_runtime_capabilities().as_payload()
    # Node-level: no per-agent tool_allowlist → every feature is available.
    # The agent-create page uses default_on to pre-fill toggles; available=True
    # lets all toggles render as enabled (not greyed out).
    node_features_projection: list[dict[str, object]] = [
        {
            "key": key,
            "label_i18n": entry["label_i18n"],
            "help_i18n": entry["help_i18n"],
            "default_on": entry["default_on"],
            "available": True,
            "requires_tool": entry["requires_tool"],
        }
        for key, entry in FEATURE_REGISTRY.items()
    ]
    base["features"] = node_features_projection
    return base


def build_agent_capabilities_payload(
    *,
    workspace_root: str,
    tool_allowlist: tuple[str, ...] = (),
) -> dict[str, object]:
    """按 Agent 工作区根路径解析可选技能（含描述），供 agent.capabilities.resolve 响应。

    Args:
        workspace_root: Agent workspace root path for per-workspace skill discovery.
        tool_allowlist: Tool names enabled for this agent.  Used to determine
            whether feature-gated tools are available (feat-379 decision 7).
    """
    from agent.sdk import FEATURE_REGISTRY  # noqa: PLC0415  # refactor-387-M4

    root = Path(workspace_root).expanduser().resolve()
    config_resolver = ConfigResolver(
        profile=PERSONAL_ASSISTANT_PROFILE, workspace_root=root
    )
    registry = SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=root,
            config_resolver=config_resolver,
            product_skill_root=_product_root() / "skills",
        )
    )
    skills: list[dict[str, str]] = [
        {"name": skill.name, "description": skill.description or ""}
        for skill in registry.list_skills()
    ]
    base = build_runtime_capabilities().as_payload()
    base["skills"] = skills

    # feat-379-M2: build feature toggles projection for the IM frontend
    # (decision 7: registry is the single event source; frontend renders dynamically)
    allowlist_set = set(tool_allowlist)
    features_projection: list[dict[str, object]] = [
        {
            "key": key,
            "label_i18n": entry["label_i18n"],
            "help_i18n": entry["help_i18n"],
            "default_on": entry["default_on"],
            # available=False means the required tool is not in the agent's allowlist
            "available": entry["requires_tool"] is None
            or entry["requires_tool"] in allowlist_set,
            "requires_tool": entry["requires_tool"],
        }
        for key, entry in FEATURE_REGISTRY.items()
    ]
    base["features"] = features_projection
    return base


class UpstreamReporter:
    """Build and send gateway upstream protocol frames.

    Args:
        node: Local node identity reported upstream.
        agents: Managed agents hosted on this gateway.
        send_frame: Transport callback that sends one ``type`` + ``payload`` frame.
        capabilities: Optional capability flags advertised on registration.
        node_name: Optional operator-facing node name.
        version: Optional gateway version string.
    """

    def __init__(
        self,
        *,
        node: NodeConfig,
        agents: tuple[AgentWorkspaceConfig, ...],
        send_frame: SendFrame,
        capabilities: ReporterCapabilities | None = None,
        node_name: str | None = None,
        version: str | None = None,
    ) -> None:
        self._node = node
        self._agents = agents
        self._send_frame = send_frame
        self._capabilities = capabilities or ReporterCapabilities()
        self._node_name = (node_name or node.node_id).strip()
        self._version = (version or "").strip()

    def replace_agents(self, agents: tuple[AgentWorkspaceConfig, ...]) -> None:
        """在运行时在 IM 上新建 Agent 后，刷新登记到本机的 agent 列表（供 heartbeat 等使用）。"""
        self._agents = agents

    @property
    def node_id(self) -> str:
        """Return the stable node identifier used for upstream IM frames."""
        return self._node.node_id

    def send_register(self) -> dict[str, object]:
        """Send one ``node.register`` frame for the current node."""

        payload: dict[str, object] = {
            "node_id": self._node.node_id,
            "node_name": self._node_name,
            "version": self._version,
            "agents": [agent.agent_id for agent in self._agents],
            "capabilities": self._capabilities.register_flags_payload(),
        }
        if self._node.user_id is not None:
            payload["user_id"] = self._node.user_id
        self._send_frame("node.register", payload)
        return payload

    def send_heartbeat(
        self,
        *,
        status: str,
        last_error: str | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Send one ``node.heartbeat`` frame.

        Args:
            status: Node health summary such as ``online`` or ``degraded``.
            last_error: Optional latest error summary surfaced to IM.
            extra: Optional additional scalar fields such as running counts.
        """

        payload: dict[str, object] = {
            "node_id": self._node.node_id,
            "status": status,
            "agent_count": len(self._agents),
        }
        if self._version:
            payload["version"] = self._version
        if last_error is not None and last_error.strip():
            payload["last_error"] = last_error.strip()
        if extra is not None:
            payload.update(dict(extra))
        self._send_frame("node.heartbeat", payload)
        return payload

    def send_report(
        self,
        *,
        run_id: str,
        status: str,
        agent_id: str | None = None,
        session_key: str | None = None,
        conversation_id: str | None = None,
        message_id: str | None = None,
        summary: str | None = None,
        guidance: str | None = None,
        detail: Mapping[str, Any] | None = None,
        usage: Mapping[str, int] | None = None,
    ) -> dict[str, object]:
        """Send one ``node.report`` execution report frame."""

        payload: dict[str, object] = {
            "node_id": self._node.node_id,
            "run_id": run_id,
            "status": status,
        }
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if session_key is not None:
            payload["session_key"] = session_key
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        if message_id is not None:
            payload["message_id"] = message_id
        if summary is not None:
            payload["summary"] = summary
        if guidance is not None:
            payload["guidance"] = guidance
        if detail is not None:
            payload["detail"] = dict(detail)
        if usage is not None:
            payload["usage"] = dict(usage)
        self._send_frame("node.report", payload)
        return payload

    def send_delivery_receipt(
        self,
        *,
        relay_task_id: str,
        delivery_status: str,
        detail: str | None = None,
        target: str | None = None,
    ) -> dict[str, object]:
        """Send one ``node.delivery_receipt`` frame for a relay task."""

        payload: dict[str, object] = {
            "node_id": self._node.node_id,
            "relay_task_id": relay_task_id,
            "delivery_status": delivery_status,
        }
        if detail is not None:
            payload["detail"] = detail
        if target is not None:
            payload["target"] = target
        self._send_frame("node.delivery_receipt", payload)
        return payload
