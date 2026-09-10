"""Runtime IM frames hide source paths and complete only after image projection."""

import asyncio
from pathlib import Path

from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages
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


class Connection:
    connected = True

    def __init__(self):
        self.frames = []

    async def send_json(self, kind, payload):
        self.frames.append((kind, payload))

    async def send_json_await_ack(self, kind, payload):
        self.frames.append((kind, payload))
        return {"message_id": "message"}


class Images(ReplyImages):
    def __init__(self, root):
        super().__init__(root)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def project_im(self, reply, conversation_id):
        self.entered.set()
        await self.release.wait()
        assert conversation_id == "conversation"
        return self.render(reply, {0: "/im/v1/conversations/conversation/images/image"})


async def test_completion_waits_for_snapshot_and_pending_never_leaks_path(
    tmp_path: Path,
):
    context = RunDeliveryContext(
        "run",
        "agent",
        "session",
        RunDeliveryTarget.for_im_relay(IMRelayTarget("conversation", "relay")),
    )
    contexts = RunDeliveryContextStore()
    contexts.seed(context)
    tracker = RuntimeDeliveryTaskTracker(context_store=contexts)
    connection = Connection()
    images = Images(tmp_path / "state")
    factory = lambda ctx, output_key: ReplyImageContext(
        output_key, "owner", ctx.agent_id, ctx.run_id, "0", tmp_path
    )
    wrapped = ImageReplyConnection(
        connection,
        reply_images=images,
        context_store=contexts,
        task_tracker=tracker,
        image_context_factory=factory,
    )
    source = tmp_path / ".nanoassistant/exports/image.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    for text in ["before ![chart](", str(source), ") after"]:
        await wrapped.send_json(
            "node.streaming_delta",
            {
                "kind": "message_delta",
                "run_id": "run",
                "message_id": "message",
                "delta_text": text,
            },
        )
    visible = "".join(frame[1].get("delta_text", "") for frame in connection.frames)
    assert visible == "before ![chart](nano-image-pending:0) after"
    completion = asyncio.create_task(
        wrapped.send_json(
            "node.streaming_delta",
            {
                "kind": "message_completed",
                "run_id": "run",
                "message_id": "message",
                "final_content": None,
            },
        )
    )
    await images.entered.wait()
    assert not any(
        frame[1]["kind"] == "message_completed" for frame in connection.frames
    )
    images.release.set()
    await completion
    assert (
        connection.frames[-1][1]["final_content"]
        == "before ![chart](/im/v1/conversations/conversation/images/image) after"
    )


async def test_reset_discard_does_not_wait_for_image_preparation(tmp_path: Path):
    contexts = RunDeliveryContextStore()
    ctx = contexts.seed(
        RunDeliveryContext(
            "run",
            "agent",
            "session",
            RunDeliveryTarget.for_im_relay(IMRelayTarget("conversation", "relay")),
        )
    )
    tracker = RuntimeDeliveryTaskTracker(context_store=contexts)
    images = Images(tmp_path / "state")
    connection = Connection()
    wrapped = ImageReplyConnection(
        connection,
        reply_images=images,
        context_store=contexts,
        task_tracker=tracker,
        image_context_factory=lambda ctx, key: ReplyImageContext(
            key, "owner", "agent", "run", "0", tmp_path
        ),
    )
    await wrapped.send_json(
        "node.streaming_delta",
        {
            "kind": "message_delta",
            "run_id": "run",
            "message_id": "message",
            "delta_text": "![image](missing.png)",
        },
    )
    completing = asyncio.create_task(
        wrapped.send_json(
            "node.streaming_delta",
            {"kind": "message_completed", "run_id": "run", "message_id": "message"},
        )
    )
    await images.entered.wait()
    contexts.quiesce("run")
    await tracker.drain_admitted(("run",))
    contexts.suppress("run")
    await wrapped.send_json(
        "node.streaming_delta",
        {
            "kind": "message_discarded",
            "run_id": "run",
            "message_id": "message",
            "reason": "new_session",
        },
    )
    assert connection.frames[-1][1]["kind"] == "message_discarded"
    images.release.set()
    await completing
    assert not any(
        frame[1]["kind"] == "message_completed" for frame in connection.frames
    )
