"""Coordinator stages readable text only for normal Kernel submissions."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.human_message_context import (
    PaHumanMessageContext,
    PaTimeContext,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.readable_input_projection import (
    ReadableInputProjectionStore,
)
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


def _build(tmp_path: Path):
    kernel = _FakeKernel()
    store = ReadableInputProjectionStore()
    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=_agents(tmp_path),
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        human_message_context=PaHumanMessageContext(
            PaTimeContext(zone=ZoneInfo("Asia/Shanghai"), prompt_label="Asia/Shanghai")
        ),
        readable_input_projection_store=store,
    )
    return pipeline, kernel, store


def _message() -> InboundMessage:
    return InboundMessage(
        channel_name="web_relay",
        text="[Feishu Mon 2026-08-10 09:16 CST] user-authored",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        source_timestamp=datetime(2026, 8, 10, 1, 17, tzinfo=timezone.utc),
        received_timestamp=datetime(2026, 8, 10, 1, 18, tzinfo=timezone.utc),
    )


def test_normal_submit_stages_exact_model_and_readable_fallback(tmp_path: Path) -> None:
    pipeline, kernel, store = _build(tmp_path)

    asyncio.run(pipeline.handle_inbound(_message()))

    model = kernel.send_calls[0]["texts"][0]
    assert model == (
        "[Web IM Mon 2026-08-10 09:17 CST] "
        "[Feishu Mon 2026-08-10 09:16 CST] user-authored"
    )
    assert store.resolve_exact("sess-1", model) == (
        "[Feishu Mon 2026-08-10 09:16 CST] user-authored"
    )


def test_synchronous_submit_failure_rolls_back_staged_projection(
    tmp_path: Path,
) -> None:
    pipeline, kernel, store = _build(tmp_path)

    def fail_submit(**_kwargs):
        raise RuntimeError("submit failed")

    kernel.submit = fail_submit
    model = (
        "[Web IM Mon 2026-08-10 09:17 CST] "
        "[Feishu Mon 2026-08-10 09:16 CST] user-authored"
    )

    with pytest.raises(RuntimeError, match="submit failed"):
        asyncio.run(pipeline.handle_inbound(_message()))

    assert store.resolve_exact("sess-1", model) is None
