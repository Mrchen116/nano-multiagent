"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import tempfile
import webbrowser
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

_log = logging.getLogger("personal_assistant.main")
_PA_GLOBAL_SKILL_ROOT = Path("~/.nanoassistant/skills")

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import ReplyContext
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)
from personal_assistant.channels.feishu import FeishuAdapter
from personal_assistant.channels.channel_credentials import GatewayChannelKeyStore

from personal_assistant.config.local_store import (
    ChannelConfig,
    IMServiceConfig,
    LocalConfig,
    RuntimeConfigOwner,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
    default_local_config_path,
    ensure_feishu_doc_skill_for_feishu_agents,
    load_local_config,
    save_local_config,
    save_sensitive_local_config,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.managed_channel_control import (
    ManagedChannelBindings,
    ManagedChannelConnectionSender,
    ManagedChannelControl,
)
from personal_assistant.gateway import kernel_client, runtime
from personal_assistant.scheduler import heartbeat_runner
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync,
    _make_workspace_root_factory,
    _parse_heartbeat_from_im_payload,  # noqa: F401 - compatibility re-export
)
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
)
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)
from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher
from personal_assistant.gateway.inbound_pipeline import (
    InboundPipeline,
    InboundRouteConfig,
)
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContextStore,
)
from personal_assistant.gateway.runtime_delivery.background import (
    build_bg_reply_sender as _build_bg_reply_sender,
    build_session_event_callback as _build_session_event_callback,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback as _build_relay_lifecycle_callback,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer as _build_kernel_event_observer,
    extract_ack_message_id as _extract_ack_message_id,  # noqa: F401
    roll_bubble as _roll_bubble,  # noqa: F401
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    build_conversation_session_key,
    build_external_session_key,
)
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_agent_capabilities_payload,
    build_node_capabilities_payload,
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
from personal_assistant.scheduler.cron_execution_service import (
    CronExecutionService,
    CronRunTerminalConsumer,
)
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_service_registry import CronServiceRegistry
from personal_assistant.auth.im_auth_client import IMAuthClient, IMAuthError
from personal_assistant.ws.im_connection import (
    AgentCreateHandler,
    IMConnectionConfig,
    IMConnectionManager,
    PromptPreviewProvider,
    SessionForkHandler,
)

ProcessLike = subprocess.Popen[Any]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
StartWaiter = Callable[[ProcessLike, LocalConfig, float], None]
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
    print(f"Gateway started (pid={result.pid})")
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
    build_runtime: Callable[[LocalConfig], runtime.GatewayRuntimeLike] | None = None
    install_signal_handlers: SignalHandlerInstaller | None = None


@dataclass(frozen=True, slots=True)
class BackgroundLaunchResult:
    """Describe the operator-facing result of a successful background launch.

    Args:
        pid: Process id of the detached foreground child now hosting the gateway runtime.
        log_path: File receiving the detached child stdout/stderr stream.
        im_service_url: Optional IM service URL configured for this gateway.
    """

    pid: int
    log_path: Path
    im_service_url: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayRuntimeState:
    """Persist the operator-facing metadata needed to locate one background gateway.

    Args:
        pid: Background gateway process id launched for this config.
        config_path: Absolute config path used for that process.
        log_path: Log file receiving the detached process output.
        process_start: OS process birth identity. ``None`` identifies legacy state.
    """

    pid: int
    config_path: str
    log_path: str
    process_start: str | None = None


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
        self._base_headers = build_im_http_headers(token)
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
            self._base_headers = build_im_http_headers(token)
            for client in self._clients.values():
                client.headers.update(self._base_headers)

    def ensure_node_binding(self, *, node_id: str) -> str | None:
        """Open the bind URL when the upstream node still has no owner.

        Args:
            node_id: Gateway node id that was just registered over IM websocket.

        Returns:
            The opened bind URL for unbound nodes, or `None` when the node is already owned.

        Raises:
            GatewayStartupError: When IM bootstrap APIs do not expose the registered
                node or binding cannot be started/confirmed.
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


def _load_runtime_config(
    config_path: str | Path,
    *,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    save_config: Callable[[LocalConfig, str | Path], None] = save_local_config,
    im_service_url_override: str | None = None,
) -> LocalConfig:
    config = load_config(config_path)
    config = _autofill_feishu_bot_open_id(
        config,
        save_config=save_config,
        bot_identity_fetcher=_infer_feishu_bot_open_id_from_app_credentials,
    )
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


def _autofill_feishu_bot_open_id(
    config: LocalConfig,
    *,
    save_config: Callable[[LocalConfig, str | Path], None] = save_local_config,
    bot_identity_fetcher: Callable[[str, str, str], str | None] | None = None,
) -> LocalConfig:
    """Fill missing Feishu bot open IDs from app-credential runtime probes."""
    updated_channels: list[ChannelConfig] = []
    changed = False
    for channel in config.channels:
        if not channel.enabled or not channel.name.startswith("feishu:"):
            updated_channels.append(channel)
            continue
        settings = dict(channel.settings)
        bot_open_id = settings.get("botOpenId")
        needs_bot_open_id = not (isinstance(bot_open_id, str) and bot_open_id.strip())
        if not needs_bot_open_id:
            updated_channels.append(channel)
            continue
        app_id = settings.get("appId")
        if not isinstance(app_id, str) or not app_id.strip():
            updated_channels.append(channel)
            continue
        cleaned_app_id = app_id.strip()
        app_secret = settings.get("appSecret")
        domain = settings.get("domain")
        cleaned_domain = (
            domain.strip()
            if isinstance(domain, str) and domain.strip()
            else "https://open.feishu.cn"
        )
        if bot_identity_fetcher is None or not (
            isinstance(app_secret, str) and app_secret.strip()
        ):
            updated_channels.append(channel)
            continue
        inferred_bot_open_id = bot_identity_fetcher(
            cleaned_app_id, app_secret.strip(), cleaned_domain
        )
        if inferred_bot_open_id is None:
            updated_channels.append(channel)
            continue
        settings["botOpenId"] = inferred_bot_open_id
        updated_channels.append(replace(channel, settings=settings))
        changed = True
    if not changed:
        return config
    updated = replace(config, channels=tuple(updated_channels))
    source_path = getattr(updated, "source_path", None)
    if source_path is not None:
        save_config(updated, source_path)
    return updated


def _infer_feishu_bot_open_id_from_app_credentials(
    app_id: str, app_secret: str, domain: str
) -> str | None:
    """Return bot open_id by probing Feishu with app credentials."""
    try:
        from lark_oapi.channel.bot_identity import fetch_bot_identity
        from lark_oapi.core.model import Config
    except ImportError:
        _log.warning("lark-oapi bot identity helper unavailable; botOpenId not filled")
        return None

    sdk_config = Config()
    sdk_config.app_id = app_id
    sdk_config.app_secret = app_secret
    sdk_config.domain = domain
    sdk_config.timeout = 10
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            identity = asyncio.run(fetch_bot_identity(sdk_config))
        else:
            identity = _run_sync_in_thread(
                lambda: asyncio.run(fetch_bot_identity(sdk_config)),
                name="feishu-bot-id-probe",
            )
    except Exception:  # noqa: BLE001
        _log.warning("failed to probe Feishu bot identity", exc_info=True)
        return None

    open_id = getattr(identity, "open_id", None) if identity is not None else None
    if isinstance(open_id, str) and open_id.strip():
        return open_id.strip()
    _log.warning("Feishu bot identity probe returned no bot open_id")
    return None


def _run_sync_in_thread(func: Callable[[], Any], *, name: str) -> Any:
    result: list[Any] = []
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            result.append(func())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=_target, name=name, daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0] if result else None


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
    # refactor-406-M2: model registry init is build_kernel's responsibility (决策 5):
    # build_runtime → build_pa_kernel → build_kernel inits the registry from config.llm.
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    restore_signal_handlers = (
        resolved_factories.install_signal_handlers
        or _install_default_signal_handlers(runtime)
    )
    restore = restore_signal_handlers()
    pid = os.getpid()
    process_start = _process_start_identity(pid)
    if process_start is None:
        raise RuntimeError(f"cannot read process birth identity for gateway pid={pid}")
    state = GatewayRuntimeState(
        pid=pid,
        process_start=process_start,
        config_path=str(config.source_path.resolve()),
        log_path=str(_default_gateway_log_path(config)),
    )
    _write_gateway_state(config, state)
    try:
        return runtime.run_forever()
    finally:
        restore()
        _remove_gateway_state(_gateway_state_path(config), expected=state)


def launch_gateway_in_background(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Start the gateway in a detached child and confirm its PID is live.

    Args:
        config_path: Operator-provided config path forwarded to the detached child.
        load_config: Config loader used to resolve lifecycle timing before spawning.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional PID/start confirmation waiter override used by tests.

    Returns:
        Detached process metadata once the child writes its PID and remains alive.

    Raises:
        RuntimeError: When the detached child exits or never confirms startup.
    """
    with _gateway_lifecycle_lock(config_path):
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _launch_gateway_in_background_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
    spawn_process: BackgroundProcessFactory | None,
    wait_for_start: StartWaiter | None,
    im_service_url_override: str | None,
) -> BackgroundLaunchResult:
    """Execute one background launch while the caller holds its lifecycle lock."""

    config = _load_runtime_config(
        config_path,
        load_config=load_config,
        im_service_url_override=im_service_url_override,
    )
    state_path = _gateway_state_path(config)
    existing_state = _read_gateway_state(state_path)
    if existing_state is not None:
        _assert_gateway_state_static(config, existing_state)
        signal_state = (
            _upgrade_legacy_gateway_state(config, existing_state.pid, existing_state)
            if existing_state.process_start is None
            else existing_state
        )
        if signal_state is not None and _gateway_process_matches(signal_state):
            raise GatewayStartupError(
                summary=f"gateway is already running (pid={existing_state.pid})",
                next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
            )
        _remove_gateway_state(state_path, expected=existing_state)
    else:
        legacy_pid = _read_legacy_gateway_pid(config)
        if legacy_pid is not None:
            legacy_state = _upgrade_legacy_gateway_state(config, legacy_pid, None)
            if legacy_state is not None and _gateway_process_matches(legacy_state):
                raise GatewayStartupError(
                    summary=f"gateway is already running (pid={legacy_pid})",
                    next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
                )
            _remove_legacy_gateway_pid(config, expected_pid=legacy_pid)

    log_path = _default_gateway_log_path(config)
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    argv = _background_gateway_argv(
        config.source_path, im_service_url_override=im_service_url_override
    )
    launcher = spawn_process or _spawn_background_gateway_process
    start_waiter = wait_for_start or _wait_for_gateway_start
    process = launcher(argv, log_path)
    try:
        start_waiter(process, config, config.gateway.startup_timeout_seconds)
    except Exception as exc:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        hint = _read_log_last_error(log_path, offset=log_offset)
        summary = hint if hint else str(exc)
        raise GatewayStartupError(
            summary=summary,
            next_step=f"Check the log for details: tail -20 {log_path}",
        ) from exc
    result = BackgroundLaunchResult(
        pid=process.pid,
        log_path=log_path,
        im_service_url=config.im_service.url if config.im_service is not None else None,
    )
    published_state = _read_gateway_state(state_path)
    if published_state is None:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        raise GatewayStartupError(
            summary="gateway child did not publish lifecycle state",
            next_step=f"Check the log for details: tail -20 {log_path}",
        )
    _assert_gateway_state_static(config, published_state, expected_pid=process.pid)
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
        One operator-facing status line describing stop success, not-running, or stale state.

    Side Effects:
        Sends SIGTERM and possibly SIGKILL to the background gateway process and removes stale state.
    """
    with _gateway_lifecycle_lock(config_path):
        return _stop_gateway_unlocked(config_path=config_path, load_config=load_config)


def restart_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Stop and start one Gateway as a single serialized lifecycle operation.

    Args:
        config_path: Operator-provided config path identifying the lifecycle owner.
        load_config: Config loader shared by the stop and start phases.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional process-start confirmation override used by tests.
        im_service_url_override: Optional IM service URL forwarded to the new process.

    Returns:
        Metadata for the replacement background Gateway.

    Side Effects:
        Stops the owned Gateway, then launches its replacement while holding one lock.
    """
    with _gateway_lifecycle_lock(config_path):
        _stop_gateway_unlocked(config_path=config_path, load_config=load_config)
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _stop_gateway_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
) -> str:
    """Stop one Gateway while the caller holds its lifecycle lock."""

    config = load_config(config_path)
    state_path = _gateway_state_path(config)
    state = _read_gateway_state(state_path)
    if state is None:
        pid = _read_legacy_gateway_pid(config)
        if pid is None:
            return f"NOT RUNNING config={config.source_path.name} state={state_path}"
        success_target = f"pid_file={_legacy_gateway_pid_path(config)}"
        state_to_remove = None
    else:
        pid = state.pid
        _assert_gateway_state_static(config, state)
        success_target = f"state={state_path}"
        state_to_remove = state_path

    if state is None or state.process_start is None:
        signal_state = _upgrade_legacy_gateway_state(config, pid, state)
        if signal_state is None:
            _remove_legacy_gateway_pid(config, expected_pid=pid)
            if state_to_remove is not None:
                _remove_gateway_state(state_to_remove, expected=state)
            return f"STALE pid={pid} {success_target}"
    else:
        signal_state = state
    if not _gateway_process_matches(signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STALE pid={pid} {success_target}"

    if not _signal_gateway_process(signal_state, signal.SIGTERM):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if _wait_for_gateway_exit(config, signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if not _signal_gateway_process(signal_state, signal.SIGKILL):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target} forced=true"
    if not _wait_for_gateway_exit(config, signal_state):
        raise RuntimeError(
            f"gateway pid={pid} did not exit after SIGKILL; lifecycle state retained"
        )
    _clear_gateway_lifecycle(config, state_to_remove, signal_state)
    return f"STOPPED pid={pid} {success_target} forced=true"


def _wait_for_gateway_exit(config: LocalConfig, state: GatewayRuntimeState) -> bool:
    """Wait one shutdown grace interval for the original process instance to exit."""
    deadline = time.monotonic() + config.gateway.shutdown_grace_seconds
    while _gateway_process_matches(state):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(config.gateway.poll_interval_seconds, remaining))
    return True


def _clear_gateway_lifecycle(
    config: LocalConfig,
    state_path: Path | None,
    completed: GatewayRuntimeState,
) -> None:
    """Clear only lifecycle evidence that still names the completed instance."""
    if state_path is not None:
        _remove_gateway_state(state_path, expected=completed)
    _remove_legacy_gateway_pid(config, expected_pid=completed.pid)


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
        # refactor-406-M1 R6 决策 8 (preview same-source): build PromptSlots with
        # the SAME prompt_for factory the runtime uses, from an "imaginary agent"
        # carrying the preview's feature flags / custom prompt.  Preview-seen ==
        # runtime-run; one byte-identity golden guards both.  Group scenario maps
        # to the prompt_for tail.
        from personal_assistant.product import prompt_for  # noqa: PLC0415

        feat = dict(features or {})
        scen_type = scenario or "direct"

        class _PreviewAgent:
            heartbeat_enabled = bool(feat.get("heartbeat", False))
            cron_enabled = bool(feat.get("cron_scheduling", False))

        _PreviewAgent.custom_prompt = custom_prompt  # type: ignore[attr-defined]
        prompt_scenario: dict = {"conversation_type": scen_type}
        prompt = prompt_for(_PreviewAgent(), scenario=prompt_scenario)

        return kernel.assemble_prompt_preview(
            workspace_root=_Path(workspace_root) if workspace_root else None,
            features=feat,
            tool_ids=list(tool_ids) if tool_ids else [],
            scenario=scen_type,
            skill_ids=list(skill_ids) if skill_ids else [],
            prompt=prompt,
            enabled_tools=list(tool_ids) if tool_ids else None,
        )

    return _provider  # type: ignore[return-value]


def build_runtime(config: LocalConfig) -> runtime.GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config.

    refactor-387 M3: kernel is now in-process via agent.sdk.  No kernel child
    no independent Kernel process is spawned.
    """
    # refactor-406-M1 R6: PA assembles its kernel through the 2-layer SDK surface
    # via its own factory (personal_assistant.product).  PA imports only agent.sdk +
    # its own package — no product_profile / host_capabilities.
    from agent.sdk import LLMConfig
    from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
    from personal_assistant.product import PA_SKILL_SEARCH_ROOTS, build_pa_kernel

    # PA does not supply can_use_tool: permission ask always parks on broker future
    # and is resolved by the user clicking Allow/Deny on the IM card via
    # kernel.submit_permission_decision.  Unattended origins (heartbeat/cron) short-circuit
    # before reaching ask via auto_mode_gate's unattended_fallback — they never park.
    #
    # The LLM catalog + active connection come from the Gateway config's ``llm:``
    # block (config.llm, an LLMConfigPayload) — NOT from_env — so the configured
    # default_model + provider catalog (incl. per-model extra_request_body like the
    # K2.6 thinking config) flow into build_kernel and the model registry.  decision 5:
    # build_kernel owns registry init internally from this LLMConfig.
    llm = LLMConfig.from_payload(config.llm)

    try:
        installed_builtin_skills = install_builtin_skills()
        if installed_builtin_skills:
            installed_names = ", ".join(sorted(installed_builtin_skills))
            _log.info(
                "installed built-in personal assistant skills: %s", installed_names
            )
    except Exception:  # noqa: BLE001
        _log.warning(
            "failed to install built-in personal assistant skills", exc_info=True
        )
    config_owner = RuntimeConfigOwner(config)
    _, feishu_skill_config_changed = ensure_feishu_doc_skill_for_feishu_agents(config)
    if feishu_skill_config_changed:
        # Startup may still hold legacy channel credentials. Keep every bootstrap
        # mutation on the sensitive writer until manifest migration removes them,
        # otherwise the ordinary writer can copy the legacy secret into backups.
        config = config_owner.persist(
            lambda current: ensure_feishu_doc_skill_for_feishu_agents(current)[0],
            save_config=save_sensitive_local_config,
        )

    # CronServiceRegistry holds the per-agent CronExecutionService map + lifecycle
    # (set_gateway_loop / drain_all / register).  refactor-406 决策 9: the cron *tool*
    # holds this registry's mutable ``services`` dict directly and routes by agent_id —
    # no HostCapabilityDispatcher round-trip into the kernel.  Sharing the same dict
    # reference means services registered after build (post-kernel_shim) are visible to
    # the already-built tool closure.
    _cron_dispatcher = CronServiceRegistry()
    # The listener URL is a process-scoped capability. Construct its lifecycle owner
    # before the PA Kernel so send_message can resolve current_url on every tool call;
    # durable session metadata remains only a standalone/backward-compatible seed.
    _internal_dispatch_endpoint = InternalDispatchEndpoint()

    kernel = build_pa_kernel(
        llm=llm,
        cron_services=_cron_dispatcher.services,  # shared mutable map (决策 9)
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        # can_use_tool=None: IM card flow; see submit_permission_decision.
    )

    agent_catalog = LiveAgentCatalog(config.agents)
    permission_response_handler = _build_permission_response_handler(kernel=kernel)

    runtime_dir = config.source_path.parent
    # Shared GroupContextStore for FeishuAdapter (non-mention group message buffer)
    # and InboundPipeline (context retrieval). Must be a single instance.
    group_context_store = GroupContextStore(
        db_path=runtime_dir / "group_context_buffer.sqlite3"
    )
    # The shim builds per-session PromptSlots/enabled_tools/features from agent config
    # (决策 8). The shared LiveAgentCatalog keeps heartbeat/cron session creation
    # current when config sync publishes a new Agent revision.
    channel_registry = _build_channel_registry(
        config.channels,
        dedup_db_path=runtime_dir / "relay_dedup.sqlite3",
        group_context_store=group_context_store,
        feishu_owner_open_id_binder=_build_feishu_owner_open_id_binder(
            config, config_owner=config_owner
        ),
        feishu_permission_decision_callback=permission_response_handler,
    )
    outbound_router = OutboundRouter(channel_registry)
    # Use SQLite-backed store so kernel session mappings survive gateway restarts
    # (NodeGateway-SPEC §4.2).  Live session validation is owned by
    # GatewaySessionBinder via the in-process Kernel — no HTTP kernel client is needed.
    # Must be created before HeartbeatScheduler so the store can be injected for
    # tick-time canonical session lookup (feat-394 decision 3).
    session_store = PersistentSessionBindingStore(
        db_path=runtime_dir / "session_bindings.sqlite3"
    )
    session_binder = GatewaySessionBinder(
        catalog=agent_catalog,
        repository=session_store,
        kernel=kernel,
    )
    kernel_shim = kernel_client.InProcessKernelClient(
        kernel,
        agent_catalog=agent_catalog,
        session_binder=session_binder,
        product_default_model=config.llm.default_model,
    )
    # feat-394 decision 3: canonical direct-chat kernel session store.
    # Updated by HeartbeatScheduler.tick() via session_store.find_direct_by_agent()
    # BEFORE each run submission (tick-time read, no reactive ack dependency).
    # This replaces the prior approach of populating from turn_start ack, which failed
    # for first-tick / restart / silent-polling scenarios (silent polls never ack → never fill).
    _canonical_session_store: dict[str, str] = {}
    reporter: UpstreamReporter | None = None
    im_connection_manager: IMConnectionManager | None = None
    managed_channel_control: ManagedChannelControl | None = None
    im_bootstrap_client: _IMBootstrapClient | None = None
    im_config_sync_client: IMAgentConfigSync | None = None
    run_delivery_contexts = RunDeliveryContextStore()
    _owner_user_id = config.node.user_id or ""
    _gateway_internal_port = 0
    shadow_sync: IMShadowConversationSync | None = None
    image_resolver = ImageAttachmentResolver()

    def _send_external_reply(text: str, metadata: Mapping[str, str]) -> None:
        channel_name = metadata.get("channel_name") or ""
        target_chat_id = metadata.get("target_chat_id") or ""
        if not channel_name or not target_chat_id:
            return
        reply_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in {"channel_name", "target_chat_id", "reply_thread_id"}
        }
        outbound_router.send_text(
            text=text,
            reply_context=ReplyContext(
                channel_name=channel_name,
                target_chat_id=target_chat_id,
                thread_id=metadata.get("reply_thread_id") or None,
                metadata=reply_metadata,
            ),
        )

    def _send_external_permission_request(
        request: Mapping[str, Any], metadata: Mapping[str, str]
    ) -> None:
        channel_name = metadata.get("channel_name") or ""
        target_chat_id = metadata.get("target_chat_id") or ""
        if not channel_name or not target_chat_id:
            return
        adapter = channel_registry.get(channel_name)
        sender = getattr(adapter, "send_permission_request", None)
        if not callable(sender):
            return
        sender(
            target_chat_id=target_chat_id,
            request=request,
            run_id=metadata.get("run_id") or "",
        )

    def _mark_external_permission_resolved(
        request_id: str, decision: str, metadata: Mapping[str, str]
    ) -> None:
        channel_name = metadata.get("channel_name") or ""
        if not channel_name:
            return
        adapter = channel_registry.get(channel_name)
        resolver = getattr(adapter, "mark_permission_resolved", None)
        if not callable(resolver):
            return
        resolver(request_id=request_id, decision=decision)

    def _on_agent_created(agent_id: str, workspace_root: Path) -> None:
        try:
            gateway_loop = asyncio.get_running_loop()
        except RuntimeError:
            gateway_loop = None
        _register_cron_service(agent_id, workspace_root, gateway_loop=gateway_loop)

    if config.im_service is not None:
        relay_adapter = channel_registry.get("web_relay")
        if not isinstance(relay_adapter, WebRelayAdapter):
            raise ValueError("im_service requires enabled web_relay channel")
        channel_key = GatewayChannelKeyStore(
            runtime_dir / "channel-credentials-v1.pem"
        ).load_or_create()
        channel_manifest_store = ChannelManifestStore(
            runtime_dir / "channel-manifest-v1.json",
            node_id=config.node.node_id,
            key_id=channel_key.key_id,
        )

        reporter = UpstreamReporter(
            node=config.node,
            agents=config.agents,
            send_frame=lambda _message_type, _payload: None,
            capabilities=build_runtime_capabilities(kernel),
            channel_credential_key=channel_key.registration_payload(),
        )
        # bugfix-424 (#127): derive dynamically-created agents' workspace from the
        # node's configured workspace_base so they land under the same isolation
        # root as preset agents (e.g. a worktree's `.gateway-workspace`) instead of
        # the hardcoded `~/nano-assistant/workspace` default. When workspace_base is
        # unset the factory stays None and the config sync keeps its legacy
        # default — existing deployments are unaffected.
        workspace_root_factory = _make_workspace_root_factory(
            config.node.workspace_base
        )
        im_config_sync_client = IMAgentConfigSync(
            base_url=config.im_service.url,
            token=config.im_service.token,
            agent_catalog=agent_catalog,
            session_binder=session_binder,
            local_config=config,
            config_owner=config_owner,
            reporter=reporter,
            workspace_root_factory=workspace_root_factory,
            global_skill_root=PA_SKILL_SEARCH_ROOTS[0],
            on_agent_created=_on_agent_created,
        )
        # Build a token_getter closure that auto-refreshes the access token on reconnect.
        # The auth client uses the IM HTTP base URL so it can reach /im/v1/auth/* endpoints.
        _auth_client = IMAuthClient(
            base_url=normalize_im_http_base_url(config.im_service.url)
        )
        _raw_token_getter = _make_token_getter(
            im_service=config.im_service,
            local_config=config,
            config_owner=config_owner,
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

        shadow_sync = IMShadowConversationSync(
            base_url=config.im_service.url,
            token_getter=_token_getter,
            owner_user_id=_owner_user_id,
        )
        image_resolver = ImageAttachmentResolver(
            fetcher=_build_attachment_fetcher(token_getter=_token_getter)
        )

        # M3: permission response handler is no longer wired — the SDK's can_use_tool
        # callback handles all permission decisions in-process (design decision 3).
        _im_sync_client = ConfigSyncClient(fetcher=im_config_sync_client.sync_agent)

        im_bootstrap_client = _IMBootstrapClient(
            base_url=normalize_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=_token_getter,
        )

        # feat-394-M12 决策 F: reconcile 回调——WS bind 完成后（含重连）拉全量 profile
        # 对账，消除漏推送导致的内存状态滞留。reconcile_all_agents 是同步 HTTP 调用，
        # 用 asyncio.to_thread 包装使其在 WS 事件循环中安全运行。
        # bugfix-446-M1 决策 3: node binding 并入 on_connected（移出启动关键路径）。
        # ensure_node_binding 对已绑定节点幂等（return None），其失败都是连接恢复期
        # 的瞬态条件或需人工处理的绑定问题。两者都不能阻断 agent reconcile；失败先
        # 以 degraded heartbeat 暴露给 IM，再让配置对账继续收敛。
        async def _reconcile_on_connect(
            connection: ManagedChannelConnectionSender,
        ) -> None:
            try:
                await asyncio.to_thread(
                    im_bootstrap_client.ensure_node_binding,
                    node_id=config.node.node_id,
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, GatewayStartupError):
                    summary = exc.summary
                    next_step = exc.next_step
                else:
                    summary = f"node {config.node.node_id} binding failed: {exc}"
                    next_step = None
                heartbeat_last_error = (
                    f"{summary}; next step: {next_step}" if next_step else summary
                )
                _log.warning("IM node binding failed during reconnect: %s", summary)
                _emit_gateway_feedback("ERROR", summary, next_step)
                try:
                    await connection.send_json(
                        "node.heartbeat",
                        reporter.send_heartbeat(
                            status="degraded", last_error=heartbeat_last_error
                        ),
                    )
                except Exception as heartbeat_exc:  # noqa: BLE001
                    _log.warning(
                        "failed to send degraded IM heartbeat after binding failure: %s",
                        heartbeat_exc,
                    )
            if managed_channel_control is not None:
                await managed_channel_control.reconcile_after_register(connection)
            memory_versions = {
                agent_id: ver
                for agent_id in (a.agent_id for a in config.agents)
                if (ver := _im_sync_client.latest_profile_version(agent_id)) is not None
            }
            await asyncio.to_thread(
                im_config_sync_client.reconcile_all_agents,
                memory_versions=memory_versions,
            )

    relay_lifecycle_callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        owner_user_id=_owner_user_id,
        channel_registry=channel_registry,
    )

    runtime_delivery_tasks = RuntimeDeliveryTaskTracker()
    _kernel_event_observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        external_reply_sender=_send_external_reply,
        external_permission_request_sender=_send_external_permission_request,
        external_permission_resolved_sender=_mark_external_permission_resolved,
        skill_created_handler=getattr(
            im_config_sync_client, "handle_skill_created", None
        ),
        task_tracker=runtime_delivery_tasks,
    )
    bg_reply_sender = _build_bg_reply_sender(
        im_connection_manager_factory=lambda: im_connection_manager,
        external_reply_sender=_send_external_reply,
    )
    session_event_callback = None
    if config.im_service is not None:
        # feat-349-M3: wire background session event callback so self_evolution_review
        # events published by background hooks reach IM as system/meta messages.
        session_event_callback = _build_session_event_callback(
            im_connection_manager_factory=lambda: im_connection_manager,
        )

    background_subscriptions = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=session_event_callback,
        bg_reply_sender=bg_reply_sender,
    )
    run_coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=session_binder,
        outbound_router=outbound_router,
        group_context_store=group_context_store,
        gateway_internal_port=_gateway_internal_port,
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        product_default_model=config.llm.default_model,
        relay_lifecycle_callback=relay_lifecycle_callback,
        kernel_event_observer=_kernel_event_observer,
        bg_reply_sender=bg_reply_sender,
        background_subscriptions=background_subscriptions,
        image_resolver=image_resolver,
    )
    pipeline = InboundPipeline(
        agent_catalog=agent_catalog,
        run_coordinator=run_coordinator,
        group_context_store=group_context_store,
        route_config=InboundRouteConfig(),
        shadow_sync=shadow_sync,
    )
    inbound_dispatcher = InboundDispatcher(pipeline)
    if config.im_service is not None:
        assert im_config_sync_client is not None
        managed_channel_control = ManagedChannelControl(
            node_id=config.node.node_id,
            channel_key=channel_key,
            manifest_store=channel_manifest_store,
            registry=channel_registry,
            on_inbound=inbound_dispatcher,
            agent_config_sync=im_config_sync_client,
            group_context_store=group_context_store,
            permission_decision_callback=permission_response_handler,
        )

    # bugfix-402-M4 R4 / bugfix-402-M6: build per-agent CronExecutionService and
    # register with dispatcher. execute_fn captures only owners already constructed;
    # the runtime-delivery observer is supplied directly rather than read from a
    # heartbeat runner private field.
    #
    # bugfix-402 round-2: routing key changed from workspace_root to agent_id —
    # workspace_root has two data sources (local YAML vs IM-synced value from
    # reconcile_all_agents), causing lookup misses when the two differ.
    def _register_cron_service(
        agent_id: str,
        ws_root: Path,
        *,
        gateway_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Create a CronExecutionService for agent and register it with the dispatcher.

        bugfix-402-M6: extracted from the startup loop so handle_agent_create can
        call the same path for dynamically created agents.
        workspace_root must already be resolved (expanduser().resolve()).

        bugfix-402 round-2 code-review fix: gateway_loop is explicitly passed in
        rather than discovered via get_running_loop() at registration time.  When
        called from on_agent_created (inside the WS event loop), pass
        asyncio.get_running_loop() at the call site — not inside this function —
        so the loop reference comes from the caller's known context rather than
        an implicit environment that may not exist in all call paths.
        When called during static startup (before _run_until_shutdown sets the
        loop), pass None; set_gateway_loop() will inject the loop later.
        """
        # Skip if already registered (idempotent — reconcile may call multiple times).
        if _cron_dispatcher.resolve(agent_id) is not None:
            return
        runner = CronRunner(
            agent_id=agent_id,
            workspace_root=ws_root,
            kernel_client=kernel_shim,
            session_binder=session_binder,
            canonical_session_id_provider=lambda: _canonical_session_store.get(
                agent_id
            ),
        )
        terminal_consumer = CronRunTerminalConsumer(
            kernel=kernel,
            owner_user_id=_owner_user_id,
            run_context_store=run_delivery_contexts,
            observer=(
                _kernel_event_observer
                if _owner_user_id and _kernel_event_observer is not None
                else None
            ),
        )
        service = CronExecutionService(
            agent_id=agent_id,
            workspace_root=ws_root,
            runner=runner,
            terminal_consumer=terminal_consumer,
            gateway_loop=gateway_loop,
        )
        _cron_dispatcher.register(agent_id, service)
        # Converge stale accepted/running records from any previous crash so they
        # are never permanently in-progress.
        service.converge_stale_on_restart()

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
        agent_snapshot = agent_catalog.get(agent_id)
        if agent_snapshot is None or not agent_snapshot.config.cron_enabled:
            return
        agent_cfg = agent_snapshot.config
        ws_root = Path(agent_cfg.workspace_root).expanduser().resolve()

        # bugfix-402 round-2: route by agent_id, not workspace_root.
        # workspace_root from pipeline may differ from the registered key when
        # reconcile_all_agents() rewrites it from IM (IM stores the original main
        # config path; the registered CronExecutionService may use a local/worktree
        # path).  agent_id is stable and unambiguous across all data sources.
        _service = _cron_dispatcher.resolve(agent_id)
        if _service is None:
            # Agent was dynamically registered after startup (IM config sync) without a
            # corresponding CronExecutionService.  Warn and skip — the service will be
            # created on the next Gateway restart when the agent appears in config.agents.
            _log.warning(
                "cron tick: no CronExecutionService for agent=%s; skipping",
                agent_id,
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

    _heartbeat_scheduler = HeartbeatScheduler(
        agents=config.agents,
        kernel_client=kernel_shim,
        state_store=HeartbeatSchedulerStateStore(_default_heartbeat_state_path(config)),
        canonical_session_store=_canonical_session_store,
        agent_catalog=agent_catalog,
        session_binder=session_binder,
        is_session_busy=run_coordinator.is_session_busy,
    )
    polling_heartbeat_runner = heartbeat_runner.PollingHeartbeatRunner(
        scheduler=_heartbeat_scheduler,
        config=config.heartbeat,
        kernel=kernel if _owner_user_id else None,
        run_context_store=run_delivery_contexts if _owner_user_id else None,
        owner_user_id=_owner_user_id,
        agent_catalog=agent_catalog,
        kernel_event_observer=(_kernel_event_observer if _owner_user_id else None),
        cron_tick_fn=_cron_tick_for_agent,
    )

    if config.im_service is not None:
        assert reporter is not None
        assert im_config_sync_client is not None
        im_connection_manager = _build_im_connection_manager(
            config=config,
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_runner=polling_heartbeat_runner,
            sync_client=_im_sync_client,
            agent_config_provider=lambda agent_id: (
                im_config_sync_client.current_agent_payload(agent_id=agent_id)
            ),
            agent_capabilities_provider=lambda agent_id, workspace_root: (
                build_agent_capabilities_payload(
                    kernel,
                    workspace_root=workspace_root,
                    tool_allowlist=_resolve_agent_tool_allowlist(
                        im_config_sync_client, agent_id
                    ),
                )
            ),
            node_capabilities_provider=lambda: build_node_capabilities_payload(kernel),
            prompt_preview_provider=_make_prompt_preview_provider(kernel),
            agent_create_handler=im_config_sync_client.handle_agent_create,
            session_fork_handler=_build_session_fork_handler(
                kernel=kernel,
                session_binder=session_binder,
                channel_name=WebRelayAdapter.name,
            ),
            token_getter=_token_getter,
            permission_response_handler=permission_response_handler,
            on_connected=_reconcile_on_connect,
            managed_channel_bindings=managed_channel_control.connection_bindings(),
        )

    # bugfix-402-M3 R3: kernel is closed explicitly via runtime.GatewayRuntime(kernel=) and
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
        session_binder=session_binder,
    )
    return runtime.GatewayRuntime(
        config,
        channel_registry=channel_registry,
        heartbeat_runner=polling_heartbeat_runner,
        im_connection_manager=im_connection_manager,
        on_inbound=inbound_dispatcher,
        resource_closers=tuple(closers),
        internal_dispatch_handler=internal_dispatch_handler,
        internal_dispatch_endpoint=_internal_dispatch_endpoint,
        kernel=kernel,
        cron_dispatcher=_cron_dispatcher,
        managed_channel_control=managed_channel_control,
        run_coordinator=run_coordinator,
        runtime_delivery_tasks=runtime_delivery_tasks,
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
            result = restart_gateway(
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
    group_context_store: GroupContextStore | None = None,
    feishu_owner_open_id_binder: Callable[[str, str], str | None] | None = None,
    feishu_permission_decision_callback: (
        Callable[[Mapping[str, object]], bool | None] | None
    ) = None,
) -> ChannelRegistry:
    has_feishu = any(
        ch.enabled
        and ch.name.startswith("feishu:")
        and isinstance(ch.settings.get("appSecret"), str)
        for ch in channels
    )
    if has_feishu and group_context_store is None:
        raise ValueError(
            "group_context_store is required when feishu channels are enabled"
        )
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
        # feat-447: feishu channels are named "feishu:<agent_id>"
        if channel.name.startswith("feishu:"):
            settings = channel.settings
            if "credentialRef" in settings and "appSecret" not in settings:
                continue
            registry.register(
                FeishuAdapter(
                    name=channel.name,
                    app_id=settings["appId"],
                    app_secret=settings["appSecret"],
                    bot_open_id=settings.get("botOpenId"),
                    owner_open_id=settings.get("ownerOpenId"),
                    owner_open_id_binder=feishu_owner_open_id_binder,
                    permission_decision_callback=feishu_permission_decision_callback,
                    group_context_store=group_context_store,
                )
            )
            continue
        raise ValueError(f"unsupported channel adapter: {channel.name}")
    return registry


def _build_feishu_owner_open_id_binder(
    config: LocalConfig,
    *,
    config_owner: RuntimeConfigOwner | None = None,
    save_config: Callable[
        [LocalConfig, str | Path], None
    ] = save_sensitive_local_config,
) -> Callable[[str, str], str | None]:
    """Bind missing Feishu ownerOpenId to the first real sender for an adapter."""
    lock = threading.Lock()
    owner = config_owner or RuntimeConfigOwner(config)

    def _bind(channel_name: str, sender_open_id: str) -> str | None:
        cleaned_sender = (
            sender_open_id.strip() if isinstance(sender_open_id, str) else ""
        )
        if not cleaned_sender:
            return None
        with lock:
            existing_owner: str | None = None

            def update(current: LocalConfig) -> LocalConfig:
                nonlocal existing_owner
                for index, channel in enumerate(current.channels):
                    if channel.name != channel_name or not channel.enabled:
                        continue
                    if not channel.name.startswith("feishu:"):
                        return current
                    existing = channel.settings.get("ownerOpenId")
                    if isinstance(existing, str) and existing.strip():
                        existing_owner = existing.strip()
                        return current
                    settings = {**channel.settings, "ownerOpenId": cleaned_sender}
                    channels = list(current.channels)
                    channels[index] = replace(channel, settings=settings)
                    return replace(current, channels=tuple(channels))
                return current

            current = owner.snapshot()
            if current.source_path is not None:
                try:
                    owner.persist(update, save_config=save_config)
                except Exception:  # noqa: BLE001
                    _log.warning(
                        "failed to persist feishu ownerOpenId for channel %s",
                        channel_name,
                        exc_info=True,
                    )
                    return None
            else:
                owner.replace(update(current))
            if existing_owner is not None:
                return existing_owner
            if owner.snapshot() == current:
                return None
            _log.info(
                "bound feishu ownerOpenId from first inbound sender for channel %s",
                channel_name,
            )
            return cleaned_sender
        return None

    return _bind


def _make_token_getter(
    *,
    im_service: IMServiceConfig,
    local_config: LocalConfig,
    config_owner: RuntimeConfigOwner | None = None,
    auth_client: IMAuthClient,
    save_config: Callable[
        [LocalConfig, str | Path], None
    ] = save_sensitive_local_config,
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
    owner = config_owner or RuntimeConfigOwner(local_config)

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
        def update(current: LocalConfig) -> LocalConfig:
            old_im = current.im_service
            if old_im is None:
                return current
            updated_im = replace(
                old_im,
                token=access,
                refresh_token=new_refresh,
            )
            return replace(current, im_service=updated_im)

        if owner.snapshot().im_service is not None:
            owner.persist(update, save_config=save_config)

    return _getter


def _build_session_fork_handler(
    *,
    kernel: Any,
    session_binder: GatewaySessionBinder,
    channel_name: str,
) -> SessionForkHandler:
    """Build the gateway-side handler for IM-delegated session fork (feat-445-M1 决策 2).

    Resolves the source kernel session from the source conversation's binding, forks it
    at ``fork_point.message_id`` (kernel reproduces the source's as-of-M context view),
    and binds the new conversation to the forked session so its first inbound relay
    reuses it. Returns ``{ok, new_session_id}`` on success or ``{ok: False, error}`` —
    IM does the new-conversation rollback (decision 5), the gateway only reports.
    """

    async def _handle(payload: Mapping[str, object]) -> Mapping[str, object]:
        source_conversation_id = str(payload.get("source_conversation_id") or "")
        new_conversation_id = str(payload.get("new_conversation_id") or "")
        agent_id = str(payload.get("agent_id") or "")
        fork_point = payload.get("fork_point")
        message_id = (
            str(fork_point.get("message_id") or "")
            if isinstance(fork_point, Mapping)
            else ""
        )
        if not (
            source_conversation_id and new_conversation_id and agent_id and message_id
        ):
            return {"ok": False, "error": "fork request missing required fields"}

        source = session_binder.capture_binding_provenance(
            build_conversation_session_key(
                channel_name=channel_name,
                conversation_id=source_conversation_id,
                agent_id=agent_id,
            ),
            expected_agent_id=agent_id,
        )
        if source is None:
            external_source = str(payload.get("source_external_source") or "").strip()
            external_chat_id = str(payload.get("source_external_chat_id") or "").strip()
            if external_source and external_chat_id:
                source = session_binder.capture_binding_provenance(
                    build_external_session_key(
                        external_source=external_source,
                        external_chat_id=external_chat_id,
                        agent_id=agent_id,
                    ),
                    expected_agent_id=agent_id,
                )
        if source is None:
            return {"ok": False, "error": "source session binding not found"}

        try:
            new_session = await kernel.fork_session(
                source.binding.kernel_session_id,
                workspace_root=source.agent.config.workspace_root,
                up_to=message_id,
            )
        except Exception as exc:  # noqa: BLE001 — report to IM, which rolls back
            return {"ok": False, "error": str(exc)}

        bind_result = session_binder.bind_conversation(
            ConversationBindingRequest(
                channel_name=channel_name,
                conversation_id=new_conversation_id,
                agent_id=agent_id,
                kernel_session_id=new_session.session_id,
                guard=source.guard,
            ),
            source.agent,
        )
        if bind_result.status == "stale":
            return {
                "ok": False,
                "error": "agent config changed while session fork was running",
            }
        # feat-445-M2 #5: hand back the source→branch kernel-uuid re-stamp map so IM can
        # realign each copied bubble's kernel_message_id to the branch session's JSONL
        # uuids (else a recursive fork from a copied bubble 502s on the source uuid).
        return {
            "ok": True,
            "new_session_id": new_session.session_id,
            "id_map": dict(new_session.fork_id_map or {}),
        }

    return _handle


def _build_im_connection_manager(
    *,
    config: LocalConfig,
    relay_adapter: WebRelayAdapter,
    reporter: UpstreamReporter,
    heartbeat_runner: heartbeat_runner.PollingHeartbeatRunner,
    sync_client: ConfigSyncClient | None = None,
    agent_config_provider: Callable[[str], dict[str, object] | None] | None = None,
    agent_capabilities_provider: Callable[[str, str], dict[str, object]] | None = None,
    node_capabilities_provider: Callable[[], dict[str, object]] | None = None,
    prompt_preview_provider: Callable[..., Any] | None = None,
    agent_create_handler: AgentCreateHandler | None = None,
    session_fork_handler: SessionForkHandler | None = None,
    token_getter: Callable[[], Awaitable[str | None]] | None = None,
    permission_response_handler: Callable[[Mapping[str, object]], bool] | None = None,
    on_connected: Callable[[], Awaitable[None]] | None = None,
    managed_channel_bindings: ManagedChannelBindings | None = None,
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
        node_capabilities_provider=node_capabilities_provider,
        prompt_preview_provider=prompt_preview_provider,
        agent_create_handler=agent_create_handler,
        session_fork_handler=session_fork_handler,
        token_getter=token_getter,
        connect=_connect_websocket,
        permission_response_handler=permission_response_handler,
        on_connected=on_connected,
        managed_channel_bindings=managed_channel_bindings,
    )


def _build_permission_response_handler(
    *,
    kernel: Any,
) -> Callable[[Mapping[str, object]], bool]:
    """Build handler that routes IM permission_response frames to the kernel.

    The frame carries ``request_id``, ``decision``, and an optional ``reason``.
    request_id is globally unique (assigned by auto_mode_gate at ask time), so
    no session lookup is required — the broker finds the pending future by id.
    """

    def _handler(body: Mapping[str, object]) -> bool:
        request_id = str(body.get("request_id") or "").strip()
        decision = str(body.get("decision") or "").strip()
        if not request_id or not decision:
            return False
        reason = str(body.get("reason") or "").strip()
        try:
            return bool(
                kernel.submit_permission_decision(
                    request_id=request_id,
                    decision=decision,
                    reason=reason,
                )
            )
        except Exception:  # noqa: BLE001 — side-effect; failure must not cascade
            return False

    return _handler


def _build_attachment_fetcher(
    *,
    token_getter: "Callable[[], Awaitable[str | None]]",
) -> "Callable[[str], Awaitable[bytes]]":
    """Build an async callable that downloads an IM attachment URL to raw bytes.

    bugfix-433 决策1: the inbound pipeline uses this to turn an IM-hosted HTTP image
    URL (unreachable to a remote provider) into a self-contained base64 data URL. The
    URL is the full attachment URL carried on the relay message; auth uses the live IM
    access token. Any HTTP / network error raises so the pipeline stops the turn and
    replies with the fixed "没能加载" message (决策5).
    """
    import httpx  # noqa: PLC0415

    async def _fetch(url: str) -> bytes:
        token = await token_getter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=build_im_http_headers(token))
            response.raise_for_status()
            return response.content

    return _fetch


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


def _legacy_gateway_pid_path(config: LocalConfig) -> Path:
    """Return the pre-refactor PID file path used only during live migration.

    Returns:
        Path to ``gateway.pid`` inside the config's runtime directory.
    """
    return config.source_path.parent / "gateway.pid"


@contextmanager
def _gateway_lifecycle_lock(config_path: str | Path) -> Iterator[None]:
    """Serialize lifecycle operations for one resolved config across processes."""
    resolved = Path(config_path).expanduser().resolve()
    lock_path = resolved.parent / f".{resolved.name}.gateway-lifecycle.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _remove_legacy_gateway_pid(
    config: LocalConfig, *, expected_pid: int | None = None
) -> None:
    """Remove a legacy ``gateway.pid`` only while it names the expected process.

    Side Effects:
        Deletes the PID file; silently succeeds if the file is already gone.
    """
    if expected_pid is not None and _read_legacy_gateway_pid(config) != expected_pid:
        return
    with suppress(FileNotFoundError):
        _legacy_gateway_pid_path(config).unlink()


def _read_legacy_gateway_pid(config: LocalConfig) -> int | None:
    """Read a pre-refactor ``gateway.pid``, or ``None`` if absent/invalid.

    Returns:
        Integer PID when the file exists and contains a parseable integer; ``None`` otherwise.
    """
    pid_path = _legacy_gateway_pid_path(config)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _process_start_identity(pid: int) -> str | None:
    """Read the OS process birth identity for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    return " ".join(value.split())


def _process_command(pid: int) -> str | None:
    """Read the full live command for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    command = result.stdout.strip()
    return command if result.returncode == 0 and command else None


def _process_cwd(pid: int) -> Path | None:
    """Return the live process working directory when the OS exposes it."""
    proc_cwd = Path(f"/proc/{pid}/cwd")
    try:
        return proc_cwd.resolve(strict=True)
    except (FileNotFoundError, OSError):
        pass
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve()
    return None


def _legacy_gateway_command_matches(
    command: str, *, pid: int, config: LocalConfig
) -> bool:
    """Validate one legacy Gateway command by argv semantics, not formatting."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if (
        not any(
            argv[index : index + 2] == ["-m", "personal_assistant.main"]
            for index in range(max(0, len(argv) - 1))
        )
        or "--foreground" not in argv
    ):
        return False

    raw_config: str | None = None
    for index, value in enumerate(argv):
        if value == "--config" and index + 1 < len(argv):
            raw_config = argv[index + 1]
            break
        if value.startswith("--config="):
            raw_config = value.split("=", 1)[1]
            break
    if raw_config is None:
        candidate = default_local_config_path()
    else:
        candidate = Path(raw_config).expanduser()
        if not candidate.is_absolute():
            cwd = _process_cwd(pid)
            if cwd is None:
                return False
            candidate = cwd / candidate
    return candidate.resolve() == config.source_path.resolve()


def _upgrade_legacy_gateway_state(
    config: LocalConfig,
    pid: int,
    state: GatewayRuntimeState | None,
) -> GatewayRuntimeState | None:
    """Adopt a legacy PID only after its live command proves Gateway ownership."""
    before = _process_start_identity(pid)
    if before is None:
        return None
    command = _process_command(pid)
    after = _process_start_identity(pid)
    if after is None:
        return None
    if before != after:
        raise RuntimeError("legacy Gateway process changed; evidence retained")
    config_path = str(config.source_path.resolve())
    if command is None or not _legacy_gateway_command_matches(
        command, pid=pid, config=config
    ):
        raise RuntimeError("legacy Gateway ownership mismatch; evidence retained")
    upgraded = (
        replace(state, process_start=after)
        if state is not None
        else GatewayRuntimeState(
            pid=pid,
            process_start=after,
            config_path=config_path,
            log_path=str(_default_gateway_log_path(config)),
        )
    )
    if state is not None:
        _write_gateway_state(config, upgraded)
    _log.warning(
        "adopted legacy Gateway lifecycle evidence after live command verification"
    )
    return upgraded


def _assert_gateway_state_static(
    config: LocalConfig,
    state: GatewayRuntimeState,
    *,
    expected_pid: int | None = None,
) -> None:
    """Reject state that does not claim the selected PID and resolved config."""
    if (expected_pid is not None and state.pid != expected_pid) or Path(
        state.config_path
    ).resolve() != config.source_path.resolve():
        raise RuntimeError("gateway state does not match process and config")


def _gateway_process_matches(state: GatewayRuntimeState) -> bool:
    """Return whether the PID still names the original process birth."""
    return (
        state.process_start is not None
        and _process_start_identity(state.pid) == state.process_start
    )


def _signal_gateway_process(state: GatewayRuntimeState, sig: int) -> bool:
    """Signal the original Gateway instance after rechecking its PID birth."""
    if not _gateway_process_matches(state):
        return False
    try:
        pgid = os.getpgid(state.pid)
    except ProcessLookupError:
        return False
    if not _gateway_process_matches(state):
        return False
    try:
        if pgid == state.pid:
            os.killpg(pgid, sig)
        else:
            # Foreground launches do not own their shell's process group.
            os.kill(state.pid, sig)
    except ProcessLookupError:
        return False
    return True


def _gateway_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / ".gateway-state.json"


def _write_gateway_state(config: LocalConfig, state: GatewayRuntimeState) -> None:
    """Atomically publish the single lifecycle state document."""
    path = _gateway_state_path(config)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path: Path | None = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(asdict(state), stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _read_gateway_state(state_path: Path) -> GatewayRuntimeState | None:
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return GatewayRuntimeState(
        pid=int(payload["pid"]),
        config_path=str(payload["config_path"]),
        log_path=str(payload["log_path"]),
        process_start=(
            str(payload["process_start"]).strip()
            if payload.get("process_start") is not None
            else None
        ),
    )


def _remove_gateway_state(
    state_path: Path, *, expected: GatewayRuntimeState | None = None
) -> None:
    if expected is not None and _read_gateway_state(state_path) != expected:
        return
    with suppress(FileNotFoundError):
        state_path.unlink()


def _resolve_agent_tool_allowlist(
    sync_client: "IMAgentConfigSync",
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


def _im_bootstrap_base_urls(url: str) -> tuple[str, ...]:
    return (normalize_im_http_base_url(url),)


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


def _wait_for_gateway_start(
    process: ProcessLike, config: LocalConfig, timeout_seconds: float
) -> None:
    """Wait for the background Gateway child to publish complete lifecycle state.

    This is a process-start confirmation, not a runtime/channel readiness signal.
    ``run_gateway`` writes one atomic state document before entering ``run_forever``.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"gateway exited before startup confirmation with return code {return_code}"
            )
        state = _read_gateway_state(_gateway_state_path(config))
        if state is not None and state.process_start is not None:
            _assert_gateway_state_static(config, state, expected_pid=process.pid)
            if not _gateway_process_matches(state):
                raise RuntimeError(
                    "gateway exited before process identity confirmation"
                )
            return
        time.sleep(config.gateway.poll_interval_seconds or 0.2)
    raise RuntimeError(
        "timed out waiting for gateway startup confirmation "
        "(lifecycle state never appeared)"
    )


def _stop_background_process(process: ProcessLike, *, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    # Gateway owns the session created by start_new_session=True. Terminating the
    # process group also reaps channel/tool descendants owned by that Gateway.
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

    Gateway 后台启动时 ``start_new_session=True``，其 channel/tool 后代进程位于同一 pgid。
    killpg 一次性回收 Gateway 拥有的整棵进程树。
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
    gateway_runtime: runtime.GatewayRuntimeLike,
) -> SignalHandlerInstaller:
    def _installer() -> Callable[[], None]:
        if not isinstance(gateway_runtime, runtime.GatewayRuntime):
            return lambda: None
        if threading.current_thread() is not threading.main_thread():
            return lambda: None

        previous: dict[signal.Signals, Any] = {}

        def _handler(_signum: int, _frame: Any) -> None:
            gateway_runtime.request_shutdown()

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


if __name__ == "__main__":
    raise SystemExit(main())
