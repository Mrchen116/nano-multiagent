"""Upstream reporter that emits gateway -> IM websocket protocol frames."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig


SendFrame = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class ReporterCapabilities:
    """Describe upstream feature flags declared during node registration.

    Args:
        relay: Whether the node accepts Web IM relay traffic.
        send_message: Whether the node supports agent-to-agent send_message delivery.
        config_sync: Whether the node can react to config.sync notifications.
    """

    relay: bool = True
    send_message: bool = True
    config_sync: bool = True

    def as_payload(self) -> dict[str, object]:
        """Return a JSON-serializable capability declaration."""

        return {
            "relay": self.relay,
            "send_message": self.send_message,
            "config_sync": self.config_sync,
        }


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

    def send_register(self) -> dict[str, object]:
        """Send one ``node.register`` frame for the current node."""

        payload: dict[str, object] = {
            "node_id": self._node.node_id,
            "node_name": self._node_name,
            "version": self._version,
            "agents": [agent.agent_id for agent in self._agents],
            "capabilities": self._capabilities.as_payload(),
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
