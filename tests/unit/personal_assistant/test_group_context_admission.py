"""Group context survives failed admission and is consumed only by accepted input."""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


def request(catalog, text="new request", attachments=()):
    message = replace(
        inbound(chat_id="room", text=text, is_group=True),
        metadata={"attachments": list(attachments)},
    )
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=catalog.require("agent-a"),
        session_key=build_session_key(message, agent_id="agent-a"),
        sender_label="Alice",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["image", "submit"])
async def test_unaccepted_group_input_keeps_buffer_for_next_request(
    tmp_path: Path, failure: str
):
    kernel, catalog, binder, router, store = build_dependencies(tmp_path)
    key = "agent-a:web_relay:room"
    store.append(key, "remember me", sender="Bob")

    async def fetch(url, agent_id):
        return b"not an image"

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=store,
        image_resolver=ImageAttachmentResolver(fetcher=fetch),
    )
    original = kernel.submit
    if failure == "submit":

        def reject(**kwargs):
            raise RuntimeError("admission rejected")

        kernel.submit = reject
        with pytest.raises(RuntimeError, match="admission rejected"):
            await coordinator.dispatch(request(catalog))
        kernel.submit = original
    else:
        result = await coordinator.dispatch(
            request(
                catalog,
                attachments=[
                    {"url": "https://im.invalid/bad.png", "content_type": "image/png"}
                ],
            )
        )
        assert "图片" in result.reply_text
    running = asyncio.create_task(coordinator.dispatch(request(catalog, "retry")))
    await kernel.wait_stream("run-1")
    assert "remember me" in str(kernel.submit_calls[-1]["parts"])
    kernel.finish("run-1")
    await running
    assert store.drain(key) == []


@pytest.mark.asyncio
async def test_accepting_snapshot_does_not_consume_later_background(tmp_path: Path):
    kernel, catalog, binder, router, store = build_dependencies(tmp_path)
    key = "agent-a:web_relay:room"
    store.append(key, "before", sender="Bob")
    original = kernel.submit

    def submit(**kwargs):
        store.append(key, "arrived during admission", sender="Carol")
        return original(**kwargs)

    kernel.submit = submit
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=store,
    )
    running = asyncio.create_task(coordinator.dispatch(request(catalog)))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1")
    await running
    assert store.drain(key) == [("Carol", "arrived during admission")]


@pytest.mark.asyncio
async def test_rejected_steer_fallback_does_not_repeat_accepted_background(
    tmp_path: Path,
):
    kernel, catalog, binder, router, store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=store,
    )
    first = asyncio.create_task(coordinator.dispatch(request(catalog, "first")))
    await kernel.wait_stream("run-1")
    store.append("agent-a:web_relay:room", "background once", sender="Bob")
    queued = asyncio.create_task(coordinator.dispatch(request(catalog, "queued")))
    await kernel.wait_try_steer_count(1)
    kernel.inject_steer = True
    await coordinator.dispatch(request(catalog, "accepted steer"))
    assert "background once" in str(kernel.try_steer_calls[-1]["parts"])
    kernel.finish("run-1")
    await first
    await kernel.wait_stream("run-2")
    assert "background once" not in str(kernel.submit_calls[-1]["parts"])
    kernel.finish("run-2")
    await queued
