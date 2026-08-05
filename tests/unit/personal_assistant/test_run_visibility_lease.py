"""Run visibility lease behavior around an abortable `/new` transition."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)


def _seed(store: RunDeliveryContextStore) -> None:
    store.seed(
        RunDeliveryContext(
            run_id="run-1",
            agent_id="agent-a",
            kernel_session_id="kernel-1",
            delivery_target=RunDeliveryTarget.none(),
        )
    )


@pytest.mark.asyncio
async def test_visibility_lease_defers_until_failed_reset_restores_old_run() -> None:
    store = RunDeliveryContextStore()
    _seed(store)
    store.quiesce("run-1")
    permit = asyncio.create_task(store.await_visibility("run-1"))
    await asyncio.sleep(0)
    assert not permit.done()

    store.restore("run-1")

    assert await permit is True
    assert store.is_suppressed("run-1") is False


@pytest.mark.asyncio
async def test_visibility_lease_revokes_deferred_old_output_after_reset_commits() -> (
    None
):
    store = RunDeliveryContextStore()
    _seed(store)
    store.quiesce("run-1")
    permit = asyncio.create_task(store.await_visibility("run-1"))
    await asyncio.sleep(0)

    store.suppress("run-1")

    assert await permit is False
    assert store.is_suppressed("run-1") is True
