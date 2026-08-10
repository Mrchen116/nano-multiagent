"""Shutdown terminal guarantees for an already-submitted inbound run."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import RelayLifecycleUpdate
from tests.helpers.inbound_pipeline import build_inbound_pipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


class _HangingKernel(_FakeKernel):
    """Keep the submitted run stream open until shutdown cancels its consumer."""

    def __init__(self) -> None:
        super().__init__()
        self.stream_started = asyncio.Event()

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        del session_id, after_sequence

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            self.stream_started.set()
            await asyncio.Event().wait()
            if False:  # pragma: no cover - preserve the async-generator contract.
                yield {}

        return _gen()


def test_shutdown_cancellation_fails_submitted_relay_before_worker_exits(
    tmp_path: Path,
) -> None:
    """A deadline-cancelled active worker must not leave its relay at ``sent``."""

    async def _exercise() -> list[RelayLifecycleUpdate]:
        kernel = _HangingKernel()
        channel = _FakeChannel("web_relay")
        run_queue = SessionRunQueue()
        lifecycle: list[RelayLifecycleUpdate] = []

        async def _capture(
            _message: InboundMessage, update: RelayLifecycleUpdate
        ) -> None:
            lifecycle.append(update)

        pipeline = build_inbound_pipeline(
            kernel=kernel,
            agents=_agents(tmp_path),
            outbound_router=OutboundRouter(ChannelRegistry((channel,))),
            run_queue=run_queue,
            default_agent_id="agent-a",
            relay_lifecycle_callback=_capture,
        )
        inbound = InboundMessage(
            channel_name="web_relay",
            text="keep running",
            external_user_id="user-1",
            external_chat_id="conversation-1",
            is_group=False,
            metadata={"relay_task_id": "relay-active"},
        )
        root = asyncio.create_task(pipeline.handle_inbound(inbound))
        await asyncio.wait_for(kernel.stream_started.wait(), timeout=1)

        run_queue.seal_and_cancel_pending()
        with pytest.raises(TimeoutError, match="workers exceeded deadline"):
            await run_queue.drain_workers(asyncio.get_running_loop().time())
        with pytest.raises(asyncio.CancelledError):
            await root
        return lifecycle

    lifecycle = asyncio.run(_exercise())

    assert [update.phase for update in lifecycle] == ["accepted", "failed"]
    assert lifecycle[-1].run_id == "run-1"
    assert lifecycle[-1].error == "gateway_shutdown_active_run_cancelled"
