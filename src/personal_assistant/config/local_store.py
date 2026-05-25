"""Load local Node Gateway configuration from YAML files."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
from typing import Any

import yaml

_DEFAULT_KERNEL_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_KERNEL_ENTRYPOINT = "python -m uvicorn personal_assistant.kernel_app:app"
_DEFAULT_KERNEL_HEALTH_PATH = "/v1/health"
DEFAULT_LOCAL_KERNEL_TOKEN = "nano-local-gateway"
DEFAULT_LOCAL_CONFIG_DIR = Path("~/.nano-assistant").expanduser()
DEFAULT_LOCAL_CONFIG_PATH = DEFAULT_LOCAL_CONFIG_DIR / "config.yaml"
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 15.0
_DEFAULT_SHUTDOWN_GRACE_SECONDS = 5.0
_DEFAULT_POLL_INTERVAL_SECONDS = 0.25
_DEFAULT_HEARTBEAT_TICK_INTERVAL_SECONDS = 30.0
_DEFAULT_WORKSPACE_MEMORY_CONTENT = "# MEMORY\n\nUse this file for stable long-term notes shared across the agent workspace.\n"
_DEFAULT_WORKSPACE_USER_CONTENT = "# USER PROFILE\n\nUse this file for stable notes about the user (preferences, context).\n"
_DEFAULT_WORKSPACE_HEARTBEAT_CONTENT = (
    "# HEARTBEAT\n\n"
    "<!-- Add one schedule (interval/at/cron) and actionable checklist items when heartbeat automation is needed. -->\n"
)

# Memory files (MEMORY.md + USER.md) live under .nanoassistant/memory/ so that
# MemoryStore can read/write them without path gymnastics (feat-349-M3).
# HEARTBEAT.md stays at workspace root (heartbeat scheduler reads it there).
_WORKSPACE_MEMORY_SUBDIR = ".nanoassistant/memory"

DEFAULT_WORKSPACE_MEMORY_FILES: tuple[tuple[str, str], ...] = (
    ("MEMORY.md", _DEFAULT_WORKSPACE_MEMORY_CONTENT),
    ("USER.md", _DEFAULT_WORKSPACE_USER_CONTENT),
)
DEFAULT_WORKSPACE_ROOT_FILES: tuple[tuple[str, str], ...] = (
    ("HEARTBEAT.md", _DEFAULT_WORKSPACE_HEARTBEAT_CONTENT),
)

# Retained for backward-compatibility with any external references; new code
# should use DEFAULT_WORKSPACE_MEMORY_FILES + DEFAULT_WORKSPACE_ROOT_FILES.
DEFAULT_WORKSPACE_FILES: tuple[tuple[str, str], ...] = (
    *DEFAULT_WORKSPACE_MEMORY_FILES,
    *DEFAULT_WORKSPACE_ROOT_FILES,
)


def ensure_workspace_defaults(workspace_root: Path) -> Path:
    """Create one agent workspace directory and seed default workspace files.

    Memory files (``MEMORY.md``, ``USER.md``) are seeded under
    ``<workspace_root>/.nanoassistant/memory/`` so that ``MemoryStore`` can
    read/write them at its canonical path (feat-349-M3).
    ``HEARTBEAT.md`` remains at the workspace root.

    Args:
        workspace_root: Workspace root that should contain stable MEMORY/HEARTBEAT files.

    Returns:
        Resolved workspace path after ensuring the directory and default files exist.

    Side Effects:
        Creates the workspace directory and writes default files when they are missing.
        Existing files are left untouched.
    """

    resolved_root = workspace_root.expanduser().resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)

    # Seed memory files under the .nanoassistant/memory/ subdirectory.
    memory_dir = resolved_root / _WORKSPACE_MEMORY_SUBDIR
    memory_dir.mkdir(parents=True, exist_ok=True)
    for filename, default_content in DEFAULT_WORKSPACE_MEMORY_FILES:
        file_path = memory_dir / filename
        if file_path.exists():
            continue
        file_path.write_text(default_content, encoding="utf-8")

    # Seed workspace-root files (HEARTBEAT.md).
    for filename, default_content in DEFAULT_WORKSPACE_ROOT_FILES:
        file_path = resolved_root / filename
        if file_path.exists():
            continue
        file_path.write_text(default_content, encoding="utf-8")

    return resolved_root




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
        skills: Enabled skill identifiers for this agent.
        tool_allowlist: Allowed tool names restricting the agent's tool access.
        system_prompt: Custom system prompt override for the agent.
        group_reply_policy: Reply policy in group conversations (e.g. "always", "mention_only").
        default_model: Default LLM model identifier for this agent.
        features: Per-agent feature-flag overrides keyed by FEATURE_REGISTRY key.
            Absent keys inherit the registry default_on value at session creation time.
            See feat-379 decision 3 and FEATURE_REGISTRY in prompt_sections/feature_registry.py.
        custom_prompt: Optional user-written text appended as the pa.user_custom segment
            (order=800).  None or empty string means the segment is omitted entirely.
            See feat-379 decision 5/6.
    """

    agent_id: str
    workspace_root: Path
    title: str | None = None
    skills: tuple[str, ...] = ()
    tool_allowlist: tuple[str, ...] = ()
    system_prompt: str | None = None
    group_reply_policy: str | None = None
    default_model: str | None = None
    # feat-379-M2: per-agent feature flags and custom prompt supplement
    features: dict[str, bool] = field(default_factory=dict)
    custom_prompt: str | None = None


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
        refresh_token: Optional long-lived refresh token for automatic access-token renewal.
            When present, the gateway uses it to obtain a fresh access token on each reconnect
            instead of relying on the fixed ``token`` value (which expires after 15 minutes).
        username: Optional IM account username used as credential fallback when the
            refresh token itself has expired and the gateway must perform a full login.
        password: Optional IM account password paired with ``username`` for credential fallback.
    """

    url: str
    token: str | None = None
    refresh_token: str | None = None
    username: str | None = None
    password: str | None = None


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


def default_local_config_path() -> Path:
    """Return the canonical Gateway config path under the user home directory."""

    return Path("~/.nano-assistant/config.yaml").expanduser().resolve()


def save_local_config(config: LocalConfig, config_path: str | Path) -> None:
    """Serialize a LocalConfig back to YAML and write to disk.

    Args:
        config: Typed configuration to serialize.
        config_path: Destination file path. Parent directories must exist.

    Side Effects:
        Writes one UTF-8 YAML file to local disk, overwriting any existing file.
    """
    data: dict[str, Any] = {}

    # Node
    node_dict: dict[str, Any] = {"node_id": config.node.node_id}
    if config.node.user_id is not None:
        node_dict["user_id"] = config.node.user_id
    data["node"] = node_dict

    # Agents
    agents_list: list[dict[str, Any]] = []
    for agent in config.agents:
        agent_dict: dict[str, Any] = {
            "agent_id": agent.agent_id,
            "workspace_root": str(agent.workspace_root),
        }
        if agent.title is not None:
            agent_dict["title"] = agent.title
        if agent.skills:
            agent_dict["skills"] = list(agent.skills)
        if agent.tool_allowlist:
            agent_dict["tool_allowlist"] = list(agent.tool_allowlist)
        if agent.system_prompt is not None:
            agent_dict["system_prompt"] = agent.system_prompt
        if agent.group_reply_policy is not None:
            agent_dict["group_reply_policy"] = agent.group_reply_policy
        if agent.default_model is not None:
            agent_dict["default_model"] = agent.default_model
        # feat-379-M2: only emit when non-empty to keep config.yaml readable
        if agent.features:
            agent_dict["features"] = dict(agent.features)
        if agent.custom_prompt is not None:
            agent_dict["custom_prompt"] = agent.custom_prompt
        agents_list.append(agent_dict)
    data["agents"] = agents_list

    # Channels
    if config.channels:
        channels_list: list[dict[str, Any]] = []
        for ch in config.channels:
            ch_dict: dict[str, Any] = {"name": ch.name}
            if not ch.enabled:
                ch_dict["enabled"] = ch.enabled
            if ch.settings:
                ch_dict["settings"] = dict(ch.settings)
            channels_list.append(ch_dict)
        data["channels"] = channels_list

    # Kernel — only emit non-default values to keep output concise
    kernel_dict: dict[str, Any] = {}
    if config.kernel.base_url != _DEFAULT_KERNEL_BASE_URL:
        kernel_dict["base_url"] = config.kernel.base_url
    if config.kernel.command != _DEFAULT_KERNEL_ENTRYPOINT:
        kernel_dict["command"] = config.kernel.command
    if config.kernel.health_path != _DEFAULT_KERNEL_HEALTH_PATH:
        kernel_dict["health_path"] = config.kernel.health_path
    if config.kernel.request_id is not None:
        kernel_dict["request_id"] = config.kernel.request_id
    if config.kernel.timeout_seconds != 10.0:
        kernel_dict["timeout_seconds"] = config.kernel.timeout_seconds
    if config.kernel.startup_timeout_seconds != _DEFAULT_STARTUP_TIMEOUT_SECONDS:
        kernel_dict["startup_timeout_seconds"] = config.kernel.startup_timeout_seconds
    if config.kernel.shutdown_grace_seconds != _DEFAULT_SHUTDOWN_GRACE_SECONDS:
        kernel_dict["shutdown_grace_seconds"] = config.kernel.shutdown_grace_seconds
    if config.kernel.health_poll_interval_seconds != _DEFAULT_POLL_INTERVAL_SECONDS:
        kernel_dict["health_poll_interval_seconds"] = config.kernel.health_poll_interval_seconds
    if kernel_dict:
        data["kernel"] = kernel_dict

    # Heartbeat — only emit non-default
    if config.heartbeat.tick_interval_seconds != _DEFAULT_HEARTBEAT_TICK_INTERVAL_SECONDS:
        data["heartbeat"] = {"tick_interval_seconds": config.heartbeat.tick_interval_seconds}

    # IM service
    if config.im_service is not None:
        im_dict: dict[str, Any] = {"url": config.im_service.url}
        if config.im_service.token is not None:
            im_dict["token"] = config.im_service.token
        if config.im_service.refresh_token is not None:
            im_dict["refresh_token"] = config.im_service.refresh_token
        if config.im_service.username is not None:
            im_dict["username"] = config.im_service.username
        if config.im_service.password is not None:
            im_dict["password"] = config.im_service.password
        data["im_service"] = im_dict

    dest = Path(config_path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")


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
        else:
            workspace_root = Path(workspace_text).expanduser()
            if not workspace_root.exists():
                raise ValueError(f"workspace_root does not exist: {workspace_root.resolve()}")
        workspace_root = ensure_workspace_defaults(workspace_root)
        title = _optional_string(item.get("title"), field_name=f"agents[{index}].title")
        skills = _parse_string_list(item.get("skills"), field_name=f"agents[{index}].skills")
        tool_allowlist = _parse_string_list(item.get("tool_allowlist"), field_name=f"agents[{index}].tool_allowlist")
        system_prompt = _optional_string(item.get("system_prompt"), field_name=f"agents[{index}].system_prompt")
        group_reply_policy = _optional_string(item.get("group_reply_policy"), field_name=f"agents[{index}].group_reply_policy")
        default_model = _optional_string(item.get("default_model"), field_name=f"agents[{index}].default_model")
        features = _parse_features(item.get("features"), field_name=f"agents[{index}].features")
        custom_prompt = _optional_string(item.get("custom_prompt"), field_name=f"agents[{index}].custom_prompt")
        agents.append(
            AgentWorkspaceConfig(
                agent_id=agent_id,
                workspace_root=workspace_root,
                title=title,
                skills=skills,
                tool_allowlist=tool_allowlist,
                system_prompt=system_prompt,
                group_reply_policy=group_reply_policy,
                default_model=default_model,
                features=features,
                custom_prompt=custom_prompt,
            )
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
    refresh_token = _optional_string(payload.get("refresh_token"), field_name="im_service.refresh_token")
    username = _optional_string(payload.get("username"), field_name="im_service.username")
    password = _optional_string(payload.get("password"), field_name="im_service.password")
    return IMServiceConfig(url=url, token=token, refresh_token=refresh_token, username=username, password=password)


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


def _parse_string_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    """Parse an optional YAML list of strings into a tuple.

    Args:
        value: Raw YAML value (None, list, or invalid).
        field_name: Diagnostic label for error messages.

    Returns:
        Tuple of stripped non-empty strings, or empty tuple when value is None.

    Raises:
        ValueError: When value is not a list or contains non-string elements.
    """
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[str] = []
    for i, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"{field_name}[{i}] must be a non-empty string")
        result.append(entry.strip())
    return tuple(result)


def _parse_features(value: Any, *, field_name: str) -> dict[str, bool]:
    """Parse an optional YAML feature-flag mapping into a dict[str, bool].

    Only bool values are accepted — YAML ``true``/``false`` map cleanly.  Any
    non-bool value causes a hard error so misconfigured flags fail loudly
    (feat-379 decision 3: no silent fallback for user-written config).

    Args:
        value: Raw YAML value (None, dict, or invalid).
        field_name: Diagnostic label for error messages.

    Returns:
        Dict of feature key → bool, or empty dict when value is None.

    Raises:
        ValueError: When value is not a mapping or contains non-bool values.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    result: dict[str, bool] = {}
    for k, v in value.items():
        if not isinstance(k, str) or not k.strip():
            raise ValueError(f"{field_name}: key must be a non-empty string, got {k!r}")
        if not isinstance(v, bool):
            raise ValueError(f"{field_name}.{k} must be a bool (true/false), got {v!r}")
        result[k.strip()] = v
    return result
