"""Image delivery retains prepared snapshots and exact identities across recovery."""

from __future__ import annotations

import json
import sqlite3

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from personal_assistant.gateway.reply_delivery_recovery import ReplyDeliveryRecovery
from personal_assistant.gateway.reply_images import ReplyImages
from tests.integration.test_pa_candidate_delivery import (
    Model,
    Transport,
    build,
    close,
    deltas,
    receive,
)


class RemoveSourceTransport(Transport):
    source = None
    lose_ack = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.accepted = {}
        self.lost = False

    async def send_json_await_ack(self, kind, payload):
        if kind == "node.streaming_delta" and payload.get("kind") == "message_delta":
            key = payload["idempotency_key"]
            self.accepted.setdefault(key, dict(payload))
            if self.source is not None:
                self.source.unlink(missing_ok=True)
            if self.lose_ack and not self.lost:
                self.lost = True
                self.frames.append((kind, dict(payload)))
                raise ConnectionError("accepted delta, lost ACK")
        return await super().send_json_await_ack(kind, payload)


def receipts(tmp_path):
    with sqlite3.connect(tmp_path / "reply-images/reply_images.sqlite3") as db:
        return [
            (key, json.loads(value))
            for key, value in db.execute(
                "SELECT output_key, receipt_json FROM reply_deliveries WHERE channel='im'"
            )
        ]


@pytest.mark.asyncio
async def test_native_completion_uses_prepared_image_after_original_source_removed(
    tmp_path, monkeypatch
):
    source = tmp_path / "original.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    monkeypatch.setattr(RemoveSourceTransport, "source", source)
    rt, model, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [f"![picture](<{source}>)"],
        transport=RemoveSourceTransport,
    )
    try:
        await receive(rt)
        assert not source.exists()
        assert len(uploads) == 1
        completed = [
            p
            for kind, p in rt._im_connection_manager.frames
            if kind == "node.streaming_delta" and p.get("kind") == "message_completed"
        ]
        assert completed
        assert all(
            "http://im.test/im/v1/images/image123" in p["final_content"]
            for p in completed
        )
        assert all(str(source) not in p["final_content"] for p in completed)
        assert receipts(tmp_path)[0][1]["state"] == "delivered"
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_ack_loss_keeps_pending_receipt_and_replays_same_delta_without_duplication(
    tmp_path, monkeypatch
):
    source = tmp_path / "lost-ack.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    monkeypatch.setattr(RemoveSourceTransport, "source", source)
    monkeypatch.setattr(RemoveSourceTransport, "lose_ack", True)
    rt, model, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [f"![picture](<{source}>)"],
        transport=RemoveSourceTransport,
    )
    try:
        result = await receive(rt)
        assert len(model.requests) == 1
        assert len(uploads) == 1
        assert not source.exists()
        stored = receipts(tmp_path)
        assert len(stored) == 1
        assert stored[0][1]["state"] == "pending"
        saved_delta = stored[0][1]["recovery"]["payload"]
        assert saved_delta["idempotency_key"]
        assert str(source) not in saved_delta["delta_text"]
        images = ReplyImages(tmp_path / "reply-images")
        recovery = ReplyDeliveryRecovery(
            images=images,
            im_connection_manager=rt._im_connection_manager,
            outbound_router=None,
        )
        assert await recovery.recover() == 1
        assert await recovery.recover() == 0
        assert len(rt._im_connection_manager.accepted) == 1
        assert len(deltas(rt)) == 2
        assert deltas(rt)[0] == deltas(rt)[1] == saved_delta
        assert receipts(tmp_path)[0][1]["state"] == "delivered"
        assert len(uploads) == 1
        assert not rt._kernel.get_run(result.run_id).status == "running"
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_permission_denied_image_continues_same_run_without_exposing_draft(
    tmp_path, monkeypatch
):
    source = tmp_path / "denied.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    rt, model, uploads, permissions = build(
        tmp_path,
        monkeypatch,
        [
            f"Private draft ![picture](<{source}>)",
            "I will respect the permission decision.",
        ],
        deny_images=True,
    )
    try:
        result = await receive(rt)
        assert len(model.requests) == 2
        assert len(permissions) == 1
        assert not uploads
        assert "permission was denied" in str(model.requests[1].messages)
        assert [p["delta_text"] for p in deltas(rt)] == [
            "I will respect the permission decision."
        ]
        assert {p["run_id"] for p in deltas(rt)} == {result.run_id}
        assert str(source) not in str(rt._im_connection_manager.frames)
    finally:
        await close(rt)


class TwoRoundModel(Model):
    async def generate(self, request):
        if request.stop_sequences:
            async for message in super().generate(request):
                yield message
            return
        self.requests.append(request)
        first = len(self.requests) == 1
        yield LLMMessage(
            role="assistant",
            content=self.texts[0 if first else 1],
            tool_calls=(
                LLMToolCall(
                    call_id="between-images",
                    name="read",
                    arguments={"path": self.texts[2]},
                ),
            )
            if first
            else (),
        )
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason="tool_calls" if first else "stop",
        )


@pytest.mark.asyncio
async def test_two_image_rounds_keep_distinct_prepared_candidates_and_tool_result(
    tmp_path, monkeypatch
):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"\x89PNG\r\n\x1a\nfirst")
    second.write_bytes(b"\x89PNG\r\n\x1a\nsecond")
    note = tmp_path / "note.txt"
    note.write_text("tool fact between images")
    model = TwoRoundModel(
        [f"First ![one](<{first}>)", f"Second ![two](<{second}>)", str(note)]
    )
    rt, _, uploads, _ = build(
        tmp_path, monkeypatch, [], model=model, enabled_tools=("read",)
    )
    try:
        await receive(rt)
        assert len(model.requests) == 2
        assert "tool fact between images" in str(model.requests[1].messages)
        assert len(uploads) == 2
        assert len(deltas(rt)) == 2
        assert len({p["idempotency_key"] for p in deltas(rt)}) == 2
        assert len({p["message_id"] for p in deltas(rt)}) == 2
        completed = [
            p
            for kind, p in rt._im_connection_manager.frames
            if kind == "node.streaming_delta" and p.get("kind") == "message_completed"
        ]
        assert len(completed) == 2
        assert completed[0]["final_content"].startswith("First")
        assert completed[1]["final_content"].startswith("Second")
        assert len(receipts(tmp_path)) == 2
        assert all(receipt["state"] == "delivered" for _, receipt in receipts(tmp_path))
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_late_running_event_preserves_managed_image_bubble(tmp_path, monkeypatch):
    import asyncio

    source = tmp_path / "early-candidate.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    published = asyncio.Event()

    class EarlyCandidateTransport(RemoveSourceTransport):
        async def send_json_await_ack(self, kind, payload):
            result = await super().send_json_await_ack(kind, payload)
            if payload.get("kind") == "message_delta":
                published.set()
            return result

    monkeypatch.setattr(EarlyCandidateTransport, "source", source)
    rt, _, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [f"![picture](<{source}>)"],
        transport=EarlyCandidateTransport,
    )
    observer = rt._run_coordinator._kernel_event_observer

    async def delayed_running(event):
        if event.get("event") == "run_status" and event.get("status") == "running":
            await published.wait()
        pending = observer(event)
        if asyncio.iscoroutine(pending):
            await pending

    monkeypatch.setattr(rt._run_coordinator, "_kernel_event_observer", delayed_running)
    try:
        await receive(rt)
        frames = rt._im_connection_manager.frames
        assert len([p for _, p in frames if p.get("kind") == "turn_start"]) == 1
        assert len(uploads) == 1
        completed = [p for _, p in frames if p.get("kind") == "message_completed"]
        assert len(completed) == 1
        assert "http://im.test/im/v1/images/image123" in completed[0]["final_content"]
        assert not source.exists()
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_managed_image_waits_for_inflight_initial_bubble_ack(
    tmp_path, monkeypatch
):
    import asyncio
    import threading

    from personal_assistant.gateway.runtime_delivery.image_connection import (
        ImageReplyConnection,
    )

    source = tmp_path / "pending-start.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    started = threading.Event()
    prepared = asyncio.Event()
    prepare = ImageReplyConnection.prepare_candidate

    def notify_prepared(self, *args):
        prepare(self, *args)
        prepared.set()

    class WaitingModel(Model):
        async def generate(self, request):
            if not request.stop_sequences:
                assert await asyncio.to_thread(started.wait, 5)
            async for message in super().generate(request):
                yield message

    class PendingStartTransport(RemoveSourceTransport):
        async def send_json_await_ack(self, kind, payload):
            if payload.get("kind") == "turn_start":
                started.set()
                await prepared.wait()
            return await super().send_json_await_ack(kind, payload)

    monkeypatch.setattr(PendingStartTransport, "source", source)
    monkeypatch.setattr(ImageReplyConnection, "prepare_candidate", notify_prepared)
    rt, _, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [],
        model=WaitingModel([f"![picture](<{source}>)"]),
        transport=PendingStartTransport,
    )
    try:
        await receive(rt)
        frames = rt._im_connection_manager.frames
        assert len([p for _, p in frames if p.get("kind") == "turn_start"]) == 1
        assert len(uploads) == 1
        completed = [p for _, p in frames if p.get("kind") == "message_completed"]
        assert len(completed) == 1
        assert "http://im.test/im/v1/images/image123" in completed[0]["final_content"]
        assert not source.exists()
    finally:
        await close(rt)
