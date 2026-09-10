"""Global explicit replies must reach the external channel, not only its IM shadow."""

import asyncio
import threading
from dataclasses import replace

import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import (
    GatewayShadowState,
    ShadowConversationRef,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from tests.integration.test_global_gateway_runtime import (
    _Model,
    _close,
    _message,
    _runtime,
    _wait,
)


class _ExternalChannel:
    name = "feishu:worker"

    def __init__(self, fail):
        self.fail = fail
        self.started = threading.Event()
        self.release = threading.Event()
        self.sent = []

    def send(self, outbound):
        self.started.set()
        self.release.wait(timeout=10)
        if self.fail:
            raise RuntimeError("provider rejected delivery")
        self.sent.append(outbound)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_external_dispatch_waits_for_provider_before_confirming_work(
    tmp_path, fail
):
    channel = _ExternalChannel(fail)
    router = OutboundRouter(ChannelRegistry([channel]))
    rt = await _runtime(tmp_path, _Model(), outbound_router=router)
    try:
        message = replace(
            _message("provider-m1", "Please acknowledge"),
            channel_name=channel.name,
            external_chat_id="feishu:app:dm:human",
            is_group=False,
            ingress=InboundIngress(
                external_event=ExternalInboundEventIdentity("app", "provider-m1"),
                external_conversation=ExternalConversationIdentity(
                    "feishu", "feishu:app:dm:human", "worker", "direct", "external"
                ),
            ),
        )
        await rt.coordinator.receive(
            message=message,
            agent=rt.catalog.require("worker"),
            shadow=GatewayShadowState(
                saga_id="saga-m1", ref=ShadowConversationRef("c_group001", "shadow-m1")
            ),
            should_process=True,
            sender_label="Human",
        )
        await _wait(
            lambda: (
                channel.started.is_set()
                or (bool(rt.manager.sent) and not rt.coordinator._monitors)
            )
        )
        await asyncio.sleep(0)
        assert channel.started.is_set(), (
            "IM shadow ACK must also route the external reply"
        )
        assert not any(
            event["type"] == "dispatch_confirmed"
            for event in rt.store.read_unacked_events(limit=200)
        )
        channel.release.set()
        await _wait(lambda: not rt.coordinator._monitors and not rt.coordinator._drains)
        facts = [
            event
            for event in rt.store.read_unacked_events(limit=200)
            if event["type"] == "dispatch_confirmed"
        ]
        if fail:
            assert not facts and not channel.sent
        else:
            assert len(facts) == 1
            assert facts[0]["payload"]["conversation_id"] == "c_group001"
            assert [(x.target_chat_id, x.text) for x in channel.sent] == [
                ("feishu:app:dm:human", "Acknowledged")
            ]
            assert channel.sent[0].metadata["reply_dedupe_key"]
    finally:
        channel.release.set()
        await _close(rt)


@pytest.mark.asyncio
async def test_external_local_target_from_inbox_replies_after_shadow_recovery(tmp_path):
    import json
    from types import SimpleNamespace
    from agent.core.llm.interfaces import LLMMessage, LLMToolCall

    class ReplyModel:
        requests = []
        target = None

        async def generate(self, request):
            self.requests.append(request)
            count = len([c for m in request.messages for c in m.tool_calls])
            if count == 1:
                output = next(
                    m.content for m in reversed(request.messages) if m.role == "tool"
                )
                self.target = json.loads(output)["conversations"][0]["target"]
            steps = [
                ("check", "inbox", {"action": "check"}),
                ("read", "inbox", {"action": "read", "target": self.target}),
                (
                    "send",
                    "send_message",
                    {"target": self.target, "text": "Recovered reply"},
                ),
            ]
            if count < len(steps):
                call, name, args = steps[count]
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id=call, name=name, arguments=args),),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
            else:
                yield LLMMessage(role="assistant", content="Done", finish_reason="stop")

    channel = _ExternalChannel(False)
    channel.release.set()
    model = ReplyModel()
    shadow = SimpleNamespace(
        resolved_anchor=lambda saga: ShadowConversationRef("c_group001", "shadow-m1")
    )
    rt = await _runtime(
        tmp_path,
        model,
        outbound_router=OutboundRouter(ChannelRegistry([channel])),
        shadow_sync=shadow,
    )
    try:
        message = replace(
            _message("external", "Please reply"),
            channel_name=channel.name,
            external_chat_id="feishu:app:dm:human",
            is_group=False,
            ingress=InboundIngress(
                external_event=ExternalInboundEventIdentity("app", "external"),
                external_conversation=ExternalConversationIdentity(
                    "feishu", "feishu:app:dm:human", "worker", "direct", "external"
                ),
            ),
        )
        await rt.coordinator.receive(
            message=message,
            agent=rt.catalog.require("worker"),
            shadow=GatewayShadowState(saga_id="recover-saga"),
            should_process=True,
            sender_label="Human",
        )
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert model.target.startswith("local:")
        assert [(item.target_chat_id, item.text) for item in channel.sent] == [
            ("feishu:app:dm:human", "Recovered reply")
        ]
        assert rt.manager.sent[0]["to"] == "c_group001"
    finally:
        await _close(rt)
