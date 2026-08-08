"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

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
    LocalConfig,
    RuntimeConfigOwner,
    build_feishu_owner_open_id_binder,
)
from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.managed_channel_control import (
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
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
)
from personal_assistant.gateway.image_attachments import (
    ImageAttachmentResolver,
    build_im_attachment_fetcher,
)
from personal_assistant.gateway.im_http_transport import normalize_im_http_base_url
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
from personal_assistant.gateway.external_control_delivery import (
    ExternalControlDeliveryMaterializer,
)
from personal_assistant.gateway.boundary_outbox import BoundaryOutboxDispatcher
from personal_assistant.gateway.shadow_saga import ExternalShadowSagaStore
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    build_session_fork_handler,
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
from personal_assistant.scheduler.cron_gateway_runtime import GatewayCronRuntime
from personal_assistant.scheduler.cron_service_registry import CronServiceRegistry
from personal_assistant.auth.im_auth_client import IMAuthClient, IMTokenProvider
from personal_assistant.ws.im_connection import (
    IMConnectionConfig,
    IMConnectionManager,
    PromptPreviewProvider,
    build_permission_response_handler,
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


def compose_gateway(config: LocalConfig) -> runtime.GatewayRuntime:
    """Compose the default long-running gateway runtime from parsed local config.

    refactor-387 M3: kernel is now in-process via agent.sdk.  No kernel child
    no independent Kernel process is spawned.
    """
    # refactor-406-M1 R6: PA assembles its kernel through the 2-layer SDK surface
    # via its own factory (personal_assistant.product).  PA imports only agent.sdk +
    # its own package — no product_profile / host_capabilities.
    from agent.sdk import LLMConfig
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
    reasoning_catalog = ModelReasoningCatalog(config.llm)

    config_owner = RuntimeConfigOwner(config)

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
        tool_approval_model=getattr(config.llm, "tool_approval_model", None),
        cron_services=_cron_dispatcher.services,  # shared mutable map (决策 9)
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        # can_use_tool=None: IM card flow; see submit_permission_decision.
    )

    agent_catalog = LiveAgentCatalog(config.agents)
    permission_response_handler = build_permission_response_handler(kernel=kernel)

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
        feishu_owner_open_id_binder=build_feishu_owner_open_id_binder(
            config, config_owner=config_owner
        ),
        feishu_permission_decision_callback=permission_response_handler,
    )
    outbound_router = OutboundRouter(channel_registry)
    # Use SQLite-backed store so kernel session mappings survive gateway restarts
    # (docs/specs/gateway/routing-delivery.md). Live session validation is owned by
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
        reasoning_catalog=reasoning_catalog,
    )
    boundary_outbox = BoundaryOutboxDispatcher(store=session_store)
    kernel_shim = kernel_client.InProcessKernelClient(
        kernel,
        agent_catalog=agent_catalog,
        session_binder=session_binder,
        product_default_model=config.llm.default_model,
        reasoning_catalog=reasoning_catalog,
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
    external_control_delivery: ExternalControlDeliveryMaterializer | None = None
    connection_ready_coordinator: connection_ready.ConnectionReadyCoordinator | None = (
        None
    )
    image_resolver = ImageAttachmentResolver()
    _kernel_event_observer: Any | None = None
    cron_runtime = GatewayCronRuntime(
        registry=_cron_dispatcher,
        agent_catalog=agent_catalog,
        kernel=kernel,
        kernel_client=kernel_shim,
        session_binder=session_binder,
        canonical_session_store=_canonical_session_store,
        owner_user_id=_owner_user_id,
        run_context_store=run_delivery_contexts,
        kernel_event_observer_provider=lambda: _kernel_event_observer,
    )

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
            capabilities=build_runtime_capabilities(
                kernel, reasoning_catalog=reasoning_catalog
            ),
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
            on_agent_created=cron_runtime.on_agent_created,
            reasoning_catalog=reasoning_catalog,
            operation_receipts=ConfigApplyReceiptStore(
                runtime_dir / "config-apply-receipts-v1.json"
            ),
        )
        # Build a token_getter closure that auto-refreshes the access token on reconnect.
        # The auth client uses the IM HTTP base URL so it can reach /im/v1/auth/* endpoints.
        token_provider = IMTokenProvider(
            im_service=config.im_service,
            local_config=config,
            config_owner=config_owner,
            auth_client=IMAuthClient(
                base_url=normalize_im_http_base_url(config.im_service.url)
            ),
        )
        token_provider.add_token_listener(im_config_sync_client.update_token)
        token_getter = token_provider.get_token

        shadow_sync = IMShadowConversationSync(
            base_url=config.im_service.url,
            token_getter=token_getter,
            owner_user_id=_owner_user_id,
            node_id=config.node.node_id,
            saga_store=ExternalShadowSagaStore(
                db_path=runtime_dir / "external_shadow_sagas.sqlite3"
            ),
            promote_pending_boundary=lambda saga_id, shadow_ref: (
                session_store.promote_pending_boundary(
                    shadow_saga_id=saga_id,
                    shadow_ref=shadow_ref,
                ),
                boundary_outbox.notify_pending(),
            )[0],
        )
        image_resolver = ImageAttachmentResolver(
            fetcher=build_im_attachment_fetcher(token_getter=token_getter)
        )

        # M3: permission response handler is no longer wired — the SDK's can_use_tool
        # callback handles all permission decisions in-process (design decision 3).
        _im_sync_client = ConfigSyncClient(fetcher=im_config_sync_client.sync_agent)

        im_bootstrap_client = im_bootstrap.IMBootstrapClient(
            base_url=normalize_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=token_getter,
        )

    relay_lifecycle_callback = build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        owner_user_id=_owner_user_id,
        channel_registry=channel_registry,
    )

    runtime_delivery_tasks = RuntimeDeliveryTaskTracker()
    shadow_output_prepare = None
    if shadow_sync is not None:
        external_control_delivery = ExternalControlDeliveryMaterializer(
            session_binder=session_binder,
            outbound_router=outbound_router,
            shadow_sync=shadow_sync,
        )

    async def _recover_external_control_and_shadows() -> None:
        """Resume the binder-to-saga handoff before ordinary shadow replay."""

        if external_control_delivery is not None:
            await external_control_delivery.drain()
        if shadow_sync is not None:
            await shadow_sync.recover_pending()

    def _notify_shadow_pending() -> None:
        if connection_ready_coordinator is not None:
            connection_ready_coordinator.notify_external_shadows_pending()

    _kernel_event_observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        external_reply_sender=_send_external_reply,
        shadow_output_prepare=shadow_output_prepare,
        shadow_output_mirror=None,
        shadow_bubble_record=(
            shadow_sync.record_bubble_event if shadow_sync is not None else None
        ),
        shadow_bubble_reconcile=(
            shadow_sync.reconcile_snapshot if shadow_sync is not None else None
        ),
        shadow_pending_notify=(
            _notify_shadow_pending if shadow_sync is not None else None
        ),
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

    async def _quiesce_run_delivery(run_id: str) -> None:
        """Hold new old-run output, then settle already permitted delivery."""

        run_delivery_contexts.quiesce(run_id)
        await runtime_delivery_tasks.drain_run(run_id)

    def _restore_run_delivery(run_id: str) -> None:
        """Release deferred old-run output when reset publication aborts."""

        run_delivery_contexts.restore(run_id)

    async def _commit_run_delivery(run_id: str) -> None:
        """Revoke old output and close any pre-existing provisional IM bubble."""

        run_delivery_contexts.suppress(run_id)
        result = _kernel_event_observer(
            {"event": "run_reset_discard", "run_id": run_id}
        )
        if asyncio.iscoroutine(result):
            await result
        runtime_delivery_tasks.cancel_run(run_id)

    run_coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=session_binder,
        outbound_router=outbound_router,
        group_context_store=group_context_store,
        gateway_internal_port=_gateway_internal_port,
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        product_default_model=config.llm.default_model,
        reasoning_catalog=reasoning_catalog,
        relay_lifecycle_callback=relay_lifecycle_callback,
        kernel_event_observer=_kernel_event_observer,
        shadow_output_prepare=shadow_output_prepare,
        bg_reply_sender=bg_reply_sender,
        node_id=config.node.node_id,
        boundary_outbox=boundary_outbox,
        quiesce_run_delivery=_quiesce_run_delivery,
        restore_run_delivery=_restore_run_delivery,
        commit_run_delivery=_commit_run_delivery,
        drain_external_control_deliveries=(
            external_control_delivery.drain
            if external_control_delivery is not None
            else None
        ),
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
            boundary_outbox=boundary_outbox,
            recover_external_shadows=(
                _recover_external_control_and_shadows
                if shadow_sync is not None
                else None
            ),
        )

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
        cron_tick_fn=cron_runtime.tick_agent,
    )

    if config.im_service is not None:
        assert reporter is not None
        assert im_config_sync_client is not None
        im_connection_manager = IMConnectionManager(
            config=IMConnectionConfig(
                url=config.im_service.url, token=config.im_service.token
            ),
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_trigger=lambda _agent_id, _reason: (
                polling_heartbeat_runner.request_tick()
            ),
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
                    reasoning_catalog=reasoning_catalog,
                )
            ),
            node_capabilities_provider=lambda: build_node_capabilities_payload(
                kernel, reasoning_catalog=reasoning_catalog
            ),
            prompt_preview_provider=_make_prompt_preview_provider(kernel),
            agent_create_handler=im_config_sync_client.handle_agent_create,
            agent_config_operation_handler=lambda kind, payload: (
                im_config_sync_client.config_operation_status(payload)
                if kind == "status"
                else im_config_sync_client.handle_agent_config_operation(kind, payload)
            ),
            session_fork_handler=build_session_fork_handler(
                kernel=kernel,
                session_binder=session_binder,
                channel_name=WebRelayAdapter.name,
            ),
            token_getter=token_getter,
            connect=_connect_websocket,
            permission_response_handler=permission_response_handler,
            on_connected=connection_ready_coordinator.on_connected,
            managed_channel_bindings=managed_channel_control.connection_bindings(),
            channel_bootstrap_items_provider=lambda owner_id: (
                channel_manifest_store.bootstrap_items(
                    owner_id=owner_id, channel_key=channel_key
                )
            ),
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
        startup_collaborators=(cron_runtime,),
        managed_channel_control=managed_channel_control,
        run_coordinator=run_coordinator,
        runtime_delivery_tasks=runtime_delivery_tasks,
        external_control_recovery=(
            external_control_delivery.drain
            if external_control_delivery is not None
            else None
        ),
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
