"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

_log = logging.getLogger("personal_assistant.main")

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)

# refactor-387-M4: import from agent.sdk (public surface) instead of agent.core internals.
from agent.sdk import init_model_registry
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
    default_local_config_path,
    ensure_workspace_defaults,
    load_local_config,
    save_local_config,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_pipeline import (
    InboundPipeline,
    RelayLifecycleUpdate,
)
from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    SessionBindingStore,
)
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_agent_capabilities_payload,
    build_runtime_capabilities,
)
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)
from personal_assistant.scheduler.cron_scheduler import (
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_execution_service import CronExecutionService
from personal_assistant.scheduler.gateway_cron_dispatcher import GatewayCronDispatcher
from personal_assistant.auth.im_auth_client import IMAuthClient, IMAuthError
from personal_assistant.ws.im_connection import (
    AgentCreateHandler,
    IMConnectionConfig,
    IMConnectionManager,
    PromptPreviewProvider,
)


ProcessLike = subprocess.Popen[Any]
ProcessFactory = Callable[[str], ProcessLike]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
ReadyWaiter = Callable[[ProcessLike, LocalConfig, float], None]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
AsyncConnect = Callable[[str, Mapping[str, str]], Awaitable[ClientConnection]]
SignalHandlerInstaller = Callable[[], Callable[[], None]]
BootstrapClientFactory = Callable[[str], httpx.Client]
FeedbackSink = Callable[[str, str, str | None], None]


class GatewayStartupError(RuntimeError):
    """Represent one actionable startup failure shown to gateway operators.

    Args:
        summary: Human-readable failure summary.
        next_step: Optional concrete remediation step shown alongside the error.
    """

    def __init__(self, *, summary: str, next_step: str | None = None) -> None:
        cleaned_summary = summary.strip()
        cleaned_next_step = (
            next_step.strip()
            if isinstance(next_step, str) and next_step.strip()
            else None
        )
        super().__init__(cleaned_summary)
        self.summary = cleaned_summary
        self.next_step = cleaned_next_step


def _read_log_last_error(
    log_path: Path, *, offset: int = 0, lines: int = 20
) -> str | None:
    """Return the last non-empty line written after *offset* bytes, or None if unreadable."""
    try:
        with log_path.open("rb") as f:
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="replace")
        tail = [l for l in chunk.splitlines()[-lines:] if l.strip()]
        return tail[-1] if tail else None
    except Exception:  # noqa: BLE001
        return None


def _check_im_reachable(url: str) -> bool:
    """Return True if the IM service HTTP endpoint responds within 1 second."""
    try:
        httpx.get(url, timeout=1.0, trust_env=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def _print_gateway_started(result: "BackgroundLaunchResult") -> None:
    print(f"Gateway started  (pid={result.pid})")
    print(f"Health:          {result.health_url}")
    if result.im_service_url is not None:
        reachable = _check_im_reachable(result.im_service_url)
        status = (
            "connected" if reachable else "unavailable (running offline, will retry)"
        )
        print(f"IM service:      {result.im_service_url}  [{status}]")
    print(f"Log:             {result.log_path}")


def _emit_gateway_feedback(
    level: str, summary: str, next_step: str | None = None
) -> None:
    """Print one operator-facing gateway feedback line to stderr."""

    if level == "ERROR":
        print("Gateway failed to start\n", file=sys.stderr)
        for line in summary.splitlines():
            print(f"  {line}", file=sys.stderr)
        if next_step is not None:
            print(f"\n  → {next_step}", file=sys.stderr)
    else:
        print(f"{level} {summary}", file=sys.stderr)
        if next_step is not None:
            print(f"  → {next_step}", file=sys.stderr)


class GatewayRuntimeLike(Protocol):
    """Describe the minimal lifecycle contract used by `run_gateway`."""

    def run_forever(self) -> int:
        """Run the gateway until shutdown and return the process exit code."""


class HeartbeatRunner(Protocol):
    """Describe the async lifecycle expected from the heartbeat runner wrapper."""

    async def start(self) -> None:
        """Start background scheduler ticking."""

    async def close(self) -> None:
        """Stop background scheduler ticking and wait for drain."""


class IMConnectionManagerLike(Protocol):
    """Describe the async lifecycle required from the optional IM connector."""

    async def connect_once(self) -> None:
        """Establish the initial websocket connection and register the node."""

    async def run_forever(self) -> None:
        """Keep the websocket alive until close is requested."""

    async def close(self) -> None:
        """Close the websocket and stop reconnect attempts."""


class BrowserOpener(Protocol):
    """Describe the minimal browser-launch interface needed by bind bootstrap."""

    def __call__(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        """Open one browser URL and report whether a handler accepted the request."""


@dataclass(frozen=True, slots=True)
class RuntimeFactories:
    """Collect replaceable construction hooks used by the gateway entry.

    Args:
        load_config: Function used to load YAML config into `LocalConfig`.
        build_runtime: Factory that creates the runtime orchestrator from config.
        install_signal_handlers: Optional hook that installs OS signal handlers before run.
    """

    load_config: Callable[[str | Path], LocalConfig] = load_local_config
    build_runtime: Callable[[LocalConfig], GatewayRuntimeLike] | None = None
    install_signal_handlers: SignalHandlerInstaller | None = None


@dataclass(frozen=True, slots=True)
class BackgroundLaunchResult:
    """Describe the operator-facing result of a successful background launch.

    Args:
        pid: Process id of the detached foreground child now hosting the gateway runtime.
        health_url: Ready-check URL operators can probe during follow-up troubleshooting.
        log_path: File receiving the detached child stdout/stderr stream.
        im_service_url: Optional IM service URL configured for this gateway.
    """

    pid: int
    health_url: str
    log_path: Path
    im_service_url: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayRuntimeState:
    """Persist the operator-facing metadata needed to locate one background gateway.

    Args:
        pid: Background gateway process id launched for this config.
        config_path: Absolute config path used for that process.
        health_url: Health endpoint associated with the launched gateway.
        log_path: Log file receiving the detached process output.
    """

    pid: int
    config_path: str
    health_url: str
    log_path: str


class _IMConfigSyncClient:
    """Fetch IM agent config snapshots and extend the live gateway agent registry."""

    # bugfix-402-M6: optional callback invoked at the end of handle_agent_create
    # so build_runtime can register a CronExecutionService for dynamically created
    # agents without handle_agent_create needing to know about the cron subsystem.
    on_agent_created: Callable[[str, Path], None] | None = None

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        pipeline: InboundPipeline,
        local_config: LocalConfig,
        workspace_root_factory: Callable[[str], Path] | None = None,
        reporter: UpstreamReporter | None = None,
        client: httpx.Client | None = None,
        client_factory: BootstrapClientFactory | None = None,
        timeout_seconds: float = 5.0,
        retry_interval_seconds: float = 0.1,
        max_attempts: int = 50,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
        token_getter: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._base_url = _im_http_base_url(base_url)
        self._base_headers = _im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._max_attempts = max(max_attempts, 1)
        self._pipeline = pipeline
        self._local_config = local_config
        self._workspace_root_factory = (
            workspace_root_factory or self._default_workspace_root
        )
        self._reporter = reporter
        self._client_factory = client_factory
        self._client = client
        self._monotonic = monotonic
        self._sleep = sleep
        # feat-394-M3 fix: accept token_getter so auto-bind token refresh propagates
        # to config sync requests. Without this, sync_agent calls 401 after auto-bind
        # because the initial token is empty and is never updated. Mirrors the pattern
        # used by _IMBootstrapClient (main.py:599-613).
        self._token_getter = token_getter

    def sync_agent(self, *, agent_id: str, profile_version: int) -> None:
        deadline = self._monotonic() + self._timeout_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                payload = self._fetch_agent_config(agent_id=agent_id)
                resolved_profile_version = int(payload.get("profile_version", 0))
                if resolved_profile_version < profile_version:
                    raise RuntimeError(
                        f"agent {agent_id} config stale: expected >= {profile_version}, got {resolved_profile_version}"
                    )
                workspace_root_text = payload.get("workspace_root")
                if isinstance(workspace_root_text, str) and workspace_root_text.strip():
                    workspace_root = Path(workspace_root_text).expanduser().resolve()
                else:
                    workspace_root = self._workspace_root_factory(agent_id)
                workspace_root = ensure_workspace_defaults(workspace_root)
                # feat-379-M2: parse per-agent features/custom_prompt from IM mirror payload
                raw_features = payload.get("features")
                synced_features = (
                    {
                        k: v
                        for k, v in raw_features.items()
                        if isinstance(k, str) and isinstance(v, bool)
                    }
                    if isinstance(raw_features, dict)
                    else {}
                )
                synced_custom_prompt_val = payload.get("custom_prompt")
                synced_custom_prompt = (
                    synced_custom_prompt_val.strip()
                    if isinstance(synced_custom_prompt_val, str)
                    and synced_custom_prompt_val.strip()
                    else None
                )
                # feat-394 decision 5: parse heartbeat cadence (every / active_hours) from
                # heartbeat_json; enable state lives in features["heartbeat"] (M9 decision D).
                _hb_raw_str = payload.get("heartbeat_json")
                if isinstance(_hb_raw_str, str) and _hb_raw_str.strip():
                    import json as _json  # noqa: PLC0415

                    try:
                        _hb_raw = _json.loads(_hb_raw_str)
                    except (ValueError, TypeError):
                        _hb_raw = payload.get("heartbeat")
                else:
                    _hb_raw = payload.get("heartbeat")
                (
                    synced_heartbeat_every,
                    synced_hb_start,
                    synced_hb_end,
                    synced_hb_tz,
                ) = _parse_heartbeat_from_im_payload(_hb_raw)
                # feat-394 fix: cron is a gated capability decoupled from the user tool
                # whitelist — cron_enabled must NEVER be written into tool_allowlist.
                # The cron tool is appended to the effective session toolset via the
                # feature→requires_tool invariant (feat-394 M9 decision D).
                _raw_allowlist = [
                    item.strip()
                    for item in payload.get("tool_allowlist", [])
                    if isinstance(item, str) and item.strip()
                ]
                agent_config = AgentWorkspaceConfig(
                    agent_id=agent_id,
                    workspace_root=workspace_root,
                    title=str(payload.get("display_name") or agent_id),
                    skills=tuple(
                        item.strip()
                        for item in payload.get("skills", [])
                        if isinstance(item, str) and item.strip()
                    ),
                    tool_allowlist=tuple(_raw_allowlist),
                    system_prompt=(
                        payload.get("system_prompt").strip()
                        if isinstance(payload.get("system_prompt"), str)
                        and payload.get("system_prompt").strip()
                        else None
                    ),
                    group_reply_policy=(
                        payload.get("group_reply_policy").strip()
                        if isinstance(payload.get("group_reply_policy"), str)
                        and payload.get("group_reply_policy").strip()
                        else None
                    ),
                    default_model=(
                        payload.get("default_model").strip()
                        if isinstance(payload.get("default_model"), str)
                        and payload.get("default_model").strip()
                        else None
                    ),
                    features=synced_features,
                    custom_prompt=synced_custom_prompt,
                    heartbeat_every=synced_heartbeat_every,
                    heartbeat_active_hours_start=synced_hb_start,
                    heartbeat_active_hours_end=synced_hb_end,
                    heartbeat_active_hours_timezone=synced_hb_tz,
                )
                self._pipeline.register_agent(agent_config)
                self._persist_agent_config(agent_config)
                self._pipeline.drop_agent_sessions(agent_id)
                return
            except (httpx.HTTPError, RuntimeError, ValueError):
                if attempt >= self._max_attempts or self._monotonic() >= deadline:
                    raise
                self._sleep(self._retry_interval_seconds)

    def handle_agent_create(
        self, agent_payload: Mapping[str, object]
    ) -> dict[str, object]:
        """在节点上落地工作区并注册 Agent，供 IM ``agent.create`` / ``agent.created`` 回包使用。"""
        agent_id_raw = agent_payload.get("agent_id")
        if not isinstance(agent_id_raw, str) or not agent_id_raw.strip():
            raise ValueError("agent.create requires non-empty agent_id")
        agent_id = agent_id_raw.strip()
        ws_raw = agent_payload.get("workspace_root")
        if isinstance(ws_raw, str) and ws_raw.strip():
            workspace_root = Path(ws_raw.strip()).expanduser()
            if not workspace_root.is_absolute():
                raise ValueError(
                    "workspace_root must be an absolute path or start with ~/"
                )
            workspace_root = workspace_root.resolve()
        else:
            workspace_root = self._workspace_root_factory(agent_id)
        workspace_root = ensure_workspace_defaults(workspace_root)
        display = agent_payload.get("display_name")
        title = (
            display.strip()
            if isinstance(display, str) and display.strip()
            else agent_id
        )
        desc_val = agent_payload.get("description")
        description_str = desc_val.strip() if isinstance(desc_val, str) else ""
        system_prompt_val = agent_payload.get("system_prompt")
        system_prompt = (
            system_prompt_val.strip()
            if isinstance(system_prompt_val, str) and system_prompt_val.strip()
            else None
        )
        raw_skills = agent_payload.get("skills")
        skills = tuple(
            item.strip()
            for item in (raw_skills if isinstance(raw_skills, list) else [])
            if isinstance(item, str) and item.strip()
        )
        raw_tools = agent_payload.get("tool_allowlist")
        tool_allowlist = tuple(
            item.strip()
            for item in (raw_tools if isinstance(raw_tools, list) else [])
            if isinstance(item, str) and item.strip()
        )
        grp = agent_payload.get("group_reply_policy")
        group_reply_policy = (
            grp.strip() if isinstance(grp, str) and grp.strip() else "MENTION"
        )
        dm = agent_payload.get("default_model")
        default_model = dm.strip() if isinstance(dm, str) and dm.strip() else None
        # feat-379-M2: per-agent features and custom_prompt from IM push payload
        raw_features = agent_payload.get("features")
        features = (
            {
                k: v
                for k, v in raw_features.items()
                if isinstance(k, str) and isinstance(v, bool)
            }
            if isinstance(raw_features, dict)
            else {}
        )
        cp_val = agent_payload.get("custom_prompt")
        custom_prompt = (
            cp_val.strip() if isinstance(cp_val, str) and cp_val.strip() else None
        )
        agent_config = AgentWorkspaceConfig(
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
        self._pipeline.register_agent(agent_config)
        self._persist_agent_config(agent_config)
        if self._reporter is not None:
            self._reporter.replace_agents(tuple(self._local_config.agents))
        # bugfix-402-M6: notify build_runtime so it can register a
        # CronExecutionService for this newly created agent.  The callback is
        # wired after im_config_sync_client is constructed (see build_runtime).
        if self.on_agent_created is not None:
            try:
                self.on_agent_created(agent_id, workspace_root)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "on_agent_created callback failed for agent=%s; "
                    "cron execution service may not be registered",
                    agent_id,
                )
        return {
            "agent_id": agent_id,
            "display_name": title,
            "description": description_str,
            "system_prompt": system_prompt or "",
            "skills": list(skills),
            "tool_allowlist": list(tool_allowlist),
            "group_reply_policy": group_reply_policy,
            "default_model": default_model,
            "workspace_root": str(workspace_root),
            "features": features,
            "custom_prompt": custom_prompt,
        }

    def close(self) -> None:
        client = self._client
        if client is not None:
            client.close()
            self._client = None

    def reconcile_all_agents(
        self,
        *,
        memory_versions: dict[str, int] | None = None,
    ) -> None:
        """拉 IM 权威 profile 做全量对账，按 profile_version 取大覆盖内存 config。

        feat-394-M12 决策 F：gateway WS bind 完成（含重连）后调用一次，消除「漏一次
        增量推送即永久停在旧状态」的问题。对每个 local_config.agents 拉 source=mirror
        profile；若 IM 返回的 profile_version >= memory_versions[agent_id] 则
        register_agent 覆盖内存，否则保留内存（取大原则，避免回退新版本）。HTTP 失败
        时记录警告并跳过该 agent——不抛出，WS 连接生命周期不受影响。

        Args:
            memory_versions: 可选的 agent_id → 当前内存 profile_version 映射（由
                ConfigSyncClient 维护）。缺失或无对应 key 时视作内存版本为 0，即接受
                任意 IM 版本。
        """
        if memory_versions is None:
            memory_versions = {}
        for agent in self._local_config.agents:
            agent_id = agent.agent_id
            mem_ver = memory_versions.get(agent_id, 0)
            try:
                payload = self._fetch_agent_config(agent_id=agent_id)
            except (httpx.HTTPError, ValueError):
                _log.warning(
                    "reconcile_all_agents: failed to fetch profile for agent %s, skipping",
                    agent_id,
                )
                continue
            im_version = int(payload.get("profile_version", 0))
            if im_version < mem_ver:
                # IM 版本落后内存（增量推送已带来更新版本），保留内存不回退
                _log.debug(
                    "reconcile_all_agents: skipping agent %s — IM version %d < memory %d",
                    agent_id,
                    im_version,
                    mem_ver,
                )
                continue
            # IM 版本 >= 内存版本：覆盖内存 config 使其收敛到 IM 真值
            workspace_root_text = payload.get("workspace_root")
            if isinstance(workspace_root_text, str) and workspace_root_text.strip():
                workspace_root = Path(workspace_root_text).expanduser().resolve()
            else:
                workspace_root = self._workspace_root_factory(agent_id)
            workspace_root = ensure_workspace_defaults(workspace_root)
            raw_features = payload.get("features")
            synced_features = (
                {
                    k: v
                    for k, v in raw_features.items()
                    if isinstance(k, str) and isinstance(v, bool)
                }
                if isinstance(raw_features, dict)
                else {}
            )
            synced_custom_prompt_val = payload.get("custom_prompt")
            synced_custom_prompt = (
                synced_custom_prompt_val.strip()
                if isinstance(synced_custom_prompt_val, str)
                and synced_custom_prompt_val.strip()
                else None
            )
            _hb_raw_str = payload.get("heartbeat_json")
            if isinstance(_hb_raw_str, str) and _hb_raw_str.strip():
                import json as _json  # noqa: PLC0415

                try:
                    _hb_raw = _json.loads(_hb_raw_str)
                except (ValueError, TypeError):
                    _hb_raw = payload.get("heartbeat")
            else:
                _hb_raw = payload.get("heartbeat")
            (
                synced_heartbeat_every,
                synced_hb_start,
                synced_hb_end,
                synced_hb_tz,
            ) = _parse_heartbeat_from_im_payload(_hb_raw)
            _raw_allowlist = [
                item.strip()
                for item in payload.get("tool_allowlist", [])
                if isinstance(item, str) and item.strip()
            ]
            agent_config = AgentWorkspaceConfig(
                agent_id=agent_id,
                workspace_root=workspace_root,
                title=str(payload.get("display_name") or agent_id),
                skills=tuple(
                    item.strip()
                    for item in payload.get("skills", [])
                    if isinstance(item, str) and item.strip()
                ),
                tool_allowlist=tuple(_raw_allowlist),
                system_prompt=(
                    payload.get("system_prompt").strip()
                    if isinstance(payload.get("system_prompt"), str)
                    and payload.get("system_prompt").strip()
                    else None
                ),
                group_reply_policy=(
                    payload.get("group_reply_policy").strip()
                    if isinstance(payload.get("group_reply_policy"), str)
                    and payload.get("group_reply_policy").strip()
                    else None
                ),
                default_model=(
                    payload.get("default_model").strip()
                    if isinstance(payload.get("default_model"), str)
                    and payload.get("default_model").strip()
                    else None
                ),
                features=synced_features,
                custom_prompt=synced_custom_prompt,
                heartbeat_every=synced_heartbeat_every,
                heartbeat_active_hours_start=synced_hb_start,
                heartbeat_active_hours_end=synced_hb_end,
                heartbeat_active_hours_timezone=synced_hb_tz,
            )
            self._pipeline.register_agent(agent_config)
            _log.debug(
                "reconcile_all_agents: updated agent %s to IM version %d",
                agent_id,
                im_version,
            )

    def _persist_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        agents = list(self._local_config.agents)
        for index, existing in enumerate(agents):
            if existing.agent_id == agent_config.agent_id:
                agents[index] = agent_config
                break
        else:
            agents.append(agent_config)
        persist_path = (
            Path(self._local_config.source_path)
            if self._local_config.source_path
            else default_local_config_path()
        )
        self._local_config = LocalConfig(
            node=self._local_config.node,
            agents=tuple(agents),
            channels=self._local_config.channels,
            kernel=self._local_config.kernel,
            heartbeat=self._local_config.heartbeat,
            im_service=self._local_config.im_service,
            llm=self._local_config.llm,
            source_path=persist_path,
        )
        save_local_config(self._local_config, persist_path)

    def current_agent_payload(self, *, agent_id: str) -> dict[str, object] | None:
        for agent in self._local_config.agents:
            if agent.agent_id != agent_id:
                continue
            payload: dict[str, object] = {
                "display_name": agent.title or agent.agent_id,
                "system_prompt": agent.system_prompt or "",
                "skills": list(agent.skills),
                "tool_allowlist": list(agent.tool_allowlist),
                "group_reply_policy": agent.group_reply_policy or "manual",
                "default_model": agent.default_model,
                "workspace_root": str(agent.workspace_root),
                # feat-379-M2: expose per-agent features/custom_prompt for capabilities reporting
                "features": dict(agent.features),
                "custom_prompt": agent.custom_prompt,
            }
            return payload
        return None

    def _fetch_agent_config(self, *, agent_id: str) -> dict[str, object]:
        response = self._get_client().get(
            f"/im/v1/agents/{agent_id}/config", params={"source": "mirror"}
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("agent config response must be an object")
        return payload

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory(self._base_url)
        else:
            self._client = httpx.Client(
                base_url=self._base_url,
                headers=self._base_headers,
                timeout=self._timeout_seconds,
                trust_env=False,
            )
        return self._client

    def update_token(self, token: str | None) -> None:
        """Propagate a refreshed access token so future sync requests use it.

        feat-394-M3 fix: called by the token_getter wrapper in _run_gateway after
        each successful token refresh so this client does not hold a stale/empty
        Bearer token when auto-bind has rotated credentials.  Mirrors the
        _refresh_token pattern in _IMBootstrapClient (main.py:621-628).

        Args:
            token: New access token, or None to clear.
        """
        self._base_headers = _im_http_headers(token)
        # Propagate updated headers to any live client instance so in-flight
        # connections also pick up the new token without a full reconnect.
        # Injected test clients (passed via constructor) are updated in-place;
        # self-built clients are rebuilt by _get_client() on the next request
        # if they were previously None (first call) or by headers update here.
        if self._client is not None:
            self._client.headers.update(self._base_headers)

    @staticmethod
    def _default_workspace_root(agent_id: str) -> Path:
        return Path("~/nano-assistant/workspace").expanduser() / agent_id


class _IMBootstrapClient:
    """Query IM ownership state and launch browser binding when a node is unbound.

    Args:
        base_url: HTTP base URL used for IM account and node APIs.
        token: Optional bearer token forwarded to IM HTTP APIs.
        client: Optional preconfigured HTTP client used by tests.
        browser_opener: Function used to open the operator browser on pending bind URLs.
        timeout_seconds: HTTP timeout used for node/bind bootstrap calls.
        monotonic: Monotonic clock source used for short startup polling windows.
        sleep: Sleep function used between node-visibility retries.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        client: httpx.Client | None = None,
        client_factory: BootstrapClientFactory | None = None,
        browser_opener: BrowserOpener = webbrowser.open,
        feedback_sink: FeedbackSink = _emit_gateway_feedback,
        timeout_seconds: float = 5.0,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
        token_getter: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._base_urls = _im_bootstrap_base_urls(base_url)
        self._base_headers = _im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._clients: dict[str, httpx.Client] = {}
        self._base_url = self._base_urls[0]
        if client is not None:
            self._clients[self._base_url] = client
        self._browser_opener = browser_opener
        self._feedback_sink = feedback_sink
        self._monotonic = monotonic
        self._sleep = sleep
        self._token_getter = token_getter

    def _refresh_token(self) -> None:
        # bootstrap 跑在 asyncio.to_thread 工作线程里(main.py:894-896),无运行中 event
        # loop,因此可以直接 asyncio.run 同步等异步 token_getter。fix bugfix-346 漏接
        # bootstrap 路径导致 username/password 配置首次启动 401 的问题。
        if self._token_getter is None:
            return
        token = asyncio.run(self._token_getter())
        if token:
            self._base_headers = _im_http_headers(token)
            for client in self._clients.values():
                client.headers.update(self._base_headers)

    def ensure_node_binding(self, *, node_id: str) -> str | None:
        """Open the bind URL when the upstream node still has no owner.

        Args:
            node_id: Gateway node id that was just registered over IM websocket.

        Returns:
            The opened bind URL for unbound nodes, or `None` when the node is already owned.

        Raises:
            RuntimeError: When IM bootstrap APIs do not expose the registered node.
        """

        self._refresh_token()
        owner_id, resolved_base_url = self._wait_for_owner(node_id=node_id)
        if owner_id:
            return None
        client = self._get_client(resolved_base_url)
        try:
            response = client.post(
                "/im/v1/bind", json={"action": "start", "node_id": node_id}
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GatewayStartupError(
                summary=f"node {node_id} could not start IM binding",
                next_step=f"Verify {resolved_base_url}/im/v1/bind is reachable, then rerun gateway.",
            ) from exc
        payload = response.json()
        bind_url = _require_text(payload.get("bind_url"), field_name="bind_url")

        # refactor-381: when NANO_MULTIAGENT_AUTO_BIND=1 (or --auto-bind via CLI),
        # confirm the binding programmatically instead of asking the operator to
        # click a URL. Removes the worktree-e2e blocker where automation cannot
        # complete the interactive bind step.
        if os.environ.get("NANO_MULTIAGENT_AUTO_BIND") == "1":
            bind_token = _extract_bind_token(bind_url)
            if not bind_token:
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind failed: bind_url missing token",
                    next_step=f"Inspect {bind_url} or unset NANO_MULTIAGENT_AUTO_BIND.",
                )
            try:
                confirm_resp = client.post(
                    "/im/v1/bind",
                    json={"action": "confirm", "bind_token": bind_token},
                )
                confirm_resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind confirm failed",
                    next_step=(
                        f"POST {resolved_base_url}/im/v1/bind with action=confirm + bind_token failed. "
                        "Verify the IM Bearer token has confirm permission, then rerun."
                    ),
                ) from exc
            self._feedback_sink(
                "INFO",
                f"node {node_id} auto-bound to IM",
                f"NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for {resolved_base_url}.",
            )
            return None

        self._browser_opener(bind_url, new=2, autoraise=True)
        self._feedback_sink(
            "ACTION",
            f"node {node_id} is waiting for IM binding",
            f"Open {bind_url} to finish binding this node.",
        )
        return bind_url

    def close(self) -> None:
        """Release the owned HTTP client."""

        seen_ids: set[int] = set()
        for client in self._clients.values():
            client_id = id(client)
            if client_id in seen_ids:
                continue
            seen_ids.add(client_id)
            client.close()

    def _wait_for_owner(self, *, node_id: str) -> tuple[str, str]:
        deadline = self._monotonic() + 5.0
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            for base_url in self._base_urls:
                try:
                    return self._get_owner_id(
                        node_id=node_id, base_url=base_url
                    ), base_url
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self._sleep(0.1)
        checked_urls = ", ".join(
            f"{base_url}/im/v1/nodes" for base_url in self._base_urls
        )
        message = f"node {node_id} did not appear in IM bootstrap"
        next_step = (
            f"Verify the IM node API is reachable at {checked_urls} and rerun gateway."
        )
        if last_error is not None:
            raise GatewayStartupError(
                summary=message, next_step=next_step
            ) from last_error
        raise GatewayStartupError(summary=message, next_step=next_step)

    def _get_owner_id(self, *, node_id: str, base_url: str) -> str:
        response = self._get_client(base_url).get("/im/v1/nodes")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("nodes response must be a list")
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            if _require_text(item.get("node_id"), field_name="node_id") != node_id:
                continue
            owner_id = item.get("owner_id")
            return owner_id.strip() if isinstance(owner_id, str) else ""
        raise RuntimeError(f"node {node_id} not found")

    def _get_client(self, base_url: str) -> httpx.Client:
        client = self._clients.get(base_url)
        if client is not None:
            return client
        if self._client_factory is not None:
            client = self._client_factory(base_url)
        else:
            client = httpx.Client(
                base_url=base_url,
                headers=self._base_headers,
                timeout=self._timeout_seconds,
                trust_env=False,
            )
        self._clients[base_url] = client
        return client


class GatewayProcessManager:
    """Legacy kernel subprocess manager — unused since refactor-387.

    refactor-387 M3: the kernel runs in-process via agent.sdk; no child process
    is spawned.  This class is retained only because GatewayRuntime still
    accepts a ``process_manager`` parameter typed as ``GatewayProcessManager | None``
    for backward compatibility with tests that pass None.  It will be removed
    in a follow-up unit that trims the dead config+process management layer.

    Args:
        config: Legacy KernelConfig (unused at runtime).
        kernel_client: Unused (was: HTTP client for readiness probes).
        process_factory: Unused (was: factory to spawn the kernel subprocess).
        monotonic: Monotonic clock source for timeout accounting.
        sleep: Sleep function used between readiness probes.
    """

    def __init__(
        self,
        *,
        config: KernelConfig,
        kernel_client: Any,  # KernelApiClient removed in M3; GatewayProcessManager is dead code until M4
        process_factory: ProcessFactory | None = None,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._config = config
        self._kernel_client = kernel_client
        self._process_factory = process_factory or _spawn_process
        self._monotonic = monotonic
        self._sleep = sleep
        self.process: ProcessLike | None = None

    def start_kernel_process(self) -> ProcessLike:
        """Spawn the kernel subprocess and poll until ``/v1/health`` reports ready.

        Legacy method — not called since refactor-387 (kernel runs in-process).

        Returns:
            The spawned process handle once health probing succeeds.

        Raises:
            RuntimeError: When the kernel does not become healthy before timeout.
        """

        if self.process is not None:
            return self.process
        process = self._process_factory(self._config.command)
        self.process = process
        self._wait_for_health()
        return process

    def stop_kernel_process(self) -> None:
        """Terminate the managed kernel child, escalating to kill when needed.

        Side Effects:
            Sends terminate/kill signals to the managed child process.
        """

        process = self.process
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._config.shutdown_grace_seconds)
        except (TimeoutError, subprocess.TimeoutExpired):
            process.kill()
        finally:
            self.process = None

    def _wait_for_health(self) -> None:
        deadline = self._monotonic() + self._config.startup_timeout_seconds
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            try:
                payload = self._kernel_client.health()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            else:
                if bool(payload.get("healthy")):
                    return
                last_error = RuntimeError(
                    f"kernel reported unhealthy payload: {payload}"
                )
            self._sleep(self._config.health_poll_interval_seconds)
        message = "kernel health check timed out"
        if last_error is not None:
            raise RuntimeError(message) from last_error
        raise RuntimeError(message)


async def _stream_run_to_completion(
    *,
    run_id: str,
    kernel_session_id: str,
    agent_id: str,
    owner_user_id: str,
    kernel: Any,
    run_context_store: dict,
    observer: Callable[..., Any] | None,
    stream_anchor: int = 0,
) -> tuple[str, dict | None]:
    """Stream one kernel run to terminal state, driving the event observer.

    Seeds run_context_store with the standard heartbeat/cron context (empty
    conversation_id triggers lazy IM turn_start creation), then replays the
    kernel event stream until a terminal run_status.

    Args:
        run_id: Kernel run ID to track.
        kernel_session_id: Kernel session the run lives in.
        agent_id: Agent ID, forwarded into run_context_store for routing.
        owner_user_id: IM user_id of the gateway owner; drives lazy direct-chat
            creation via to_user_id in the context entry.
        kernel: In-process kernel; must implement stream(session_id, after_sequence).
        run_context_store: Shared dict seeded here and popped in finally.
        observer: kernel_event_observer callable (sync or async); None skips driving.
        stream_anchor: after_sequence passed to kernel.stream; 0 means replay all.

    Returns:
        Tuple of (last_assistant_text, popped_ctx).  last_assistant_text is the last
        assistant_message content seen, stripped (empty string on silence).
        popped_ctx is the context entry that was removed from run_context_store on
        completion — callers can inspect e.g. conversation_id to detect silent ticks.

    Raises:
        Nothing — stream failures are re-raised to the caller for per-path logging.
    """
    run_context_store[run_id] = {
        "conversation_id": "",  # lazy: filled by IM turn_start ack
        "message_id": "",  # lazy: filled by IM turn_start ack
        "agent_id": agent_id,
        "to_user_id": owner_user_id,
        "kernel_session_id": kernel_session_id,
    }

    final_result_text = ""
    popped_ctx: dict | None = None
    try:
        async for event in kernel.stream(
            kernel_session_id, after_sequence=stream_anchor
        ):
            if event.get("run_id") != run_id:
                continue
            if event.get("event") == "assistant_message":
                content = str(event.get("content") or "").strip()
                if content:
                    final_result_text = content
            if observer is not None:
                obs_result = observer(event)
                if asyncio.iscoroutine(obs_result):
                    await obs_result
            if event.get("event") == "run_status" and event.get("status") in (
                "completed",
                "failed",
                "cancelled",
                "error",
            ):
                break
    except Exception:
        # Re-raise so caller can log with per-path context (agent/job/run identifiers).
        run_context_store.pop(run_id, None)
        raise
    finally:
        popped_ctx = run_context_store.pop(run_id, None)

    return final_result_text, popped_ctx


class PollingHeartbeatRunner:
    """Run the existing heartbeat scheduler as a background tick loop.

    Args:
        scheduler: Existing scheduler implementation that evaluates `HEARTBEAT.md`.
        config: Local heartbeat runtime settings.
        sleep: Async sleep function used between tick passes.
        kernel: In-process kernel used to stream heartbeat run events (feat-393).
            When provided alongside run_context_store and owner_user_id, the runner
            seeds run_context_store and awaits each run to terminal state, driving the
            kernel_event_observer to create the heartbeat IM message if there is content.
        run_context_store: Shared run-context map seeded with heartbeat run metadata
            (feat-393).  Observer reads this to route streaming events to IM.
        owner_user_id: IM user_id of the gateway node owner; used as to_user_id in
            turn_start so the heartbeat message lands in the owner's direct conversation
            with the agent (feat-393).

    Notes:
        The runner keeps scheduler semantics local and configuration-driven. It does not
        introduce hot reload or remote orchestration; it only provides the missing long-
        running process wrapper required to keep the gateway alive.
    """

    def __init__(
        self,
        *,
        scheduler: HeartbeatScheduler,
        config: HeartbeatConfig,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        kernel: Any | None = None,
        run_context_store: "dict[str, dict[str, str]] | None" = None,
        owner_user_id: str = "",
        kernel_event_observer: Any | None = None,
        cron_tick_fn: Callable[[str], Awaitable[None]] | None = None,
        agents: "dict[str, Any] | None" = None,
    ) -> None:
        self._scheduler = scheduler
        self._config = config
        self._sleep = sleep
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        # feat-393: kernel + run_context_store enable streaming delivery of heartbeat results.
        self._kernel = kernel
        self._run_context_store = run_context_store
        self._owner_user_id = owner_user_id
        self._kernel_event_observer = kernel_event_observer
        # feat-394-M3 CRITICAL-1 fix: wire cron into the unified polling tick.
        # cron_tick_fn(agent_id) is called once per tick for each cron_enabled agent.
        # When None, cron is skipped (backward compat, no cron subsystem configured).
        self._cron_tick_fn = cron_tick_fn
        self._agents = agents or {}

    async def start(self) -> None:
        """Start background scheduler ticking exactly once."""

        if self._task is not None:
            return
        self._stop_requested = False
        self._wake_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(), name="personal-assistant-heartbeat"
        )

    async def close(self) -> None:
        """Stop the background loop and wait for the worker task to finish."""

        task = self._task
        if task is None:
            return
        self._stop_requested = True
        self._wake_event.set()
        await task
        self._task = None

    def request_tick(self) -> None:
        """Wake the loop so a manual IM-triggered tick can run promptly."""

        self._wake_event.set()

    async def _run_loop(self) -> None:
        while not self._stop_requested:
            summary = await self._scheduler.tick()
            # feat-393: consume each triggered heartbeat run through the shared observer so
            # results are delivered to the owner's canonical IM direct conversation.
            if (
                self._kernel is not None
                and self._run_context_store is not None
                and self._owner_user_id
            ):
                for record in summary.triggered_runs:
                    if self._stop_requested:
                        break
                    await self._consume_heartbeat_run(record)
            # feat-394-M3 CRITICAL-1 fix: unified polling tick also drives cron scheduling.
            # Design §架构总览: "统一 Polling 调度 tick（扩展现 PollingHeartbeatRunner）".
            # For each agent with cron_enabled=True, invoke the cron tick function.
            if self._cron_tick_fn is not None and not self._stop_requested:
                for agent_id, agent in list(self._agents.items()):
                    if self._stop_requested:
                        break
                    cron_enabled = getattr(agent, "cron_enabled", False)
                    if cron_enabled:
                        try:
                            await self._cron_tick_fn(agent_id)
                        except Exception:  # noqa: BLE001
                            import logging as _logging  # noqa: PLC0415

                            _logging.getLogger(__name__).exception(
                                "cron tick failed: agent=%s", agent_id
                            )
            if self._stop_requested:
                break
            try:
                await asyncio.wait_for(
                    self._wake_event.wait(), timeout=self._config.tick_interval_seconds
                )
            except TimeoutError:
                continue
            finally:
                self._wake_event.clear()

    @staticmethod
    async def trim_silent_tick(
        *,
        session_file: "Path",
        pre_submit_line_count: int,
    ) -> None:
        """Truncate a JSONL session file to remove heartbeat turns added by a silent tick.

        feat-394 decision 3 (transcript trim): after a silent heartbeat run (HEARTBEAT_OK
        or empty response), the triggering prompt and ack turns are removed from the
        canonical direct-chat session so they do not pollute the next LLM context window.
        "Silent" is detected by the caller when run_context_store[run_id]["conversation_id"]
        remains empty after the run completes (no turn_start was ever sent — zero IM trace).

        The trim reads all lines, keeps only the first ``pre_submit_line_count`` non-empty
        lines, and rewrites the file atomically (rename after write).  Lines beyond that
        count are the heartbeat trigger prompt + HEARTBEAT_OK (or empty) assistant turn.

        This approach is safe because:
        - JSONL append is the only mutation normally done; we own the file.
        - The rewrite is atomic (tmp file → rename) so a crash mid-write does not
          corrupt existing history.
        - heartbeat-only turns do not refresh session idle time (design §B requirement).

        Args:
            session_file: Absolute path to the session ``.jsonl`` file.
            pre_submit_line_count: Number of non-empty lines present before the heartbeat
                run was submitted.  Lines beyond this index are removed.
        """

        import os  # noqa: PLC0415

        if not session_file.exists():
            return  # nothing to trim
        raw_text = session_file.read_text(encoding="utf-8")
        all_lines = raw_text.splitlines(keepends=True)
        # Count only non-empty lines to match the pre-submit count.
        non_empty_indices: list[int] = []
        for idx, line in enumerate(all_lines):
            if line.strip():
                non_empty_indices.append(idx)
        if len(non_empty_indices) <= pre_submit_line_count:
            return  # nothing to trim (no heartbeat lines were appended)
        # Keep lines up to and including the last pre-submit non-empty line.
        last_kept_line_idx = (
            non_empty_indices[pre_submit_line_count - 1]
            if pre_submit_line_count > 0
            else -1
        )
        kept_lines = all_lines[: last_kept_line_idx + 1]
        tmp_path = session_file.with_suffix(".jsonl.trim_tmp")
        try:
            tmp_path.write_text("".join(kept_lines), encoding="utf-8")
            os.replace(tmp_path, session_file)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    async def _consume_heartbeat_run(self, record: "HeartbeatRunRecord") -> None:
        """Stream one heartbeat run to completion, driving the kernel_event_observer for IM delivery.

        Delegates streaming to the module-level _stream_run_to_completion helper, then applies
        heartbeat-specific post-processing: silent-tick transcript trim (feat-394 decision 3-B).
        The observer handles lazy turn_start creation and NO_REPLY/empty suppression.

        Args:
            record: HeartbeatRunRecord returned by the scheduler tick.

        Notes:
            Failures are logged and swallowed; the next tick will re-evaluate and re-report
            if the condition persists.  This matches design decision 6: heartbeat delivery
            inherits normal-chat failure behavior (no persistent retry).
        """
        _hb_logger = _log  # module-level logger; no per-call import needed

        run_id = record.run_id
        kernel_session_id = record.session_id
        agent_id = record.agent_id

        assert self._run_context_store is not None  # guard (checked in _run_loop)

        # feat-394 decision 3 transcript trim (B): snapshot session file line count before run.
        # After a silent tick (HEARTBEAT_OK / empty), the triggered prompt + ack turns are
        # removed so they don't pollute the canonical session's next LLM context window.
        # We also don't refresh session idle time for heartbeat-only ticks.
        _session_file_for_trim: "Path | None" = None
        _pre_submit_line_count = 0
        try:
            _get_session_fn = getattr(self._kernel, "get_session", None)
            if _get_session_fn is not None:
                _sess_info = _get_session_fn(kernel_session_id)
                _ws_root = (
                    _sess_info.get("workspace_root")
                    if isinstance(_sess_info, dict)
                    else None
                )
                if _ws_root:
                    _sess_path = (
                        Path(_ws_root)
                        / _WCD
                        / "sessions"
                        / f"{kernel_session_id}.jsonl"
                    )
                    if _sess_path.exists():
                        _session_file_for_trim = _sess_path
                        _content = _sess_path.read_text(encoding="utf-8")
                        _pre_submit_line_count = sum(
                            1 for ln in _content.splitlines() if ln.strip()
                        )
        except Exception:  # noqa: BLE001
            pass  # trim snapshot failure is non-fatal; trim skipped for this tick

        try:
            # feat-393 fix-r2 Fix B: stream from the pre-submit anchor to skip replaying
            # history from prior ticks.  Falls back to 0 when anchor is absent (test path).
            _, ctx = await _stream_run_to_completion(
                run_id=run_id,
                kernel_session_id=kernel_session_id,
                agent_id=agent_id,
                owner_user_id=self._owner_user_id,
                kernel=self._kernel,
                run_context_store=self._run_context_store,
                observer=self._kernel_event_observer,
                stream_anchor=record.stream_anchor,
            )
        except Exception:  # noqa: BLE001  — delivery failure does not disrupt gateway loop
            _hb_logger.exception(
                "heartbeat run delivery failed: agent=%s run_id=%s", agent_id, run_id
            )
            return

        # feat-394 B: silent-tick transcript trim.
        # If conversation_id was never filled (no turn_start sent → zero IM trace → silent tick),
        # truncate the session JSONL back to the pre-submit state.
        _was_silent = ctx is not None and not ctx.get("conversation_id")
        if (
            _was_silent
            and _session_file_for_trim is not None
            and _pre_submit_line_count > 0
        ):
            try:
                await self.trim_silent_tick(
                    session_file=_session_file_for_trim,
                    pre_submit_line_count=_pre_submit_line_count,
                )
            except Exception:  # noqa: BLE001
                _hb_logger.debug(
                    "heartbeat transcript trim failed (non-fatal): agent=%s run_id=%s",
                    agent_id,
                    run_id,
                )


class _InboundDispatcher:
    """Bridge synchronous channel callbacks onto the async inbound pipeline."""

    def __init__(self, pipeline: InboundPipeline) -> None:
        self._pipeline = pipeline
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the runtime event loop used to execute inbound pipeline coroutines."""

        self._loop = loop

    def __call__(self, message: InboundMessage) -> None:
        """Schedule one inbound message on the runtime loop.

        Raises:
            RuntimeError: When called before the runtime loop is available.
        """

        loop = self._loop
        if loop is None:
            raise RuntimeError("gateway runtime loop is not ready")
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            task = loop.create_task(self._pipeline.handle_inbound(message))
            task.add_done_callback(_consume_task_exception)
            return
        future = asyncio.run_coroutine_threadsafe(
            self._pipeline.handle_inbound(message), loop
        )
        future.add_done_callback(_consume_future_exception)


class GatewayRuntime:
    """Run the assembled Node Gateway process until shutdown is requested.

    Args:
        config: Parsed immutable local gateway config.
        process_manager: Optional kernel child-process lifecycle manager.
            Pass ``None`` (M3+) when the kernel runs in-process; the
            runtime then skips subprocess spawn/stop.
        channel_registry: Registry containing configured channel adapters.
        heartbeat_runner: Background heartbeat loop wrapper.
        im_connection_manager: Optional IM websocket connector.
        on_inbound: Shared synchronous inbound callback given to channel adapters.
        post_im_connect: Optional synchronous hook invoked after IM connect/register succeeds.
        resource_closers: Additional cleanup callables invoked after runtime shutdown.
    """

    def __init__(
        self,
        config: LocalConfig,
        process_manager: GatewayProcessManager | None,
        *,
        channel_registry: ChannelRegistry | None = None,
        heartbeat_runner: HeartbeatRunner | None = None,
        im_connection_manager: IMConnectionManagerLike | None = None,
        on_inbound: Callable[[InboundMessage], None] | None = None,
        post_im_connect: Callable[[], None] | None = None,
        resource_closers: tuple[Callable[[], None], ...] = (),
        feedback_sink: FeedbackSink = _emit_gateway_feedback,
        internal_dispatch_handler: InternalDispatchHandler | None = None,
        gateway_internal_port: int = 8089,
        kernel: object | None = None,
        cron_dispatcher: GatewayCronDispatcher | None = None,
    ) -> None:
        self._config = config
        self._process_manager = process_manager
        self._channel_registry = channel_registry or ChannelRegistry()
        self._heartbeat_runner = heartbeat_runner
        self._im_connection_manager = im_connection_manager
        self._on_inbound = on_inbound or (lambda _message: None)
        self._post_im_connect = post_im_connect
        self._resource_closers = resource_closers
        self._feedback_sink = feedback_sink
        self._internal_dispatch_handler = internal_dispatch_handler
        self._gateway_internal_port = gateway_internal_port
        # bugfix-402-M3 R3: explicit kernel reference for ordered async shutdown
        # (Decision 7). Kernel is closed via aclose() between producers and consumers,
        # not via the untyped resource_closers list.
        self._kernel = kernel
        # bugfix-402-M4: inject gateway loop into cron services so enqueue() from
        # worker threads (asyncio.to_thread) can schedule execute_fn correctly.
        self._cron_dispatcher = cron_dispatcher
        self._ready_event = threading.Event()
        self._shutdown_requested = threading.Event()

    def wait_until_ready(self, timeout: float | None = None) -> bool:
        """Block until the runtime reaches ready state or timeout expires."""

        return self._ready_event.wait(timeout)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from another thread or signal handler."""

        self._shutdown_requested.set()

    def run_forever(self) -> int:
        """Run the gateway until shutdown is requested.

        Returns:
            `0` after startup succeeds and graceful shutdown completes.
        """

        self._ready_event.clear()
        self._shutdown_requested.clear()
        return asyncio.run(self._run_until_shutdown())

    async def _run_until_shutdown(self) -> int:
        loop = asyncio.get_running_loop()
        if isinstance(self._on_inbound, _InboundDispatcher):
            self._on_inbound.bind_loop(loop)
        # bugfix-402-M4: wire gateway loop into cron dispatcher so enqueue()
        # called from asyncio.to_thread (tool.run) can schedule execute_fn on
        # this loop rather than silently dropping (no-running-loop path).
        if self._cron_dispatcher is not None:
            self._cron_dispatcher.set_gateway_loop(loop)

        channels_started = False
        heartbeat_started = False
        im_connected = False
        dispatch_runner: Any | None = None
        im_task: asyncio.Task[None] | None = None
        try:
            if self._process_manager is not None:
                self._process_manager.start_kernel_process()
            start_channels(self._channel_registry, self._on_inbound)
            channels_started = True
            if self._internal_dispatch_handler is not None:
                try:
                    from aiohttp import web as _aiohttp_web

                    _dispatch_app = _aiohttp_web.Application()
                    _dispatch_app.router.add_post(
                        "/internal/dispatch",
                        self._internal_dispatch_handler.build_aiohttp_handler(),
                    )
                    dispatch_runner = _aiohttp_web.AppRunner(_dispatch_app)
                    await dispatch_runner.setup()
                    _dispatch_site = _aiohttp_web.TCPSite(
                        dispatch_runner, "127.0.0.1", self._gateway_internal_port
                    )
                    await _dispatch_site.start()
                except Exception:  # noqa: BLE001
                    dispatch_runner = None
            self._ready_event.set()
            if self._im_connection_manager is not None:
                await self._im_connection_manager.connect_once()
                im_connected = True
                if self._post_im_connect is not None:
                    try:
                        await asyncio.to_thread(self._post_im_connect)
                    except GatewayStartupError as exc:
                        await self._publish_startup_failure(exc)
                        raise
                im_task = asyncio.create_task(
                    self._im_connection_manager.run_forever(),
                    name="personal-assistant-im",
                )
            # feat-393 fix-r1: heartbeat must start AFTER im.connect_once so that
            # manager.connected=True when the first tick's kernel_event_observer fires.
            # Starting before connect_once was the root cause of 0 IM deliveries:
            # fast local LLM responses completed before the WS was established, and
            # observer saw connected=False, silently skipping every heartbeat delivery.
            if self._heartbeat_runner is not None:
                await self._heartbeat_runner.start()
                heartbeat_started = True
            await asyncio.to_thread(self._shutdown_requested.wait)
            return 0
        finally:
            self._ready_event.clear()
            if dispatch_runner is not None:
                try:
                    await dispatch_runner.cleanup()
                except Exception as exc:
                    # Cleanup failure (e.g. socket already closed) must not prevent
                    # further shutdown steps; log so the error is observable (refactor-395-M1).
                    _log.warning(
                        "dispatch runner cleanup failed during shutdown: %s", exc
                    )
            if heartbeat_started and self._heartbeat_runner is not None:
                await self._heartbeat_runner.close()
            if channels_started:
                stop_channels(self._channel_registry)
            # bugfix-402-M3 R3: drain in-flight runs before closing the IM transport
            # (Decision 7). Producers are already stopped above; aclose() waits for
            # the Registry to reach CLOSED before returning.
            if self._kernel is not None and hasattr(self._kernel, "aclose"):
                try:
                    await self._kernel.aclose()
                except Exception as exc:  # noqa: BLE001
                    _log.warning("kernel.aclose() raised during shutdown: %s", exc)
            # bugfix-402-M6 W-1: drain in-flight cron executions after kernel is
            # closed (no new runs accepted) but before IM transport is torn down.
            if self._cron_dispatcher is not None:
                try:
                    await self._cron_dispatcher.drain_all()
                except Exception as exc:  # noqa: BLE001
                    _log.warning(
                        "cron dispatcher drain_all() raised during shutdown: %s", exc
                    )
            if im_connected and self._im_connection_manager is not None:
                await self._im_connection_manager.close()
                if im_task is not None:
                    await _await_background_task(im_task)
            elif im_task is not None:
                im_task.cancel()
                with suppress(asyncio.CancelledError):
                    await im_task
            if self._process_manager is not None:
                self._process_manager.stop_kernel_process()
            for closer in self._resource_closers:
                closer()

    async def _publish_startup_failure(self, exc: GatewayStartupError) -> None:
        self._feedback_sink("ERROR", exc.summary, exc.next_step)
        manager = self._im_connection_manager
        if manager is None or not manager.connected:
            return
        last_error = (
            exc.summary
            if exc.next_step is None
            else f"{exc.summary} Next: {exc.next_step}"
        )
        payload = {
            "node_id": self._config.node.node_id,
            "status": "degraded",
            "agent_count": len(self._config.agents),
            "last_error": last_error,
        }
        try:
            await manager.send_json("node.heartbeat", payload)
        except Exception:  # noqa: BLE001
            return


def _load_runtime_config(
    config_path: str | Path,
    *,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    im_service_url_override: str | None = None,
) -> LocalConfig:
    config = load_config(config_path)
    if (
        not isinstance(im_service_url_override, str)
        or not im_service_url_override.strip()
    ):
        return config
    override_url = im_service_url_override.strip()
    old_im = config.im_service
    if old_im is None:
        return replace(config, im_service=IMServiceConfig(url=override_url))
    return replace(
        config,
        im_service=IMServiceConfig(
            url=override_url,
            token=old_im.token,
            refresh_token=old_im.refresh_token,
            username=old_im.username,
            password=old_im.password,
        ),
    )


def run_gateway(
    *,
    config_path: str | Path,
    factories: RuntimeFactories | Mapping[str, Any] | None = None,
    im_service_url_override: str | None = None,
) -> int:
    """Load config, build runtime, and execute the gateway entry flow.

    Args:
        config_path: YAML config file passed by the operator.
        factories: Optional factory overrides used by tests.

    Returns:
        Process exit code. `0` means the managed startup/shutdown sequence succeeded.
    """

    resolved_factories = _coerce_factories(factories)
    config = _load_runtime_config(
        config_path,
        load_config=resolved_factories.load_config,
        im_service_url_override=im_service_url_override,
    )
    init_model_registry(config.llm)
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    restore_signal_handlers = (
        resolved_factories.install_signal_handlers
        or _install_default_signal_handlers(runtime)
    )
    restore = restore_signal_handlers()
    # Write PID file so the background launcher can detect a live instance.
    _write_gateway_pid(config)
    try:
        return runtime.run_forever()
    finally:
        restore()
        _remove_gateway_pid(config)


def launch_gateway_in_background(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_ready: ReadyWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Start the gateway in a detached child and wait until it is ready.

    Args:
        config_path: Operator-provided config path forwarded to the detached child.
        load_config: Config loader used to resolve health-check details before spawning.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_ready: Optional readiness waiter override used by tests.

    Returns:
        Detached process metadata once the child reaches ready state.

    Raises:
        RuntimeError: When the detached child exits or never becomes ready.
    """

    config = _load_runtime_config(
        config_path,
        load_config=load_config,
        im_service_url_override=im_service_url_override,
    )
    # Single-instance protection: refuse to start if a live gateway is already running.
    existing_pid = _read_gateway_pid(config)
    if existing_pid is not None:
        if _pid_is_running(existing_pid):
            raise GatewayStartupError(
                summary=f"gateway is already running (pid={existing_pid})",
                next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
            )
        # Stale PID file from a crashed process — clean it up and continue.
        _remove_gateway_pid(config)
    log_path = _default_gateway_log_path(config)
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    argv = _background_gateway_argv(
        config.source_path, im_service_url_override=im_service_url_override
    )
    launcher = spawn_process or _spawn_background_gateway_process
    ready_waiter = wait_for_ready or _wait_for_gateway_ready
    process = launcher(argv, log_path)
    try:
        ready_waiter(process, config, config.kernel.startup_timeout_seconds)
    except Exception as exc:
        _stop_background_process(
            process, timeout_seconds=config.kernel.shutdown_grace_seconds
        )
        hint = _read_log_last_error(log_path, offset=log_offset)
        summary = hint if hint else str(exc)
        raise GatewayStartupError(
            summary=summary,
            next_step=f"Check the log for details: tail -20 {log_path}",
        ) from exc
    result = BackgroundLaunchResult(
        pid=process.pid,
        # refactor-387 M3: kernel is in-process; no separate health endpoint.
        # Use the IM service URL as the operator-facing health hint when available.
        health_url=config.im_service.url
        if config.im_service is not None
        else f"pid={process.pid}",
        log_path=log_path,
        im_service_url=config.im_service.url if config.im_service is not None else None,
    )
    _write_gateway_state(config, result)
    return result


def stop_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
) -> str:
    """Stop the background gateway associated with one config path.

    Args:
        config_path: Operator-provided config path used to resolve the runtime state file.
        load_config: Config loader used to derive the state file and shutdown timing.

    Returns:
        One operator-facing status line describing stop success, not-running, stale state, or
        a remaining listener that still answers on the same health URL.

    Side Effects:
        Sends SIGTERM and possibly SIGKILL to the background gateway process and removes stale state.
    """

    config = load_config(config_path)
    state_path = _gateway_state_path(config)
    state = _read_gateway_state(state_path)
    if state is None:
        pid = _read_gateway_pid(config)
        if pid is None:
            return f"NOT RUNNING config={config.source_path.name} state={state_path}"
        if not _pid_is_running(pid):
            _remove_gateway_pid(config)
            return f"STALE pid={pid} pid_file={_gateway_pid_path(config)}"
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            _remove_gateway_pid(config)
            return f"STALE pid={pid} pid_file={_gateway_pid_path(config)}"
        # bugfix-359: 顺手 killpg 把 kernel uvicorn 子进程一起带走;leader 进程已收过 SIGTERM,
        # 多发一次无副作用,pgid 拿不到时静默吞掉。
        _kill_process_tree(pid, signal.SIGTERM)
        deadline = time.monotonic() + config.kernel.shutdown_grace_seconds
        while time.monotonic() <= deadline:
            if not _pid_is_running(pid):
                _remove_gateway_pid(config)
                return f"STOPPED pid={pid} pid_file={_gateway_pid_path(config)}"
            time.sleep(config.kernel.health_poll_interval_seconds)
        os.kill(pid, signal.SIGKILL)
        _kill_process_tree(pid, signal.SIGKILL)
        _remove_gateway_pid(config)
        return f"STOPPED pid={pid} pid_file={_gateway_pid_path(config)} forced=true"
    if not _pid_is_running(state.pid):
        _remove_gateway_state(state_path)
        _remove_gateway_pid(config)
        if _healthcheck_reports_healthy(state.health_url):
            return f"STALE pid={state.pid} state={state_path} health_url={state.health_url} still_healthy=true"
        return f"STALE pid={state.pid} state={state_path}"
    try:
        os.kill(state.pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_gateway_state(state_path)
        _remove_gateway_pid(config)
        if _healthcheck_reports_healthy(state.health_url):
            return f"STALE pid={state.pid} state={state_path} health_url={state.health_url} still_healthy=true"
        return f"STALE pid={state.pid} state={state_path}"
    # bugfix-359: 顺手 killpg 把 kernel uvicorn 子进程一起带走。
    _kill_process_tree(state.pid, signal.SIGTERM)
    deadline = time.monotonic() + config.kernel.shutdown_grace_seconds
    while time.monotonic() <= deadline:
        if not _pid_is_running(state.pid):
            _remove_gateway_state(state_path)
            _remove_gateway_pid(config)
            if _verify_stopped_health_url(
                state.health_url,
                timeout_seconds=config.kernel.shutdown_grace_seconds,
                sleep_seconds=config.kernel.health_poll_interval_seconds,
            ):
                return f"STOPPED pid={state.pid} state={state_path}"
            return (
                f"STOPPED pid={state.pid} state={state_path} "
                f"health_url={state.health_url} still_healthy=true"
            )
        time.sleep(config.kernel.health_poll_interval_seconds)
    os.kill(state.pid, signal.SIGKILL)
    _kill_process_tree(state.pid, signal.SIGKILL)
    _remove_gateway_state(state_path)
    _remove_gateway_pid(config)
    forced = f"STOPPED pid={state.pid} state={state_path} forced=true"
    if _verify_stopped_health_url(
        state.health_url,
        timeout_seconds=config.kernel.shutdown_grace_seconds,
        sleep_seconds=config.kernel.health_poll_interval_seconds,
    ):
        return forced
    return f"{forced} health_url={state.health_url} still_healthy=true"


def _healthcheck_reports_healthy(health_url: str) -> bool:
    try:
        response = httpx.get(health_url, timeout=1.0, trust_env=False)
        payload = response.json()
    except Exception:  # noqa: BLE001
        return False
    return (
        response.status_code == 200
        and isinstance(payload, dict)
        and bool(payload.get("healthy"))
    )


class _KernelClientShim:
    """Adapt agent.sdk.Kernel to the kernel_client protocol.

    HeartbeatScheduler and InternalDispatchHandler use the old kernel_client
    interface (create_session/submit_message/append_message).  This shim
    bridges them to the in-process Kernel SDK.

    create_session is async so it can be properly awaited from the gateway's
    async event loop — run_until_complete on an already-running loop raises
    RuntimeError (refactor-387 M4 fix; previously the shim used that approach
    which silently prevented all heartbeat/cron runs from being submitted).
    """

    def __init__(self, kernel: "Kernel") -> None:
        self._kernel = kernel

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        session = await self._kernel.create_session(
            title=title,
            workspace_root=Path(workspace_root),
            metadata=metadata,
        )
        return {"session_id": session.session_id}

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, object]] | None = None,
        workspace_root: str | None = None,
        origin: str | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        from agent.sdk import RunOrigin as _RunOrigin  # refactor-387-M4

        parts: list[dict] = [{"type": "text", "text": t} for t in texts]
        for img in image_urls or []:
            url = img.get("url")
            if isinstance(url, str) and url.strip():
                img_part: dict = {"type": "image", "image_url": url.strip()}
                mime = img.get("content_type")
                if isinstance(mime, str) and mime.strip():
                    img_part["mime_type"] = mime.strip()
                parts.append(img_part)
        # Map string origin → RunOrigin enum.
        # feat-394-M7 R5-1 fix: cron is an unattended isolated origin (no user present);
        # RunOrigin.SYSTEM does not exist — use per-origin explicit mapping.
        if origin == "heartbeat":
            run_origin: _RunOrigin = _RunOrigin.HEARTBEAT
        elif origin == "cron":
            run_origin = _RunOrigin.CRON
        else:
            run_origin = _RunOrigin.USER
        run_record = self._kernel.submit(
            session_id=session_id,
            parts=parts,
            origin=run_origin,
            workspace_root=Path(workspace_root) if workspace_root else None,
        )
        return {"run_id": run_record.run_id, "anchor_sequence": 0, "status": "queued"}

    def current_event_sequence(self) -> int:
        """Return the kernel's current max event sequence for use as a stream anchor.

        Delegated to Kernel.current_event_sequence() which reads the EventStreamHub
        without requiring access to agent.core internals.
        """
        return self._kernel.current_event_sequence()

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        workspace_root: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        self._kernel.append_message(
            session_id,
            role=role,
            content=content,
            message_id=message_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
        return {"status": "appended"}

    def get_session(
        self, *, session_id: str, workspace_root: str | None = None
    ) -> dict[str, object]:
        return self._kernel.get_session(
            session_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
        )

    def close(self) -> None:
        pass


def _verify_stopped_health_url(
    health_url: str, *, timeout_seconds: float, sleep_seconds: float
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if not _healthcheck_reports_healthy(health_url):
            return True
        time.sleep(sleep_seconds)
    return not _healthcheck_reports_healthy(health_url)


def _make_prompt_preview_provider(kernel: Any) -> "PromptPreviewProvider":
    """Build a PromptPreviewProvider backed by Kernel.assemble_prompt_preview.

    sdk-fix-prompt-preview: in-process replacement for the removed kernel HTTP
    /v1/prompt-preview endpoint (refactor-387 M3 regression).  The returned
    callable matches PromptPreviewProvider signature so IMConnectionManager can
    call it transparently.

    Args:
        kernel: Assembled Kernel instance (agent.sdk.Kernel).

    Returns:
        Sync callable matching PromptPreviewProvider: (agent_id, workspace_root,
        features, custom_prompt, tool_ids, scenario, skill_ids) → dict.
    """
    from pathlib import Path as _Path  # noqa: PLC0415 — local import avoids circular risk

    def _provider(
        agent_id: str,
        workspace_root: str,
        features: dict,
        custom_prompt: "str | None",
        tool_ids: list,
        scenario: str,
        skill_ids: list = (),
    ) -> dict:
        # feat-394-M9: heartbeat/cron gates are now driven by ctx.flags via
        # features dict; heartbeat_enabled/cron_enabled params retired.
        return kernel.assemble_prompt_preview(
            workspace_root=_Path(workspace_root) if workspace_root else None,
            features=features or {},
            custom_prompt=custom_prompt,
            tool_ids=list(tool_ids) if tool_ids else [],
            scenario=scenario or "direct",
            skill_ids=list(skill_ids) if skill_ids else [],
        )

    return _provider  # type: ignore[return-value]


def _parse_heartbeat_from_im_payload(
    raw: object,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse heartbeat cadence fields from an IM agent config payload.

    feat-394 decision 5 / M9-E: enable state lives in features["heartbeat"] (decision D).
    This function only extracts cadence data: every, active_hours_{start,end,timezone}.

    Args:
        raw: The raw value of ``payload["heartbeat"]`` from an IM API response.

    Returns:
        4-tuple of (heartbeat_every, active_hours_start, active_hours_end,
        active_hours_timezone).  All fields are None when absent.
    """
    if not isinstance(raw, dict):
        return None, None, None, None
    every_raw = raw.get("every")
    heartbeat_every = (
        every_raw.strip() if isinstance(every_raw, str) and every_raw.strip() else None
    )
    active_hours_raw = raw.get("active_hours")
    if isinstance(active_hours_raw, dict):
        start_raw = active_hours_raw.get("start")
        end_raw = active_hours_raw.get("end")
        tz_raw = active_hours_raw.get("timezone")
        hb_start = (
            start_raw.strip()
            if isinstance(start_raw, str) and start_raw.strip()
            else None
        )
        hb_end = (
            end_raw.strip() if isinstance(end_raw, str) and end_raw.strip() else None
        )
        hb_tz = tz_raw.strip() if isinstance(tz_raw, str) and tz_raw.strip() else None
    else:
        hb_start, hb_end, hb_tz = None, None, None
    return heartbeat_every, hb_start, hb_end, hb_tz


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config.

    refactor-387 M3: kernel is now in-process via agent.sdk.  No kernel child
    process is spawned; GatewayProcessManager is no longer used here.
    """
    # refactor-387-M4: import from agent.sdk only
    from agent.sdk import (
        build_kernel,
        LLMFactoryConfig as _LLMFactoryConfig,
        PERSONAL_ASSISTANT_PROFILE,
    )

    # PA does not supply can_use_tool: permission ask always parks on broker future
    # and is resolved by the user clicking Allow/Deny on the IM card via
    # kernel.submit_permission_decision.  Unattended origins (heartbeat/cron) short-circuit
    # before reaching ask via auto_mode_gate's unattended_fallback — they never park.
    llm_factory_config = _LLMFactoryConfig.from_env()

    # bugfix-402-M4 R4: create a mutable GatewayCronDispatcher before build_kernel so the
    # dispatcher reference can be injected into the kernel's base ToolContext immediately.
    # Per-agent CronExecutionService instances are registered after kernel_shim is ready
    # (execute_fn captures kernel_shim; services dict is mutable so register() works post-build).
    _cron_dispatcher = GatewayCronDispatcher()

    kernel = build_kernel(
        product_profile=PERSONAL_ASSISTANT_PROFILE,
        llm_config=llm_factory_config,
        host_capabilities=_cron_dispatcher,
        # can_use_tool=None: IM card flow; see submit_permission_decision.
    )

    # Wrap Kernel as a _KernelClientLike shim so HeartbeatScheduler and
    # InternalDispatchHandler (which still use kernel_client protocol) work
    # without modification until M4 cleanup.
    kernel_shim = _KernelClientShim(kernel)

    runtime_dir = config.source_path.parent
    channel_registry = _build_channel_registry(
        config.channels,
        dedup_db_path=runtime_dir / "relay_dedup.sqlite3",
    )
    outbound_router = OutboundRouter(channel_registry)
    # Use SQLite-backed store so kernel session mappings survive gateway restarts
    # (NodeGateway-SPEC §4.2).  Live session validation is done via kernel.get_session
    # inside InboundPipeline._binding_matches_workspace_root — no kernel_client needed.
    # Must be created before HeartbeatScheduler so the store can be injected for
    # tick-time canonical session lookup (feat-394 decision 3).
    session_store = PersistentSessionBindingStore(
        db_path=runtime_dir / "session_bindings.sqlite3"
    )
    # feat-394 decision 3: canonical direct-chat kernel session store.
    # Updated by HeartbeatScheduler.tick() via session_store.find_direct_by_agent()
    # BEFORE each run submission (tick-time read, no reactive ack dependency).
    # This replaces the prior approach of populating from turn_start ack, which failed
    # for first-tick / restart / silent-polling scenarios (silent polls never ack → never fill).
    _canonical_session_store: dict[str, str] = {}
    _heartbeat_scheduler = HeartbeatScheduler(
        agents=config.agents,
        kernel_client=kernel_shim,
        state_store=HeartbeatSchedulerStateStore(_default_heartbeat_state_path(config)),
        canonical_session_store=_canonical_session_store,
        session_store=session_store,
    )
    reporter: UpstreamReporter | None = None
    im_connection_manager: IMConnectionManager | None = None
    im_bootstrap_client: _IMBootstrapClient | None = None
    im_config_sync_client: _IMConfigSyncClient | None = None
    post_im_connect: Callable[[], None] | None = None
    _run_context_store: dict[str, dict[str, str]] = {}
    # feat-393: heartbeat_runner is built here (before im_connection_manager which references it),
    # but the kernel_event_observer is wired after im_service block via attribute set below.
    # NOTE: session_store + _heartbeat_scheduler are constructed earlier (feat-394 moved
    # them up so HeartbeatScheduler can take the store for tick-time canonical lookup);
    # this supersedes origin/main's simpler heartbeat_runner/session_store block here.
    _owner_user_id = config.node.user_id or ""
    heartbeat_runner = PollingHeartbeatRunner(
        scheduler=_heartbeat_scheduler,
        config=config.heartbeat,
        kernel=kernel if _owner_user_id else None,
        run_context_store=_run_context_store if _owner_user_id else None,
        owner_user_id=_owner_user_id,
        # kernel_event_observer is set below after _build_kernel_event_observer runs.
    )
    _gateway_internal_port = 8089
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=config.agents,
        outbound_router=outbound_router,
        run_queue=SessionRunQueue(),
        session_store=session_store,
        group_context_store=GroupContextStore(
            db_path=runtime_dir / "group_context_buffer.sqlite3"
        ),
        gateway_internal_port=_gateway_internal_port,
    )
    if config.im_service is not None:
        relay_adapter = channel_registry.get("web_relay")
        if not isinstance(relay_adapter, WebRelayAdapter):
            raise ValueError("im_service requires enabled web_relay channel")
        reporter = UpstreamReporter(
            node=config.node,
            agents=config.agents,
            send_frame=lambda _message_type, _payload: None,
            capabilities=build_runtime_capabilities(),
        )
        im_config_sync_client = _IMConfigSyncClient(
            base_url=config.im_service.url,
            token=config.im_service.token,
            pipeline=pipeline,
            local_config=config,
            reporter=reporter,
        )
        # Build a token_getter closure that auto-refreshes the access token on reconnect.
        # The auth client uses the IM HTTP base URL so it can reach /im/v1/auth/* endpoints.
        _auth_client = IMAuthClient(base_url=_im_http_base_url(config.im_service.url))
        _raw_token_getter = _make_token_getter(
            im_service=config.im_service,
            local_config=config,
            auth_client=_auth_client,
        )
        # feat-394-M3 fix: wrap token_getter so each successful token refresh also
        # propagates the new token to im_config_sync_client.  Without this, auto-bind
        # refreshes the token for WS reconnection but the sync client keeps the old
        # empty token, causing every sync_agent call to return 401.
        _sync_client_ref = im_config_sync_client

        async def _token_getter() -> str | None:
            token = await _raw_token_getter()
            if token is not None:
                _sync_client_ref.update_token(token)
            return token

        # M3: permission response handler is no longer wired — the SDK's can_use_tool
        # callback handles all permission decisions in-process (design decision 3).
        _im_sync_client = ConfigSyncClient(fetcher=im_config_sync_client.sync_agent)

        # bugfix-402-M6: wire cron service registration into the agent-create callback
        # so dynamically created agents (via IM agent.create push) also get a
        # CronExecutionService registered before their first cron tick fires.
        def _on_agent_created(agent_id: str, workspace_root: Path) -> None:
            _register_cron_service(agent_id, workspace_root)

        im_config_sync_client.on_agent_created = _on_agent_created

        # feat-394-M12 决策 F: reconcile 回调——WS bind 完成后（含重连）拉全量 profile
        # 对账，消除漏推送导致的内存状态滞留。reconcile_all_agents 是同步 HTTP 调用，
        # 用 asyncio.to_thread 包装使其在 WS 事件循环中安全运行。
        async def _reconcile_on_connect() -> None:
            memory_versions = {
                agent_id: ver
                for agent_id in (a.agent_id for a in config.agents)
                if (ver := _im_sync_client.latest_profile_version(agent_id)) is not None
            }
            await asyncio.to_thread(
                im_config_sync_client.reconcile_all_agents,
                memory_versions=memory_versions,
            )

        im_connection_manager = _build_im_connection_manager(
            config=config,
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_runner=heartbeat_runner,
            sync_client=_im_sync_client,
            agent_config_provider=lambda agent_id: (
                im_config_sync_client.current_agent_payload(agent_id=agent_id)
            ),
            agent_capabilities_provider=lambda agent_id, workspace_root: (
                build_agent_capabilities_payload(
                    workspace_root=workspace_root,
                    tool_allowlist=_resolve_agent_tool_allowlist(
                        im_config_sync_client, agent_id
                    ),
                )
            ),
            # sdk-fix-prompt-preview: assemble_prompt_preview is now available on the
            # in-process Kernel (refactor-387 M3 regression fix).  The provider
            # signature matches PromptPreviewProvider: (agent_id, workspace_root,
            # features, custom_prompt, tool_ids, scenario, skill_ids) → preview dict.
            prompt_preview_provider=_make_prompt_preview_provider(kernel),
            agent_create_handler=im_config_sync_client.handle_agent_create,
            token_getter=_token_getter,
            permission_response_handler=_build_permission_response_handler(
                kernel=kernel
            ),
            on_connected=_reconcile_on_connect,
        )
        im_bootstrap_client = _IMBootstrapClient(
            base_url=_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=_token_getter,
        )
        post_im_connect = lambda: im_bootstrap_client.ensure_node_binding(
            node_id=config.node.node_id
        )
    pipeline._relay_lifecycle_callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=_run_context_store,
    )
    if config.im_service is not None:
        _kernel_event_observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: im_connection_manager,
            run_context_store=_run_context_store,
        )
        pipeline._kernel_event_observer = _kernel_event_observer
        # feat-393: wire observer into heartbeat_runner now that it's built.
        # When im_service is absent the runner runs fire-and-forget (no observer, no delivery).
        if _owner_user_id:
            heartbeat_runner._kernel_event_observer = _kernel_event_observer  # noqa: SLF001
        else:
            # No owner bound → heartbeat delivery disabled; clear kernel reference.
            heartbeat_runner._kernel = None  # noqa: SLF001
            heartbeat_runner._run_context_store = None  # noqa: SLF001
        # feat-349-M3: wire background session event callback so self_evolution_review
        # events published by background hooks reach IM as system/meta messages.
        pipeline._session_event_callback = _build_session_event_callback(
            im_connection_manager_factory=lambda: im_connection_manager,
            session_store=pipeline._session_store,
        )

    # bugfix-402-M4 R4 / bugfix-402-M6: build per-agent CronExecutionService and
    # register with dispatcher.  execute_fn is a closure that captures kernel_shim,
    # kernel, heartbeat_runner, etc.  All captured references are set before the
    # first cron tick fires.  _canonical_session_store and
    # heartbeat_runner._kernel_event_observer use late binding: they may be None
    # at construction time but are populated by the im_service block before any
    # tick runs.
    #
    # bugfix-402-M6 key fix: workspace_root key normalisation.  register() always
    # stores the key as str(Path.expanduser().resolve()).  _resolve_service() does
    # the same normalisation.  Both static (config.agents) and dynamic
    # (handle_agent_create) registration paths go through _register_cron_service
    # so the key is always consistent.
    def _register_cron_service(agent_id: str, ws_root: Path) -> None:
        """Create a CronExecutionService for agent and register it with the dispatcher.

        bugfix-402-M6: extracted from the startup loop so handle_agent_create can
        call the same path for dynamically created agents.
        workspace_root must already be resolved (expanduser().resolve()).
        """
        # Skip if already registered (idempotent — reconcile may call multiple times).
        if _cron_dispatcher._resolve_service(str(ws_root)) is not None:  # noqa: SLF001
            return
        execute_fn = _build_cron_execute_fn(agent_id=agent_id, ws_root=ws_root)
        service = CronExecutionService(
            agent_id=agent_id,
            workspace_root=ws_root,
            execute_fn=execute_fn,
        )
        _cron_dispatcher.register(ws_root, service)
        # Converge stale accepted/running records from any previous crash so they
        # are never permanently in-progress.
        service.runs_store.converge_stale_on_restart()
        # If the Gateway loop is already running (dynamic agent create path),
        # inject it immediately so enqueue() can schedule execute_fn.
        try:
            import asyncio as _asyncio  # noqa: PLC0415

            running_loop = _asyncio.get_running_loop()
            service._gateway_loop = running_loop  # noqa: SLF001
        except RuntimeError:
            # Not inside a running event loop — loop will be injected later
            # via GatewayCronDispatcher.set_gateway_loop() in _run_until_shutdown.
            pass

    def _build_cron_execute_fn(
        agent_id: str,
        ws_root: Path,
    ):
        """Return the execute_fn for a single agent's CronExecutionService.

        bugfix-402-M4: both scheduled ticks and manual tool calls share this
        execution chain.  CronRunner is instantiated once per agent (not per tick)
        so session binding state is preserved across runs.
        """
        _cron_runner = CronRunner(
            agent_id=agent_id,
            workspace_root=ws_root,
            kernel_client=kernel_shim,
            session_binding_store=session_store,
        )

        async def _execute(
            *, agent_id: str, job_id: str, request_id: str, trigger: str
        ) -> None:
            """Submit cron job then stream result to IM direct chat.

            bugfix-402-M4 Decision 2: replaces per-tick _submit_and_deliver_fn.
            Both scheduled and manual triggers enter here via CronExecutionService.enqueue().
            Writes accepted→running→(completed|failed) state transitions to runs.jsonl.
            """
            from personal_assistant.scheduler.cron_execution_service import (
                CronRunsStore,
            )  # noqa: PLC0415

            _runs_store = CronRunsStore(workspace_root=ws_root)
            _now = datetime.now(timezone.utc).isoformat()

            job_store = CronJobStore(workspace_root=ws_root)
            job = job_store.get(job_id)
            if job is None:
                _log.warning(
                    "cron execute: job not found at execution time: agent=%s job=%s request=%s",
                    agent_id,
                    job_id,
                    request_id,
                )
                _runs_store.update_status(
                    request_id,
                    "failed",
                    finished_at=_now,
                    error="job_not_found",
                )
                return

            _runs_store.update_status(request_id, "running", started_at=_now)

            # _submit_cron_job returns (run_id, kernel_session_id) or None.
            result = await _cron_runner._submit_cron_job(job=job)  # noqa: SLF001
            if result is None:
                _log.warning(
                    "cron: submit returned no result: agent=%s job=%s request=%s",
                    agent_id,
                    job_id,
                    request_id,
                )
                _runs_store.update_status(
                    request_id,
                    "failed",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error="submit_failed",
                )
                return
            run_id, kernel_session_id = result
            _runs_store.update_status(request_id, "running", kernel_run_id=run_id)

            # Observer is set on heartbeat_runner after im_service block; read at call time.
            _observer = heartbeat_runner._kernel_event_observer  # noqa: SLF001

            if not _owner_user_id or _observer is None:
                # No IM delivery path: fire-and-forget is correct.
                _log.debug(
                    "cron: no delivery path configured (owner=%r), skipping stream",
                    _owner_user_id,
                )
                _runs_store.update_status(
                    request_id,
                    "completed",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    result_summary="no_delivery_path",
                )
                return

            # Deliver result to IM by consuming the kernel stream.
            final_result_text = ""
            try:
                final_result_text, _ = await _stream_run_to_completion(
                    run_id=run_id,
                    kernel_session_id=kernel_session_id,
                    agent_id=agent_id,
                    owner_user_id=_owner_user_id,
                    kernel=kernel,
                    run_context_store=_run_context_store,
                    observer=_observer,
                    stream_anchor=0,
                )
            except Exception:  # noqa: BLE001
                _log.exception(
                    "cron: stream consume failed: agent=%s job=%s run=%s",
                    agent_id,
                    job_id,
                    run_id,
                )
                _runs_store.update_status(
                    request_id,
                    "failed",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error="stream_failed",
                )
                return

            _runs_store.update_status(
                request_id,
                "completed",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=(final_result_text[:200] if final_result_text else ""),
            )

            # Decision C-awareness: append result text as System(untrusted) to canonical
            # direct-chat JSONL so user can ask follow-up questions about cron output.
            if final_result_text:
                # feat-394-M8 R6-2 fix: two-source canonical session resolution (priority order).
                # (1) _canonical_session_store — populated by HeartbeatScheduler.tick().
                # (2) _cron_runner._resolve_canonical_session_id() — SQLite session_bindings.
                _awareness_session_id = (
                    _canonical_session_store.get(agent_id)
                    or _cron_runner._resolve_canonical_session_id()  # noqa: SLF001
                )
                if _awareness_session_id:
                    try:
                        await _cron_runner._append_awareness(  # noqa: SLF001
                            session_id=_awareness_session_id,
                            result_text=final_result_text,
                            workspace_root=ws_root,
                        )
                    except Exception:  # noqa: BLE001
                        _log.warning(
                            "cron: awareness inject failed: agent=%s job=%s session=%s",
                            agent_id,
                            job_id,
                            _awareness_session_id,
                        )
                else:
                    _log.debug(
                        "cron: awareness skip — no canonical session for agent=%s",
                        agent_id,
                    )

        return _execute

    # Create one CronExecutionService per configured agent and register with dispatcher.
    # bugfix-402-M6: use _register_cron_service so dynamic (handle_agent_create) and
    # static (startup) paths share the same key normalisation.
    for _agent_cfg in config.agents:
        _agent_ws_root = Path(_agent_cfg.workspace_root).expanduser().resolve()
        _register_cron_service(_agent_cfg.agent_id, _agent_ws_root)

    # feat-394-M3 CRITICAL-1 fix: wire cron tick into the unified polling runner.
    # bugfix-402-M4 R4: _cron_tick_for_agent now uses CronExecutionService.enqueue()
    # instead of building a submit_fn closure per tick.  Both scheduled and manual
    # triggers share the same execute chain via the dispatcher.
    async def _cron_tick_for_agent(agent_id: str) -> None:
        """Evaluate cron jobs for one agent and enqueue due runs via CronExecutionService.

        bugfix-402-M4 R4: replaces per-tick CronRunner+submit_fn with a call to the
        shared CronExecutionService.enqueue(trigger="scheduled") for each due job.
        CronScheduler still handles due-time computation and last_due_at persistence.
        """
        agent_cfg = pipeline._agents.get(agent_id)  # noqa: SLF001
        if agent_cfg is None or not getattr(agent_cfg, "cron_enabled", False):
            return
        ws_root = Path(agent_cfg.workspace_root).expanduser().resolve()

        # Route to the CronExecutionService for this agent.
        _service = _cron_dispatcher._resolve_service(str(ws_root))  # noqa: SLF001
        if _service is None:
            # Agent was dynamically registered after startup (IM config sync) without a
            # corresponding CronExecutionService.  Warn and skip — the service will be
            # created on the next Gateway restart when the agent appears in config.agents.
            _log.warning(
                "cron tick: no CronExecutionService for agent=%s ws=%s; skipping",
                agent_id,
                ws_root,
            )
            return

        job_store = CronJobStore(workspace_root=ws_root)
        # Per-agent state path so job last_due timestamps are isolated per agent.
        state_store = CronSchedulerStateStore(
            state_path=ws_root / _WCD / "cron" / "state.json"
        )

        # Use CronScheduler only for due-time computation; submit via CronExecutionService.
        async def _enqueue_via_service(*, agent_id: str, job: object) -> None:
            """Bridge CronScheduler.tick() → CronExecutionService.enqueue()."""
            job_id = getattr(job, "id", None)
            if not job_id:
                return
            _service.enqueue(job_id=job_id, trigger="scheduled")

        scheduler = CronScheduler(
            agent_id=agent_id,
            job_store=job_store,
            state_store=state_store,
            submit_fn=_enqueue_via_service,
        )
        await scheduler.tick()

    # Provide agents dict reference (closure over pipeline for dynamic updates).
    heartbeat_runner._cron_tick_fn = _cron_tick_for_agent  # noqa: SLF001
    heartbeat_runner._agents = pipeline._agents  # noqa: SLF001
    # feat-394-M4 R3 S1.3 fix: wire a live agents_getter into the heartbeat scheduler
    # so each tick reads the current agent config from pipeline._agents rather than the
    # frozen config.agents tuple captured at init time.  This lets heartbeat_enabled=False
    # take effect on the next tick without requiring a gateway restart.
    _heartbeat_scheduler._agents_getter = lambda: pipeline._agents.values()  # noqa: SLF001
    # feat-394-M4 R2-3 fix: wire SessionRunQueue into scheduler so heartbeat skips
    # when a user message is currently being processed on the canonical session.
    # This prevents the heartbeat LLM call from blocking user message responses.
    _heartbeat_scheduler._run_queue = pipeline._run_queue  # noqa: SLF001

    inbound_dispatcher = _InboundDispatcher(pipeline)
    # bugfix-402-M3 R3: kernel is closed explicitly via GatewayRuntime(kernel=) and
    # its aclose() in the ordered shutdown phase (Decision 7). It must not be in
    # resource_closers — that list only holds lightweight sync cleanup (HTTP clients).
    closers: list[Callable[[], None]] = []
    if im_bootstrap_client is not None:
        closers.append(im_bootstrap_client.close)
    if im_config_sync_client is not None:
        closers.append(im_config_sync_client.close)
    internal_dispatch_handler = InternalDispatchHandler(
        im_connection_manager=im_connection_manager,
        kernel_client=kernel_shim,
        session_store=session_store,
        agent_workspace_roots={
            agent.agent_id: str(agent.workspace_root) for agent in config.agents
        },
    )
    return GatewayRuntime(
        config,
        None,  # no kernel subprocess — kernel runs in-process (M3+)
        channel_registry=channel_registry,
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=im_connection_manager,
        on_inbound=inbound_dispatcher,
        post_im_connect=post_im_connect,
        resource_closers=tuple(closers),
        internal_dispatch_handler=internal_dispatch_handler,
        kernel=kernel,
        cron_dispatcher=_cron_dispatcher,
        gateway_internal_port=_gateway_internal_port,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""

    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description="Run personal assistant gateway runtime"
    )
    parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    parser.add_argument(
        "--auto-bind",
        action="store_true",
        help=(
            "Automatically confirm the IM node binding instead of opening a browser URL. "
            "Equivalent to setting NANO_MULTIAGENT_AUTO_BIND=1. "
            "Intended for worktree e2e scripts where no human can click the bind URL."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    stop_parser = subparsers.add_parser(
        "stop", help="Stop the current background gateway for one config"
    )
    stop_parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    stop_parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    restart_parser = subparsers.add_parser(
        "restart",
        help="Stop then start the background gateway (equivalent to stop + start)",
    )
    restart_parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    restart_parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    args = parser.parse_args(argv)
    command = args.command or "start"
    resolved_config_path = (
        str(Path(args.config).expanduser())
        if args.config
        else str(default_local_config_path())
    )
    if getattr(args, "auto_bind", False):
        os.environ["NANO_MULTIAGENT_AUTO_BIND"] = "1"
    try:
        if command == "stop":
            print(stop_gateway(config_path=resolved_config_path))
            return 0
        if command == "restart":
            # Ignore NOT RUNNING / STALE statuses — they are not errors during restart.
            stop_gateway(config_path=resolved_config_path)
            result = launch_gateway_in_background(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
            _print_gateway_started(result)
            return 0
        if args.foreground:
            return run_gateway(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
        result = launch_gateway_in_background(
            config_path=resolved_config_path,
            im_service_url_override=args.im_service_url,
        )
        _print_gateway_started(result)
        return 0
    except GatewayStartupError as exc:
        _emit_gateway_feedback("ERROR", exc.summary, exc.next_step)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


def _coerce_factories(
    factories: RuntimeFactories | Mapping[str, Any] | None,
) -> RuntimeFactories:
    if factories is None:
        return RuntimeFactories()
    if isinstance(factories, RuntimeFactories):
        return factories
    load_config = factories.get("load_config", load_local_config)
    build_runtime_factory = factories.get("build_runtime")
    install_signal_handlers = factories.get("install_signal_handlers")
    return RuntimeFactories(
        load_config=load_config,
        build_runtime=build_runtime_factory,
        install_signal_handlers=install_signal_handlers,
    )


def _build_channel_registry(
    channels: tuple[ChannelConfig, ...],
    *,
    dedup_db_path: Path | None = None,
) -> ChannelRegistry:
    registry = ChannelRegistry()
    for channel in channels:
        if not channel.enabled:
            continue
        if channel.name == "web_relay":
            dedup_store = None
            if dedup_db_path is not None:
                dedup_store = RelayDeduplicationStore(db_path=dedup_db_path)
            registry.register(WebRelayAdapter(dedup_store=dedup_store))
            continue
        raise ValueError(f"unsupported channel adapter: {channel.name}")
    return registry


def _make_token_getter(
    *,
    im_service: IMServiceConfig,
    local_config: LocalConfig,
    auth_client: IMAuthClient,
    save_config: Callable[[LocalConfig, Path], None] = save_local_config,
) -> Callable[[], Awaitable[str | None]]:
    """Build an async closure that returns a fresh access token before each reconnect.

    Priority:
    1. If ``im_service.refresh_token`` is set, call ``IMAuthClient.refresh()``.
    2. If refresh fails and ``im_service.username`` + ``im_service.password`` are set,
       call ``IMAuthClient.login()`` as a fallback.
    3. If neither credential is available, return ``im_service.token`` unchanged
       (backwards-compatible behaviour for configs without auto-refresh).

    On success the returned (access_token, refresh_token) pair is persisted back into
    config.yaml so the new refresh token is available on the next process restart.

    Args:
        im_service: IM connectivity settings containing token credentials.
        local_config: Full gateway config used for ``save_config`` persistence path.
        auth_client: HTTP client implementing refresh/login against the IM auth API.
        save_config: Callable used to persist the updated config (injectable for tests).

    Returns:
        Async zero-argument callable that resolves to the latest access token or None.
    """
    # Mutable state: keep a local reference so token rotation is visible across calls
    # within the same gateway process lifetime.
    _state: dict[str, str | None] = {
        "refresh_token": im_service.refresh_token,
        "token": im_service.token,
    }
    _config_holder: list[LocalConfig] = [local_config]

    async def _getter() -> str | None:
        current_refresh = _state["refresh_token"]
        if current_refresh is not None:
            try:
                access, new_refresh = await auth_client.refresh(current_refresh)
                _state["token"] = access
                _state["refresh_token"] = new_refresh
                _persist(access, new_refresh)
                return access
            except IMAuthError:
                # Refresh token expired or revoked — fall through to credential login.
                pass

        username = im_service.username
        password = im_service.password
        if username and password:
            try:
                access, new_refresh = await auth_client.login(
                    username=username, password=password
                )
                _state["token"] = access
                _state["refresh_token"] = new_refresh
                _persist(access, new_refresh)
                return access
            except IMAuthError:
                pass

        # No dynamic auth configured or all methods failed — use the static token.
        return _state["token"]

    def _persist(access: str, new_refresh: str) -> None:
        current_cfg = _config_holder[0]
        old_im = current_cfg.im_service
        if old_im is None:
            return
        updated_im = IMServiceConfig(
            url=old_im.url,
            token=access,
            refresh_token=new_refresh,
            username=old_im.username,
            password=old_im.password,
        )
        new_cfg = replace(current_cfg, im_service=updated_im)
        _config_holder[0] = new_cfg
        save_config(new_cfg, new_cfg.source_path)

    return _getter


def _build_im_connection_manager(
    *,
    config: LocalConfig,
    relay_adapter: WebRelayAdapter,
    reporter: UpstreamReporter,
    heartbeat_runner: PollingHeartbeatRunner,
    sync_client: ConfigSyncClient | None = None,
    agent_config_provider: Callable[[str], dict[str, object] | None] | None = None,
    agent_capabilities_provider: Callable[[str, str], dict[str, object]] | None = None,
    prompt_preview_provider: Callable[..., Any] | None = None,
    agent_create_handler: AgentCreateHandler | None = None,
    token_getter: Callable[[], Awaitable[str | None]] | None = None,
    permission_response_handler: Callable[[Mapping[str, object]], None] | None = None,
    on_connected: Callable[[], Awaitable[None]] | None = None,
) -> IMConnectionManager:
    im_service = config.im_service
    if im_service is None:
        raise ValueError("im_service configuration is required")
    return IMConnectionManager(
        config=IMConnectionConfig(url=im_service.url, token=im_service.token),
        reporter=reporter,
        relay_adapter=relay_adapter,
        sync_client=sync_client,
        heartbeat_trigger=lambda _agent_id, _reason: heartbeat_runner.request_tick(),
        agent_config_provider=agent_config_provider,
        agent_capabilities_provider=agent_capabilities_provider,
        prompt_preview_provider=prompt_preview_provider,
        agent_create_handler=agent_create_handler,
        token_getter=token_getter,
        connect=_connect_websocket,
        permission_response_handler=permission_response_handler,
        on_connected=on_connected,
    )


def _build_permission_response_handler(
    *,
    kernel: Any,
) -> Callable[[Mapping[str, object]], None]:
    """Build handler that routes IM permission_response frames to the kernel.

    The frame carries ``request_id``, ``decision``, and an optional ``reason``.
    request_id is globally unique (assigned by auto_mode_gate at ask time), so
    no session lookup is required — the broker finds the pending future by id.
    """

    def _handler(body: Mapping[str, object]) -> None:
        request_id = str(body.get("request_id") or "").strip()
        decision = str(body.get("decision") or "").strip()
        if not request_id or not decision:
            return
        reason = str(body.get("reason") or "").strip()
        try:
            kernel.submit_permission_decision(
                request_id=request_id,
                decision=decision,
                reason=reason,
            )
        except Exception:  # noqa: BLE001 — IM-bound side-effect; failure must not cascade
            return

    return _handler


def _build_relay_lifecycle_callback(
    *,
    reporter: UpstreamReporter | None,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: dict[str, dict[str, str]] | None = None,
):
    async def _callback(message: InboundMessage, update: RelayLifecycleUpdate) -> None:
        if reporter is None:
            return
        relay_task_id = _metadata_text(message.metadata, key="relay_task_id")
        if relay_task_id is None:
            return
        manager = im_connection_manager_factory()
        if manager is None:
            return
        if update.phase == "accepted":
            # Seed run_context_store with conversation/agent meta so kernel_event_observer
            # can send the turn_start frame.  message_id starts empty; it is filled
            # by the turn_start ack (gateway returns the created placeholder message_id).
            if run_context_store is not None and update.run_id:
                conversation_id = message.external_chat_id or ""
                agent_id_meta = (
                    _metadata_text(message.metadata, key="agent_id")
                    or update.agent_id
                    or ""
                )
                run_context_store[update.run_id] = {
                    "conversation_id": conversation_id,
                    "message_id": "",  # filled by turn_start ack
                    "agent_id": agent_id_meta,
                    # Stored so permission_response_handler can route the user's
                    # decision back to the correct kernel session via reverse lookup.
                    "kernel_session_id": update.kernel_session_id or "",
                }
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="sent",
                detail=f"run_id={update.run_id}" if update.run_id is not None else None,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "running":
            message_id = _metadata_text(message.metadata, key="message_id")
            if message_id is None or update.run_id is None:
                return
            payload = reporter.send_report(
                run_id=update.run_id,
                status="running",
                agent_id=update.agent_id,
                session_key=update.session_key,
                conversation_id=message.external_chat_id,
                message_id=message_id,
                summary=update.reply_text,
            )
            await manager.send_json("node.report", payload)
            return
        if update.phase == "completed":
            if run_context_store is not None and update.run_id:
                run_context_store.pop(update.run_id, None)
            message_id = _metadata_text(message.metadata, key="message_id")
            send_report = getattr(reporter, "send_report", None)
            if (
                callable(send_report)
                and message_id is not None
                and update.run_id is not None
            ):
                payload = send_report(
                    run_id=update.run_id,
                    status="completed",
                    agent_id=update.agent_id,
                    session_key=update.session_key,
                    conversation_id=message.external_chat_id,
                    message_id=message_id,
                    summary=update.reply_text,
                    detail=update.detail,
                    usage=update.usage,
                )
                await manager.send_json("node.report", payload)
            suppression_detail = None
            if update.detail is not None:
                detail_parts = [
                    f"{key}={value}" for key, value in update.detail.items()
                ]
                suppression_detail = " | ".join(detail_parts) if detail_parts else None
            receipt_detail = update.reply_text
            if suppression_detail is not None:
                receipt_detail = (
                    suppression_detail
                    if InboundPipeline._is_no_reply_token(update.reply_text or "")
                    else (
                        " | ".join(
                            [
                                part
                                for part in [receipt_detail, suppression_detail]
                                if part
                            ]
                        )
                        or None
                    )
                )
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="completed",
                detail=receipt_detail,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "failed":
            if run_context_store is not None and update.run_id:
                run_context_store.pop(update.run_id, None)
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="failed",
                detail=update.error,
            )
            await manager.send_json("node.delivery_receipt", payload)

    return _callback


def _build_kernel_event_observer(
    *,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: dict[str, dict[str, str]],
) -> Callable[[Mapping[str, Any]], "Coroutine[Any, Any, None] | None"]:
    """Build a kernel SSE event observer that forwards streaming events to IM via node.streaming_delta.

    The observer returns a coroutine for run_status=running so the pipeline can
    await the turn_start ack before processing the following assistant_message event.
    For all other events the observer schedules tasks and returns None.

    Kernel SSE events translated:
    - run_status=running  → node.streaming_delta kind=turn_start (creates placeholder message)
    - assistant_message   → node.streaming_delta kind=message_delta
    - tool_start          → node.streaming_delta kind=tool_call_upserted
    - tool_end            → node.streaming_delta kind=tool_call_completed
    - turn_end            → node.streaming_delta kind=message_completed (with token_usage if available)

    Heartbeat lazy-bubble path (feat-393):
    - run_context_store entries with ``to_user_id`` (no ``conversation_id``) are heartbeat runs.
    - turn_start is deferred until the first non-empty, non-NO_REPLY assistant_message arrives.
    - NO_REPLY/empty content → no turn_start is ever sent → zero IM trace (silent tick).
    - Normal chat (conversation_id present) is unchanged (eager placeholder on run_status=running).

    Canonical session (feat-394 decision 3):
    - HeartbeatScheduler.tick() calls session_store.find_direct_by_agent() BEFORE each run
      submission to update canonical_session_store — tick-time read, no ack dependency.
    """

    async def _send(
        manager: IMConnectionManager, message_type: str, payload: Mapping[str, Any]
    ) -> None:
        try:
            await manager.send_json(message_type, payload)
        except Exception as exc:  # noqa: BLE001
            # IM send failure must not propagate into the event stream; log so the
            # drop is observable (refactor-395-M1).
            _log.warning("IM observer send failed for %s: %s", message_type, exc)

    def observer(event: Mapping[str, Any]) -> "Coroutine[Any, Any, None] | None":
        manager = im_connection_manager_factory()
        if manager is None or not manager.connected:
            return None
        run_id = str(event.get("run_id") or "").strip()
        if not run_id:
            return None
        ctx = run_context_store.get(run_id)
        if ctx is None:
            return None
        conversation_id = ctx.get("conversation_id") or ""
        message_id = ctx.get("message_id") or ""
        agent_id = ctx.get("agent_id") or ""

        # feat-393: heartbeat runs carry to_user_id instead of conversation_id.
        # The lazy-bubble gate: skip eager turn_start; defer to assistant_message.
        to_user_id = ctx.get("to_user_id") or ""

        event_name = str(event.get("event") or "").strip()
        loop = asyncio.get_event_loop()

        if event_name == "run_status" and event.get("status") == "running":
            if to_user_id:
                # Heartbeat: skip eager turn_start; bubble is created lazily on first
                # real content (see assistant_message branch below).
                return None
            if conversation_id and agent_id:
                # Return a coroutine so the pipeline awaits turn_start ack before processing
                # the following assistant_message; without awaiting, message_id would still be
                # empty when assistant_message fires and the delta would be silently dropped.
                async def _send_turn_start_and_store(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
                            },
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                    except Exception as exc:  # noqa: BLE001
                        _log.warning("IM observer turn_start send/ack failed: %s", exc)

                return _send_turn_start_and_store()

        elif event_name == "assistant_message":
            content = str(event.get("content") or "").strip()
            if not content:
                return None
            kernel_msg_id = str(event.get("message_id") or "").strip()
            prev_kernel_msg_id = ctx.get("kernel_message_id") or ""

            # feat-393 heartbeat lazy-bubble path:
            # When to_user_id is set and no bubble exists yet, this is the first real
            # content event.  Gate on NO_REPLY: if agent chose to be quiet → stay silent.
            # Otherwise fire turn_start{to_user_id}, get back the resolved conversation_id
            # and message_id, store them, then emit the delta so streaming starts.
            if to_user_id and not message_id:
                from personal_assistant.gateway.inbound_pipeline import (
                    InboundPipeline as _IP,
                )

                if _IP._is_no_reply_token(content):
                    # NO_REPLY: heartbeat has nothing to report; do not create any IM trace.
                    return None

                async def _heartbeat_lazy_turn_start(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    aid: str = agent_id,
                    uid: str = to_user_id,
                    text: str = content,
                    new_kernel_id: str = kernel_msg_id,
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "to_user_id": uid,
                                "agent_id": aid,
                                "run_id": rid,
                            },
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        returned_conv_id = (
                            ack_payload.get("conversation_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        skipped_reason = (
                            ack_payload.get("skipped")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        if skipped_reason:
                            # feat-393 fix-r1: IM skipped delivery (e.g. owner_unresolved).
                            # Per design decision-6: delivery failure ≠ run failure; log and
                            # let this heartbeat run finish normally — no exception, no retry.
                            import logging as _obs_logging  # noqa: PLC0415

                            _obs_logging.getLogger(__name__).warning(
                                "heartbeat delivery skipped for run_id=%s agent=%s: %s",
                                rid,
                                aid,
                                skipped_reason,
                            )
                            return
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                        if returned_conv_id and rid in run_context_store:
                            run_context_store[rid]["conversation_id"] = str(
                                returned_conv_id
                            )
                        if new_kernel_id and rid in run_context_store:
                            run_context_store[rid]["kernel_message_id"] = new_kernel_id
                        if returned_msg_id:
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": str(returned_msg_id),
                                    "delta_text": text,
                                    "run_id": rid,
                                },
                            )
                    except Exception:  # noqa: BLE001
                        pass

                return _heartbeat_lazy_turn_start()

            # Detect a new assistant message within the same run (e.g. textA → tool_calls → textB).
            # The kernel's while-loop generates a fresh assistant_msg_id per iteration; when it
            # differs from the previous one we must close the old IM message and start a new one
            # so the frontend renders textA and textB as separate bubbles.
            if (
                kernel_msg_id
                and prev_kernel_msg_id
                and kernel_msg_id != prev_kernel_msg_id
            ):

                async def _close_old_and_restart(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                    old_msg_id: str = message_id,
                    text: str = content,
                    new_kernel_id: str = kernel_msg_id,
                ) -> None:
                    try:
                        if old_msg_id:
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_completed",
                                    "message_id": old_msg_id,
                                    "final_content": None,
                                    "token_usage": None,
                                    "run_id": rid,
                                },
                            )
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
                            },
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                            run_context_store[rid]["kernel_message_id"] = new_kernel_id
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": str(returned_msg_id),
                                    "delta_text": text,
                                    "run_id": rid,
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "IM observer close/restart delta send failed: %s", exc
                        )

                return _close_old_and_restart()

            if message_id:
                # turn_start already ack'd — send delta directly.
                if kernel_msg_id:
                    ctx["kernel_message_id"] = kernel_msg_id
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "message_delta",
                            "message_id": message_id,
                            "delta_text": content,
                            "run_id": run_id,
                        },
                    )
                )
            elif conversation_id and agent_id:
                # Kernel skipped run_status=running; send turn_start inline and await ack
                # so we have message_id before the delta frame is dispatched.
                async def _turn_start_then_delta(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                    text: str = content,
                    new_kernel_id: str = kernel_msg_id,
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
                            },
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                            if new_kernel_id:
                                run_context_store[rid]["kernel_message_id"] = (
                                    new_kernel_id
                                )
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": str(returned_msg_id),
                                    "delta_text": text,
                                    "run_id": rid,
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "IM observer turn_start_then_delta send failed: %s", exc
                        )

                return _turn_start_then_delta()

        elif event_name == "turn_end":
            # bugfix-380 R3: completed=False = ModelError path.
            # Send message_completed with delivery_status="failed" to finalize the bubble
            # (error content was already sent via message_delta; final_content=None preserves it).
            # completed=True = normal success path, delivery_status defaults to "completed".
            turn_completed = event.get("completed") is not False

            # Finalize message with token_usage if present (only on success path).
            usage_raw = event.get("usage") if turn_completed else None
            token_usage_payload: dict[str, object] | None = None
            if isinstance(usage_raw, Mapping):
                prompt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens")
                completion = usage_raw.get("completion_tokens") or usage_raw.get(
                    "output_tokens"
                )
                if isinstance(prompt, int) and isinstance(completion, int):
                    token_usage_payload = {
                        "prompt": prompt,
                        "completion": completion,
                        "total": prompt + completion,
                    }
                    cw = event.get("context_window")
                    if isinstance(cw, int) and cw > 0:
                        token_usage_payload["context_window"] = cw
            if message_id:
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "message_completed",
                            "message_id": message_id,
                            "final_content": None,
                            "token_usage": token_usage_payload,
                            "delivery_status": "completed"
                            if turn_completed
                            else "failed",
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "tool_start":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
            if message_id:
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "tool_call_upserted",
                            "message_id": message_id,
                            "tool_call": {
                                "id": call_id,
                                "name": tool_name,
                                "status": "running",
                                "input": arguments
                                if isinstance(arguments, dict)
                                else {},
                            },
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "tool_end":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
            duration_ms = event.get("duration_ms")
            status = "failed" if event.get("error") else "completed"
            output_parts = []
            if event.get("error"):
                output_parts.append(str(event["error"]))
            pres = event.get("presentation")
            if isinstance(pres, Mapping) and pres.get("summary"):
                output_parts.append(str(pres["summary"]))
            if message_id:
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "tool_call_completed",
                            "message_id": message_id,
                            "tool_call": {
                                "id": call_id,
                                "name": tool_name,
                                "status": status,
                                "input": arguments
                                if isinstance(arguments, dict)
                                else {},
                                "output": " | ".join(output_parts)
                                if output_parts
                                else None,
                                "duration_ms": int(duration_ms)
                                if isinstance(duration_ms, (int, float))
                                else None,
                            },
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "permission_request":
            # Agent auto_mode_gate is awaiting a user decision; forward to IM so the
            # permission card can be rendered in the chat.  Only forwarded when we have
            # a message_id (turn_start already acked) so IM can attach the card to the
            # correct message row.  No message_id → card would be orphaned; skip.
            if message_id:
                request_id = str(event.get("request_id") or "").strip()
                tool_name = str(event.get("tool_name") or "").strip()
                tool_input = event.get("tool_input")
                question = str(event.get("question") or "").strip()
                options_raw = event.get("options")
                options = list(options_raw) if isinstance(options_raw, list) else []
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "permission_request",
                            "message_id": message_id,
                            "permission_request": {
                                "request_id": request_id,
                                "tool_name": tool_name,
                                "tool_input": dict(tool_input)
                                if isinstance(tool_input, Mapping)
                                else (tool_input or {}),
                                "question": question,
                                "options": options,
                                "status": "pending",
                            },
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "permission_resolved":
            # Agent resolved a permission request (hook resumed); update the IM card
            # so the user sees the final decision.
            if message_id:
                request_id = str(event.get("request_id") or "").strip()
                decision = str(event.get("decision") or "").strip()
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "permission_resolved",
                            "message_id": message_id,
                            "request_id": request_id,
                            "decision": decision,
                            "run_id": run_id,
                        },
                    )
                )

    return observer


def _build_session_event_callback(
    *,
    im_connection_manager_factory: Callable[[], "IMConnectionManager | None"],
    session_store: "SessionBindingStore",
) -> Callable[[str, Mapping[str, Any]], Awaitable[None]]:
    """Build a session event callback that sends self_evolution_review as IM system messages.

    When the background hook publishes ``self_evolution_review`` after a turn, this
    callback is invoked with the kernel_session_id and the raw event payload.  It
    resolves the conversation_id via the session binding store and sends a
    ``node.system_message`` frame to IM so users see a non-first-person notification.

    Args:
        im_connection_manager_factory: Returns the live IM connection manager (may be None).
        session_store: Gateway session binding store used to reverse-resolve conversation_id.

    Returns:
        Async callable ``(kernel_session_id, event) -> None``.
    """

    async def _callback(kernel_session_id: str, event: Mapping[str, Any]) -> None:
        manager = im_connection_manager_factory()
        if manager is None or not manager.connected:
            return

        event_name = event.get("event")
        if event_name != "self_evolution_review":
            return

        # Resolve conversation_id from the session binding.
        binding = session_store.find_by_kernel_session_id(kernel_session_id)
        if binding is None:
            return
        conversation_id = binding.reply_context.target_chat_id
        if not conversation_id:
            return

        # Format a human-readable system notification matching the CLI style.
        # The SSE event dict is flat: the hook's payload fields (reviewed_skills,
        # reviewed_memory) are merged to the top level by the kernel stream, not
        # nested under "data".  Reading event["data"] here always missed them and
        # degraded every notification to the generic "self-evolution" subject.
        reviewed_skills: bool = bool(event.get("reviewed_skills", False))
        reviewed_memory: bool = bool(event.get("reviewed_memory", False))
        if reviewed_skills and reviewed_memory:
            subject = "skills + memory"
        elif reviewed_skills:
            subject = "skills"
        elif reviewed_memory:
            subject = "memory"
        else:
            subject = "self-evolution"
        text = f"· background self-evolution review: {subject} updated"

        try:
            await manager.send_json(
                "node.system_message",
                {
                    "conversation_id": conversation_id,
                    "text": text,
                },
            )
        except Exception as exc:  # noqa: BLE001
            # Background notification delivery must never crash the gateway.
            _log.warning(
                "session event notification delivery failed (conversation_id=%s): %s",
                conversation_id,
                exc,
            )

    return _callback


def _metadata_text(metadata: Mapping[str, object], *, key: str) -> str | None:
    value = metadata.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field_name} must be a non-empty string")
    return value.strip()


def _default_heartbeat_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "heartbeat-state.json"


def _default_gateway_log_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "gateway.log"


def _extract_bind_token(bind_url: str) -> str | None:
    """Pull the ``token`` query parameter out of an IM bind URL.

    refactor-381: used by ``_IMBootstrapClient.ensure_node_binding`` when
    NANO_MULTIAGENT_AUTO_BIND=1 to programmatically confirm the binding.
    """

    parsed = urlparse(bind_url)
    qs = parse_qs(parsed.query)
    tokens = qs.get("token") or qs.get("bind_token") or []
    return tokens[0] if tokens else None


def _gateway_pid_path(config: LocalConfig) -> Path:
    """Return the PID file path used for single-instance protection.

    Returns:
        Path to ``gateway.pid`` inside the config's runtime directory.
    """
    return config.source_path.parent / "gateway.pid"


def _write_gateway_pid(config: LocalConfig) -> None:
    """Write the current process PID to ``gateway.pid``.

    Side Effects:
        Creates or overwrites ``gateway.pid`` in the runtime directory.
    """
    _gateway_pid_path(config).write_text(str(os.getpid()), encoding="utf-8")


def _remove_gateway_pid(config: LocalConfig) -> None:
    """Remove ``gateway.pid`` if it exists.

    Side Effects:
        Deletes the PID file; silently succeeds if the file is already gone.
    """
    with suppress(FileNotFoundError):
        _gateway_pid_path(config).unlink()


def _read_gateway_pid(config: LocalConfig) -> int | None:
    """Read and return the PID stored in ``gateway.pid``, or ``None`` if absent/invalid.

    Returns:
        Integer PID when the file exists and contains a parseable integer; ``None`` otherwise.
    """
    pid_path = _gateway_pid_path(config)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _gateway_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / ".gateway-state.json"


def _write_gateway_state(config: LocalConfig, result: BackgroundLaunchResult) -> None:
    state = GatewayRuntimeState(
        pid=result.pid,
        config_path=str(Path(config.source_path).resolve()),
        health_url=result.health_url,
        log_path=str(result.log_path),
    )
    _gateway_state_path(config).write_text(
        json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8"
    )


def _read_gateway_state(state_path: Path) -> GatewayRuntimeState | None:
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return GatewayRuntimeState(
        pid=int(payload["pid"]),
        config_path=str(payload["config_path"]),
        health_url=str(payload["health_url"]),
        log_path=str(payload["log_path"]),
    )


def _remove_gateway_state(state_path: Path) -> None:
    with suppress(FileNotFoundError):
        state_path.unlink()


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _resolve_agent_tool_allowlist(
    sync_client: "_IMConfigSyncClient",
    agent_id: str,
) -> tuple[str, ...]:
    """Return the tool_allowlist for an agent from the live local config snapshot.

    Used when building the agent capabilities payload so feature toggle availability
    can be evaluated against the current tool allowlist (feat-379 decision 7).

    Args:
        sync_client: The config sync client that holds the current LocalConfig.
        agent_id: Agent whose tool_allowlist to look up.

    Returns:
        Tuple of allowed tool names; empty tuple when agent is not found.
    """
    payload = sync_client.current_agent_payload(agent_id=agent_id)
    if payload is None:
        return ()
    raw = payload.get("tool_allowlist")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _im_http_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": "nano-multiagent-gateway-bootstrap"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _im_http_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "http":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "ws":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "wss":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    raise ValueError("IM URL must use http(s) or ws(s)")


def _im_bootstrap_base_urls(url: str) -> tuple[str, ...]:
    return (_im_http_base_url(url),)


def _background_gateway_argv(
    config_path: Path, *, im_service_url_override: str | None = None
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
    ]
    if isinstance(im_service_url_override, str) and im_service_url_override.strip():
        argv.extend(["--im-service-url", im_service_url_override.strip()])
    argv.append("--foreground")
    return argv


def _spawn_background_gateway_process(argv: list[str], log_path: Path) -> ProcessLike:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        return subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )


def _wait_for_gateway_ready(
    process: ProcessLike, config: LocalConfig, timeout_seconds: float
) -> None:
    """Wait for the background gateway to write its PID file (ready signal).

    refactor-387 M3: the kernel is in-process and has no HTTP health endpoint.
    We detect readiness by waiting for the gateway PID file to appear on disk —
    run_gateway() writes it via _write_gateway_pid() after runtime.run_forever() starts.
    """
    pid_path = _gateway_pid_path(config)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"gateway exited before ready with return code {process.poll()}"
            )
        if pid_path.exists():
            return
        time.sleep(config.kernel.health_poll_interval_seconds or 0.2)
    raise RuntimeError(
        "timed out waiting for gateway readiness (pid file never appeared)"
    )


def _stop_background_process(process: ProcessLike, *, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    # bugfix-359: Gateway 启动用 start_new_session=True,kernel uvicorn 子进程在同一个 pgid 下。
    # process.terminate() 只发给 Gateway pid,kernel 接不到。补一发 killpg 把整个会话带走;
    # fake/mock ProcessLike 的 pid 拿不到 pgid 时 _kill_process_tree 静默吞掉。
    _kill_process_tree(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=timeout_seconds)
    except (TimeoutError, subprocess.TimeoutExpired):
        process.kill()
        _kill_process_tree(process.pid, signal.SIGKILL)
        with suppress(TimeoutError, subprocess.TimeoutExpired):
            process.wait(timeout=timeout_seconds)


def _kill_process_tree(pid: int, sig: int) -> None:
    """Send ``sig`` to the entire process group led by ``pid``; falls back to single pid.

    Gateway 后台启动时 ``start_new_session=True``,kernel uvicorn 子进程在同一个 pgid 下。
    killpg 是唯一能一次性把 Gateway + kernel + 任何其它 Gateway 派生的孙进程都带走的方式。
    pgid 拿不到(进程刚消失)时静默吞掉,让上层走 wait 路径决定下一步。
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return


def _install_default_signal_handlers(
    runtime: GatewayRuntimeLike,
) -> SignalHandlerInstaller:
    def _installer() -> Callable[[], None]:
        if not isinstance(runtime, GatewayRuntime):
            return lambda: None
        if threading.current_thread() is not threading.main_thread():
            return lambda: None

        previous: dict[signal.Signals, Any] = {}

        def _handler(_signum: int, _frame: Any) -> None:
            runtime.request_shutdown()

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, _handler)

        def _restore() -> None:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

        return _restore

    return _installer


async def _connect_websocket(url: str, headers: Mapping[str, str]) -> ClientConnection:
    return await websockets.connect(
        url, additional_headers=dict(headers), user_agent_header=None
    )


async def _await_background_task(task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        _log.exception("background task raised unexpected exception: %s", exc)


def _consume_future_exception(future: object) -> None:
    result = getattr(future, "result", None)
    if callable(result):
        with suppress(asyncio.CancelledError):
            result()


def _spawn_process(command: str) -> ProcessLike:
    _kernel_log = Path("~/.nano-assistant/kernel.log").expanduser()
    _kernel_log.parent.mkdir(parents=True, exist_ok=True)
    _log_file = _kernel_log.open("ab")
    return subprocess.Popen(shlex.split(command), stdout=_log_file, stderr=_log_file)


if __name__ == "__main__":
    raise SystemExit(main())
