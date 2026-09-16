"""New group input fences drafts during asynchronous image preparation."""

import asyncio
from dataclasses import replace

import pytest

from personal_assistant.channels.base import IMRelayIngress, InboundIngress
from tests.integration.test_pa_candidate_delivery import build, close, deltas
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


def group_message(number, text):
    return replace(
        inbound(chat_id="c_chat", text=text, is_group=True),
        metadata={"sender_display_name": "Alice", "mentioned_agent_ids": ["agent-a"]},
        ingress=InboundIngress(
            im_relay=IMRelayIngress(
                f"relay-{number}", f"key-{number}", f"input-{number}"
            )
        ),
    )


@pytest.mark.asyncio
async def test_new_group_input_during_upload_rejects_old_draft(tmp_path, monkeypatch):
    source = tmp_path / "image.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    runtime, _, _, _ = build(
        tmp_path,
        monkeypatch,
        [f"Old draft ![image](<{source}>)", "Answer to new question"],
    )
    delivery = runtime._startup_collaborators[0]
    entered, release, received = asyncio.Event(), asyncio.Event(), asyncio.Event()
    project = delivery.images.project_im
    note_input = delivery.contexts.note_input

    async def paused_projection(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            await release.wait()
        return await project(*args, **kwargs)

    def observe_input(*args):
        note_input(*args)
        received.set()

    monkeypatch.setattr(delivery.images, "project_im", paused_projection)
    monkeypatch.setattr(delivery.contexts, "note_input", observe_input)
    tasks = []
    try:
        pipeline = runtime._on_inbound._pipeline
        tasks.append(
            asyncio.create_task(pipeline.handle_inbound(group_message(1, "show image")))
        )
        await asyncio.wait_for(entered.wait(), 5)
        tasks.append(
            asyncio.create_task(
                pipeline.handle_inbound(
                    group_message(2, "do not send image; new question")
                )
            )
        )
        await asyncio.wait_for(received.wait(), 5)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 10)
        await runtime._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        assert [frame["delta_text"] for frame in deltas(runtime)] == [
            "Answer to new question"
        ]
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close(runtime)
