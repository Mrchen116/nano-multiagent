"""Upstream reporter that emits gateway -> IM websocket protocol frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping

from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.reporter.capability_projection import (
    project_features,
    project_tools,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from agent.sdk import Kernel


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
    # bugfix-429 R5: each entry is ``{"name", "provider"}`` so the IM dropdown can
    # label a model's registered format (was a bare model-id tuple).
    models: tuple[dict[str, str], ...] = ()
    skills: tuple[dict[str, str], ...] = ()
    # feat-394 M9 R5: tools changed from bare str tuple to rich dict tuple carrying
    # {name, description, default_on}.  IM frontend uses default_on to render tool
    # pills as "selected by default" when the agent's tool_allowlist is empty.
    tools: tuple[dict[str, object], ...] = ()
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


def _models_from_kernel(kernel: "Kernel") -> tuple[dict[str, str], ...]:
    """Project ``kernel.list_models()`` into deduped ``{name, provider}`` entries.

    bugfix-429 R5: the kernel's ``ModelInfo`` already carries ``provider``; keep it
    through to the IM payload so the agent-config dropdown can label each model's
    registered format (anthropic / openai_compat). Dedupe by name, preserve order.
    """
    seen: set[str] = set()
    entries: list[dict[str, str]] = []
    for m in kernel.list_models():
        name = m.name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        entries.append({"name": name, "provider": getattr(m, "provider", "") or ""})
    return tuple(entries)


def _platform_default_model_from_kernel(kernel: "Kernel") -> str | None:
    """Return the catalog default model id (the ``is_default`` entry), or None."""
    for m in kernel.list_models():
        if getattr(m, "is_default", False):
            return m.name
    return None


def _tools_from_kernel(kernel: "Kernel") -> tuple[dict[str, object], ...]:
    """Project ``kernel.list_tools()`` into IM tool pills with ``default_on``.

    The kernel reports name/description (neutral fact); the Gateway projection
    (``project_tools``) adds the PA default/optional ``default_on`` split.
    """
    tool_infos = tuple((t.name, t.description) for t in kernel.list_tools())
    return project_tools(tool_infos)


def _skills_from_kernel(
    kernel: "Kernel", workspace_root: str | None
) -> list[dict[str, str | None]]:
    """Project ``kernel.list_skills(workspace_root)`` into IM skill entries.

    Per-workspace skill discovery is the kernel's job (决策 4); the reporter no
    longer rebuilds the on-disk layout. ``workspace_root=None`` resolves to the
    kernel's repo_root (node level). ``location`` is forwarded so the IM slash
    picker can distinguish same-named skills at different paths (feat-430).
    """
    from pathlib import Path  # noqa: PLC0415

    ws = Path(workspace_root).expanduser().resolve() if workspace_root else None
    return [
        {
            "name": skill.name,
            "description": skill.description or "",
            "location": skill.location,
        }
        for skill in kernel.list_skills(ws)
    ]


def build_runtime_capabilities(kernel: "Kernel") -> ReporterCapabilities:
    """Build node-level selectable runtime items projected from ``kernel.list_*``.

    Args:
        kernel: In-process Kernel whose neutral ``list_*`` queries (决策 4) supply
            models/tools/skills; product semantics (tool default_on split, skill
            workspace) are projected here.
    """

    return ReporterCapabilities(
        models=_models_from_kernel(kernel),
        skills=tuple(_skills_from_kernel(kernel, workspace_root=None)),
        tools=_tools_from_kernel(kernel),
        platform_default_model=_platform_default_model_from_kernel(kernel),
        # feat-379-M5 (ISSUE-4): do NOT expose the raw RUNTIME_FILL template; the
        # sections assembler owns prompt construction at runtime.  Consumers (IM
        # agent-create page) that relied on this field for a system_prompt prefill
        # are migrated to custom_prompt (R5) — empty string is the safe neutral value.
        default_system_prompt="",
    )


def build_node_capabilities_payload(kernel: "Kernel") -> dict[str, object]:
    """Build node-level capability payload with the Gateway feature projection.

    The agent-create page queries GET /im/v1/nodes/{id}/capabilities (no per-agent
    context yet), so the feature projection has every entry ``available=True`` (no
    tool_allowlist exists at this point to constrain them). The i18n text and the
    heartbeat/cron product toggles are Gateway-owned (决策 4 — the kernel stays
    product-neutral).

    Returns:
        Capability dict suitable for node.capabilities response frames.
    """
    base = build_runtime_capabilities(kernel).as_payload()
    base["features"] = project_features(tool_allowlist=None)
    return base


def build_agent_capabilities_payload(
    kernel: "Kernel",
    *,
    workspace_root: str,
    tool_allowlist: tuple[str, ...] = (),
) -> dict[str, object]:
    """按 Agent 工作区根路径解析可选技能（含描述），供 agent.capabilities.resolve 响应。

    Args:
        kernel: In-process Kernel; ``list_skills(workspace_root)`` does per-workspace
            skill discovery (决策 4 — replaces the reporter's hand-built disk layout).
        workspace_root: Agent workspace root path for per-workspace skill discovery.
        tool_allowlist: Tool names enabled for this agent.  Used to determine
            whether feature-gated tools are available (feat-379 decision 7).
    """
    base = build_runtime_capabilities(kernel).as_payload()
    base["skills"] = _skills_from_kernel(kernel, workspace_root=workspace_root)
    base["features"] = project_features(tool_allowlist=tool_allowlist)
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
            # bugfix-404-M2: carry per-agent workspace seeds so IM can persist
            # the correct path on first registration instead of synthesising a
            # managed default.  IM uses "first seen wins" semantics — existing
            # profiles are not overwritten (feat-379-M6 pattern, decision 3).
            "agent_workspaces": {
                agent.agent_id: str(agent.workspace_root)
                for agent in self._agents
                if agent.workspace_root is not None
            },
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
