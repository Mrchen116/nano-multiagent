"""Exercise global admission and committed Inbox reads through the real SDK loop."""

import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest
from aiohttp import web

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import build_kernel
from personal_assistant.channels.base import (
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.global_inbox import GlobalInboxService, GlobalInboxStore
from personal_assistant.gateway.global_run_coordinator import GlobalRunCoordinator
from personal_assistant.gateway.global_work import GlobalWorkRecorder
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_models import GatewayShadowState
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.kernel_client import InProcessKernelClient
from personal_assistant.gateway.model_fallback import ModelStickyStore
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.tools.inbox import InboxTool
from personal_assistant.tools.conversations import ConversationsTool
from personal_assistant.tools.send_message import SendMessageTool
from personal_assistant.ws.im_connection import IMDispatchAck
from tests.contract.test_kernel_sdk_behavior_contract import _allow_all, _lc_llm


class _Manager:
    connected = True

    def __init__(self):
        self.sent = []

    async def send_agent_message(self, payload):
        self.sent.append(payload)
        return IMDispatchAck(
            payload["to"],
            f"sent-{len(self.sent)}",
            "conversation_id",
            payload["to"],
            "worker",
        )


class _Model:
    def __init__(self, *, pause=False):
        self.requests = []
        self.read_done = threading.Event()
        self.resume = threading.Event()
        self.pause = pause

    async def generate(self, request):
        self.requests.append(request)
        calls = [c for m in request.messages for c in m.tool_calls]
        count = len(calls)
        if count == 1 and self.pause:
            self.read_done.set()
            await asyncio.to_thread(self.resume.wait)
        steps = [
            ("read-first", "inbox", {"action": "read", "target": "group-a"}),
            ("send-first", "send_message", {"to": "group-a", "text": "Acknowledged"}),
        ]
        if self.pause:
            steps += [
                ("read-new", "inbox", {"action": "read", "target": "group-a"}),
                (
                    "send-new",
                    "send_message",
                    {"to": "group-a", "text": "Updated acknowledgment"},
                ),
            ]
        if count < len(steps):
            call_id, name, arguments = steps[count]
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id=call_id, name=name, arguments=arguments),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
        else:
            yield LLMMessage(
                role="assistant",
                content="Private work trace only.",
                finish_reason="stop",
            )


def _message(identity, text, target="group-a"):
    return InboundMessage(
        channel_name="web_relay",
        text=text,
        external_user_id="human",
        external_chat_id=target,
        is_group=True,
        agent_id="worker",
        metadata={"mentioned_agent_ids": ["worker"]},
        ingress=InboundIngress(
            im_relay=IMRelayIngress(f"relay-{identity}", f"key-{identity}", identity)
        ),
    )


async def _wait(predicate):
    async with asyncio.timeout(10):
        while not predicate():
            await asyncio.sleep(0.01)


async def _runtime(tmp_path, model, *, outbound_router=None):
    endpoint = InternalDispatchEndpoint()
    kernel = build_kernel(
        llm=_lc_llm(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanoassistant",
        can_use_tool=_allow_all,
        _llm_client_override=model,
        tools=[
            InboxTool(gateway_dispatch_url_provider=endpoint.current_url),
            ConversationsTool(gateway_dispatch_url_provider=endpoint.current_url),
            SendMessageTool(gateway_dispatch_url_provider=endpoint.current_url),
        ],
    )
    catalog = LiveAgentCatalog(
        [
            AgentWorkspaceConfig(
                agent_id="worker",
                workspace_root=tmp_path,
                work_mode="global",
                default_model=_lc_llm().default_model,
            )
        ]
    )
    store = GlobalInboxStore(tmp_path / "global.sqlite3")
    inbox = GlobalInboxService(store)
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
        global_store=store,
        product_default_model=_lc_llm().default_model,
    )
    recorder = GlobalWorkRecorder(kernel=kernel, store=store, inbox=inbox)
    sticky = ModelStickyStore()
    shim = InProcessKernelClient(
        kernel,
        agent_catalog=catalog,
        session_binder=binder,
        product_default_model=_lc_llm().default_model,
        sticky_store=sticky,
        work_recorder=recorder,
    )
    manager = _Manager()
    handler = InternalDispatchHandler(
        im_connection_manager=manager,
        kernel=kernel,
        session_binder=binder,
        global_inbox=inbox,
        work_recorder=recorder,
        outbound_router=outbound_router,
    )
    app = web.Application()
    app.router.add_post("/internal/dispatch", handler.build_aiohttp_handler())
    for name in ("inbox", "conversations"):
        app.router.add_post(f"/internal/{name}", handler.build_query_handler(name))
    server = web.AppRunner(app)
    await server.setup()
    site = web.TCPSite(server, "127.0.0.1", 0)
    await site.start()
    endpoint.publish(host="127.0.0.1", port=site._server.sockets[0].getsockname()[1])
    controls = []
    receipts = []

    async def control(text, reply, identity):
        controls.append((text, reply.target_chat_id, identity))

    async def receipt(routed, update):
        receipts.append((routed.message.external_chat_id, update.phase))

    coordinator = GlobalRunCoordinator(
        kernel=kernel,
        kernel_client=shim,
        catalog=catalog,
        binder=binder,
        inbox=inbox,
        store=store,
        recorder=recorder,
        outbound_router=None,
        image_resolver=ImageAttachmentResolver(),
        sticky_store=sticky,
        product_default_model=_lc_llm().default_model,
        bg_reply_sender=control,
        relay_lifecycle_callback=receipt,
    )
    recorder.on_event = coordinator.observe_event
    recorder.start()
    return SimpleNamespace(
        kernel=kernel,
        store=store,
        inbox=inbox,
        binder=binder,
        recorder=recorder,
        coordinator=coordinator,
        manager=manager,
        catalog=catalog,
        server=server,
        controls=controls,
        receipts=receipts,
    )


async def _receive(runtime, message, **kwargs):
    return await runtime.coordinator.receive(
        message=message,
        agent=runtime.catalog.require("worker"),
        shadow=GatewayShadowState(),
        should_process=True,
        sender_label="Human",
        **kwargs,
    )


async def _close(runtime):
    runtime.coordinator.seal()
    await runtime.kernel.aclose()
    await runtime.coordinator.close(asyncio.get_running_loop().time() + 2)
    runtime.recorder.close()
    await runtime.server.cleanup()
    runtime.store.close()


@pytest.mark.asyncio
async def test_actual_loop_reads_commits_then_sends_without_default_chat_body(tmp_path):
    model = _Model()
    rt = await _runtime(tmp_path, model)
    try:
        result = await _receive(rt, _message("m1", "请确认这个请求"))
        await _wait(
            lambda: (
                rt.manager.sent
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert result.reply_text == "" and result.outbound is None
        assert [x["text"] for x in rt.manager.sent] == ["Acknowledged"]
        assert rt.inbox.blocking_entries("worker", "group-a") == []
        assert rt.receipts == [("group-a", "accepted"), ("group-a", "completed")]
        events = rt.store.read_unacked_events(limit=200)
        proof = next(
            e
            for e in events
            if e["type"] == "tool_result_committed" and e["payload"]["name"] == "inbox"
        )
        committed = next(e for e in events if e["type"] == "inbox_read_committed")
        sent = next(e for e in events if e["type"] == "dispatch_confirmed")
        assert proof["seq"] < committed["seq"] < sent["seq"]
        assert sent["turn_id"] and sent["payload"]["message_id"] == "sent-1"
        first_input = [
            m.content for m in model.requests[0].messages if m.role == "user"
        ]
        assert "请确认这个请求" not in str(first_input)
        reminder = next(text for text in first_input if "Inbox" in str(text))
        assert reminder.startswith("<system-reminder>\n")
        assert reminder.endswith("\n</system-reminder>")
        assert "batch" not in reminder and "inbox:worker:" not in reminder
        assert any(
            "请确认这个请求" in str(m.content)
            for r in model.requests
            for m in r.messages
            if m.role == "tool"
        )
        assert rt.store.get_signal_state("worker")["signaled_through_seq"] == 1
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_target_refresh_holds_old_draft_and_new_message_is_read_before_send(
    tmp_path,
):
    model = _Model(pause=True)
    rt = await _runtime(tmp_path, model)
    try:
        await _receive(rt, _message("m1", "Initial requirement"))
        await _wait(model.read_done.is_set)
        await _receive(rt, _message("m2", "Changed requirement"))
        assert rt.store.get_signal_state("worker")["latest_signal_seq"] == 2
        model.resume.set()
        await _wait(
            lambda: (
                rt.manager.sent
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert [x["text"] for x in rt.manager.sent] == ["Updated acknowledgment"]
        held = [
            e
            for e in rt.store.read_unacked_events(limit=200)
            if e["type"] == "draft_withheld"
        ]
        assert len(held) == 1
        assert held[0]["payload"]["source_refs"][0]["message_id"] == "m2"
        assert rt.inbox.blocking_entries("worker", "group-a") == []
    finally:
        model.resume.set()
        await _close(rt)


@pytest.mark.asyncio
async def test_stop_retains_inbox_and_new_rejects_without_rebinding(tmp_path):
    model = _Model(pause=True)
    rt = await _runtime(tmp_path, model)
    try:
        await _receive(rt, _message("m1", "Initial requirement"))
        await _wait(model.read_done.is_set)
        await _receive(rt, _message("m2", "Another request", "group-b"))
        main = rt.store.get_global_session("worker")["session_id"]
        await _receive(
            rt,
            _message("stop", "/stop", "group-b"),
            command="stop",
            operation_id="stop-op",
        )
        await _receive(
            rt, _message("new", "/new", "group-c"), command="new", operation_id="new-op"
        )
        assert rt.store.get_global_session("worker")["session_id"] == main
        assert rt.store.get_signal_state("worker")["stop_through_seq"] == 2
        assert len(rt.inbox.blocking_entries("worker", "group-b")) == 1
        assert [row[1] for row in rt.controls] == ["group-b", "group-c"]
        rt.store.update_signal_state("worker", latest_signal_seq=3)
        await _receive(
            rt,
            _message("stop", "/stop", "group-b"),
            command="stop",
            operation_id="stop-op",
        )
        assert rt.store.get_signal_state("worker")["stop_through_seq"] == 2
    finally:
        model.resume.set()
        await _close(rt)


@pytest.mark.asyncio
async def test_restart_restores_one_main_and_does_not_reawaken_committed_signal(
    tmp_path,
):
    first = await _runtime(tmp_path, _Model())
    try:
        await _receive(first, _message("m1", "Read this once"))
        await _wait(
            lambda: (
                first.manager.sent
                and not first.coordinator._monitors
                and not first.coordinator._drains
            )
        )
        main_id = first.store.get_global_session("worker")["session_id"]
    finally:
        await _close(first)
    model = _Model()
    restored = await _runtime(tmp_path, model)
    try:
        restored.coordinator.start()
        await _wait(lambda: not restored.coordinator._drains)
        assert not model.requests
        assert restored.store.get_global_session("worker")["session_id"] == main_id
        await _receive(restored, _message("m2", "A new input after restart"))
        await _wait(
            lambda: (
                model.requests
                and not restored.coordinator._monitors
                and not restored.coordinator._drains
            )
        )
        assert len(model.requests) == 1
        assert restored.store.get_signal_state("worker")["signaled_through_seq"] == 2
        assert len(restored.inbox.blocking_entries("worker", "group-a")) == 1
        # Choosing not to read leaves pending content without a repeated wake.
        restored.coordinator.notify("worker")
        await _wait(lambda: not restored.coordinator._drains)
        assert len(model.requests) == 1
    finally:
        await _close(restored)
