"""Shadow recovery projects the already-frozen reply rather than rereading sources."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.gateway.inbound_models import ShadowConversationRef
from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.shadow_saga import (
    ExternalShadowBubbleEvent,
    ExternalShadowSagaStore,
)
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync
from tests.helpers.runtime_delivery import delivery_context_store


class _ConnectedIM:
    connected = True

    async def send_json(self, _message_type, _payload):
        return None

    async def send_json_await_ack(self, _message_type, payload):
        if payload["kind"] == "turn_start":
            return {"payload": {"message_id": "im-message"}}
        return {"payload": {"kind": payload["kind"]}}

    def finish_external_shadow_run(self, _run_id):
        return None


def _saga(store, event="event"):
    return store.prepare(
        message=InboundMessage(
            channel_name="feishu:agent",
            text="show image",
            external_user_id="external-user",
            external_chat_id="chat",
            is_group=False,
            agent_id="agent",
            ingress=InboundIngress(
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="chat",
                    agent_id="agent",
                    conversation_type="direct",
                    trigger_source="external",
                ),
                external_event=ExternalInboundEventIdentity(
                    connector_account_id="app", provider_event_id=event
                ),
            ),
        ),
        agent_id="agent",
        owner_id="owner",
    )


def test_each_external_bubble_freezes_images_under_its_own_output_key(tmp_path):
    store = ExternalShadowSagaStore(db_path=tmp_path / "sagas.db")
    saga = _saga(store)
    source = tmp_path / ".nanoassistant/exports/chart.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    images = ReplyImages(tmp_path / "images")
    tracker = RuntimeDeliveryTaskTracker()
    contexts = delivery_context_store(
        {
            "run": {
                "agent_id": "agent",
                "conversation_id": "conversation",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent",
                "reply_target_chat_id": "chat",
                "shadow_saga_id": saga.saga_id,
            }
        }
    )

    def deliver(text, metadata):
        images.prepare(
            ReplyImageContext(
                metadata["output_key"],
                "owner",
                "agent",
                "run",
                metadata["output_key"],
                tmp_path,
            ),
            text,
        )

    observer = build_kernel_event_observer(
        im_connection_manager_factory=_ConnectedIM,
        run_context_store=contexts,
        external_reply_sender=deliver,
        shadow_bubble_record=store.record,
        task_tracker=tracker,
    )

    async def emit():
        for event in (
            {"event": "run_status", "run_id": "run", "status": "running"},
            {
                "event": "assistant_message",
                "run_id": "run",
                "message_id": "kernel-1",
                "content": "first bubble",
            },
            {
                "event": "assistant_message",
                "run_id": "run",
                "message_id": "kernel-2",
                "content": f"before ![chart](<{source}>) after",
            },
        ):
            pending = observer(event)
            if pending is not None:
                await pending
        observer({"event": "turn_end", "run_id": "run", "completed": True})
        await tracker.drain_run("run")

    asyncio.run(emit())

    assert images.load("run:bubble:0").markdown_template == "first bubble"
    second = images.load("run:bubble:1")
    assert second is not None
    assert len(second.images) == 1


@pytest.mark.parametrize("kind", ["rich", "legacy"])
@pytest.mark.parametrize("revoked", [False, True], ids=["deliver", "revoke"])
def test_shadow_recovery_uploads_original_snapshot_before_public_write(
    tmp_path: Path, monkeypatch, kind, revoked
):
    store = ExternalShadowSagaStore(db_path=tmp_path / "sagas.db")
    saga = _saga(store)
    store.record_anchor(
        saga_id=saga.saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="conversation", im_message_id="user"
        ),
    )
    source = tmp_path / ".nanoassistant/exports/chart.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    content = f"Before ![chart]({source}) after"
    if kind == "rich":
        record = store.record(
            ExternalShadowBubbleEvent(
                kind="terminal",
                saga_id=saga.saga_id,
                run_id="run",
                content=content,
                delivery_status="completed",
            )
        )
    else:
        record = store.prepare_output(
            saga_id=saga.saga_id,
            run_id="run",
            output_kind="final",
            kernel_message_id="kernel",
            content=content,
        )
    key = record.output_key
    images = ReplyImages(
        tmp_path / "images", im_base_url="http://im.local", token_getter=lambda: "token"
    )
    factory = lambda agent_id, run_id, bubble_id, output_key: ReplyImageContext(
        output_key, "owner", agent_id, run_id, bubble_id, tmp_path
    )
    # External delivery already froze this exact output while IM was offline.
    images.prepare(factory("agent", "run", "0", key), content)
    source.unlink()
    actions = []
    fail = [True]

    def handler(request):
        if request.url.path.endswith("/images"):
            assert request.content == b"\x89PNG\r\n\x1a\noriginal"
            assert request.headers["Idempotency-Key"] == f"{key}:0"
            actions.append("upload")
            if fail[0]:
                return httpx.Response(503)
            return httpx.Response(
                201, json={"url": "/im/v1/conversations/conversation/images/image"}
            )
        actions.append("write")
        payload = json.loads(request.content)
        assert (
            payload["content"]
            == "Before ![chart](/im/v1/conversations/conversation/images/image) after"
        )
        return httpx.Response(200, json={"id": "agent-message"})

    transport = httpx.MockTransport(handler)
    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(**{**kwargs, "transport": transport}),
    )

    async def token():
        return "token"

    async def before(run_id):
        assert run_id == "run"
        actions.append("admit")
        return not revoked

    def after(run_id):
        assert run_id == "run"
        actions.append("release")

    reopened = ExternalShadowSagaStore(db_path=tmp_path / "sagas.db")
    sync = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token,
        owner_user_id="owner",
        saga_store=reopened,
        reply_images=images,
        image_context_factory=factory,
        before_publish=before,
        after_publish=after,
    )
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(sync.recover_pending())
    assert actions == ["upload"]
    fail[0] = False
    asyncio.run(sync.recover_pending())
    expected = ["upload", "upload", "admit"]
    if not revoked:
        expected.extend(["write", "release"])
    assert actions == expected
    # A restart has no live context gate. Durable revocation must still prevent
    # the old image reply from becoming an eligible recovery output again.
    restarted = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token,
        owner_user_id="owner",
        saga_store=ExternalShadowSagaStore(db_path=tmp_path / "sagas.db"),
        reply_images=images,
        image_context_factory=factory,
    )
    asyncio.run(restarted.recover_pending())
    assert actions == expected


def test_bubble_image_identity_survives_late_kernel_id_and_follower_saga(
    tmp_path: Path,
):
    store = ExternalShadowSagaStore(db_path=tmp_path / "sagas.db")
    first_saga = _saga(store)
    first = store.record(
        ExternalShadowBubbleEvent(
            kind="begin", saga_id=first_saga.saga_id, run_id="run"
        )
    )
    terminal = store.record(
        ExternalShadowBubbleEvent(
            kind="terminal",
            saga_id=first_saga.saga_id,
            run_id="run",
            content="first",
            kernel_message_id="late-kernel",
            delivery_status="completed",
        )
    )
    assert first.output_key == terminal.output_key == "run:bubble:0"
    second_saga = _saga(store, "followup")
    second = store.record(
        ExternalShadowBubbleEvent(
            kind="begin", saga_id=second_saga.saga_id, run_id="run"
        )
    )
    assert second.output_key == "run:bubble:1"
    legacy = store.prepare_output(
        saga_id=first_saga.saga_id,
        run_id="run",
        output_kind="intermediate",
        kernel_message_id="late-kernel",
        content="first",
    )
    assert legacy.output_key == first.output_key
