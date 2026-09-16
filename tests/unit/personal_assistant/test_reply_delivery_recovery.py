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
    ReplyDeliveryRecovery,
    external_recovery_payload,
)
from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages


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
    images.record_delivery(
        ctx.output_key, kind, {"state": "pending", "recovery": recovery}
    )
    images.record_delivery(
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
    service = ReplyDeliveryRecovery(
        images=restarted, im_connection_manager=manager, outbound_router=router
    )
    assert await service.recover() == 0
    assert len(restarted.unresolved_deliveries()) == 1
    assert await service.recover() == 1
    assert await service.recover() == 0
    assert not restarted.unresolved_deliveries()
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
    images.record_delivery(
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
    service = ReplyDeliveryRecovery(
        images=images,
        im_connection_manager=manager,
        outbound_router=SimpleNamespace(),
        is_run_active=lambda run: run == "still-running",
    )
    assert sorted(await asyncio.gather(service.recover(), service.recover())) == [0, 1]
    manager.send_json_await_ack.assert_awaited_once_with(
        "node.streaming_delta", payload
    )
