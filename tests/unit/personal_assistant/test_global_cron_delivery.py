"""Global cron delivery facts require the actual final-message acknowledgement."""

import asyncio
from types import SimpleNamespace

import pytest

from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from .test_steer_bubble_roll import _FakeManager


@pytest.mark.asyncio
async def test_cron_records_actual_target_only_after_final_ack():
    entered, release = asyncio.Event(), asyncio.Event()
    facts = []

    class Manager(_FakeManager):
        async def send_json_await_ack(self, message_type, payload):
            if payload.get("kind") == "message_completed":
                entered.set()
                await release.wait()
            result = await super().send_json_await_ack(message_type, payload)
            result["payload"]["conversation_id"] = "target"
            return result

    manager = Manager(new_message_id="final")
    contexts = RunDeliveryContextStore()
    contexts.seed_owner_direct_run(
        run_id="run",
        agent_id="agent",
        kernel_session_id="cron-session",
        owner_user_id="owner",
    )
    recorder = SimpleNamespace(
        store=SimpleNamespace(
            get_work_session=lambda sid: (
                {
                    "scope": "cron",
                    "root_agent_id": "agent",
                }
                if sid == "cron-session"
                else None
            )
        ),
        record=lambda **fact: facts.append(fact),
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=contexts,
        work_recorder=recorder,
    )
    result = observer(
        {"event": "assistant_message", "run_id": "run", "content": "actual cron result"}
    )
    if asyncio.iscoroutine(result):
        await result
    assert (
        next(p for _, p in manager.sent if p.get("kind") == "turn_start")[
            "delivery_source"
        ]
        == "cron"
    )
    observer({"event": "turn_end", "run_id": "run", "completed": True})
    async with asyncio.timeout(2):
        await entered.wait()
    assert facts == []
    release.set()
    async with asyncio.timeout(2):
        while not facts:
            await asyncio.sleep(0)
    assert facts[0]["event_type"] == "cron_delivery"
    assert facts[0]["session_id"] == "cron-session"
    assert facts[0]["payload"] == {
        "run_id": "run",
        "conversation_id": "target",
        "message_id": "final",
        "text": "actual cron result",
    }
