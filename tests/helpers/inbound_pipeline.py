"""Compose the public inbound ownership graph for behavior tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from weakref import WeakKeyDictionary

from personal_assistant.channels.base import ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
)
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_models import RelayLifecycleCallback
from personal_assistant.gateway.inbound_pipeline import (
    InboundPipeline,
    InboundRouteConfig,
    ShadowConversationSync,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    session_binding_store,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.shadow_saga import ExternalShadowOutput


@dataclass(frozen=True, slots=True)
class InboundTestGraph:
    """Expose independently owned graph nodes to tests that update their owners."""

    pipeline: InboundPipeline
    catalog: LiveAgentCatalog
    binder: GatewaySessionBinder
    coordinator: SessionRunCoordinator
    run_queue: SessionRunQueue
    session_store: SessionBindingStore


_GRAPHS: WeakKeyDictionary[InboundPipeline, InboundTestGraph] = WeakKeyDictionary()


def build_inbound_pipeline(
    *,
    kernel: Any,
    outbound_router: OutboundRouter,
    run_queue: SessionRunQueue,
    agents: tuple[AgentWorkspaceConfig, ...] = (),
    session_store: SessionBindingStore = session_binding_store,
    agent_catalog: LiveAgentCatalog | None = None,
    session_binder: GatewaySessionBinder | None = None,
    channel_bindings: Mapping[str, str] | None = None,
    default_agent_id: str | None = None,
    relay_lifecycle_callback: RelayLifecycleCallback | None = None,
    group_context_store: GroupContextStore | None = None,
    gateway_internal_port: int = 8089,
    gateway_dispatch_url_provider: Callable[[], str | None] | None = None,
    run_idle_timeout_seconds: float = 120.0,
    kernel_event_observer: Callable[[Mapping[str, Any]], object] | None = None,
    product_default_model: str | None = None,
    image_resolver: ImageAttachmentResolver | None = None,
    background_subscriptions: BackgroundSubscriptionManager | None = None,
    shadow_sync: ShadowConversationSync | None = None,
    shadow_output_prepare: (
        Callable[[str, str, str, str | None, str], ExternalShadowOutput] | None
    ) = None,
    bg_reply_sender: Callable[[str, ReplyContext, str], Awaitable[None]] | None = None,
    update_workflow_size_guideline: Callable[[str, str], None] | None = None,
    max_session_drain_locks: int = 4096,
) -> InboundPipeline:
    """Build production owners explicitly while preserving concise test setup."""

    catalog = agent_catalog or LiveAgentCatalog(agents)
    binder = session_binder or GatewaySessionBinder(
        catalog=catalog,
        repository=session_store,
        kernel=kernel,
    )
    if product_default_model is None:
        product_default_model = "test-model"
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=outbound_router,
        run_queue=run_queue,
        group_context_store=group_context_store,
        image_resolver=image_resolver,
        background_subscriptions=background_subscriptions,
        gateway_internal_port=gateway_internal_port,
        gateway_dispatch_url_provider=gateway_dispatch_url_provider,
        product_default_model=product_default_model,
        relay_lifecycle_callback=relay_lifecycle_callback,
        kernel_event_observer=kernel_event_observer,
        shadow_output_prepare=shadow_output_prepare,
        bg_reply_sender=bg_reply_sender,
        update_workflow_size_guideline=update_workflow_size_guideline,
        run_idle_timeout_seconds=run_idle_timeout_seconds,
        max_transition_locks=max_session_drain_locks,
    )
    pipeline = InboundPipeline(
        agent_catalog=catalog,
        run_coordinator=coordinator,
        group_context_store=group_context_store,
        route_config=InboundRouteConfig(
            channel_bindings=channel_bindings or {},
            default_agent_id=default_agent_id,
        ),
        shadow_sync=shadow_sync,
    )
    _GRAPHS[pipeline] = InboundTestGraph(
        pipeline=pipeline,
        catalog=catalog,
        binder=binder,
        coordinator=coordinator,
        run_queue=run_queue,
        session_store=session_store,
    )
    return pipeline


def inbound_graph(pipeline: InboundPipeline) -> InboundTestGraph:
    """Return explicit owners composed for a test pipeline."""

    return _GRAPHS[pipeline]
