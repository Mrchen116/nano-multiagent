"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
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
from urllib.parse import urlparse

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.web_relay_adapter import RelayDeduplicationStore, WebRelayAdapter
from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    default_local_config_path,
    ensure_workspace_defaults,
    load_local_config,
    resolve_kernel_token,
    save_local_config,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_pipeline import InboundPipeline, RelayLifecycleUpdate
from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore, SessionBindingStore
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_agent_capabilities_payload,
    build_runtime_capabilities,
)
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
    HeartbeatTickSummary,
)
from personal_assistant.auth.im_auth_client import IMAuthClient, IMAuthError
from personal_assistant.ws.im_connection import AgentCreateHandler, IMConnectionConfig, IMConnectionManager


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
        cleaned_next_step = next_step.strip() if isinstance(next_step, str) and next_step.strip() else None
        super().__init__(cleaned_summary)
        self.summary = cleaned_summary
        self.next_step = cleaned_next_step


def _read_log_last_error(log_path: Path, *, offset: int = 0, lines: int = 20) -> str | None:
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
        status = "connected" if reachable else "unavailable (running offline, will retry)"
        print(f"IM service:      {result.im_service_url}  [{status}]")
    print(f"Log:             {result.log_path}")


def _emit_gateway_feedback(level: str, summary: str, next_step: str | None = None) -> None:
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

    def build_product_reports(self) -> list[dict[str, object]]:
        """Return IM-facing heartbeat report payloads ready for `node.report`.

        Returns:
            Report payloads that should be forwarded to IM after heartbeat work has produced
            a user-visible result. Implementations may return an empty list when there is
            nothing new to publish.
        """


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
    ) -> None:
        self._base_url = _im_http_base_url(base_url)
        self._base_headers = _im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._max_attempts = max(max_attempts, 1)
        self._pipeline = pipeline
        self._local_config = local_config
        self._workspace_root_factory = workspace_root_factory or self._default_workspace_root
        self._reporter = reporter
        self._client_factory = client_factory
        self._client = client
        self._monotonic = monotonic
        self._sleep = sleep

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
                agent_config = AgentWorkspaceConfig(
                    agent_id=agent_id,
                    workspace_root=workspace_root,
                    title=str(payload.get("display_name") or agent_id),
                    skills=tuple(
                        item.strip()
                        for item in payload.get("skills", [])
                        if isinstance(item, str) and item.strip()
                    ),
                    tool_allowlist=tuple(
                        item.strip()
                        for item in payload.get("tool_allowlist", [])
                        if isinstance(item, str) and item.strip()
                    ),
                    system_prompt=(
                        payload.get("system_prompt").strip()
                        if isinstance(payload.get("system_prompt"), str) and payload.get("system_prompt").strip()
                        else None
                    ),
                    group_reply_policy=(
                        payload.get("group_reply_policy").strip()
                        if isinstance(payload.get("group_reply_policy"), str) and payload.get("group_reply_policy").strip()
                        else None
                    ),
                    default_model=(
                        payload.get("default_model").strip()
                        if isinstance(payload.get("default_model"), str) and payload.get("default_model").strip()
                        else None
                    ),
                )
                self._pipeline.register_agent(agent_config)
                self._persist_agent_config(agent_config)
                self._pipeline.drop_agent_sessions(agent_id)
                return
            except (httpx.HTTPError, RuntimeError, ValueError):
                if attempt >= self._max_attempts or self._monotonic() >= deadline:
                    raise
                self._sleep(self._retry_interval_seconds)

    def handle_agent_create(self, agent_payload: Mapping[str, object]) -> dict[str, object]:
        """在节点上落地工作区并注册 Agent，供 IM ``agent.create`` / ``agent.created`` 回包使用。"""
        agent_id_raw = agent_payload.get("agent_id")
        if not isinstance(agent_id_raw, str) or not agent_id_raw.strip():
            raise ValueError("agent.create requires non-empty agent_id")
        agent_id = agent_id_raw.strip()
        ws_raw = agent_payload.get("workspace_root")
        if isinstance(ws_raw, str) and ws_raw.strip():
            workspace_root = Path(ws_raw.strip()).expanduser()
            if not workspace_root.is_absolute():
                raise ValueError("workspace_root must be an absolute path or start with ~/")
            workspace_root = workspace_root.resolve()
        else:
            workspace_root = self._workspace_root_factory(agent_id)
        workspace_root = ensure_workspace_defaults(workspace_root)
        display = agent_payload.get("display_name")
        title = display.strip() if isinstance(display, str) and display.strip() else agent_id
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
        group_reply_policy = grp.strip() if isinstance(grp, str) and grp.strip() else "MENTION"
        dm = agent_payload.get("default_model")
        default_model = dm.strip() if isinstance(dm, str) and dm.strip() else None
        agent_config = AgentWorkspaceConfig(
            agent_id=agent_id,
            workspace_root=workspace_root,
            title=title,
            skills=skills,
            tool_allowlist=tool_allowlist,
            system_prompt=system_prompt,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
        )
        self._pipeline.register_agent(agent_config)
        self._persist_agent_config(agent_config)
        if self._reporter is not None:
            self._reporter.replace_agents(tuple(self._local_config.agents))
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
        }

    def close(self) -> None:
        client = self._client
        if client is not None:
            client.close()
            self._client = None

    def _persist_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        agents = list(self._local_config.agents)
        for index, existing in enumerate(agents):
            if existing.agent_id == agent_config.agent_id:
                agents[index] = agent_config
                break
        else:
            agents.append(agent_config)
        persist_path = Path(self._local_config.source_path) if self._local_config.source_path else default_local_config_path()
        self._local_config = LocalConfig(
            node=self._local_config.node,
            agents=tuple(agents),
            channels=self._local_config.channels,
            kernel=self._local_config.kernel,
            heartbeat=self._local_config.heartbeat,
            im_service=self._local_config.im_service,
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
            }
            return payload
        return None

    def _fetch_agent_config(self, *, agent_id: str) -> dict[str, object]:
        response = self._get_client().get(f"/im/v1/agents/{agent_id}/config", params={"source": "mirror"})
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
            response = client.post("/im/v1/bind", json={"action": "start", "node_id": node_id})
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GatewayStartupError(
                summary=f"node {node_id} could not start IM binding",
                next_step=f"Verify {resolved_base_url}/im/v1/bind is reachable, then rerun gateway.",
            ) from exc
        payload = response.json()
        bind_url = _require_text(payload.get("bind_url"), field_name="bind_url")
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
                    return self._get_owner_id(node_id=node_id, base_url=base_url), base_url
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self._sleep(0.1)
        checked_urls = ", ".join(f"{base_url}/im/v1/nodes" for base_url in self._base_urls)
        message = f"node {node_id} did not appear in IM bootstrap"
        next_step = f"Verify the IM node API is reachable at {checked_urls} and rerun gateway."
        if last_error is not None:
            raise GatewayStartupError(summary=message, next_step=next_step) from last_error
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
    """Manage the local agent kernel child process for the gateway.

    Args:
        config: Kernel process and health-probe settings loaded from local config.
        kernel_client: HTTP client used for readiness probes.
        process_factory: Factory used to spawn the kernel child process.
        monotonic: Monotonic clock source for timeout accounting.
        sleep: Sleep function used between readiness probes.
    """

    def __init__(
        self,
        *,
        config: KernelConfig,
        kernel_client: KernelApiClient,
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
        """Spawn the local kernel child and wait until `/v1/health` reports ready.

        Returns:
            The spawned process handle once health probing succeeds.

        Raises:
            RuntimeError: When the kernel does not become healthy before timeout.

        Side Effects:
            Starts a subprocess and performs repeated HTTP health checks.
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
                last_error = RuntimeError(f"kernel reported unhealthy payload: {payload}")
            self._sleep(self._config.health_poll_interval_seconds)
        message = "kernel health check timed out"
        if last_error is not None:
            raise RuntimeError(message) from last_error
        raise RuntimeError(message)


class PollingHeartbeatRunner:
    """Run the existing heartbeat scheduler as a background tick loop.

    Args:
        scheduler: Existing scheduler implementation that evaluates `HEARTBEAT.md`.
        config: Local heartbeat runtime settings.
        sleep: Async sleep function used between tick passes.

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
    ) -> None:
        self._scheduler = scheduler
        self._config = config
        self._sleep = sleep
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._product_reports: list[dict[str, object]] = []

    async def start(self) -> None:
        """Start background scheduler ticking exactly once."""

        if self._task is not None:
            return
        self._stop_requested = False
        self._wake_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="personal-assistant-heartbeat")

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

    def build_product_reports(self) -> list[dict[str, object]]:
        """Return heartbeat report payloads ready for IM publication.

        Returns:
            Newly accumulated heartbeat summaries and clears the local queue so the runtime
            publishes each heartbeat result to IM at most once.
        """
        payloads = list(self._product_reports)
        self._product_reports.clear()
        return payloads

    async def _run_loop(self) -> None:
        while not self._stop_requested:
            summary = self._scheduler.tick()
            self._product_reports.extend(_build_heartbeat_product_reports(summary))
            if self._stop_requested:
                break
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=self._config.tick_interval_seconds)
            except TimeoutError:
                continue
            finally:
                self._wake_event.clear()


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
        future = asyncio.run_coroutine_threadsafe(self._pipeline.handle_inbound(message), loop)
        future.add_done_callback(_consume_future_exception)


class GatewayRuntime:
    """Run the assembled Node Gateway process until shutdown is requested.

    Args:
        config: Parsed immutable local gateway config.
        process_manager: Kernel child-process lifecycle manager.
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
        process_manager: GatewayProcessManager,
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

        channels_started = False
        heartbeat_started = False
        im_connected = False
        dispatch_runner: Any | None = None
        im_task: asyncio.Task[None] | None = None
        try:
            self._process_manager.start_kernel_process()
            start_channels(self._channel_registry, self._on_inbound)
            channels_started = True
            if self._heartbeat_runner is not None:
                await self._heartbeat_runner.start()
                heartbeat_started = True
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
                await self._publish_heartbeat_product_reports()
                im_task = asyncio.create_task(self._im_connection_manager.run_forever(), name="personal-assistant-im")
            await asyncio.to_thread(self._shutdown_requested.wait)
            await self._publish_heartbeat_product_reports()
            return 0
        finally:
            self._ready_event.clear()
            if dispatch_runner is not None:
                with suppress(Exception):
                    await dispatch_runner.cleanup()
            if heartbeat_started and self._heartbeat_runner is not None:
                await self._heartbeat_runner.close()
            if channels_started:
                stop_channels(self._channel_registry)
            if im_connected and self._im_connection_manager is not None:
                await self._im_connection_manager.close()
                if im_task is not None:
                    await _await_background_task(im_task)
            elif im_task is not None:
                im_task.cancel()
                with suppress(asyncio.CancelledError):
                    await im_task
            self._process_manager.stop_kernel_process()
            for closer in self._resource_closers:
                closer()

    async def _publish_startup_failure(self, exc: GatewayStartupError) -> None:
        self._feedback_sink("ERROR", exc.summary, exc.next_step)
        manager = self._im_connection_manager
        if manager is None or not manager.connected:
            return
        last_error = exc.summary if exc.next_step is None else f"{exc.summary} Next: {exc.next_step}"
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

    async def _publish_heartbeat_product_reports(self) -> None:
        """Forward any newly produced heartbeat summaries to IM as user-visible reports.

        Notes:
            Heartbeat scheduling itself stays local to the gateway process. This bridge only
            ships already-prepared report payloads into the existing IM `node.report` path so
            the result becomes visible in the same product conversation surface as normal relay
            work.
        """
        manager = self._im_connection_manager
        runner = self._heartbeat_runner
        if manager is None or not manager.connected or runner is None:
            return
        build_reports = getattr(runner, "build_product_reports", None)
        if build_reports is None:
            return
        for payload in build_reports():
            try:
                await manager.send_json("node.report", payload)
            except Exception:  # noqa: BLE001
                return


def _load_runtime_config(
    config_path: str | Path,
    *,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    im_service_url_override: str | None = None,
) -> LocalConfig:
    config = load_config(config_path)
    if not isinstance(im_service_url_override, str) or not im_service_url_override.strip():
        return config
    override_url = im_service_url_override.strip()
    override_token = config.im_service.token if config.im_service is not None else None
    return replace(config, im_service=IMServiceConfig(url=override_url, token=override_token))


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
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    restore_signal_handlers = resolved_factories.install_signal_handlers or _install_default_signal_handlers(runtime)
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
                next_step=f"Run 'stop' to shut it down first, or 'restart' to replace it.",
            )
        # Stale PID file from a crashed process — clean it up and continue.
        _remove_gateway_pid(config)
    log_path = _default_gateway_log_path(config)
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    argv = _background_gateway_argv(config.source_path, im_service_url_override=im_service_url_override)
    launcher = spawn_process or _spawn_background_gateway_process
    ready_waiter = wait_for_ready or _wait_for_gateway_ready
    process = launcher(argv, log_path)
    try:
        ready_waiter(process, config, config.kernel.startup_timeout_seconds)
    except Exception as exc:
        _stop_background_process(process, timeout_seconds=config.kernel.shutdown_grace_seconds)
        hint = _read_log_last_error(log_path, offset=log_offset)
        summary = hint if hint else str(exc)
        raise GatewayStartupError(
            summary=summary,
            next_step=f"Check the log for details: tail -20 {log_path}",
        ) from exc
    result = BackgroundLaunchResult(
        pid=process.pid,
        health_url=f"{config.kernel.base_url}{config.kernel.health_path}",
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
    return response.status_code == 200 and isinstance(payload, dict) and bool(payload.get("healthy"))


def _verify_stopped_health_url(health_url: str, *, timeout_seconds: float, sleep_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if not _healthcheck_reports_healthy(health_url):
            return True
        time.sleep(sleep_seconds)
    return not _healthcheck_reports_healthy(health_url)


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config."""

    kernel_token = resolve_kernel_token(config.kernel.token)
    kernel_client = KernelApiClient(
        config=KernelApiClientConfig(
            base_url=config.kernel.base_url,
            token=kernel_token,
            request_id=config.kernel.request_id,
            timeout_seconds=config.kernel.timeout_seconds,
        )
    )
    process_manager = GatewayProcessManager(config=config.kernel, kernel_client=kernel_client)
    runtime_dir = config.source_path.parent
    channel_registry = _build_channel_registry(
        config.channels,
        dedup_db_path=runtime_dir / "relay_dedup.sqlite3",
    )
    outbound_router = OutboundRouter(channel_registry)
    heartbeat_runner = PollingHeartbeatRunner(
        scheduler=HeartbeatScheduler(
            agents=config.agents,
            kernel_client=kernel_client,
            state_store=HeartbeatSchedulerStateStore(_default_heartbeat_state_path(config)),
        ),
        config=config.heartbeat,
    )
    reporter: UpstreamReporter | None = None
    im_connection_manager: IMConnectionManager | None = None
    im_bootstrap_client: _IMBootstrapClient | None = None
    im_config_sync_client: _IMConfigSyncClient | None = None
    post_im_connect: Callable[[], None] | None = None
    _run_context_store: dict[str, dict[str, str]] = {}
    # Use SQLite-backed store so kernel session mappings survive gateway restarts
    # (NodeGateway-SPEC §4.2).  The kernel_client is injected below after construction
    # so that live session validation (GET /v1/sessions/{id}) is enabled at runtime.
    session_store = PersistentSessionBindingStore(
        db_path=runtime_dir / "session_bindings.sqlite3"
    )
    session_store.set_kernel_client(kernel_client)
    _gateway_internal_port = 8089
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
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
        _token_getter = _make_token_getter(
            im_service=config.im_service,
            local_config=config,
            auth_client=_auth_client,
        )
        _permission_response_handler = _build_permission_response_handler(
            kernel_client=kernel_client,
            run_context_store=_run_context_store,
        )
        im_connection_manager = _build_im_connection_manager(
            config=config,
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_runner=heartbeat_runner,
            sync_client=ConfigSyncClient(fetcher=im_config_sync_client.sync_agent),
            agent_config_provider=lambda agent_id: im_config_sync_client.current_agent_payload(agent_id=agent_id),
            agent_capabilities_provider=lambda _agent_id, workspace_root: build_agent_capabilities_payload(
                workspace_root=workspace_root
            ),
            agent_create_handler=im_config_sync_client.handle_agent_create,
            token_getter=_token_getter,
            permission_response_handler=_permission_response_handler,
        )
        im_bootstrap_client = _IMBootstrapClient(
            base_url=_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=_token_getter,
        )
        post_im_connect = lambda: im_bootstrap_client.ensure_node_binding(node_id=config.node.node_id)
    pipeline._relay_lifecycle_callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=_run_context_store,
    )
    if config.im_service is not None:
        pipeline._kernel_event_observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: im_connection_manager,
            run_context_store=_run_context_store,
        )
        # feat-349-M3: wire background session event callback so self_evolution_review
        # events published by background hooks reach IM as system/meta messages.
        pipeline._session_event_callback = _build_session_event_callback(
            im_connection_manager_factory=lambda: im_connection_manager,
            session_store=pipeline._session_store,
        )
    inbound_dispatcher = _InboundDispatcher(pipeline)
    closers: list[Callable[[], None]] = [kernel_client.close]
    if im_bootstrap_client is not None:
        closers.append(im_bootstrap_client.close)
    if im_config_sync_client is not None:
        closers.append(im_config_sync_client.close)
    internal_dispatch_handler = InternalDispatchHandler(
        im_connection_manager=im_connection_manager,
        kernel_client=kernel_client,
        session_store=session_store,
    )
    return GatewayRuntime(
        config,
        process_manager,
        channel_registry=channel_registry,
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=im_connection_manager,
        on_inbound=inbound_dispatcher,
        post_im_connect=post_im_connect,
        resource_closers=tuple(closers),
        internal_dispatch_handler=internal_dispatch_handler,
        gateway_internal_port=_gateway_internal_port,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""

    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(description="Run personal assistant gateway runtime")
    parser.add_argument("--config", help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)")
    parser.add_argument("--im-service-url", help="Override the upstream IM service base URL for this launch")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    subparsers = parser.add_subparsers(dest="command")
    stop_parser = subparsers.add_parser("stop", help="Stop the current background gateway for one config")
    stop_parser.add_argument("--config", help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)")
    stop_parser.add_argument("--im-service-url", help="Override the upstream IM service base URL for this launch")
    restart_parser = subparsers.add_parser("restart", help="Stop then start the background gateway (equivalent to stop + start)")
    restart_parser.add_argument("--config", help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)")
    restart_parser.add_argument("--im-service-url", help="Override the upstream IM service base URL for this launch")
    args = parser.parse_args(argv)
    command = args.command or "start"
    resolved_config_path = str(Path(args.config).expanduser()) if args.config else str(default_local_config_path())
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
            return run_gateway(config_path=resolved_config_path, im_service_url_override=args.im_service_url)
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


def _coerce_factories(factories: RuntimeFactories | Mapping[str, Any] | None) -> RuntimeFactories:
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
                access, new_refresh = await auth_client.login(username=username, password=password)
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
    agent_create_handler: AgentCreateHandler | None = None,
    token_getter: Callable[[], Awaitable[str | None]] | None = None,
    permission_response_handler: Callable[[Mapping[str, object]], None] | None = None,
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
        agent_create_handler=agent_create_handler,
        token_getter=token_getter,
        connect=_connect_websocket,
        permission_response_handler=permission_response_handler,
    )


def _build_permission_response_handler(
    *,
    kernel_client: KernelAPIClient,
    run_context_store: dict[str, dict[str, str]],
) -> Callable[[Mapping[str, object]], None]:
    """Build handler that routes IM permission_response frames to the kernel.

    The frame carries ``request_id``, ``decision``, and the IM-side
    ``message_id``. The kernel session is recovered by scanning
    ``run_context_store`` for a matching ``message_id`` — the same store
    already maintained by the kernel event observer.
    """

    def _handler(body: Mapping[str, object]) -> None:
        request_id = str(body.get("request_id") or "").strip()
        decision = str(body.get("decision") or "").strip()
        message_id = str(body.get("message_id") or "").strip()
        if not request_id or not decision:
            return
        kernel_session_id = ""
        if message_id:
            for ctx in run_context_store.values():
                if ctx.get("message_id") == message_id:
                    kernel_session_id = ctx.get("kernel_session_id") or ""
                    break
        # Fallback: if message_id lookup misses (e.g. ack not yet stored),
        # use the only active kernel session when there's exactly one.
        if not kernel_session_id:
            distinct = {
                ctx.get("kernel_session_id")
                for ctx in run_context_store.values()
                if ctx.get("kernel_session_id")
            }
            if len(distinct) == 1:
                kernel_session_id = next(iter(distinct))  # type: ignore[assignment]
        if not kernel_session_id:
            return
        try:
            kernel_client.submit_permission_decision(
                session_id=kernel_session_id,
                request_id=request_id,
                decision=decision,
            )
        except Exception:  # noqa: BLE001 — IM-bound side-effect; failure can't cascade
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
                agent_id_meta = _metadata_text(message.metadata, key="agent_id") or update.agent_id or ""
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
            if callable(send_report) and message_id is not None and update.run_id is not None:
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
                detail_parts = [f"{key}={value}" for key, value in update.detail.items()]
                suppression_detail = " | ".join(detail_parts) if detail_parts else None
            receipt_detail = update.reply_text
            if suppression_detail is not None:
                receipt_detail = suppression_detail if InboundPipeline._is_no_reply_token(update.reply_text or "") else (
                    " | ".join([part for part in [receipt_detail, suppression_detail] if part]) or None
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
    """

    async def _send(manager: IMConnectionManager, message_type: str, payload: Mapping[str, Any]) -> None:
        try:
            await manager.send_json(message_type, payload)
        except Exception:  # noqa: BLE001
            pass

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

        event_name = str(event.get("event") or "").strip()
        loop = asyncio.get_event_loop()

        if event_name == "run_status" and event.get("status") == "running":
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
                        ack = await mgr.send_json_await_ack("node.streaming_delta", {
                            "kind": "turn_start",
                            "conversation_id": cid,
                            "agent_id": aid,
                            "run_id": rid,
                        })
                        ack_payload = ack.get("payload") if isinstance(ack.get("payload"), dict) else ack
                        returned_msg_id = ack_payload.get("message_id") if isinstance(ack_payload, dict) else None
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                    except Exception:  # noqa: BLE001
                        pass
                return _send_turn_start_and_store()

        elif event_name == "assistant_message":
            content = str(event.get("content") or "").strip()
            if not content:
                return None
            kernel_msg_id = str(event.get("message_id") or "").strip()
            prev_kernel_msg_id = ctx.get("kernel_message_id") or ""

            # Detect a new assistant message within the same run (e.g. textA → tool_calls → textB).
            # The kernel's while-loop generates a fresh assistant_msg_id per iteration; when it
            # differs from the previous one we must close the old IM message and start a new one
            # so the frontend renders textA and textB as separate bubbles.
            if kernel_msg_id and prev_kernel_msg_id and kernel_msg_id != prev_kernel_msg_id:
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
                            await mgr.send_json("node.streaming_delta", {
                                "kind": "message_completed",
                                "message_id": old_msg_id,
                                "final_content": None,
                                "token_usage": None,
                                "run_id": rid,
                            })
                        ack = await mgr.send_json_await_ack("node.streaming_delta", {
                            "kind": "turn_start",
                            "conversation_id": cid,
                            "agent_id": aid,
                            "run_id": rid,
                        })
                        ack_payload = ack.get("payload") if isinstance(ack.get("payload"), dict) else ack
                        returned_msg_id = ack_payload.get("message_id") if isinstance(ack_payload, dict) else None
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                            run_context_store[rid]["kernel_message_id"] = new_kernel_id
                            await mgr.send_json("node.streaming_delta", {
                                "kind": "message_delta",
                                "message_id": str(returned_msg_id),
                                "delta_text": text,
                                "run_id": rid,
                            })
                    except Exception:  # noqa: BLE001
                        pass
                return _close_old_and_restart()

            if message_id:
                # turn_start already ack'd — send delta directly.
                if kernel_msg_id:
                    ctx["kernel_message_id"] = kernel_msg_id
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "message_delta",
                    "message_id": message_id,
                    "delta_text": content,
                    "run_id": run_id,
                }))
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
                        ack = await mgr.send_json_await_ack("node.streaming_delta", {
                            "kind": "turn_start",
                            "conversation_id": cid,
                            "agent_id": aid,
                            "run_id": rid,
                        })
                        ack_payload = ack.get("payload") if isinstance(ack.get("payload"), dict) else ack
                        returned_msg_id = ack_payload.get("message_id") if isinstance(ack_payload, dict) else None
                        if returned_msg_id and rid in run_context_store:
                            run_context_store[rid]["message_id"] = str(returned_msg_id)
                            if new_kernel_id:
                                run_context_store[rid]["kernel_message_id"] = new_kernel_id
                            await mgr.send_json("node.streaming_delta", {
                                "kind": "message_delta",
                                "message_id": str(returned_msg_id),
                                "delta_text": text,
                                "run_id": rid,
                            })
                    except Exception:  # noqa: BLE001
                        pass
                return _turn_start_then_delta()

        elif event_name == "turn_end":
            # Finalize message with token_usage if present.
            usage_raw = event.get("usage")
            token_usage_payload: dict[str, object] | None = None
            if isinstance(usage_raw, Mapping):
                prompt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens")
                completion = usage_raw.get("completion_tokens") or usage_raw.get("output_tokens")
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
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "message_completed",
                    "message_id": message_id,
                    "final_content": None,
                    "token_usage": token_usage_payload,
                    "run_id": run_id,
                }))

        elif event_name == "tool_start":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
            if message_id:
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "tool_call_upserted",
                    "message_id": message_id,
                    "tool_call": {
                        "id": call_id,
                        "name": tool_name,
                        "status": "running",
                        "input": arguments if isinstance(arguments, dict) else {},
                    },
                    "run_id": run_id,
                }))

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
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "tool_call_completed",
                    "message_id": message_id,
                    "tool_call": {
                        "id": call_id,
                        "name": tool_name,
                        "status": status,
                        "input": arguments if isinstance(arguments, dict) else {},
                        "output": " | ".join(output_parts) if output_parts else None,
                        "duration_ms": int(duration_ms) if isinstance(duration_ms, (int, float)) else None,
                    },
                    "run_id": run_id,
                }))

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
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "permission_request",
                    "message_id": message_id,
                    "permission_request": {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "tool_input": dict(tool_input) if isinstance(tool_input, Mapping) else (tool_input or {}),
                        "question": question,
                        "options": options,
                        "status": "pending",
                    },
                    "run_id": run_id,
                }))

        elif event_name == "permission_resolved":
            # Agent resolved a permission request (hook resumed); update the IM card
            # so the user sees the final decision.
            if message_id:
                request_id = str(event.get("request_id") or "").strip()
                decision = str(event.get("decision") or "").strip()
                loop.create_task(_send(manager, "node.streaming_delta", {
                    "kind": "permission_resolved",
                    "message_id": message_id,
                    "request_id": request_id,
                    "decision": decision,
                    "run_id": run_id,
                }))

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
        data = event.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        reviewed_skills: bool = bool(data.get("reviewed_skills", False))
        reviewed_memory: bool = bool(data.get("reviewed_memory", False))
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
            await manager.send_json("node.system_message", {
                "conversation_id": conversation_id,
                "text": text,
            })
        except Exception:  # noqa: BLE001
            # Background notification delivery must never crash the gateway.
            pass

    return _callback


def _build_heartbeat_product_reports(summary: HeartbeatTickSummary) -> list[dict[str, object]]:
    """Translate heartbeat tick results into IM-visible `node.report` payloads.

    Args:
        summary: Scheduler tick result containing newly triggered heartbeat runs.

    Returns:
        One completed report payload per triggered heartbeat run. The payload is shaped to fit
        the existing IM `node.report` persistence path so heartbeat outcomes appear in the same
        product event stream as other agent execution updates.
    """
    payloads: list[dict[str, object]] = []
    for run in summary.triggered_runs:
        payloads.append(
            {
                "run_id": run.run_id,
                "status": "completed",
                "agent_id": run.agent_id,
                "session_key": f"{run.agent_id}::heartbeat",
                "conversation_id": f"heartbeat:{run.agent_id}",
                "message_id": run.run_id,
                "summary": f"Heartbeat complete for main agent {run.agent_id} at {run.due_at.isoformat()}.",
                "guidance": "Open your main agent thread in Web IM to review the latest heartbeat result.",
            }
        )
    return payloads


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
    _gateway_state_path(config).write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


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


def _background_gateway_argv(config_path: Path, *, im_service_url_override: str | None = None) -> list[str]:
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


def _wait_for_gateway_ready(process: ProcessLike, config: LocalConfig, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(f"gateway exited before ready with return code {process.poll()}")
        try:
            response = httpx.get(
                f"{config.kernel.base_url}{config.kernel.health_path}",
                timeout=1.0,
                trust_env=False,
            )
            payload = response.json()
            if isinstance(payload, dict) and bool(payload.get("healthy")):
                return
            last_error = RuntimeError(f"unexpected health payload: {payload}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(config.kernel.health_poll_interval_seconds)
    if last_error is not None:
        raise RuntimeError("timed out waiting for gateway readiness") from last_error
    raise RuntimeError("timed out waiting for gateway readiness")


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


def _install_default_signal_handlers(runtime: GatewayRuntimeLike) -> SignalHandlerInstaller:
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
    return await websockets.connect(url, additional_headers=dict(headers), user_agent_header=None)


async def _await_background_task(task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    with suppress(asyncio.CancelledError):
        task.result()


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
