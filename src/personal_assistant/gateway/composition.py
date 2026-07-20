"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

_log = logging.getLogger("personal_assistant.gateway.composition")
_PA_GLOBAL_SKILL_ROOT = Path("~/.nanoassistant/skills")

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
    ManagedChannelControl,
)
from personal_assistant.gateway import (
    connection_ready,
    im_bootstrap,
    kernel_client,
    runtime,
)
from personal_assistant.scheduler import heartbeat_runner
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync,
    _make_workspace_root_factory,
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
    build_bg_reply_sender,
    build_session_event_callback,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
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


def compose_gateway(config: LocalConfig) -> runtime.GatewayRuntime:
    """Compose the default long-running gateway runtime from parsed local config.

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
    im_bootstrap_client: im_bootstrap.IMBootstrapClient | None = None
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

        im_bootstrap_client = im_bootstrap.IMBootstrapClient(
            base_url=normalize_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=_token_getter,
        )

    relay_lifecycle_callback = build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        owner_user_id=_owner_user_id,
        channel_registry=channel_registry,
    )

    runtime_delivery_tasks = RuntimeDeliveryTaskTracker()
    _kernel_event_observer = build_kernel_event_observer(
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
    bg_reply_sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: im_connection_manager,
        external_reply_sender=_send_external_reply,
    )
    session_event_callback = None
    if config.im_service is not None:
        # feat-349-M3: wire background session event callback so self_evolution_review
        # events published by background hooks reach IM as system/meta messages.
        session_event_callback = build_session_event_callback(
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
        assert im_bootstrap_client is not None
        connection_ready_coordinator = connection_ready.ConnectionReadyCoordinator(
            node_id=config.node.node_id,
            bootstrap_client=im_bootstrap_client,
            reporter=reporter,
            managed_channel_bindings=managed_channel_control.connection_bindings(),
            sync_client=_im_sync_client,
            agent_config_sync=im_config_sync_client,
            agent_ids=(agent.agent_id for agent in config.agents),
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
            on_connected=connection_ready_coordinator.on_connected,
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


async def _connect_websocket(url: str, headers: Mapping[str, str]) -> ClientConnection:
    return await websockets.connect(
        url, additional_headers=dict(headers), user_agent_header=None
    )
