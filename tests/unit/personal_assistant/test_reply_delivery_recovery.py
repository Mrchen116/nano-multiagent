"""Lost acknowledgements resume from durable identities after Gateway restart."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from personal_assistant.channels.base import (
    OutboundMessage,
    ProviderImageEntry,
    ProviderImagePreparation,
)
from personal_assistant.gateway.reply_delivery_recovery import (
    external_recovery_payload,
)
from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages
from personal_assistant.gateway.message_delivery import MessageDelivery
from personal_assistant.gateway.delivery_ledger import DeliveryLedger


def make_delivery(
    *, images, im_connection_manager, outbound_router, is_run_active=lambda _: False
):
    return MessageDelivery(
        images=images,
        connection=im_connection_manager,
        router=outbound_router,
        contexts=SimpleNamespace(
            get=lambda run: object() if is_run_active(run) else None
        ),
        catalog=None,
        registry=None,
        image_connection=None,
        tracker=None,
        kernel=None,
        owner_id="owner",
        writer=None,
        notify_pending=lambda: None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["native_delta", "explicit_message", "external_prepared"]
)
async def test_restart_replays_original_identity_without_reading_source(tmp_path, kind):
    source = tmp_path / "image.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    images = ReplyImages(tmp_path / "state")
    ctx = ReplyImageContext("run:bubble", "owner", "agent", "run", "bubble", tmp_path)
    prepared = images.prepare(ctx, f"![image](<{source}>)")
    payload = {
        "message_id": "bubble",
        "idempotency_key": "run:bubble:0",
        "delta_text": "![image](/im/image)",
    }
    if kind == "native_delta":
        recovery = {
            "kind": kind,
            "payload": payload,
            "completion_payload": {
                **payload,
                "kind": "message_completed",
                "idempotency_key": "run:bubble:done",
            },
        }
    elif kind == "explicit_message":
        recovery = {
            "kind": kind,
            "payload": {
                "to": "c_target",
                "text": "![image](/im/image)",
                "dispatch_request_id": "original-tool-call",
            },
        }
    else:
        recovery = external_recovery_payload(
            OutboundMessage(
                "feishu:agent",
                prepared.markdown_template,
                "chat",
                metadata={"reply_dedupe_key": "original-provider-key"},
            ),
            ProviderImagePreparation(
                "app", "app", (ProviderImageEntry(0, "img_saved"),)
            ),
        )
    DeliveryLedger(images.root).record_delivery(
        ctx.output_key, kind, {"state": "pending", "recovery": recovery}
    )
    DeliveryLedger(images.root).record_delivery(
        ctx.output_key,
        "already-confirmed",
        {"state": "delivered", "recovery": recovery},
    )
    source.unlink()
    restarted = ReplyImages(tmp_path / "state")
    ack = SimpleNamespace(
        message_id="confirmed", as_dict=lambda: {"message_id": "confirmed"}
    )
    manager = SimpleNamespace(
        send_agent_message=AsyncMock(side_effect=[ConnectionError("lost ack"), ack]),
        send_json_await_ack=AsyncMock(
            side_effect=[ConnectionError("lost ack"), {"ok": True}, {"ok": True}]
        ),
    )
    router = SimpleNamespace(
        send_prepared_async=AsyncMock(
            side_effect=[ConnectionError("lost ack"), "delivered"]
        )
    )
    service = make_delivery(
        images=restarted, im_connection_manager=manager, outbound_router=router
    )
    assert await service.recover_pending() == 0
    assert len(DeliveryLedger(restarted.root).unresolved_deliveries()) == 1
    assert await service.recover_pending() == 1
    assert await service.recover_pending() == 0
    assert not DeliveryLedger(restarted.root).unresolved_deliveries()
    if kind == "explicit_message":
        assert (
            manager.send_agent_message.call_args_list[0]
            == manager.send_agent_message.call_args_list[1]
        )
    elif kind == "native_delta":
        assert (
            manager.send_json_await_ack.call_args_list[0]
            == manager.send_json_await_ack.call_args_list[1]
        )
        assert (
            manager.send_json_await_ack.call_args_list[-1].args[1]["kind"]
            == "message_completed"
        )
    else:
        calls = router.send_prepared_async.call_args_list
        assert calls[0].args == calls[1].args
        assert calls[1].args[1].entries[0].image_key == "img_saved"
        assert calls[1].args[0].metadata["reply_dedupe_key"] == "original-provider-key"


@pytest.mark.asyncio
async def test_concurrent_recovery_does_not_finalize_a_live_run(tmp_path):
    import asyncio

    images = ReplyImages(tmp_path / "state")
    payload = {
        "run_id": "still-running",
        "message_id": "bubble",
        "idempotency_key": "stable-delta",
    }
    DeliveryLedger(images.root).record_delivery(
        "draft",
        "im",
        {
            "state": "pending",
            "recovery": {
                "kind": "native_delta",
                "payload": payload,
                "completion_payload": {**payload, "kind": "message_completed"},
            },
        },
    )
    manager = SimpleNamespace(send_json_await_ack=AsyncMock(return_value={"ok": True}))
    service = make_delivery(
        images=images,
        im_connection_manager=manager,
        outbound_router=SimpleNamespace(),
        is_run_active=lambda run: run == "still-running",
    )
    assert sorted(
        await asyncio.gather(service.recover_pending(), service.recover_pending())
    ) == [0, 1]
    manager.send_json_await_ack.assert_awaited_once_with(
        "node.streaming_delta", payload
    )


def test_only_unresolved_committed_sends_reuse_content_identity(tmp_path):
    images = ReplyImages(tmp_path / "state")
    args = dict(
        agent_id="agent",
        session_id="session",
        target="c_chat",
        text="![image](/same.png)",
    )
    assert (
        DeliveryLedger(images.root).dispatch_identity(**args, call_id="first")
        == "first"
    )
    # Private preparation/withheld output has no public delivery receipt.
    assert (
        DeliveryLedger(images.root).dispatch_identity(**args, call_id="second")
        == "second"
    )
    key = "dispatch:agent:session:second"
    DeliveryLedger(images.root).record_delivery(key, "im", {"status": "delivered"})
    DeliveryLedger(images.root).record_delivery(key, "external", {"status": "unknown"})
    restarted = ReplyImages(tmp_path / "state")
    assert (
        DeliveryLedger(restarted.root).dispatch_identity(**args, call_id="third")
        == "second"
    )
    DeliveryLedger(images.root).record_delivery(
        key, "external", {"status": "delivered"}
    )
    assert (
        DeliveryLedger(restarted.root).dispatch_identity(
            **args, call_id="intentional-new"
        )
        == "intentional-new"
    )
    assert (
        DeliveryLedger(restarted.root).dispatch_identity(
            **{**args, "target": "c_other"}, call_id="other-target"
        )
        == "other-target"
    )


@pytest.mark.asyncio
async def test_expired_provider_window_keeps_unknown_without_replaying(tmp_path):
    import time
    from personal_assistant.gateway.reply_images import external_retry_allowed

    images = ReplyImages(tmp_path / "state")
    first = time.time() - 3601
    recovery = external_recovery_payload(
        OutboundMessage(
            "feishu:agent", "saved", "chat", metadata={"reply_dedupe_key": "original"}
        ),
        ProviderImagePreparation("app", "app", (ProviderImageEntry(0, "img_saved"),)),
    )
    DeliveryLedger(images.root).record_delivery(
        "draft",
        "feishu",
        {"state": "pending", "first_attempt_at": first, "recovery": recovery},
    )
    DeliveryLedger(images.root).record_delivery(
        "draft", "feishu", {"state": "pending", "recovery": recovery}
    )
    receipt = DeliveryLedger(images.root).delivery_receipt("draft", "feishu")
    assert receipt["first_attempt_at"] == first
    assert not external_retry_allowed(receipt)
    assert external_retry_allowed(receipt, now=first + 3599)
    router = SimpleNamespace(send_prepared_async=AsyncMock(return_value="delivered"))
    service = make_delivery(
        images=ReplyImages(tmp_path / "state"),
        im_connection_manager=SimpleNamespace(),
        outbound_router=router,
    )
    assert await service.recover_pending() == 0
    router.send_prepared_async.assert_not_awaited()
    assert (
        DeliveryLedger(images.root).delivery_receipt("draft", "feishu")["state"]
        == "pending"
    )
