"""Load local Node Gateway configuration from YAML files."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
from typing import Any

import yaml

_DEFAULT_KERNEL_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_KERNEL_ENTRYPOINT = "python -m agent.platform.http_api.app"
_DEFAULT_KERNEL_HEALTH_PATH = "/v1/health"
DEFAULT_LOCAL_KERNEL_TOKEN = "nano-local-gateway"
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 15.0
_DEFAULT_SHUTDOWN_GRACE_SECONDS = 5.0
_DEFAULT_POLL_INTERVAL_SECONDS = 0.25
_DEFAULT_HEARTBEAT_TICK_INTERVAL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class NodeConfig:
    """Describe the current gateway node identity.

    Args:
        node_id: Stable node identifier reported to upstream services.
        user_id: Optional owning user identifier when the node is bound upstream.
    """

    node_id: str
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentWorkspaceConfig:
    """Describe one managed agent workspace binding.

    Args:
        agent_id: Stable agent identifier used by gateway routing.
        workspace_root: Existing workspace root bound to sessions created for the agent.
        title: Optional operator-facing label.
    """

    agent_id: str
    workspace_root: Path
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Describe one configured channel adapter.

    Args:
        name: Channel adapter name used by the registry.
        enabled: Whether the channel should start during bootstrap.
        settings: Adapter-specific opaque configuration payload.
    """

    name: str
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IMServiceConfig:
    """Describe optional upstream IM service connectivity.

    Args:
        url: WebSocket or HTTPS base URL for the IM service.
        token: Optional bearer token used when connecting upstream.
    """

    url: str
    token: str | None = None


@dataclass(frozen=True, slots=True)
class KernelConfig:
    """Describe how the gateway reaches and manages the local agent kernel.

    Args:
        base_url: Base HTTP URL exposed by the local kernel process.
        token: Optional bearer token required by the kernel HTTP API.
        request_id: Optional fixed request id prefix for probes.
        timeout_seconds: Per-request HTTP timeout.
        command: Child-process command used to spawn the kernel in managed mode.
        health_path: Relative health endpoint used for readiness polling.
        startup_timeout_seconds: Maximum readiness wait time after spawning the child.
        shutdown_grace_seconds: Grace period between terminate and forced kill.
        health_poll_interval_seconds: Delay between readiness probe attempts.
    """

    base_url: str = _DEFAULT_KERNEL_BASE_URL
    token: str | None = None
    request_id: str | None = None
    timeout_seconds: float = 10.0
    command: str = _DEFAULT_KERNEL_ENTRYPOINT
    health_path: str = _DEFAULT_KERNEL_HEALTH_PATH
    startup_timeout_seconds: float = _DEFAULT_STARTUP_TIMEOUT_SECONDS
    shutdown_grace_seconds: float = _DEFAULT_SHUTDOWN_GRACE_SECONDS
    health_poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS


@dataclass(frozen=True, slots=True)
class HeartbeatConfig:
    """Describe local heartbeat scheduler lifecycle settings.

    Args:
        tick_interval_seconds: Delay between scheduler tick passes while the gateway is running.
    """

    tick_interval_seconds: float = _DEFAULT_HEARTBEAT_TICK_INTERVAL_SECONDS


@dataclass(frozen=True, slots=True)
class LocalConfig:
    """Represent the full local gateway configuration document.

    Args:
        node: Node identity and ownership metadata.
        agents: Agent workspace definitions managed by this gateway.
        channels: Configured inbound/outbound channel adapters.
        kernel: Local kernel process and HTTP connectivity settings.
        heartbeat: Local heartbeat scheduler polling settings.
        im_service: Optional upstream IM service configuration.
        source_path: Absolute file path used to load the config.
    """

    node: NodeConfig
    agents: tuple[AgentWorkspaceConfig, ...]
    channels: tuple[ChannelConfig, ...]
    kernel: KernelConfig
    heartbeat: HeartbeatConfig
    im_service: IMServiceConfig | None
    source_path: Path


def load_local_config(config_path: str | Path) -> LocalConfig:
    """Load one YAML config file into typed gateway settings.

    Args:
        config_path: YAML file path. Relative paths are resolved against the current
            process working directory.

    Returns:
        Parsed immutable configuration ready for gateway bootstrap.

    Raises:
        FileNotFoundError: When the config file does not exist.
        ValueError: When the YAML payload is malformed or required semantics are missing.

    Side Effects:
        Reads one UTF-8 YAML file from local disk.
    """

    source_path = Path(config_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"config file does not exist: {source_path}")
    raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")

    node = _parse_node_config(raw.get("node"))
    agents = _parse_agents(raw.get("agents"))
    channels = _parse_channels(raw.get("channels"))
    kernel = _parse_kernel(raw.get("kernel"))
    heartbeat = _parse_heartbeat(raw.get("heartbeat"))
    im_service = _parse_im_service(raw.get("im_service"))
    return LocalConfig(
        node=node,
        agents=agents,
        channels=channels,
        kernel=kernel,
        heartbeat=heartbeat,
        im_service=im_service,
        source_path=source_path,
    )


def resolve_kernel_token(token: str | None) -> str:
    """Return the effective bearer token used for local kernel HTTP calls.

    Args:
        token: Explicit token configured in `node-config.yaml`.

    Returns:
        Explicit token when provided, otherwise the shared process token from
        `NANO_MULTIAGENT_API_TOKEN`, and finally a stable local default that
        satisfies the kernel's bearer-header requirement for loopback startup.
    """

    if isinstance(token, str) and token.strip():
        return token.strip()
    env_token = os.getenv("NANO_MULTIAGENT_API_TOKEN", "").strip()
    if env_token:
        return env_token
    return DEFAULT_LOCAL_KERNEL_TOKEN


def _parse_node_config(payload: Any) -> NodeConfig:
    if not isinstance(payload, dict):
        raise ValueError("node must be a mapping")
    node_id = _require_non_empty_string(payload.get("node_id"), field_name="node.node_id")
    user_id = _optional_string(payload.get("user_id"), field_name="node.user_id")
    return NodeConfig(node_id=node_id, user_id=user_id)


def _parse_agents(payload: Any) -> tuple[AgentWorkspaceConfig, ...]:
    if not isinstance(payload, list):
        raise ValueError("agents must be a list")
    if not payload:
        raise ValueError("agents must contain at least one entry")

    agents: list[AgentWorkspaceConfig] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"agents[{index}] must be a mapping")
        agent_id = _require_non_empty_string(item.get("agent_id"), field_name=f"agents[{index}].agent_id")
        workspace_text = _optional_string(item.get("workspace_root"), field_name=f"agents[{index}].workspace_root")
        if workspace_text is None:
            workspace_root = Path("~/nano-assistant/workspace").expanduser() / agent_id
            # Default workspaces are gateway-managed local state, so config loading
            # creates them on demand instead of forcing operators to pre-seed paths.
            workspace_root.mkdir(parents=True, exist_ok=True)
        else:
            workspace_root = Path(workspace_text).expanduser()
            if not workspace_root.exists():
                raise ValueError(f"workspace_root does not exist: {workspace_root.resolve()}")
        workspace_root = workspace_root.resolve()
        title = _optional_string(item.get("title"), field_name=f"agents[{index}].title")
        agents.append(
            AgentWorkspaceConfig(agent_id=agent_id, workspace_root=workspace_root, title=title)
        )
    return tuple(agents)


def _parse_channels(payload: Any) -> tuple[ChannelConfig, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ValueError("channels must be a list")

    channels: list[ChannelConfig] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"channels[{index}] must be a mapping")
        name = _require_non_empty_string(item.get("name"), field_name=f"channels[{index}].name")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"channels[{index}].enabled must be a bool")
        settings = item.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError(f"channels[{index}].settings must be a mapping")
        channels.append(ChannelConfig(name=name, enabled=enabled, settings=dict(settings)))
    return tuple(channels)


def _parse_kernel(payload: Any) -> KernelConfig:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("kernel must be a mapping")
    command = _optional_string(payload.get("command"), field_name="kernel.command") or _DEFAULT_KERNEL_ENTRYPOINT
    explicit_base_url = _optional_string(payload.get("base_url"), field_name="kernel.base_url")
    base_url = explicit_base_url or _derive_kernel_base_url(command) or _DEFAULT_KERNEL_BASE_URL
    token = resolve_kernel_token(_optional_string(payload.get("token"), field_name="kernel.token"))
    request_id = _optional_string(payload.get("request_id"), field_name="kernel.request_id")
    health_path = _optional_string(payload.get("health_path"), field_name="kernel.health_path") or _DEFAULT_KERNEL_HEALTH_PATH
    timeout_seconds = _positive_number(payload.get("timeout_seconds", 10.0), field_name="kernel.timeout_seconds")
    startup_timeout_seconds = _positive_number(
        payload.get("startup_timeout_seconds", _DEFAULT_STARTUP_TIMEOUT_SECONDS),
        field_name="kernel.startup_timeout_seconds",
    )
    shutdown_grace_seconds = _positive_number(
        payload.get("shutdown_grace_seconds", _DEFAULT_SHUTDOWN_GRACE_SECONDS),
        field_name="kernel.shutdown_grace_seconds",
    )
    health_poll_interval_seconds = _positive_number(
        payload.get("health_poll_interval_seconds", _DEFAULT_POLL_INTERVAL_SECONDS),
        field_name="kernel.health_poll_interval_seconds",
    )
    return KernelConfig(
        base_url=base_url,
        token=token,
        request_id=request_id,
        timeout_seconds=timeout_seconds,
        command=command,
        health_path=health_path,
        startup_timeout_seconds=startup_timeout_seconds,
        shutdown_grace_seconds=shutdown_grace_seconds,
        health_poll_interval_seconds=health_poll_interval_seconds,
    )


def _parse_heartbeat(payload: Any) -> HeartbeatConfig:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("heartbeat must be a mapping")
    tick_interval_seconds = _positive_number(
        payload.get("tick_interval_seconds", _DEFAULT_HEARTBEAT_TICK_INTERVAL_SECONDS),
        field_name="heartbeat.tick_interval_seconds",
    )
    return HeartbeatConfig(tick_interval_seconds=tick_interval_seconds)


def _parse_im_service(payload: Any) -> IMServiceConfig | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("im_service must be a mapping")
    url = _require_non_empty_string(payload.get("url"), field_name="im_service.url")
    token = _optional_string(payload.get("token"), field_name="im_service.token")
    return IMServiceConfig(url=url, token=token)


def _derive_kernel_base_url(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    host: str | None = None
    port: str | None = None
    for index, token in enumerate(tokens):
        if token == "--host" and index + 1 < len(tokens):
            host = tokens[index + 1].strip()
            continue
        if token == "--port" and index + 1 < len(tokens):
            port = tokens[index + 1].strip()
            continue
        if token.startswith("--host="):
            host = token.partition("=")[2].strip()
            continue
        if token.startswith("--port="):
            port = token.partition("=")[2].strip()
    if not host or not port:
        return None
    if host == "0.0.0.0":
        host = "127.0.0.1"
    if host not in {"127.0.0.1", "localhost"}:
        return None
    if not port.isdigit():
        return None
    return f"http://{host}:{port}"


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = value.strip()
    return stripped or None


def _positive_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a positive number")
    resolved = float(value)
    if resolved <= 0:
        raise ValueError(f"{field_name} must be a positive number")
    return resolved
