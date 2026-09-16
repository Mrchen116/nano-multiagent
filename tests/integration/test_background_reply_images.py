"""Background model replies use the actual composed candidate and feedback owners."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.core.llm.interfaces import LLMMessage
from agent.sdk import RunOrigin
from personal_assistant.channels.base import (
    IMRelayIngress,
    InboundIngress,
    ReplyContext,
)
from personal_assistant.gateway.runtime_delivery.background import build_bg_reply_sender
from tests.integration.test_pa_candidate_delivery import Model, build, close, deltas
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class BackgroundModel(Model):
    async def generate(self, request):
        if request.stop_sequences:
            self.permission_requests.append(request)
            yield LLMMessage(role="assistant", content="<block>no</block>")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        self.requests.append(request)
        text = self.texts[min(len(self.requests) - 1, len(self.texts) - 1)]
        # Split inside image syntax: a per-chunk sender would leak the opening
        # fragment and never prepare or authorize a complete image reference.
        if "![" in text:
            opening, source = text.split("(", 1)
            yield LLMMessage(role="assistant", content=opening + "(")
            yield LLMMessage(role="assistant", content=source)
        else:
            yield LLMMessage(role="assistant", content=text)
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "permission_denied", "missing"])
async def test_composed_background_round_authorizes_and_repairs(
    tmp_path, monkeypatch, failure
):
    source = tmp_path.resolve() / "outside-workspace.png"
    if failure != "missing":
        source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    candidate = f"Background ![image](<{source}>)"
    model = BackgroundModel(["Ready", candidate, "The image could not be delivered."])
    rt, _, uploads, permissions = build(
        tmp_path,
        monkeypatch,
        [],
        model=model,
        deny_images=failure == "permission_denied",
    )
    authorizations = []
    authorize = rt._kernel.authorize_tool

    async def capture_authorization(*args, **kwargs):
        outcome = await authorize(*args, **kwargs)
        authorizations.append(outcome)
        return outcome

    monkeypatch.setattr(rt._kernel, "authorize_tool", capture_authorization)
    try:
        message = replace(
            inbound(chat_id="c_chat", text="start"),
            ingress=InboundIngress(im_relay=IMRelayIngress("relay", "key", "input")),
        )
        initial = await rt._on_inbound._pipeline.handle_inbound(message)
        workspace = rt._run_coordinator._session_binder.lookup(initial.session_key)
        agent = rt._run_coordinator._session_binder.current_agent("agent-a")
        rt._kernel.submit(
            session_id=initial.kernel_session_id,
            parts=[
                {
                    "type": "text",
                    "text": "background completion",
                    "context_origin": "system",
                }
            ],
            workspace_root=agent.config.workspace_root,
            origin=RunOrigin.BACKGROUND_TASK,
        )
        async with asyncio.timeout(10):
            while len(model.requests) < (
                3 if failure else 2
            ) or rt._run_coordinator.is_session_busy(initial.session_key):
                await asyncio.sleep(0.01)
        # Wait for terminal publication following the model request itself.
        async with asyncio.timeout(10):
            while len(deltas(rt)) < 2:
                await asyncio.sleep(0.01)
        visible = [payload["delta_text"] for payload in deltas(rt)]
        assert len(visible) == 2
        if failure:
            assert visible[-1] == "The image could not be delivered."
            assert not uploads
            assert not any("Background" in text for text in visible)
            feedback = model.requests[-1]
            assert "withheld before publication" in str(feedback.messages)
        else:
            assert len(uploads) == 1, authorizations
            assert "http://im.test/im/v1/images/image123" in visible[-1]
            assert visible[-1].startswith("Background ![image]")
        assert bool(authorizations) == (failure != "missing")
        assert workspace is not None
    finally:
        await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        await close(rt)


@pytest.mark.asyncio
async def test_control_text_keeps_existing_sender_without_assistant_identity():
    im = SimpleNamespace(connected=True, send_agent_message=AsyncMock())
    sender = build_bg_reply_sender(im_connection_manager_factory=lambda: im)
    await sender(
        "Stopped",
        ReplyContext(channel_name="web_relay", target_chat_id="conversation"),
        "agent|tool_call:session:stop-ack",
    )
    im.send_agent_message.assert_awaited_once_with(
        {
            "text": "Stopped",
            "to": "conversation",
            "from_session_id": "agent|tool_call:session:stop-ack",
        }
    )


@pytest.mark.asyncio
async def test_background_feedback_budget_is_shared_until_text_only_exhaustion(
    tmp_path, monkeypatch
):
    import sqlite3

    source = tmp_path.resolve() / "missing.png"
    model = BackgroundModel(["Ready", f"![missing](<{source}>)"])
    rt, _, uploads, _ = build(tmp_path, monkeypatch, [], model=model)
    try:
        message = replace(
            inbound(chat_id="c_chat", text="start"),
            ingress=InboundIngress(im_relay=IMRelayIngress("relay", "key", "input")),
        )
        initial = await rt._on_inbound._pipeline.handle_inbound(message)
        run = rt._kernel.submit(
            session_id=initial.kernel_session_id,
            parts=[{"type": "text", "text": "task done", "context_origin": "system"}],
            workspace_root=tmp_path / "agent-a",
            origin=RunOrigin.BACKGROUND_TASK,
        )
        async with asyncio.timeout(10):
            while len(model.requests) < 4 or rt._run_coordinator.is_session_busy(
                initial.session_key
            ):
                await asyncio.sleep(0.01)
        assert len(model.requests) == 4
        assert len(deltas(rt)) == 1
        assert not uploads
        assert "final delivery correction" in str(model.requests[-1].messages)
        with sqlite3.connect(tmp_path / "reply-images/reply_images.sqlite3") as db:
            records = db.execute(
                "SELECT request_id, submission_id FROM delivery_feedback"
            ).fetchall()
        assert len(records) == 2
        assert {record[0] for record in records} == {run.run_id}
    finally:
        await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        await close(rt)


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", [False, True])
async def test_external_background_keeps_provider_and_shadow_route(
    tmp_path, monkeypatch, denied
):
    from personal_assistant.channels.base import (
        ExternalConversationIdentity,
        ExternalInboundEventIdentity,
    )
    from personal_assistant.channels.feishu.adapter import FeishuAdapter
    from personal_assistant.gateway.group_context_store import GroupContextStore
    from personal_assistant.gateway.inbound_models import (
        GatewayShadowState,
        InboundRunRequest,
        RoutedInbound,
        ShadowConversationRef,
    )
    from personal_assistant.gateway.session_keys import build_session_key

    source = tmp_path.resolve() / "outside.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    model = BackgroundModel(
        ["Ready", f"Provider ![image](<{source}>)", "Cannot deliver the image."]
    )

    def shadow_http(request):
        if "/external-agent-messages/" in request.url.path:
            import httpx

            return httpx.Response(200, json={"id": "shadow-reply"})
        return None

    rt, _, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [],
        model=model,
        deny_images=denied,
        http_handler=shadow_http,
    )

    class Client:
        def __init__(self):
            self.sent = []
            self.uploads = []

        def add_reaction(self, **kwargs):
            return "reaction"

        def remove_reaction(self, **kwargs):
            pass

        def upload_image(self, content, *, content_type):
            self.uploads.append(content)
            return "provider-image"

        def send_prepared_message(self, **kwargs):
            assert kwargs["before_publish"]()
            self.sent.append(kwargs)
            return "delivered"

    client = Client()
    adapter = FeishuAdapter(
        name="feishu:agent-a",
        app_id="app",
        app_secret="secret",
        group_context_store=GroupContextStore(tmp_path / "external-groups.sqlite3"),
    )
    adapter._client = client
    rt._channel_registry.register(adapter)
    try:
        message = replace(
            inbound(chat_id="feishu:app:dm:human", text="start"),
            channel_name=adapter.name,
            metadata={
                "trigger_source": "feishu",
                "external_source": "feishu",
                "feishu_message_id": "external-input",
            },
            ingress=InboundIngress(
                external_event=ExternalInboundEventIdentity("app", "event"),
                external_conversation=ExternalConversationIdentity(
                    "feishu",
                    "feishu:app:dm:human",
                    "agent-a",
                    "direct",
                    "external",
                ),
            ),
        )
        agent = rt._run_coordinator._session_binder.current_agent("agent-a")
        saga_store = rt._on_inbound._pipeline._shadow_sync._saga_store
        saga = saga_store.prepare(
            message=message, agent_id=agent.agent_id, owner_id="u_owner"
        )
        saga_store.record_anchor(
            saga_id=saga.saga_id,
            shadow_ref=ShadowConversationRef("c_chat", "shadow-input"),
        )
        request = InboundRunRequest(
            routed=RoutedInbound(
                message=message,
                shadow=GatewayShadowState(
                    saga_id=saga.saga_id,
                    ref=ShadowConversationRef("c_chat", "shadow-input"),
                ),
            ),
            agent=agent,
            session_key=build_session_key(message, agent_id=agent.agent_id),
            sender_label="Human",
        )
        initial = await rt._run_coordinator.dispatch(request)
        rt._kernel.submit(
            session_id=initial.kernel_session_id,
            parts=[
                {"type": "text", "text": "task finished", "context_origin": "system"}
            ],
            workspace_root=agent.config.workspace_root,
            origin=RunOrigin.BACKGROUND_TASK,
        )
        expected = "Cannot deliver the image." if denied else "Provider"
        async with asyncio.timeout(10):
            while not any(
                expected in item["text"] for item in client.sent
            ) or rt._run_coordinator.is_session_busy(initial.session_key):
                await asyncio.sleep(0.01)
        assert len(client.sent) == 2, [
            (item["text"], item["idempotency_key"]) for item in client.sent
        ]
        assert all(item["receive_id"] == "human" for item in client.sent)
        assert len(client.uploads) == len(uploads) == int(not denied), (
            [item["text"] for item in client.sent],
            len(model.requests),
            [
                m.content
                for m in model.requests[-1].messages
                if "withheld before" in (m.content or "")
            ],
        )
        if denied:
            assert client.sent[-1]["text"] == "Cannot deliver the image."
        else:
            assert "provider-image" in client.sent[-1]["text"]
            assert "/im/v1/" not in client.sent[-1]["text"]
        assert len(deltas(rt)) == 2
        starts = [
            payload
            for kind, payload in rt._im_connection_manager.frames
            if kind == "node.streaming_delta" and payload.get("kind") == "turn_start"
        ]
        assert starts and all(
            payload["conversation_id"] == "c_chat" for payload in starts
        )
    finally:
        await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        await close(rt)
