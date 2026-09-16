"""Gateway delivery keeps complete candidates private until prepared and admitted."""

import asyncio
from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.sdk import PermissionOutcome
from personal_assistant.gateway.message_delivery import MessageDelivery, ReplyCandidate
from personal_assistant.gateway.reply_images import ReplyImages


def make_owner(tmp_path, *, allowed=True):
    context = SimpleNamespace(
        visibility_policy=ReplyVisibilityPolicy.LITERAL_TEXT,
        agent_id="a",
        conversation_id="c_target",
        owner_user_id="u",
        trigger_source="im",
        managed_image_messages=set(),
        managed_reply_text="",
        resolve_conversation=lambda _: None,
    )
    images = ReplyImages(tmp_path / "state")
    images.resolve_target = AsyncMock(return_value="c_target")
    images.project_im = AsyncMock(return_value="![image](/saved)")
    connection = SimpleNamespace(
        connected=True, send_json_await_ack=AsyncMock(return_value={"ok": True})
    )

    async def events(*args, **kwargs):
        await asyncio.Event().wait()
        yield {}

    kernel = SimpleNamespace(
        current_event_sequence=lambda: 0,
        stream=events,
        authorize_tool=AsyncMock(return_value=PermissionOutcome(allowed)),
    )
    tracker = SimpleNamespace(
        admit_publication=lambda _: True, release_publication=lambda _: None
    )
    prepared = {}
    native = SimpleNamespace(
        connected=True,
        prepare_candidate=lambda run, candidate, key, text: prepared.update(
            key=key, text=text
        ),
    )
    owner = MessageDelivery(
        images=images,
        contexts=SimpleNamespace(
            get=lambda _: context,
            has_unconsumed_input=lambda _: False,
            await_visibility=AsyncMock(return_value=True),
            await_revoked=lambda _: asyncio.Event().wait(),
        ),
        catalog=SimpleNamespace(
            require=lambda _: SimpleNamespace(
                config=SimpleNamespace(workspace_root=tmp_path)
            )
        ),
        registry=None,
        router=None,
        connection=connection,
        image_connection=lambda: native,
        tracker=tracker,
        kernel=kernel,
        owner_id="u",
        writer=None,
        notify_pending=lambda: None,
    )

    async def writer(event):
        await owner.publish_native_frame(
            prepared["key"],
            "node.streaming_delta",
            {
                "run_id": event["run_id"],
                "message_id": event["message_id"],
                "delta_text": prepared["text"],
            },
            None,
        )

    owner.writer = AsyncMock(side_effect=writer)
    return owner


def candidate(text):
    return ReplyCandidate("r", "s", "t", "g", "m", text)


@pytest.mark.asyncio
async def test_missing_image_keeps_entire_text_private(tmp_path):
    owner = make_owner(tmp_path)
    result = await owner.deliver_candidate(candidate("before ![x](/missing.png) after"))
    assert result.state == "withheld"
    owner.writer.assert_not_awaited()
    owner.kernel.authorize_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_denial_prevents_read_and_publish(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    owner = make_owner(tmp_path, allowed=False)
    result = await owner.deliver_candidate(candidate(f"![x]({path})"))
    assert result.reason_code == "permission_denied"
    assert owner.images.load("r:candidate:m") is None
    owner.writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_approved_descriptor_survives_path_replacement(tmp_path):
    path = tmp_path / "image.png"
    original = b"\x89PNG\r\n\x1a\noriginal"
    path.write_bytes(original)
    owner = make_owner(tmp_path)

    async def authorize(*args, **kwargs):
        path.rename(tmp_path / "old.png")
        path.write_bytes(b"\x89PNG\r\n\x1a\nreplacement")
        return PermissionOutcome(True)

    owner.kernel.authorize_tool.side_effect = authorize
    result = await owner.deliver_candidate(candidate(f"![x]({path})"))
    assert result.state == "delivered"
    saved = owner.images.load("r:candidate:m")
    assert owner.images.image_bytes(saved.images[0]) == original
    assert owner.ledger.delivery_receipt(saved.output_key, "im")["state"] == "delivered"


def test_feedback_budget_is_durable_and_busy_does_not_consume(tmp_path):
    owner = make_owner(tmp_path)
    first = owner.next_submission("request")
    assert first == owner.next_submission("request")
    owner.record_admitted("request", first[0])
    owner.record_admitted("request", first[0])
    restarted = make_owner(tmp_path)
    second = restarted.next_submission("request")
    assert second[1] == 2
    restarted.record_admitted("request", second[0])
    assert owner.next_submission("request") is None


@pytest.mark.asyncio
async def test_duplicate_candidate_uses_approved_snapshot_after_source_removed(
    tmp_path,
):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    owner = make_owner(tmp_path)
    intent = candidate(f"![x]({path})")
    assert (await owner.deliver_candidate(intent)).state == "delivered"
    path.unlink()
    assert (await owner.deliver_candidate(intent)).state == "delivered"
    owner.kernel.authorize_tool.assert_awaited_once()
    permission_call = owner.kernel.authorize_tool.await_args
    assert permission_call.args[1] == "send_message"
    assert permission_call.kwargs["operation_description"] == (
        "Publish the assistant's ordinary reply to its current conversation; "
        "no send_message tool is invoked."
    )
    owner.connection.send_json_await_ack.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["NO_REPLY", "  HEARTBEAT_OK\n"])
async def test_protocol_silence_is_admitted_before_any_resource_or_target_io(
    tmp_path, token
):
    owner = make_owner(tmp_path)
    owner.contexts.get(
        "r"
    ).visibility_policy = ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
    owner.writer = AsyncMock()
    result = await owner.deliver_candidate(candidate(token))
    assert result.state == "suppressed"
    owner.images.resolve_target.assert_not_awaited()
    owner.kernel.authorize_tool.assert_not_awaited()
    owner.connection.send_json_await_ack.assert_not_awaited()
    assert owner.writer.call_args.args[0]["event"] == "reply_suppressed"
    assert owner.images.load("r:candidate:m") is None
