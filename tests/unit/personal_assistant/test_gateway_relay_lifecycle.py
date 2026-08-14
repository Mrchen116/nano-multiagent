"""Unit tests for relay lifecycle callbacks and gateway runtime build functions."""

from __future__ import annotations

from tests.helpers.runtime_delivery import delivery_context_store
import asyncio
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import (
    GatewayShadowState,
    RelayLifecycleUpdate,
    RoutedInbound,
    ShadowConversationRef,
)
from personal_assistant.gateway.im_bootstrap import (
    GatewayStartupError,
    IMBootstrapClient,
)
from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.gateway.runtime_delivery.context import (
    ExternalShadowTarget,
    IMRelayTarget,
    OwnerDirectTarget,
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback as _build_relay_lifecycle_callback,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer as _build_kernel_event_observer,
    roll_bubble,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from personal_assistant.gateway.runtime_footer import ExternalFinalProjection
from personal_assistant.gateway.runtime import GatewayRuntime
from personal_assistant.gateway.process_lifecycle import RuntimeFactories, run_gateway
from personal_assistant.gateway.composition import (
    _build_channel_registry,
    compose_gateway,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

from agent.core.llm.model_registry import _reset_for_tests
from ._main_helpers import _FakeIMManager, build_config

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(
                    name="kimiCoding:K2.6",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
            ),
        ),
    ),
)


class _AckChannel:
    name = "feishu:agent-a"

    def __init__(self) -> None:
        self.acked: list[str] = []

    def start(self, on_inbound) -> None:
        pass

    def send(self, outbound) -> None:
        pass

    def stop(self) -> None:
        pass

    def ack_message(self, message_id: str) -> None:
        self.acked.append(message_id)


class _AckingIMManager:
    connected = True

    def __init__(
        self,
        *,
        message_id: str = "im-msg-1",
        conversation_id: str | None = None,
    ) -> None:
        self.sent_frames: list[tuple[str, dict[str, object]]] = []
        self._message_id = message_id
        self._conversation_id = conversation_id

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        self.sent_frames.append((message_type, payload))
        ack_payload: dict[str, object] = {"message_id": self._message_id}
        if self._conversation_id is not None:
            ack_payload["conversation_id"] = self._conversation_id
        return {"payload": ack_payload}

    async def send_json(self, message_type: str, payload: dict[str, object]) -> None:
        self.sent_frames.append((message_type, payload))


def _relay_routed(
    *,
    conversation_id: str,
    is_group: bool = False,
    message_id: str = "user-msg-1",
) -> RoutedInbound:
    return RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id=conversation_id,
            is_group=is_group,
            agent_id="agent-a",
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-1",
                    idempotency_key="idem-1",
                    im_message_id=message_id,
                )
            ),
        )
    )


def test_run_delivery_target_distinguishes_shadow_owner_direct_and_none() -> None:
    shadow_ref = ShadowConversationRef(
        conversation_id="shadow-conv-1",
        im_message_id="shadow-message-1",
    )

    shadow = RunDeliveryTarget.for_external_shadow(ExternalShadowTarget(ref=shadow_ref))
    owner_direct = RunDeliveryTarget.for_owner_direct(
        OwnerDirectTarget(to_user_id="owner-1", agent_id="agent-a")
    )
    none = RunDeliveryTarget.none(reason="external_without_shadow")

    assert shadow.kind == "external_shadow"
    assert shadow.external_shadow == ExternalShadowTarget(ref=shadow_ref)
    assert shadow.owner_direct is None
    assert owner_direct.kind == "owner_direct"
    assert owner_direct.external_shadow is None
    assert owner_direct.owner_direct == OwnerDirectTarget(
        to_user_id="owner-1", agent_id="agent-a"
    )
    assert none.kind == "none"
    assert none.external_shadow is None
    assert none.owner_direct is None


def test_relay_lifecycle_seeds_typed_owner_direct_context() -> None:
    context_store = RunDeliveryContextStore()
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=context_store,
        owner_user_id="owner-1",
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="heartbeat",
            text="tick",
            external_user_id="owner-1",
            external_chat_id="",
            is_group=False,
            metadata={},
        )
    )

    asyncio.run(
        callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="heartbeat:agent-a",
                run_id="run-owner-direct",
                kernel_session_id="sess-owner-direct",
            ),
        )
    )

    ctx = context_store.get("run-owner-direct")
    assert ctx is not None
    assert ctx.delivery_target.kind == "owner_direct"
    assert ctx.delivery_target.owner_direct == OwnerDirectTarget(
        to_user_id="owner-1",
        agent_id="agent-a",
    )


def test_relay_lifecycle_external_ingress_never_targets_owner_direct() -> None:
    context_store = RunDeliveryContextStore()
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=context_store,
        owner_user_id="owner-1",
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="feishu",
            text="hello",
            external_user_id="ou-user",
            external_chat_id="external-chat",
            is_group=False,
            ingress=InboundIngress(
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="external-chat",
                    agent_id="agent-a",
                )
            ),
        )
    )

    asyncio.run(
        callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="feishu:legacy:agent-a",
                run_id="run-partial-external",
                kernel_session_id="sess-partial-external",
            ),
        )
    )

    context = context_store.get("run-partial-external")
    assert context is not None
    assert context.delivery_target.kind == "none"
    assert context.delivery_target.reason == "external_without_shadow"


def test_relay_lifecycle_cleanup_removes_typed_context() -> None:
    context_store = RunDeliveryContextStore()
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=context_store,
        owner_user_id="owner-1",
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="conv-1",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-1",
                    idempotency_key="idem-1",
                    im_message_id="msg-1",
                )
            ),
            metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
        )
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-cleanup",
                kernel_session_id="sess-cleanup",
            ),
        )
        assert context_store.get("run-cleanup") is not None
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="failed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-cleanup",
                error="boom",
            ),
        )

    asyncio.run(_exercise())

    assert context_store.get("run-cleanup") is None


def test_typed_store_fresh_relay_accepted_still_sends_sent_receipt() -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None
    )
    manager = _FakeIMManager([])
    context_store = RunDeliveryContextStore()
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="conv-1",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-1",
                    idempotency_key="idem-1",
                    im_message_id="msg-1",
                )
            ),
            metadata={"relay_task_id": "relay-1", "message_id": "msg-1"},
        )
    )

    asyncio.run(
        callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-accepted",
                kernel_session_id="sess-accepted",
            ),
        )
    )

    assert context_store.get("run-accepted") is not None
    assert manager.sent_frames == [
        (
            "node.delivery_receipt",
            {
                "relay_task_id": "relay-1",
                "delivery_status": "sent",
                "detail": "run_id=run-accepted",
                "node_id": "node-local",
            },
        )
    ]


def test_recovery_adopted_seeds_context_without_second_ack_or_sent_receipt() -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None
    )
    manager = _FakeIMManager([])
    channel = _AckChannel()
    context_store = RunDeliveryContextStore()
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
        channel_registry=ChannelRegistry((channel,)),
    )
    routed = RoutedInbound(
        message=InboundMessage(
            channel_name="feishu:agent-a",
            text="follow-up",
            external_user_id="ou-user",
            external_chat_id="oc-chat",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-follow-up",
                    idempotency_key="idem-follow-up",
                    im_message_id="im-follow-up",
                )
            ),
            metadata={"feishu_message_id": "om-follow-up"},
        )
    )

    asyncio.run(
        callback(
            routed,
            RelayLifecycleUpdate(
                phase="recovery_adopted",
                agent_id="agent-a",
                session_key="feishu:oc-chat:agent-a",
                run_id="run-successor",
                previous_run_id="run-old",
                recovery_id="recovery-1",
                kernel_session_id="sess-1",
            ),
        )
    )

    assert context_store.get("run-successor") is not None
    assert channel.acked == []
    assert manager.sent_frames == []


def test_typed_context_store_holds_turn_start_ack_message_id() -> None:
    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-shadow-ack",
            agent_id="agent-a",
            kernel_session_id="sess-shadow",
            delivery_target=RunDeliveryTarget.for_im_relay(
                IMRelayTarget(
                    conversation_id="conv-shadow",
                    relay_task_id="relay-shadow",
                )
            ),
        )
    )
    manager = _AckingIMManager(message_id="im-msg-shadow")
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
    )

    async def _exercise() -> None:
        result = observer(
            {
                "event": "run_status",
                "run_id": "run-shadow-ack",
                "status": "running",
            }
        )
        assert asyncio.iscoroutine(result)
        await result

    asyncio.run(_exercise())

    ctx = context_store.get("run-shadow-ack")
    assert ctx is not None
    assert ctx.message_id == "im-msg-shadow"


def test_typed_owner_direct_lazy_turn_start_backfills_context_and_sends_delta() -> None:
    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-owner-lazy",
            agent_id="agent-a",
            kernel_session_id="sess-owner",
            delivery_target=RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id="owner-user", agent_id="agent-a")
            ),
        )
    )
    manager = _AckingIMManager(
        message_id="im-msg-owner",
        conversation_id="conv-owner",
    )
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
    )

    async def _exercise() -> None:
        result = observer(
            {
                "event": "assistant_message",
                "run_id": "run-owner-lazy",
                "content": "Daily summary.",
                "message_id": "kernel-owner-msg",
            }
        )
        assert asyncio.iscoroutine(result)
        await result

    asyncio.run(_exercise())

    ctx = context_store.get("run-owner-lazy")
    assert ctx is not None
    assert ctx.conversation_id == "conv-owner"
    assert ctx.message_id == "im-msg-owner"
    assert ctx.kernel_message_id == "kernel-owner-msg"
    assert [frame[1]["kind"] for frame in manager.sent_frames] == [
        "turn_start",
        "message_delta",
    ]


def test_roll_bubble_updates_typed_context_runtime_state() -> None:
    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-roll",
            agent_id="agent-a",
            kernel_session_id="sess-roll",
            delivery_target=RunDeliveryTarget.for_im_relay(
                IMRelayTarget(
                    conversation_id="conv-roll",
                    relay_task_id="relay-roll",
                )
            ),
        )
    )
    context = context_store.get("run-roll")
    assert context is not None
    context.message_id = "im-msg-a"
    context.kernel_message_id = "kernel-msg-a"
    context.visible_reply_committed = True
    manager = _AckingIMManager(message_id="im-msg-b")

    new_message_id = asyncio.run(
        roll_bubble(
            manager,
            run_id="run-roll",
            conversation_id="conv-roll",
            agent_id="agent-a",
            run_context_store=context_store,
            old_message_id="im-msg-a",
            new_kernel_message_id="kernel-msg-b",
        )
    )

    assert new_message_id == "im-msg-b"
    ctx = context_store.get("run-roll")
    assert ctx is not None
    assert ctx.message_id == "im-msg-b"
    assert ctx.kernel_message_id == "kernel-msg-b"
    assert ctx.visible_reply_committed is False
    assert ctx.rolling is False


def test_relay_lifecycle_callback_sends_receipts_and_reports_with_real_usage_to_im() -> (
    None
):
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None
    )
    manager = _FakeIMManager([])
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="conv-1",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-1",
                    idempotency_key="idem-1",
                    im_message_id="msg-1",
                )
            ),
        )
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
            ),
        )
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="running",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
            ),
        )
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
                usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            ),
        )

    asyncio.run(_exercise())

    assert [item[0] for item in manager.sent_frames] == [
        "node.delivery_receipt",
        "node.report",
        "node.report",
        "node.delivery_receipt",
    ]
    assert manager.sent_frames[0][1]["delivery_status"] == "sent"
    assert manager.sent_frames[1][1]["conversation_id"] == "conv-1"
    assert manager.sent_frames[1][1]["message_id"] == "msg-1"
    assert manager.sent_frames[2][1]["status"] == "completed"
    assert manager.sent_frames[2][1]["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert manager.sent_frames[3][1]["detail"] == "hello from agent"


def test_relay_lifecycle_reads_delivery_facts_from_typed_ingress() -> None:
    """Typed ingress overrides stale raw relay metadata for receipts and reports."""
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None
    )
    manager = _FakeIMManager([])
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="raw-conv",
            is_group=False,
            metadata={"relay_task_id": "raw-relay", "message_id": "raw-msg"},
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="typed-relay",
                    idempotency_key="typed-idem",
                    im_message_id="typed-msg",
                )
            ),
        )
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
            ),
        )
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="running",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
            ),
        )

    asyncio.run(_exercise())

    assert manager.sent_frames[0][1]["relay_task_id"] == "typed-relay"
    assert manager.sent_frames[1][1]["conversation_id"] == "raw-conv"
    assert manager.sent_frames[1][1]["message_id"] == "typed-msg"


def test_relay_lifecycle_accepted_acks_feishu_message_processing_started() -> None:
    channel = _AckChannel()
    registry = ChannelRegistry((channel,))
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        channel_registry=registry,
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="feishu:agent-a",
            text="hello",
            external_user_id="ou-user",
            external_chat_id="feishu:cli_a:group:oc_1",
            is_group=True,
            metadata={"feishu_message_id": "om_msg_1"},
        )
    )

    asyncio.run(
        callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="feishu:group:agent-a",
                run_id="run-1",
            ),
        )
    )

    assert channel.acked == ["om_msg_1"]


def test_relay_lifecycle_callback_seeds_external_shadow_run_context() -> None:
    run_context_store = delivery_context_store({})
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=run_context_store,
        owner_user_id="owner-1",
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="feishu:agent-a",
            text="hello",
            external_user_id="ou-user",
            external_chat_id="oc_feishu_chat",
            is_group=False,
            ingress=InboundIngress(
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="oc_feishu_chat",
                    agent_id="agent-a",
                    trigger_source="feishu",
                )
            ),
            metadata={"feishu_message_id": "om_msg_1"},
        ),
        shadow=GatewayShadowState(
            saga_id="saga-1",
            ref=ShadowConversationRef(
                conversation_id="shadow-conv-1",
                im_message_id="shadow-message-1",
            ),
        ),
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="feishu:oc_feishu_chat:agent-a",
                run_id="run-1",
                kernel_session_id="sess-1",
            ),
        )

    asyncio.run(_exercise())

    context = run_context_store.get("run-1")
    assert context is not None
    assert context.conversation_id == "shadow-conv-1"
    assert context.message_id == ""
    assert context.agent_id == "agent-a"
    assert context.kernel_session_id == "sess-1"
    assert context.owner_user_id == ""
    assert context.trigger_source == "feishu"
    assert context.reply_channel_name == "feishu:agent-a"
    assert context.reply_target_chat_id == "oc_feishu_chat"
    assert context.feishu_message_id == "om_msg_1"


def test_relay_lifecycle_callback_skips_lazy_direct_when_external_shadow_missing() -> (
    None
):
    run_context_store = delivery_context_store({})
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=run_context_store,
        owner_user_id="owner-1",
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="feishu:agent-a",
            text="hello",
            external_user_id="ou-user",
            external_chat_id="oc_feishu_chat",
            is_group=False,
            ingress=InboundIngress(
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="oc_feishu_chat",
                    agent_id="agent-a",
                    trigger_source="feishu",
                )
            ),
        ),
        shadow=GatewayShadowState(saga_id="saga-pending"),
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="feishu:oc_feishu_chat:agent-a",
                run_id="run-1",
                kernel_session_id="sess-1",
            ),
        )

    asyncio.run(_exercise())

    context = run_context_store.get("run-1")
    assert context is not None
    assert context.conversation_id == ""
    assert context.owner_user_id == ""
    assert context.trigger_source == "feishu"


def test_relay_lifecycle_callback_routes_im_shadow_run_to_shadow_conversation() -> None:
    run_context_store = delivery_context_store({})
    callback = _build_relay_lifecycle_callback(
        reporter=None,
        im_connection_manager_factory=lambda: None,
        run_context_store=run_context_store,
    )
    message = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="shadow-conv-1",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay-1",
                    idempotency_key="idem-1",
                    im_message_id="msg-1",
                ),
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="oc_feishu_chat",
                    agent_id="agent-a",
                    trigger_source="im",
                ),
            ),
        )
    )

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id="agent-a",
                session_key="feishu:oc_feishu_chat:agent-a",
                run_id="run-1",
                kernel_session_id="sess-1",
            ),
        )

    asyncio.run(_exercise())

    context = run_context_store.get("run-1")
    assert context is not None
    assert context.conversation_id == "shadow-conv-1"
    assert context.owner_user_id == ""
    assert context.trigger_source == "im"


def test_kernel_event_observer_mirrors_external_visible_bubbles_on_completion() -> None:
    class _Manager:
        connected = True

        def __init__(self) -> None:
            self.sent_frames: list[tuple[str, dict[str, object]]] = []
            self._counter = 0

        async def send_json_await_ack(
            self, message_type: str, payload: dict[str, object]
        ) -> dict[str, object]:
            self.sent_frames.append((message_type, payload))
            self._counter += 1
            return {
                "payload": {
                    "message_id": f"im-msg-{self._counter}",
                    "conversation_id": payload.get("conversation_id"),
                }
            }

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            self.sent_frames.append((message_type, payload))

    manager = _Manager()
    mirrored: list[tuple[str, dict[str, str]]] = []
    shadowed: list[str] = []
    run_context_store = delivery_context_store(
        {
            "run-1": {
                "conversation_id": "shadow-conv",
                "message_id": "",
                "agent_id": "agent-a",
                "kernel_session_id": "sess-1",
                "to_user_id": "",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "feishu:cli_a:dm:ou_user",
                "feishu_message_id": "om_msg_1",
                "model": "provider/path/gpt-5.4",
                "shadow_saga_id": "saga-1",
            }
        }
    )
    tracker = RuntimeDeliveryTaskTracker()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
        external_reply_sender=lambda text, metadata: mirrored.append(
            (text, dict(metadata))
        ),
        external_final_projection_builder=lambda text, _channel_name, facts: (
            ExternalFinalProjection(
                text=text,
                runtime_footer=f"{facts.model} · ctx 42%",
            )
        ),
        shadow_output_prepare=lambda _saga, _run, _phase, _kernel, text: (
            shadowed.append(text)
        ),
        task_tracker=tracker,
    )

    async def _exercise() -> None:
        result = observer(
            {"event": "run_status", "run_id": "run-1", "status": "running"}
        )
        assert asyncio.iscoroutine(result)
        await result
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-a",
                "content": "I will check.",
                "reasoning_content": "private chain of thought A",
            }
        )
        await asyncio.sleep(0)
        roll = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-b",
                "content": "Final answer.",
                "reasoning_content": "private chain of thought B",
            }
        )
        assert asyncio.iscoroutine(roll)
        await roll
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(_exercise())

    assert mirrored == [
        (
            "I will check.",
            {
                "reply_phase": "intermediate",
                "reply_dedupe_key": "run-1:bubble:kernel-msg-a",
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:cli_a:dm:ou_user",
                "feishu_message_id": "om_msg_1",
            },
        ),
        (
            "Final answer.",
            {
                "reply_phase": "final",
                "reply_dedupe_key": "run-1:bubble:kernel-msg-b",
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:cli_a:dm:ou_user",
                "feishu_message_id": "om_msg_1",
                "runtime_footer": "provider/path/gpt-5.4 · ctx 42%",
            },
        ),
    ]
    assert shadowed == ["I will check.", "Final answer."]


def test_kernel_event_observer_does_not_mirror_im_triggered_shadow_runs() -> None:
    class _Manager:
        connected = True

        async def send_json_await_ack(
            self, _message_type: str, _payload: dict[str, object]
        ) -> dict[str, object]:
            return {"payload": {"message_id": "im-msg-1"}}

        async def send_json(
            self, _message_type: str, _payload: dict[str, object]
        ) -> None:
            return None

    mirrored: list[tuple[str, dict[str, str]]] = []
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: _Manager(),
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "shadow-conv",
                    "message_id": "",
                    "agent_id": "agent-a",
                    "kernel_session_id": "sess-1",
                    "to_user_id": "",
                    "trigger_source": "im",
                    "reply_channel_name": "web_relay",
                    "reply_target_chat_id": "shadow-conv",
                }
            }
        ),
        external_reply_sender=lambda text, metadata: mirrored.append(
            (text, dict(metadata))
        ),
    )

    async def _exercise() -> None:
        result = observer(
            {"event": "run_status", "run_id": "run-1", "status": "running"}
        )
        assert asyncio.iscoroutine(result)
        await result
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-a",
                "content": "Internal only.",
            }
        )
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    assert mirrored == []


def test_group_no_reply_discards_provisional_im_message() -> None:
    """A group silence token must roll back its eager IM placeholder."""

    class _Manager:
        connected = True

        def __init__(self) -> None:
            self.sent_frames: list[tuple[str, dict[str, object]]] = []

        async def send_json_await_ack(
            self, message_type: str, payload: dict[str, object]
        ) -> dict[str, object]:
            self.sent_frames.append((message_type, payload))
            return {"payload": {"message_id": "im-msg-1"}}

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            self.sent_frames.append((message_type, payload))

    manager = _Manager()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "group-conv",
                    "message_id": "",
                    "agent_id": "agent-a",
                    "kernel_session_id": "sess-1",
                    "visibility_policy": "suppress_protocol_tokens",
                }
            }
        ),
    )

    async def _exercise() -> None:
        started = observer(
            {"event": "run_status", "run_id": "run-1", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        suppressed = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-1",
                "content": "NO_REPLY",
                "reasoning_content": "The group asked me to stay silent.",
                "group_id": "kernel-msg-1",
            }
        )
        if asyncio.iscoroutine(suppressed):
            await suppressed
        ended = observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    payloads = [payload for _, payload in manager.sent_frames]
    assert [payload["kind"] for payload in payloads] == [
        "turn_start",
        "message_discarded",
    ]
    assert payloads[-1] == {
        "kind": "message_discarded",
        "message_id": "im-msg-1",
        "run_id": "run-1",
        "reason": "no_reply_token",
    }


def test_group_relay_context_enables_protocol_token_suppression() -> None:
    """Accepted group relays must carry silence policy into runtime delivery."""
    store = RunDeliveryContextStore()
    message = InboundMessage(
        channel_name="web_relay",
        text="@agent-a stay quiet",
        external_user_id="user-1",
        external_chat_id="group-conv",
        is_group=True,
        agent_id="agent-a",
        metadata={"relay_task_id": "relay-1", "message_id": "user-msg-1"},
    )

    context = store.seed_from_lifecycle(
        routed=_relay_routed(conversation_id="group-conv", is_group=True),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="web:user-1:group-conv:agent-a",
            run_id="run-1",
            kernel_session_id="sess-1",
        ),
        owner_user_id="owner-1",
    )

    assert context is not None
    assert context.visibility_policy is ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS


def test_direct_web_relay_no_reply_discards_provisional_im_message() -> None:
    """A direct Web IM silence token must roll back its eager IM placeholder."""

    class _Manager:
        connected = True

        def __init__(self) -> None:
            self.sent_frames: list[tuple[str, dict[str, object]]] = []

        async def send_json_await_ack(
            self, message_type: str, payload: dict[str, object]
        ) -> dict[str, object]:
            self.sent_frames.append((message_type, payload))
            return {"payload": {"message_id": "im-msg-direct"}}

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            self.sent_frames.append((message_type, payload))

    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=_relay_routed(conversation_id="direct-conv"),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="web:user-1:direct-conv:agent-a",
            run_id="run-direct",
            kernel_session_id="sess-1",
        ),
        owner_user_id="owner-1",
    )
    assert context is not None

    manager = _Manager()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )

    async def _exercise() -> None:
        started = observer(
            {"event": "run_status", "run_id": "run-direct", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-direct",
                "message_id": "kernel-msg-direct",
                "content": "NO_REPLY",
            }
        )
        ended = observer(
            {"event": "turn_end", "run_id": "run-direct", "completed": True}
        )
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    assert context.visibility_policy is ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
    assert [payload["kind"] for _, payload in manager.sent_frames] == [
        "turn_start",
        "message_discarded",
    ]
    assert manager.sent_frames[-1][1]["reason"] == "no_reply_token"


def test_reset_revocation_discards_an_existing_provisional_im_message() -> None:
    """A committed `/new` must close the old run's already-open bubble."""

    store = RunDeliveryContextStore()
    store.seed(
        RunDeliveryContext(
            run_id="run-reset",
            agent_id="agent-a",
            kernel_session_id="sess-1",
            delivery_target=RunDeliveryTarget.none(),
            conversation_id="conv-1",
            message_id="im-old-bubble",
        )
    )
    manager = _AckingIMManager()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )
    store.suppress("run-reset")

    async def _exercise() -> None:
        pending = observer({"event": "run_reset_discard", "run_id": "run-reset"})
        assert pending is not None
        await pending

    asyncio.run(_exercise())

    assert manager.sent_frames == [
        (
            "node.streaming_delta",
            {
                "kind": "message_discarded",
                "message_id": "im-old-bubble",
                "run_id": "run-reset",
                "reason": "new_session",
            },
        )
    ]


def test_direct_web_empty_completion_after_process_discards_provisional_message() -> (
    None
):
    """A successful Web run with process-only output must remove its whole bubble."""
    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=_relay_routed(conversation_id="direct-conv"),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="web:user-1:direct-conv:agent-a",
            run_id="run-direct-empty",
            kernel_session_id="sess-1",
        ),
        owner_user_id="owner-1",
    )
    assert context is not None

    manager = _AckingIMManager(message_id="im-msg-direct-empty")
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )

    async def _exercise() -> None:
        started = observer(
            {"event": "run_status", "run_id": "run-direct-empty", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "event": "tool_start",
                "run_id": "run-direct-empty",
                "call_id": "tool-1",
                "name": "bash",
                "arguments": {"command": "printf OK"},
            }
        )
        observer(
            {
                "event": "tool_end",
                "run_id": "run-direct-empty",
                "call_id": "tool-1",
                "name": "bash",
                "status": "completed",
                "result": "OK",
            }
        )
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-direct-empty",
                "message_id": "kernel-msg-direct-empty",
                "content": "",
                "reasoning_content": "The requested tool completed; remain silent.",
                "group_id": "kernel-msg-direct-empty",
            }
        )
        await asyncio.sleep(0)
        ended = observer(
            {"event": "turn_end", "run_id": "run-direct-empty", "completed": True}
        )
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    assert context.discard_empty_completion is True
    kinds = [payload["kind"] for _, payload in manager.sent_frames]
    assert kinds[-1] == "message_discarded"
    assert "message_completed" not in kinds
    assert manager.sent_frames[-1][1]["reason"] == "empty_visible_reply"


def test_direct_web_opening_background_return_keeps_completed_message() -> None:
    """An opening background return is visible content even without reply text."""
    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=_relay_routed(conversation_id="direct-conv"),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="web:user-1:direct-conv:agent-a",
            run_id="run-with-background-return",
            kernel_session_id="sess-1",
        ),
        owner_user_id="owner-1",
    )
    assert context is not None

    background_return = {
        "task_id": "wt_123",
        "task_type": "workflow",
        "status": "completed",
        "description": "review changes",
        "workflow_run_id": "wf_123",
        "result": {"summary": "2 findings"},
    }
    manager = _AckingIMManager(message_id="im-msg-with-background-return")
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )

    async def _exercise() -> None:
        started = observer(
            {
                "event": "run_status",
                "run_id": "run-with-background-return",
                "status": "running",
                "background_returns": [background_return],
            }
        )
        assert asyncio.iscoroutine(started)
        await started
        ended = observer(
            {
                "event": "turn_end",
                "run_id": "run-with-background-return",
                "completed": True,
            }
        )
        if asyncio.iscoroutine(ended):
            await ended

    asyncio.run(_exercise())

    payloads = [payload for _, payload in manager.sent_frames]
    assert payloads[0]["kind"] == "turn_start"
    assert payloads[0]["background_returns"] == [background_return]
    assert payloads[-1]["kind"] == "message_completed"
    assert "message_discarded" not in {payload["kind"] for payload in payloads}
    assert context.visible_reply_committed is True


def test_direct_web_denied_workflow_keeps_terminal_tool_row() -> None:
    """A denied Workflow has no running phase but remains visible as tool audit."""
    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=_relay_routed(conversation_id="direct-conv"),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="web:user-1:direct-conv:agent-a",
            run_id="run-workflow-denied",
            kernel_session_id="sess-1",
        ),
        owner_user_id="owner-1",
    )
    assert context is not None
    manager = _AckingIMManager(message_id="im-msg-workflow-denied")
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )

    async def _exercise() -> None:
        started = observer(
            {
                "event": "run_status",
                "run_id": "run-workflow-denied",
                "status": "running",
            }
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "event": "tool_end",
                "run_id": "run-workflow-denied",
                "call_id": "workflow-call",
                "name": "Workflow",
                "arguments": {"script": "async def main(): pass"},
                "reason_code": "denied",
                "approval": "user_deny",
                "error": "Permission denied by user",
            }
        )
        await asyncio.sleep(0)
        ended = observer(
            {"event": "turn_end", "run_id": "run-workflow-denied", "completed": True}
        )
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    payloads = [payload for _, payload in manager.sent_frames]
    kinds = [payload["kind"] for payload in payloads]
    assert "tool_call_upserted" not in kinds
    denied = next(
        payload for payload in payloads if payload["kind"] == "tool_call_completed"
    )
    assert denied["tool_call"]["reason"] == "denied"
    assert denied["tool_call"]["approval"] == "user_deny"
    assert kinds[-1] == "message_completed"
    assert "message_discarded" not in kinds


def test_non_web_shadow_context_keeps_literal_reply_visibility() -> None:
    """The direct Web fix must not broaden to arbitrary shadow transports."""
    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=RoutedInbound(
            message=InboundMessage(
                channel_name="custom_relay",
                text="literal protocol text",
                external_user_id="user-1",
                external_chat_id="custom-conv",
                is_group=False,
                agent_id="agent-a",
            ),
            shadow=GatewayShadowState(
                saga_id="saga-1",
                ref=ShadowConversationRef(
                    conversation_id="shadow-conv-1",
                    im_message_id="shadow-message-1",
                ),
            ),
        ),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="custom:user-1:agent-a",
            run_id="run-custom",
            kernel_session_id="sess-1",
        ),
        owner_user_id="",
    )

    assert context is not None
    assert context.visibility_policy is ReplyVisibilityPolicy.LITERAL_TEXT
    assert context.discard_empty_completion is False


def test_non_web_empty_completion_keeps_existing_completed_message_semantics() -> None:
    """An empty external completion is not reclassified as direct-Web silence."""
    store = RunDeliveryContextStore()
    context = store.seed_from_lifecycle(
        routed=RoutedInbound(
            message=InboundMessage(
                channel_name="custom_relay",
                text="external request",
                external_user_id="user-1",
                external_chat_id="custom-conv",
                is_group=False,
                agent_id="agent-a",
            ),
            shadow=GatewayShadowState(
                saga_id="saga-1",
                ref=ShadowConversationRef(
                    conversation_id="shadow-conv-1",
                    im_message_id="shadow-message-1",
                ),
            ),
        ),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="agent-a",
            session_key="custom:user-1:agent-a",
            run_id="run-custom-empty",
            kernel_session_id="sess-1",
        ),
        owner_user_id="",
    )
    assert context is not None

    manager = _AckingIMManager(message_id="im-msg-custom-empty")
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=store,
    )

    async def _exercise() -> None:
        started = observer(
            {"event": "run_status", "run_id": "run-custom-empty", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-custom-empty",
                "message_id": "kernel-msg-custom-empty",
                "content": "",
                "reasoning_content": "External process detail.",
                "group_id": "kernel-msg-custom-empty",
            }
        )
        await asyncio.sleep(0)
        observer({"event": "turn_end", "run_id": "run-custom-empty", "completed": True})
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    kinds = [payload["kind"] for _, payload in manager.sent_frames]
    assert kinds[-1] == "message_completed"
    assert "message_discarded" not in kinds


def test_later_no_reply_preserves_preceding_real_bubble() -> None:
    """A final silence token must not discard an earlier visible assistant message."""

    class _Manager:
        connected = True

        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, object]
        ) -> dict[str, object]:
            self.payloads.append(payload)
            return {"payload": {"message_id": "im-msg-1"}}

        async def send_json(
            self, _message_type: str, payload: dict[str, object]
        ) -> None:
            self.payloads.append(payload)

    manager = _Manager()
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "group-conv",
                    "message_id": "",
                    "agent_id": "agent-a",
                    "kernel_session_id": "sess-1",
                    "visibility_policy": "suppress_protocol_tokens",
                }
            }
        ),
    )

    async def _exercise() -> None:
        started = observer(
            {"event": "run_status", "run_id": "run-1", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-1",
                "content": "I checked the state.",
            }
        )
        await asyncio.sleep(0)
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-msg-2",
                "content": "NO_REPLY",
            }
        )
        ended = observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    assert [payload["kind"] for payload in manager.payloads] == [
        "turn_start",
        "message_delta",
        "message_completed",
    ]
    assert all("NO_REPLY" not in str(payload) for payload in manager.payloads)


def test_relay_lifecycle_callback_failed_sends_message_level_report_with_real_cause() -> (
    None
):
    # bugfix-437 decision 3: a failed run must surface a message-level node.report
    # (status=failed, message_id, summary=真因) so the IM placeholder bubble flips
    # to failed within seconds with a readable cause — mirroring the completed
    # branch — instead of only a relay-task delivery_receipt that leaves the bubble
    # spinning until the 120s idle watchdog.
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None
    )
    manager = _FakeIMManager([])
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
    )
    message = _relay_routed(conversation_id="conv-1", message_id="msg-1")

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="failed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                error="context overflow: compaction failed",
            ),
        )

    asyncio.run(_exercise())

    assert [item[0] for item in manager.sent_frames] == [
        "node.report",
        "node.delivery_receipt",
    ]
    report = manager.sent_frames[0][1]
    assert report["status"] == "failed"
    assert report["message_id"] == "msg-1"
    assert report["agent_id"] == "agent-a"
    assert report["conversation_id"] == "conv-1"
    assert report["summary"] == "context overflow: compaction failed"
    receipt = manager.sent_frames[1][1]
    assert receipt["delivery_status"] == "failed"
    assert receipt["detail"] == "context overflow: compaction failed"


def test_build_relay_lifecycle_callback_marks_no_reply_suppression_in_completed_receipt() -> (
    None
):
    sent_frames: list[tuple[str, dict[str, object]]] = []

    class _Reporter:
        def send_delivery_receipt(
            self, *, relay_task_id: str, delivery_status: str, detail: str | None = None
        ):
            return {
                "relay_task_id": relay_task_id,
                "delivery_status": delivery_status,
                "detail": detail,
            }

    class _Manager:
        connected = True

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            sent_frames.append((message_type, payload))

    callback = _build_relay_lifecycle_callback(
        reporter=_Reporter(),
        im_connection_manager_factory=lambda: _Manager(),
    )
    message = _relay_routed(conversation_id="conv-1", message_id="msg-1")

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="NO_REPLY",
                detail={"suppressed_by": "no_reply_token"},
            ),
        )

    asyncio.run(_exercise())

    assert sent_frames == [
        (
            "node.delivery_receipt",
            {
                "relay_task_id": "relay-1",
                "delivery_status": "completed",
                "detail": "suppressed_by=no_reply_token",
            },
        )
    ]


def test_build_relay_lifecycle_callback_keeps_completed_updates_when_im_is_reconnecting() -> (
    None
):
    sent_frames: list[tuple[str, dict[str, object]]] = []

    class _Reporter:
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
            detail: dict[str, object] | None = None,
            usage: dict[str, object] | None = None,
        ) -> dict[str, object]:
            payload = {
                "run_id": run_id,
                "status": status,
                "agent_id": agent_id,
                "session_key": session_key,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "summary": summary,
            }
            if detail is not None:
                payload["detail"] = detail
            if usage is not None:
                payload["usage"] = usage
            return payload

        def send_delivery_receipt(
            self, *, relay_task_id: str, delivery_status: str, detail: str | None = None
        ):
            return {
                "relay_task_id": relay_task_id,
                "delivery_status": delivery_status,
                "detail": detail,
            }

    class _Manager:
        connected = False

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            sent_frames.append((message_type, payload))

    callback = _build_relay_lifecycle_callback(
        reporter=_Reporter(),
        im_connection_manager_factory=lambda: _Manager(),
    )
    message = _relay_routed(conversation_id="conv-1", message_id="msg-1")

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
                usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            ),
        )

    asyncio.run(_exercise())

    assert sent_frames == [
        (
            "node.report",
            {
                "run_id": "run-1",
                "status": "completed",
                "agent_id": "agent-a",
                "session_key": "web:user:agent-a",
                "conversation_id": "conv-1",
                "message_id": "msg-1",
                "summary": "hello from agent",
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                },
            },
        ),
        (
            "node.delivery_receipt",
            {
                "relay_task_id": "relay-1",
                "delivery_status": "completed",
                "detail": "hello from agent",
            },
        ),
    ]


def test_run_gateway_loads_config_and_starts_runtime(tmp_path: Path) -> None:
    _reset_for_tests()  # run_gateway calls init_model_registry; must start from clean state
    config = build_config(tmp_path)
    seen: dict[str, object] = {}

    class _Runtime:
        def __init__(self, loaded_config: LocalConfig) -> None:
            seen["config"] = loaded_config

        def run_forever(self) -> int:
            seen["ran"] = True
            return 0

    exit_code = run_gateway(
        config_path=tmp_path / "node-config.yaml",
        factories=RuntimeFactories(
            load_config=lambda path: (
                config if path == tmp_path / "node-config.yaml" else None
            ),
            build_runtime=lambda loaded_config: _Runtime(loaded_config),
        ),
    )

    assert exit_code == 0
    assert seen == {"config": config, "ran": True}


def test_build_channel_registry_passes_dedup_db_path(tmp_path: Path) -> None:
    registry = _build_channel_registry(
        (ChannelConfig(name="web_relay", enabled=True),),
        dedup_db_path=tmp_path / "relay-dedup.sqlite3",
    )

    relay_adapter = registry.get("web_relay")

    assert relay_adapter is not None
    assert relay_adapter._dedup_store is not None  # noqa: SLF001
    assert relay_adapter._dedup_store._db_path == tmp_path / "relay-dedup.sqlite3"  # noqa: SLF001


def test_compose_gateway_wires_web_relay_dedup_db_under_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),
        ),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        gateway=GatewayLifecycleConfig(
            startup_timeout_seconds=0.2,
            poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    class _Manager:
        connected = True

        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.IMConnectionManager", _Manager
    )

    runtime = compose_gateway(config)
    relay_adapter = runtime._channel_registry.get("web_relay")  # noqa: SLF001

    assert relay_adapter is not None
    assert relay_adapter._dedup_store is not None  # noqa: SLF001
    assert relay_adapter._dedup_store._db_path == tmp_path / "relay_dedup.sqlite3"  # noqa: SLF001


def test_im_bootstrap_client_opens_browser_for_unbound_node() -> None:
    import httpx

    opened: list[tuple[str, int, bool]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/im/v1/nodes":
            return httpx.Response(200, json=[{"node_id": "node-local", "owner_id": ""}])
        if request.method == "POST" and request.url.path == "/im/v1/bind":
            return httpx.Response(
                201, json={"bind_url": "http://127.0.0.1:4173/bind/confirm?token=t-1"}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    bootstrap = IMBootstrapClient(
        base_url="http://im.local",
        token=None,
        client=client,
        browser_opener=lambda url, new=0, autoraise=True: (
            opened.append((url, new, autoraise)) or True
        ),
    )

    bind_url = bootstrap.ensure_node_binding(node_id="node-local")

    assert bind_url == "http://127.0.0.1:4173/bind/confirm?token=t-1"
    assert opened == [("http://127.0.0.1:4173/bind/confirm?token=t-1", 2, True)]


def test_im_bootstrap_client_skips_browser_for_bound_node() -> None:
    import httpx

    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200, json=[{"node_id": "node-local", "owner_id": "owner-1"}]
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    bootstrap = IMBootstrapClient(
        base_url="http://im.local",
        token=None,
        client=client,
        browser_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("browser should not open")
        ),
    )

    bind_url = bootstrap.ensure_node_binding(node_id="node-local")

    assert bind_url is None
    assert calls == ["GET /im/v1/nodes"]


def test_im_bootstrap_client_only_uses_configured_im_base_url() -> None:
    import httpx

    requests: list[tuple[str, str]] = []

    def _client_factory(base_url: str) -> httpx.Client:
        def _handler(request: httpx.Request) -> httpx.Response:
            requests.append((base_url, request.url.path))
            return httpx.Response(200, json=[])

        return httpx.Client(
            base_url=base_url, transport=httpx.MockTransport(_handler), trust_env=False
        )

    bootstrap = IMBootstrapClient(
        base_url="http://127.0.0.1:8021",
        token=None,
        client_factory=_client_factory,
        browser_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("browser should not open")
        ),
        monotonic=iter([0.0, 0.0, 5.1]).__next__,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(
        GatewayStartupError, match="node node-local did not appear in IM bootstrap"
    ):
        bootstrap.ensure_node_binding(node_id="node-local")

    assert requests == [("http://127.0.0.1:8021", "/im/v1/nodes")]


# ---------------------------------------------------------------------------
# Prompt preview provider wiring (C1 fix: refactor-387 regression)
# ---------------------------------------------------------------------------


def test_compose_gateway_wires_prompt_preview_provider_when_im_service_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """compose_gateway must wire a non-None prompt_preview_provider when im_service is set.

    refactor-387 M3 regression: prompt_preview_provider was set to None because
    the kernel HTTP endpoint was deleted without an SDK replacement.  The fix adds
    Kernel.assemble_prompt_preview() and wires it here.

    This test verifies that:
    1. The im_connection_manager receives a non-None provider.
    2. Calling the provider returns {"prompt": <non-empty str>, "section_count": <int>}.
    """
    import asyncio

    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),
        ),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        gateway=GatewayLifecycleConfig(
            startup_timeout_seconds=0.2,
            poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    captured_kwargs: dict[str, object] = {}

    class _RecordingManager:
        connected = True

        def __init__(self, **kwargs: object) -> None:
            captured_kwargs.update(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.IMConnectionManager", _RecordingManager
    )

    compose_gateway(config)

    provider = captured_kwargs.get("prompt_preview_provider")
    assert provider is not None, (
        "compose_gateway must wire a non-None prompt_preview_provider when im_service is set; "
        "None means agent settings page Preview shows empty (M3 regression)"
    )
    assert callable(provider), "prompt_preview_provider must be callable"

    # Call the provider and verify it returns the expected schema.
    result = (
        asyncio.run(
            provider(
                "agent-a",
                str(workspace_root),
                {},  # features
                None,  # custom_prompt
                [],  # tool_ids
                "direct",  # scenario
                [],  # skill_ids
            )
        )
        if asyncio.iscoroutinefunction(provider)
        else provider(
            "agent-a",
            str(workspace_root),
            {},
            None,
            [],
            "direct",
            [],
        )
    )
    assert isinstance(result, dict), f"provider must return dict, got {type(result)}"
    assert "prompt" in result, (
        f"provider result must contain 'prompt', got {list(result)}"
    )
    assert "section_count" in result, (
        f"provider result must contain 'section_count', got {list(result)}"
    )
    assert result["prompt"], "prompt_preview_provider must return non-empty prompt"
    assert isinstance(result["section_count"], int) and result["section_count"] > 0, (
        f"section_count must be positive int, got {result['section_count']!r}"
    )
