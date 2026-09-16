"""Native writer uses approved projections and cannot finalize uncertain sends."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tests.helpers.message_delivery import message_delivery
from personal_assistant.gateway.runtime_delivery.context import (
    IMRelayTarget,
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)
from personal_assistant.gateway.runtime_delivery.image_connection import (
    ImageReplyConnection,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)


def setup_writer():
    contexts = RunDeliveryContextStore()
    contexts.seed(
        RunDeliveryContext(
            "run",
            "agent",
            "session",
            RunDeliveryTarget.for_im_relay(IMRelayTarget("conversation", "relay")),
        )
    )
    connection = SimpleNamespace(
        connected=True,
        send_json=AsyncMock(),
        send_json_await_ack=AsyncMock(return_value={"message_id": "message"}),
    )
    owner = message_delivery(connection=connection)
    owner.contexts = contexts
    writer = ImageReplyConnection(
        connection,
        publish_prepared=owner.publish_native_frame,
        is_confirmed=owner.native_confirmed,
        context_store=contexts,
        task_tracker=RuntimeDeliveryTaskTracker(context_store=contexts),
    )
    return contexts, connection, owner, writer


def frame(kind, **fields):
    return {"kind": kind, "run_id": "run", "message_id": "message", **fields}


@pytest.mark.asyncio
async def test_completion_uses_saved_projection_without_reading_raw_content():
    _, connection, owner, writer = setup_writer()
    writer.prepare_candidate("run", "candidate", "output", "![x](/saved/image)")
    await writer.send_json(
        "node.streaming_delta",
        frame(
            "message_delta",
            idempotency_key="run:assistant_message:candidate",
            delta_text="![x](/deleted.png)",
        ),
    )
    await writer.send_json(
        "node.streaming_delta",
        frame("message_completed", final_content="![x](/deleted.png)"),
    )
    assert owner.native_confirmed("output")
    assert (
        connection.send_json.call_args.args[1]["final_content"] == "![x](/saved/image)"
    )


@pytest.mark.asyncio
async def test_unprepared_body_cannot_bypass_delivery_owner():
    _, connection, _, writer = setup_writer()
    with pytest.raises(ValueError, match="prepared delivery"):
        await writer.send_json(
            "node.streaming_delta",
            frame("message_delta", delta_text="![x](/private.png)"),
        )
    connection.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_ack_loss_blocks_completion_until_same_identity_recovers():
    contexts, connection, owner, writer = setup_writer()
    writer.prepare_candidate("run", "candidate", "output", "approved")
    connection.send_json_await_ack.side_effect = [
        ConnectionError("ACK lost"),
        {"ok": True},
    ]
    with pytest.raises(ConnectionError):
        await writer.send_json(
            "node.streaming_delta",
            frame(
                "message_delta",
                idempotency_key="run:assistant_message:candidate",
                delta_text="raw",
            ),
        )
    await writer.send_json(
        "node.streaming_delta", frame("message_completed", final_content="raw")
    )
    connection.send_json.assert_not_awaited()
    assert await owner.recover_pending() == 1
    await writer.send_json(
        "node.streaming_delta", frame("message_completed", final_content="raw")
    )
    assert connection.send_json.call_args.args[1]["final_content"] == "approved"
    first, second = connection.send_json_await_ack.call_args_list
    assert first == second


@pytest.mark.asyncio
async def test_reset_discard_does_not_wait_for_body_admission():
    contexts, connection, _, writer = setup_writer()
    contexts.suppress("run")
    await writer.send_json(
        "node.streaming_delta", frame("message_discarded", reason="new_session")
    )
    assert connection.send_json.call_args.args[1]["kind"] == "message_discarded"
