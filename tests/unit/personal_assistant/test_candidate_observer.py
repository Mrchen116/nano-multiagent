"""Complete model facts are the automatic delivery admission boundary."""

import pytest

from personal_assistant.gateway.message_delivery import DeliveryResult
from personal_assistant.gateway.runtime_delivery.candidate_observer import (
    build_candidate_observer,
)
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore


def setup_observer(result=None):
    contexts = RunDeliveryContextStore()
    context = contexts.seed_owner_direct_run(
        run_id="r", agent_id="a", kernel_session_id="s", owner_user_id="u"
    )
    delivered = []
    process = []

    async def deliver(candidate):
        delivered.append(candidate)
        return result or DeliveryResult(state="delivered")

    observer = build_candidate_observer(
        writer=process.append, context_store=contexts, deliver=deliver
    )
    return observer, context, delivered, process


def event(name, **values):
    return {"event": name, "run_id": "r", "turn_id": "t", "group_id": "g", **values}


@pytest.mark.asyncio
async def test_fragmented_image_waits_for_complete_round_and_deduplicates_replay():
    observer, _, delivered, process = setup_observer()
    first = event(
        "assistant_message",
        message_id="m1",
        content="Here ![shot](<",
        reasoning_content="checking",
    )
    await observer(first)
    await observer(first)
    await observer(event("message_end"))
    await observer(event("tool_start", call_id="c"))
    assert not delivered
    assert not any(item.get("content") for item in process)
    await observer(
        event("assistant_message", message_id="m2", content="/tmp/screen.png>)")
    )
    await observer(event("model_round_end", completed=True))
    await observer(event("model_round_end", completed=True))
    assert [item.text for item in delivered] == ["Here ![shot](</tmp/screen.png>)"]
    assert delivered[0].candidate_id == "g"


@pytest.mark.asyncio
async def test_failed_stream_discards_incomplete_body():
    observer, _, delivered, _ = setup_observer()
    await observer(event("assistant_message", message_id="m", content="![shot](</tmp"))
    await observer(event("turn_end", completed=False))
    await observer(event("model_round_end", completed=True))
    assert not delivered


@pytest.mark.asyncio
async def test_unpublished_failure_only_enters_internal_feedback_and_closes_process():
    observer, context, delivered, process = setup_observer(
        DeliveryResult(
            state="withheld",
            diagnostic="Image is unavailable.",
            continuation="Correct the source.",
        )
    )
    await observer(
        event("assistant_message", message_id="m", content="![shot](</missing.png>)")
    )
    await observer(event("model_round_end", completed=True))
    await observer(event("turn_end", completed=True))
    assert len(delivered) == 1
    assert context.delivery_candidate_seen
    assert context.delivery_failed
    assert "never delivered" in context.delivery_feedback
    assert not context.delivery_published_text
    assert not any(item.get("content") for item in process)
    assert process[-1]["event"] == "run_terminal_reconcile"
    assert process[-1]["delivery_status"] == "failed"


@pytest.mark.asyncio
async def test_partial_delivery_cannot_trigger_regeneration():
    observer, context, _, _ = setup_observer(DeliveryResult(state="partial"))
    await observer(
        event("assistant_message", message_id="m", content="A delivered reply")
    )
    await observer(event("model_round_end", completed=True))
    assert context.delivery_feedback is None
    assert context.delivery_published_text == "A delivered reply"
